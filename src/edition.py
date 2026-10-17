"""Editions of the Global Macro Intelligence Brief: when to write one, and writing it.

THE RULES DECIDE WHEN; THE AI ONLY WRITES; THE OWNER PUBLISHES.

  check     Free, no API. Measures drift since the last published edition from the
            tracker's own data (config/editions.yaml) and writes
            dashboard/briefs/editions/status.json. Says whether a new edition is due.
  write     Writes a DRAFT edition (API). Each story is either REWRITTEN with fresh
            research (its level or an indicator band moved) or REFRESHED with small,
            targeted edits (nothing moved) - most of the saving. Threat levels come
            from the tracker, never from the AI. A second agent checks every story
            against the data, and deterministic guards check structure, sources and
            that nothing reads as investment advice. Output: Markdown, a web page, a
            PDF and a Word file under dashboard/briefs/editions/<id>/ - marked DRAFT.
  publish   Owner's decision (Actions form). Marks the draft published; the dashboard,
            the living brief and every story's "full write-up" link switch to it.
  discard   Throws a draft away.

    python src/edition.py check
    python src/edition.py write [--force] [--fake]     # --fake: no API, placeholder text
    python src/edition.py render <id>
    python src/edition.py publish <id> | discard <id>
"""
import argparse
import copy
import csv
import datetime
import glob
import html
import json
import os
import re
import shutil
import subprocess
import sys
import time
import urllib.request

import yaml

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
import score  # noqa: E402
import archive  # noqa: E402

CFG_PATH = os.path.join(ROOT, "config", "editions.yaml")
STORIES_PATH = os.path.join(ROOT, "config", "stories.yaml")
BRIEFS_DIR = os.path.join(ROOT, "dashboard", "briefs")
ED_PUBLIC = os.path.join(BRIEFS_DIR, "editions")
REGISTRY = os.path.join(ED_PUBLIC, "editions.json")
STATUS = os.path.join(ED_PUBLIC, "status.json")
ED_DATA = os.path.join(ROOT, "data", "editions")
IND_HIST = os.path.join(ROOT, "data", "indicator_history.csv")
LEDGER = os.path.join(ROOT, "data", "resolution_ledger.json")
API_URL = "https://api.anthropic.com/v1/messages"

SECTION_HEADS = ["### What is happening", "### Why it is under-covered", "### The debate",
                 "### Historical parallel", "### What to watch", "### Sources"]


# ======================================================================== helpers
def load_cfg():
    with open(CFG_PATH) as f:
        return yaml.safe_load(f)


def load_json(path, default):
    try:
        with open(path) as f:
            return json.load(f)
    except Exception:
        return default


def save_json(path, obj):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w") as f:
        json.dump(obj, f, indent=1, ensure_ascii=False)
    os.replace(tmp, path)


def registry():
    return load_json(REGISTRY, {"editions": []})


def current_edition(reg=None):
    eds = [e for e in (reg or registry()).get("editions", []) if e.get("status") == "published"]
    return max(eds, key=lambda e: e.get("published", "")) if eds else None


def months_between(a, b):
    a = datetime.date.fromisoformat(a[:10])
    b = datetime.date.fromisoformat(b[:10])
    return (b.year - a.year) * 12 + (b.month - a.month) + (b.day - a.day) / 31.0


def band(level):
    return score.band_name(int(level))


def daily_records():
    out = {}
    for p in sorted(glob.glob(os.path.join(archive.DAILY_DIR, "*.jsonl"))):
        for r in archive._read_jsonl(p):
            if r.get("date"):
                out[r["date"]] = r
    return out


def record_on_or_before(recs, date):
    ds = [d for d in recs if d <= date]
    return recs[max(ds)] if ds else (recs[min(recs)] if recs else None)


def levels_of(rec):
    """Integer levels under today's rounding rule, from the stored raw scores."""
    out = {}
    for sid, v in (rec or {}).get("levels", {}).items():
        raw = v.get("raw")
        out[sid] = score.round_half_up(raw) if raw is not None else v.get("level")
    return out


def overall_of(rec):
    raws = [v["raw"] for v in (rec or {}).get("levels", {}).values() if v.get("raw") is not None]
    return score.aggregate_overall(raws)["overall"] if raws else None


def indicator_bands(date):
    """{indicator: row} for the last recorded run on or before `date`."""
    rows = {}
    best = None
    if not os.path.exists(IND_HIST):
        return {}
    with open(IND_HIST, newline="") as f:
        for r in csv.DictReader(f):
            if r["date"] <= date and (best is None or r["date"] >= best):
                if r["date"] != best:
                    best, rows = r["date"], {}
                rows[r["indicator_id"]] = r
    if not rows:   # edition predates indicator history: use the first day recorded
        with open(IND_HIST, newline="") as f:
            first = None
            for r in csv.DictReader(f):
                first = first or r["date"]
                if r["date"] == first:
                    rows[r["indicator_id"]] = r
    return rows


# ======================================================================== CHECK
def drift(ed, today=None):
    """How far the tracker has moved since the edition's data date."""
    recs = daily_records()
    if not recs:
        return None
    today = today or max(recs)
    now_rec = record_on_or_before(recs, today)
    then_rec = record_on_or_before(recs, ed["data_as_of"])
    then = {k: int(v) for k, v in (ed.get("tracker_levels") or levels_of(then_rec)).items()}
    now = levels_of(now_rec)
    common = set(then) & set(now)
    ov_then = ed.get("tracker_overall") or overall_of(then_rec)
    ov_now = overall_of(now_rec)
    ib_then, ib_now = indicator_bands(ed["data_as_of"]), indicator_bands(now_rec["date"])
    moved = sorted(k for k in common if then[k] != now[k])
    return {
        "as_of": now_rec["date"],
        "edition": ed["id"],
        "months": round(months_between(ed.get("published") or ed["data_as_of"], today), 1),
        "band_changes": sum(1 for k in common if band(then[k]) != band(now[k])),
        "level_changes": len(moved),
        "high_then": sum(1 for k in common if then[k] >= 7),
        "high_now": sum(1 for k in common if now[k] >= 7),
        "overall_then": ov_then, "overall_now": ov_now,
        "overall_move": round(abs((ov_now or 0) - (ov_then or 0)), 1),
        "stories_added": sorted(set(now) - set(then)),
        "stories_retired": sorted(set(then) - set(now)),
        "indicator_band_changes": sum(1 for k, r in ib_then.items()
                                      if k in ib_now and ib_now[k]["band"] != r["band"]),
        "moved": {k: [then[k], now[k]] for k in moved},
    }


def decide(d, cfg):
    """(due, cadence, reasons). Pure function of the drift numbers and the config."""
    if d is None:
        return False, None, ["no tracker history yet"]
    st, md = cfg["strong"], cfg["moderate"]
    strong = []
    if d["band_changes"] >= st["band_changes"]:
        strong.append(f"{d['band_changes']} stories changed band")
    if d["overall_move"] >= st["overall_move"]:
        strong.append(f"overall moved {d['overall_move']}")
    if abs(d["high_now"] - d["high_then"]) >= st["high_count_change"]:
        strong.append(f"stories at High went {d['high_then']} -> {d['high_now']}")
    if st.get("story_set_changed") and (d["stories_added"] or d["stories_retired"]):
        strong.append("the set of stories changed")
    moderate = []
    if d["band_changes"] >= md["band_changes"]:
        moderate.append(f"{d['band_changes']} stories changed band")
    if d["level_changes"] >= md["level_changes"]:
        moderate.append(f"{d['level_changes']} stories changed level")
    if d["overall_move"] >= md["overall_move"]:
        moderate.append(f"overall moved {d['overall_move']}")
    if d["indicator_band_changes"] >= md["indicator_band_changes"]:
        moderate.append(f"{d['indicator_band_changes']} indicators changed band")
    m = d["months"]
    if m >= cfg["max_months"]:
        return True, "annual", [f"{m:.0f} months since the last edition"]
    if m >= cfg["semiannual_months"] and (strong or moderate):
        return True, "semi-annual", strong or moderate
    if m >= cfg["min_months"] and strong:
        return True, "quarterly", strong
    return False, None, (strong or moderate or ["little has changed"])


def check(today=None, write=True):
    cfg = load_cfg()
    reg = registry()
    ed = current_edition(reg)
    if not ed:
        st = {"due": True, "cadence": "first", "summary": "no edition published yet"}
    else:
        d = drift(ed, today)
        due, cadence, why = decide(d, cfg)
        drafts = [e for e in reg["editions"] if e.get("status") == "draft"]
        if drafts:
            summary = f"draft {drafts[-1]['id']} is waiting for review"
        elif due:
            summary = f"due now ({cadence}: {'; '.join(why)})"
        else:
            m = d["months"] if d else 0
            nxt = ("at the next monthly check if drift grows" if m >= cfg["min_months"] else
                   f"not before {cfg['min_months']} months after the last edition")
            summary = f"not yet due - {'; '.join(why)}; {nxt}"
        st = {"due": bool(due and not drafts), "cadence": cadence, "reasons": why, "drift": d,
              "draft_pending": [e["id"] for e in drafts], "summary": summary,
              "current": ed["id"]}
    st["checked"] = (today or datetime.date.today().isoformat())
    if write:
        save_json(STATUS, st)
        try:
            archive.write_index()
        except Exception:
            pass
    return st


# ======================================================================== DATA PACKS
def load_stories():
    with open(STORIES_PATH) as f:
        cfg = yaml.safe_load(f)
    return cfg["stories"], {str(k): v for k, v in (cfg.get("sets") or {}).items()}


def story_order(prev_struct, stories):
    """Previous edition's order; new stories appended at the end of their set."""
    prev = {sid: m["number"] for sid, m in (prev_struct.get("stories") or {}).items()}
    keyed = []
    for s in stories:
        keyed.append((int(s["set"]), prev.get(s["id"], 999), s["id"]))
    return [sid for _, _, sid in sorted(keyed)]


def latest_agent_evidence():
    """Most recent agent assessment per indicator, from the archive."""
    out = {}
    for p in sorted(glob.glob(os.path.join(archive.AGENT_DIR, "*.jsonl"))):
        for r in archive._read_jsonl(p):
            out[r["indicator"]] = r
    return out


def story_pack(s, ed, now_rec, then_rec, ib_then, ib_now, evidence, episodes, recs):
    sid = s["id"]
    lv_then = int((ed.get("tracker_levels") or levels_of(then_rec)).get(sid, s["base_level"]))
    lv_now = levels_of(now_rec).get(sid, s["base_level"])
    path = []
    for d in sorted(recs):
        if d >= ed["data_as_of"] and d.endswith(("-28", "-29", "-30", "-31")) or d == now_rec["date"]:
            r = recs[d]
            if sid in r.get("levels", {}):
                path.append([d, levels_of(r)[sid]])
    inds, moved = [], False
    for i in s["indicators"]:
        a, b = ib_then.get(i["id"], {}), ib_now.get(i["id"], {})
        changed = bool(a and b and a.get("band") != b.get("band"))
        moved |= changed
        row = {"id": i["id"], "label": i["label"], "then": a.get("value"), "band_then": a.get("band"),
               "now": b.get("value"), "band_now": b.get("band"), "as_of": b.get("as_of"),
               "changed_band": changed}
        ev = evidence.get(i["id"])
        if ev and i.get("source") == "manual":
            row["agent_fact"] = (ev.get("fact") or "")[:700]
            row["agent_sources"] = (ev.get("sources") or [])[:4]
        inds.append(row)
    eps = [{"opened": e.get("opened"), "closed": e.get("closed"), "peak": e.get("peak_level"),
            "grade": e.get("grade"), "note": (e.get("grade_note") or "")[:300]}
           for e in episodes if e.get("story_id") == sid
           and (e.get("closed") or "9999") >= ed["data_as_of"]]
    mode = "rewrite" if (lv_now != lv_then or moved) else "refresh"
    return {"id": sid, "name": s["name"], "set": int(s["set"]), "level_then": lv_then,
            "band_then": band(lv_then), "level_now": lv_now, "band_now": band(lv_now),
            "raw_now": (now_rec.get("levels", {}).get(sid) or {}).get("raw"),
            "monthly_levels": path[-8:], "indicators": inds, "episodes": eps, "mode": mode}


# ======================================================================== API
class Budget:
    def __init__(self, cfg):
        self.w = cfg["writer"]
        self.usd = 0.0
        self.calls = 0

    def add(self, usage):
        if not usage:
            return
        w = self.w
        self.usd += (usage.get("input_tokens", 0) * w["price_in"]
                     + usage.get("output_tokens", 0) * w["price_out"]) / 1e6
        st = (usage.get("server_tool_use") or {}).get("web_search_requests", 0) or 0
        self.usd += st * w["price_search"] / 1000.0
        self.calls += 1

    def ok(self):
        return self.usd < float(self.w["max_usd"])


def call_claude(prompt, key, model, max_tokens, searches, budget, fake=False):
    if fake:
        return fake_reply(prompt), {}
    body = {"model": model, "max_tokens": max_tokens,
            "messages": [{"role": "user", "content": prompt}]}
    if searches:
        body["tools"] = [{"type": "web_search_20250305", "name": "web_search", "max_uses": searches}]
    req = urllib.request.Request(API_URL, data=json.dumps(body).encode(),
                                 headers={"content-type": "application/json", "x-api-key": key,
                                          "anthropic-version": "2023-06-01"})
    last = None
    for attempt in range(4):
        try:
            with urllib.request.urlopen(req, timeout=300) as r:
                data = json.loads(r.read().decode())
            break
        except urllib.error.HTTPError as e:
            last = f"HTTP {e.code}: {e.read().decode()[:300]}"
            if e.code in (429, 500, 502, 503, 529):
                time.sleep(20 * (attempt + 1))
                continue
            raise RuntimeError(last)
        except Exception as e:
            last = str(e)
            time.sleep(10 * (attempt + 1))
    else:
        raise RuntimeError(last or "API call failed")
    budget.add(data.get("usage"))
    text = "".join(b.get("text", "") for b in data.get("content", []) if b.get("type") == "text")
    return text, data.get("usage") or {}


def call_second(prompt, key, budget, fake=False):
    """Independent second opinion (ASI1 when configured, else Claude without search)."""
    if fake:
        return '{"ok": true, "issues": []}'
    try:
        import agent
        provider, k2, m2 = agent.resolve_crosscheck(key)
        if provider == "asi1":
            return agent._call_asi1(prompt, m2, k2, max_tokens=1200)
        text, _ = call_claude(prompt, key, m2 or os.environ.get("EDITION_MODEL") or load_cfg()["writer"]["model"],
                              1200, 0, budget)
        return text
    except Exception as e:
        return json.dumps({"ok": False, "issues": [f"cross-check unavailable: {e}"]})


def fake_reply(prompt):
    if "RETURN JSON EDITS" in prompt:
        return json.dumps({"since": "Placeholder: nothing material changed in the tracker data.",
                           "why_level": "", "edits": []})
    if "SYNTHESIS" in prompt:
        out = ["=== WHAT CHANGED ===", "Placeholder overview of what changed since the last edition."]
        for k in range(1, 6):
            out += [f"=== SECTION {k} ===", f"Placeholder introduction for section {k}."]
        out += ["=== PATTERN ===", "Placeholder pattern analysis.", "=== CONNECTIONS ===",
                "- **Placeholder.** A connection."]
        return "\n".join(out)
    m = re.search(r"PREVIOUS TEXT START\n(.*?)\nPREVIOUS TEXT END", prompt, re.S)
    prev = m.group(1) if m else ""
    return prev.replace("**Why this level:**",
                        "**Since the last edition:** Placeholder for the rewrite.\n\n**Why this level:**", 1)


# ======================================================================== PROMPTS
RULES = """HOUSE RULES (all mandatory):
- Educational analysis for general readers. NEVER name securities, tickers, funds or brokers, and
  never tell readers to buy, sell, overweight or time anything. "What you can do now" stays at the
  level of household resilience and understanding (cash buffers, diversification as a concept,
  reading your own statements, avoiding leverage).
- Do NOT state or change the threat level number or band; the tracker sets them. Explain them.
- Tag every factual claim [Established], [Contested], [Single-source] or [Forecast] as in the text.
- Every NEW fact must come from your research or the DATA PACK and its source must be listed in
  "### Sources" as "- Publisher, Title (Month YYYY) — <URL>". Never invent a URL, figure or quote.
- Plain, precise English; same reading level and tone as the previous text; British spelling as in
  the original. Refer to other stories as "Story N" using the STORY INDEX numbers.
- Dates: the edition's data date is {asof}. Do not report anything after {asof}."""


def rewrite_prompt(pack, prev_md, number, index, asof, prev_asof, searches):
    return f"""You are updating one story of the Global Macro Intelligence Brief, an educational
briefing on under-covered risks to the global financial system. The previous edition's text was
written with data to {prev_asof}. Your job: bring it up to date to {asof}.

This story is in REWRITE mode: the tracker shows it moved since the last edition. Use up to
{searches} web searches to find what happened between {prev_asof} and {asof}. Rewrite every part
that is out of date; keep what is still true and well put. Keep the exact structure below.

{RULES.format(asof=asof)}

STRUCTURE (Markdown, in this order, nothing before the first line):
**WHO THIS HITS:** *one sentence*
**CURRENT THREAT LEVEL:** *a 2-5 word tagline only (the number is inserted by the tracker)*
**Since the last edition:** 2-4 sentences: what changed since {prev_asof} and why the level is
{pack['level_now']}/10 ({pack['band_now']}) now vs {pack['level_then']}/10 ({pack['band_then']}) then.
**Why this level:** ... **Raises it:** ... **Lowers it:** ...
### What is happening
### Why it is under-covered
### The debate
### Stress test (the benign case)
### Historical parallel
::: box
**In plain terms**
one paragraph
:::
::: box
**What you can do now**
3-5 short bolded tips
:::
### What to watch
- 4 bullets
### Sources
- list

STORY INDEX: {index}
THIS STORY: Story {number} — {pack['name']}

DATA PACK (ground truth from the tracker; values are the indicator readings, bands 0/1/2):
{json.dumps(pack, ensure_ascii=False, indent=1)}

PREVIOUS TEXT START
{prev_md}
PREVIOUS TEXT END

Return ONLY the updated Markdown story."""


def refresh_prompt(pack, prev_md, number, asof, prev_asof, searches):
    return f"""You are refreshing one story of the Global Macro Intelligence Brief (educational).
The tracker shows NO material change since the last edition (data to {prev_asof}); the threat level
stays {pack['level_now']}/10 ({pack['band_now']}). Do NOT rewrite. Use at most {searches} web search to
check the most time-sensitive fact, then return a small set of exact edits.

{RULES.format(asof=asof)}

RETURN JSON EDITS, nothing else:
{{"since": "1-2 sentences for a 'Since the last edition' line (what was confirmed or what small thing changed)",
  "why_level": "optional replacement for the 'Why this level' sentence, or empty",
  "edits": [{{"old": "exact text copied from the previous text", "new": "replacement",
             "source": "Publisher, Title (Month YYYY) — <URL> or empty"}}]}}
At most 6 edits; "old" must appear verbatim in the previous text. Prefer updating stale numbers and
dates. If nothing is stale, return an empty edits list.

THIS STORY: Story {number} — {pack['name']}
DATA PACK: {json.dumps(pack, ensure_ascii=False)}

PREVIOUS TEXT START
{prev_md}
PREVIOUS TEXT END"""


def crosscheck_prompt(pack, md):
    return f"""You are an independent fact-checker for an educational risk briefing. Check the story
below against the DATA PACK (tracker ground truth). Report only real problems:
1. a number or direction that contradicts the DATA PACK;
2. a factual claim with no source in its Sources list, or a source that does not fit the claim;
3. anything that names a security/ticker/fund or tells readers to buy, sell or time markets;
4. a claim that looks invented or implausible.
Return JSON only: {{"ok": true|false, "issues": ["short description", ...]}} (max 6 issues).

DATA PACK: {json.dumps(pack, ensure_ascii=False)}

STORY:
{md}"""


def synthesis_prompt(packs, sinces, prev_parts, struct, asof, prev_asof, d, searches):
    rows = "\n".join(f"- Story {struct['stories'][p['id']]['number']}: {p['name']} — "
                     f"{p['level_then']} -> {p['level_now']} ({p['band_now']}); since: {sinces.get(p['id'], '')}"
                     for p in packs)
    intros = "\n\n".join(f"SECTION {k} ({v['name']}) PREVIOUS INTRO:\n{v['intro']}"
                         for k, v in struct["sections"].items())
    return f"""SYNTHESIS for a new edition of the Global Macro Intelligence Brief (educational).
Data to {asof}; previous edition data to {prev_asof}. Use up to {searches} web searches only if
needed to explain a cross-story driver.

{RULES.format(asof=asof)}

Write these blocks, each starting with its marker line exactly:
=== WHAT CHANGED ===
220-320 words: what changed since the last edition and why, naming the stories that moved most
and the common drivers. Use the tracker numbers below.
=== SECTION 1 === ... === SECTION 5 ===
For each section, a 90-150 word introduction (update the previous one; keep what still holds).
=== PATTERN ===
350-500 words: how the five mechanisms interlock NOW (update the previous analysis).
=== CONNECTIONS ===
4-7 bullets "- **Short title.** One or two sentences, citing story numbers." Prefer connections
that the data shows moving together since the last edition.

TRACKER: overall {d.get('overall_then')} -> {d.get('overall_now')}; stories at High
{d.get('high_then')} -> {d.get('high_now')}; {d.get('band_changes')} band changes;
{d.get('indicator_band_changes')} indicator band changes.
STORIES:
{rows}

{intros}

PREVIOUS PATTERN ANALYSIS:
{prev_parts.get('pattern', '')}"""


# ======================================================================== GUARDS
TICKER = re.compile(r"(?:\$[A-Z]{1,5}\b|\b(?:NYSE|NASDAQ|LSE|TSE)\s*:\s*[A-Z0-9.]+|\bticker\b)")
# lower-case verbs on purpose: "Buy Now, Pay Later" is a subject of the brief, not advice
ADVICE = re.compile(r"\b(?:buy|sell|short|overweight|underweight|go long on|go short on)\s+(?:the\s+|more\s+|some\s+)?"
                    r"(?:stocks?|shares|equities|bonds? funds?|ETFs?|positions?|gold|copper|the dip)\b")


def guard(md):
    """Deterministic checks. Returns a list of problems (empty = fine)."""
    out = []
    if not md.strip().startswith("**WHO THIS HITS:**"):
        out.append("does not start with WHO THIS HITS")
    for h in SECTION_HEADS:
        if h not in md:
            out.append(f"missing heading {h}")
    if "**Why this level:**" not in md:
        out.append("missing 'Why this level'")
    if TICKER.search(md):
        out.append("contains a ticker or exchange symbol")
    if ADVICE.search(md):
        out.append("contains wording that reads as investment advice")
    srcs = md.split("### Sources", 1)[-1]
    if "http" not in srcs:
        out.append("no source links")
    if re.search(r"CURRENT THREAT LEVEL:\*\*\s*\d", md):
        out.append("the AI wrote a threat level number")
    return out


def apply_edits(prev_md, j):
    md, applied, failed, new_sources = prev_md, 0, 0, []
    for e in (j.get("edits") or [])[:6]:
        old, new = e.get("old") or "", e.get("new") or ""
        if old and old in md and new:
            md = md.replace(old, new, 1)
            applied += 1
            if e.get("source"):
                new_sources.append(e["source"])
        else:
            failed += 1
    if j.get("why_level"):
        md = re.sub(r"\*\*Why this level:\*\*.*?(?=\s\*\*Raises it:\*\*)",
                    "**Why this level:** " + j["why_level"].strip(), md, count=1, flags=re.S)
    since = (j.get("since") or "").strip()
    if since:
        md = md.replace("**Why this level:**", f"**Since the last edition:** {since}\n\n**Why this level:**", 1)
    if new_sources:
        md = md.rstrip() + "\n\n" + "\n\n".join(f"- {s}" for s in new_sources) + "\n"
    return md, applied, failed


def strip_since(md):
    return re.sub(r"\*\*Since the last edition:\*\*.*?\n\n", "", md, count=1, flags=re.S)


# ======================================================================== WRITE
def edition_id_for(date):
    return date[:7]


def write(force=False, fake=False, today=None):
    cfg = load_cfg()
    w = cfg["writer"]
    model = os.environ.get("EDITION_MODEL") or w["model"]
    key = os.environ.get("ANTHROPIC_API_KEY", "")
    if not fake and not key:
        raise SystemExit("ANTHROPIC_API_KEY is not set")
    st = check(today, write=True)
    if not (st.get("due") or force):
        print(f"Edition not due: {st.get('summary')}")
        return None
    reg = registry()
    prev = current_edition(reg)
    if not prev:
        raise SystemExit("no published edition to build on")
    recs = daily_records()
    now_rec = record_on_or_before(recs, today or max(recs))
    asof = now_rec["date"]
    eid = edition_id_for(asof)
    if any(e["id"] == eid and e.get("status") == "published" for e in reg["editions"]):
        eid = asof
    then_rec = record_on_or_before(recs, prev["data_as_of"])
    prev_dir = os.path.join(ED_DATA, prev["id"])
    struct = load_json(os.path.join(prev_dir, "structure.json"), {"stories": {}, "sections": {}})
    prev_parts = {k: open(os.path.join(prev_dir, k + ".md")).read()
                  for k in ("how_to_read", "pattern", "watchlist", "caveats", "glossary")
                  if os.path.exists(os.path.join(prev_dir, k + ".md"))}
    stories, set_names = load_stories()
    by_id = {s["id"]: s for s in stories}
    order = story_order(struct, stories)
    numbers = {sid: n + 1 for n, sid in enumerate(order)}
    index = "; ".join(f"{numbers[sid]}. {by_id[sid]['name']}" for sid in order)
    ib_then, ib_now = indicator_bands(prev["data_as_of"]), indicator_bands(asof)
    evidence = latest_agent_evidence()
    episodes = load_json(LEDGER, {}).get("episodes", [])
    out_dir = os.path.join(ED_DATA, eid)
    os.makedirs(os.path.join(out_dir, "sections"), exist_ok=True)
    budget = Budget(cfg)
    packs, sinces, review = [], {}, {}
    d = st.get("drift") or drift(prev, asof) or {}
    print(f"Writing edition {eid} (data to {asof}; previous {prev['id']}, data to {prev['data_as_of']}); "
          f"model {model}{' [FAKE]' if fake else ''}")
    for sid in order:
        s = by_id[sid]
        pack = story_pack(s, prev, now_rec, then_rec, ib_then, ib_now, evidence, episodes, recs)
        packs.append(pack)
        prev_path = os.path.join(prev_dir, "sections", sid + ".md")
        prev_md = strip_since(open(prev_path).read()) if os.path.exists(prev_path) else ""
        if not prev_md:
            pack["mode"] = "rewrite"
        issues, note = [], ""
        if not budget.ok():
            md, note = prev_md, "budget reached - previous text kept"
        elif pack["mode"] == "rewrite":
            md, _ = call_claude(rewrite_prompt(pack, prev_md or "(new story - write from scratch)",
                                               numbers[sid], index, asof, prev["data_as_of"],
                                               w["rewrite_searches"]),
                                key, model, w["max_tokens_rewrite"], w["rewrite_searches"], budget, fake)
            md = md.strip()
            md = md[md.find("**WHO THIS HITS:**"):] if "**WHO THIS HITS:**" in md else md
            g = guard(md)
            if g and prev_md:
                issues += [f"rewrite rejected ({'; '.join(g)}); previous text kept with a note"]
                md = prev_md
        else:
            raw, _ = call_claude(refresh_prompt(pack, prev_md, numbers[sid], asof, prev["data_as_of"],
                                                w["refresh_searches"]),
                                 key, model, w["max_tokens_refresh"], w["refresh_searches"], budget, fake)
            try:
                j = json.loads(raw[raw.find("{"): raw.rfind("}") + 1])
            except Exception:
                j = {"since": "", "edits": []}
                issues.append("refresh reply was not valid JSON; text kept unchanged")
            md, applied, failed = apply_edits(prev_md, j)
            if failed:
                issues.append(f"{failed} suggested edit(s) did not match the text and were skipped")
            note = f"{applied} edit(s) applied"
        issues += guard(md)
        cc = call_second(crosscheck_prompt(pack, md), key, budget, fake) if budget.ok() else ""
        try:
            cj = json.loads(cc[cc.find("{"): cc.rfind("}") + 1]) if cc else {}
        except Exception:
            cj = {"ok": None, "issues": ["cross-check reply unreadable"]}
        issues += [f"cross-check: {x}" for x in (cj.get("issues") or [])]
        m = re.search(r"\*\*Since the last edition:\*\*\s*(.*?)\n", md)
        sinces[sid] = m.group(1).strip() if m else ""
        with open(os.path.join(out_dir, "sections", sid + ".md"), "w") as f:
            f.write(md.strip() + "\n")
        review[sid] = {"mode": pack["mode"], "note": note, "issues": issues,
                       "level": [pack["level_then"], pack["level_now"]]}
        print(f"  {numbers[sid]:>2}. {sid:22s} {pack['mode']:8s} {pack['level_then']}->{pack['level_now']} "
              f"issues={len(issues)}  spend≈${budget.usd:.2f}")
    # synthesis
    syn = ""
    if budget.ok():
        syn, _ = call_claude(synthesis_prompt(packs, sinces, prev_parts, struct, asof, prev["data_as_of"], d,
                                              w["synthesis_searches"]),
                             key, model, w["max_tokens_synthesis"], w["synthesis_searches"], budget, fake)
    blocks = parse_synthesis(syn)
    sections = copy.deepcopy(struct.get("sections") or {})
    for k in sections:
        if blocks.get(f"SECTION {k}"):
            sections[k]["intro"] = blocks[f"SECTION {k}"]
    new_struct = {"stories": {sid: {"number": numbers[sid], "title": by_id[sid]["name"]
                                    if sid not in struct.get("stories", {}) else struct["stories"][sid]["title"]}
                              for sid in order},
                  "sections": sections}
    save_json(os.path.join(out_dir, "structure.json"), new_struct)
    pattern = blocks.get("PATTERN") or prev_parts.get("pattern", "")
    if blocks.get("CONNECTIONS"):
        pattern = pattern.rstrip() + "\n\n### Connections to watch\n\n" + blocks["CONNECTIONS"].strip()
    parts = dict(prev_parts, pattern=pattern, what_changed=blocks.get("WHAT CHANGED", ""))
    for k, v in parts.items():
        with open(os.path.join(out_dir, k + ".md"), "w") as f:
            f.write(v.strip() + "\n")
    levels_now = levels_of(now_rec)
    entry = {"id": eid, "status": "draft", "title": f"Global Macro Intelligence Brief — "
             f"{datetime.date.fromisoformat(asof).strftime('%B %Y')} Edition",
             "data_as_of": asof, "created": datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds"),
             "previous": prev["id"], "cadence": st.get("cadence") or "manual",
             "reasons": st.get("reasons"), "model": model, "fake": bool(fake),
             "levels": {sid: levels_now.get(sid) for sid in order},
             "tracker_levels": {sid: levels_now.get(sid) for sid in order},
             "tracker_overall": overall_of(now_rec), "overall": overall_of(now_rec),
             "cost_usd": round(budget.usd, 2), "api_calls": budget.calls,
             "rewritten": sum(1 for v in review.values() if v["mode"] == "rewrite"),
             "refreshed": sum(1 for v in review.values() if v["mode"] == "refresh"),
             "flags": sum(len(v["issues"]) for v in review.values())}
    save_json(os.path.join(out_dir, "review.json"), {"edition": eid, "stories": review})
    reg["editions"] = [e for e in reg["editions"] if e["id"] != eid] + [entry]
    save_json(REGISTRY, reg)
    render(eid)
    check(today, write=True)
    print(f"Draft {eid} written: {entry['rewritten']} rewritten, {entry['refreshed']} refreshed, "
          f"{entry['flags']} flag(s) for review, estimated spend ${budget.usd:.2f}")
    return eid


def parse_synthesis(text):
    out, cur = {}, None
    for line in (text or "").splitlines():
        m = re.match(r"^===\s*(.+?)\s*===\s*$", line.strip())
        if m:
            cur = m.group(1).upper()
            out[cur] = ""
        elif cur:
            out[cur] += line + "\n"
    return {k: v.strip() for k, v in out.items()}


# ======================================================================== RENDER
CSS = """
:root{--text:#161a1f;--muted:#5f6b7a;--line:#e3e7ec;--accent:#1F4E79;--box:#eef3f9;--bg:#fff}
@media (prefers-color-scheme:dark){:root{--text:#e7ebf0;--muted:#9aa6b4;--line:#2a313b;--accent:#7fb0e0;--box:#18212c;--bg:#0e1116}}
html{background:var(--bg)}
body{max-width:820px;margin:0 auto;padding:24px 18px 60px;color:var(--text);background:var(--bg);
  font:16px/1.6 Carlito,Calibri,-apple-system,"Segoe UI",Roboto,Helvetica,Arial,sans-serif}
h1{color:var(--accent);font-size:26px;margin:36px 0 10px;border-bottom:2px solid var(--line);padding-bottom:6px}
h2{color:var(--accent);font-size:21px;margin:34px 0 8px}
h3{font-size:16px;margin:20px 0 6px}
a{color:var(--accent);overflow-wrap:anywhere}
.box{background:var(--box);border-radius:8px;padding:10px 16px;margin:14px 0}
.meter{display:flex;gap:3px;margin:6px 0 10px;max-width:420px}
.meter span{flex:1;height:10px;border-radius:2px;background:var(--line)}
.lvl{display:inline-block;color:#fff;border-radius:6px;padding:1px 9px;font-weight:700}
.draft{background:#C0392B;color:#fff;padding:10px 14px;border-radius:8px;font-weight:600}
.cover{text-align:center;padding:30px 0 10px}
.contents{border:1px solid var(--line);border-radius:8px;padding:6px 18px;margin:18px 0}
.contents ul{padding-left:18px}
.cover .t{font-size:34px;font-weight:700;color:var(--accent);line-height:1.15}
.muted{color:var(--muted);font-size:14px}
table{border-collapse:collapse;width:100%;font-size:14px}
td,th{border-bottom:1px solid var(--line);padding:4px 6px;text-align:left}
@media print{body{max-width:none;padding:0;font-size:11pt}.noprint{display:none}h1{break-before:page}
  h2{break-before:page}.box{break-inside:avoid}}
"""


def band_color(l):
    return "#2E7D32" if l <= 2 else "#8BC34A" if l <= 4 else "#F5A623" if l <= 6 else "#E8710A" if l <= 8 else "#C0392B"


def meter_html(level):
    cells = "".join(f'<span style="background:{band_color(i)}"></span>' if i <= level else "<span></span>"
                    for i in range(1, 11))
    return f'```{{=html}}\n<div class="meter">{cells}</div>\n```\n'


def assemble(eid):
    reg = registry()
    e = next(x for x in reg["editions"] if x["id"] == eid)
    d = os.path.join(ED_DATA, eid)
    struct = load_json(os.path.join(d, "structure.json"), {})
    part = lambda k: (open(os.path.join(d, k + ".md")).read().strip()  # noqa: E731
                      if os.path.exists(os.path.join(d, k + ".md")) else "")
    stories, set_names = load_stories()
    by_id = {s["id"]: s for s in stories}
    order = sorted(struct["stories"], key=lambda k: struct["stories"][k]["number"])
    lv = e["levels"]
    out = []
    draft = e.get("status") == "draft"
    out.append("---\nlang: en\n---\n")
    if draft:
        out.append('::: draft\nDRAFT — written by the edition agent and not yet reviewed. '
                   'It becomes the current edition only when the owner publishes it.\n:::\n')
    out.append(f"::: cover\n[GLOBAL MACRO INTELLIGENCE BRIEF]{{.t}}\n\n"
               f"{datetime.date.fromisoformat(e['data_as_of']).strftime('%B %Y')} Edition\n\n"
               f"[Data to {e['data_as_of']} · Informational analysis — not investment, legal or financial "
               f"advice.]{{.muted}}\n:::\n")
    toc = ["::: contents", "**Contents**", ""]
    if part("what_changed"):
        toc.append("- [What changed since the last edition](#what-changed)")
    toc += ["- [How to read this brief](#how-to-read)", "- [Risk dashboard](#risk-dashboard)"]
    for k in sorted(struct["sections"], key=int):
        toc.append(f"- [Section {k} — {struct['sections'][k]['name']}](#section-{k})")
        toc += [f"    - [{struct['stories'][s]['number']}. {struct['stories'][s]['title']}](#{s})"
                for s in order if str(by_id[s]["set"]) == k]
    toc += ["- [Pattern analysis](#pattern)", "- [Master watchlist](#watchlist)",
            "- [Confidence and caveats](#caveats)", "- [Glossary](#glossary)", ":::", ""]
    out.append("\n".join(toc))
    if part("what_changed"):
        out.append(f"# What changed since the last edition {{#what-changed}}\n\n{part('what_changed')}\n")
    out.append(f"# How to read this brief {{#how-to-read}}\n\n{part('how_to_read')}\n")
    out.append("# Risk dashboard {#risk-dashboard}\n\nThreat levels come from the live tracker on the edition's data date "
               "(fixed rules applied to the indicator readings); the text explains them.\n")
    for k in sorted(struct["sections"], key=int):
        ids = [s for s in order if str(by_id[s]["set"]) == k]
        avg = round(sum(lv[s] for s in ids) / len(ids) + 1e-9, 1) if ids else 0
        out.append(f"### {struct['sections'][k]['name']} — avg {avg}/10\n")
        out += [f"- {struct['stories'][s]['number']}. {struct['stories'][s]['title']} — "
                f"{lv[s]}/10 ({band(lv[s])})" for s in ids]
        out.append("")
    for k in sorted(struct["sections"], key=int):
        sec = struct["sections"][k]
        out.append(f"# Section {k} — {sec['name']} {{#section-{k}}}\n\n{sec['intro']}\n")
        for sid in [s for s in order if str(by_id[s]["set"]) == k]:
            n = struct["stories"][sid]["number"]
            md = open(os.path.join(d, "sections", sid + ".md")).read().strip()
            level = lv[sid]
            md = re.sub(r"\*\*CURRENT THREAT LEVEL:\*\*",
                        f"**CURRENT THREAT LEVEL: {level}/10 — {band(level)}**", md, count=1)
            # meter after the threat-level line
            md = re.sub(r"(\*\*CURRENT THREAT LEVEL:[^\n]*\n)", lambda m: m.group(1) + "\n" + meter_html(level),
                        md, count=1)
            md = md.replace("### Sources", "#### Sources")
            out.append(f"## {n}. {struct['stories'][sid]['title']} {{#{sid}}}\n\n{md}\n")
    out.append(f"# Pattern analysis: how the five mechanisms interlock {{#pattern}}\n\n{part('pattern')}\n")
    out.append(f"# Master watchlist {{#watchlist}}\n\n{part('watchlist')}\n")
    out.append(f"# Confidence, caveats and what could make this wrong {{#caveats}}\n\n{part('caveats')}\n")
    out.append(f"# Plain-language glossary {{#glossary}}\n\n{part('glossary')}\n")
    text = "\n".join(out)
    with open(os.path.join(d, "edition.md"), "w") as f:
        f.write(text)
    return os.path.join(d, "edition.md")


def chrome_bin():
    for c in (os.environ.get("CHROME_BIN"), "google-chrome", "google-chrome-stable", "chromium",
              "chromium-browser"):
        if c and shutil.which(c):
            return shutil.which(c)
    return None


def render(eid):
    """edition.md -> index.html, PDF (headless Chrome) and DOCX (pandoc). Each step optional."""
    md = assemble(eid)
    reg = registry()
    e = next(x for x in reg["editions"] if x["id"] == eid)
    pub = os.path.join(ED_PUBLIC, eid)
    os.makedirs(pub, exist_ok=True)
    base = f"Global_Macro_Intelligence_Brief_{eid}"
    css = os.path.join(pub, "edition.css")
    with open(css, "w") as f:
        f.write(CSS)
    out_html = os.path.join(pub, "index.html")
    if not shutil.which("pandoc"):
        print("::warning::pandoc not installed - edition not rendered")
        return None
    subprocess.run(["pandoc", md, "-s", "-c", "edition.css",
                    "--metadata", "pagetitle=" + e["title"], "-o", out_html], check=True)
    # no external stylesheet needed for viewing elsewhere: inline the CSS
    with open(out_html) as f:
        page = f.read()
    page = page.replace('<link rel="stylesheet" href="edition.css" />', f"<style>{CSS}</style>")
    page = page.replace("<body>", '<body>\n<p class="noprint muted"><a href="../../../">Tracker</a> · '
                                  '<a href="../../archive/index.html">All editions</a> · '
                                  f'<a href="{base}.pdf">PDF</a> · <a href="{base}.docx">Word</a></p>', 1)
    with open(out_html, "w") as f:
        f.write(page)
    e["html"] = f"editions/{eid}/index.html"
    chrome = chrome_bin()
    if chrome:
        pdf = os.path.join(pub, base + ".pdf")
        r = subprocess.run([chrome, "--headless=new", "--no-sandbox", "--disable-gpu",
                            "--no-pdf-header-footer", f"--print-to-pdf={pdf}",
                            "file://" + os.path.abspath(out_html)], capture_output=True, timeout=180)
        if os.path.exists(pdf):
            e["pdf"] = f"editions/{eid}/{base}.pdf"
        else:
            print(f"::warning::PDF not produced: {r.stderr.decode()[-300:]}")
    ref = os.path.join(BRIEFS_DIR, "Global_Macro_Intelligence_Brief_2026.docx")
    try:
        cmd = ["pandoc", md, "-o", os.path.join(pub, base + ".docx"), "--toc"]
        if os.path.exists(ref):
            cmd += ["--reference-doc", ref]
        subprocess.run(cmd, check=True, capture_output=True)
        e["docx"] = f"editions/{eid}/{base}.docx"
    except Exception as ex:
        print(f"::warning::Word file not produced: {ex}")
    save_json(REGISTRY, reg)
    return out_html


# ======================================================================== PUBLISH
def publish(eid, today=None):
    reg = registry()
    e = next((x for x in reg["editions"] if x["id"] == eid), None)
    if not e:
        raise SystemExit(f"no edition {eid}")
    if e.get("status") == "published":
        print(f"{eid} is already published")
        return
    if e.get("fake"):
        raise SystemExit(f"{eid} was a test run (--fake) and cannot be published; discard it")
    e["status"] = "published"
    e["published"] = (today or datetime.date.today().isoformat())
    save_json(REGISTRY, reg)
    render(eid)       # re-render without the DRAFT banner
    check(today, write=True)
    print(f"Published {eid}: {e['title']}")


def discard(eid):
    reg = registry()
    e = next((x for x in reg["editions"] if x["id"] == eid), None)
    if not e or e.get("status") != "draft":
        raise SystemExit(f"{eid} is not a draft")
    reg["editions"] = [x for x in reg["editions"] if x["id"] != eid]
    save_json(REGISTRY, reg)
    shutil.rmtree(os.path.join(ED_PUBLIC, eid), ignore_errors=True)
    shutil.rmtree(os.path.join(ED_DATA, eid), ignore_errors=True)
    check(write=True)
    print(f"Discarded draft {eid}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["check", "write", "render", "publish", "discard"])
    ap.add_argument("id", nargs="?")
    ap.add_argument("--force", action="store_true", help="write even if not due")
    ap.add_argument("--fake", action="store_true", help="no API calls; placeholder text (testing)")
    ap.add_argument("--today")
    a = ap.parse_args()
    if a.cmd == "check":
        print(json.dumps(check(a.today), indent=1))
    elif a.cmd == "write":
        write(force=a.force, fake=a.fake, today=a.today)
    elif a.cmd == "render":
        print(render(a.id))
    elif a.cmd == "publish":
        publish(a.id, a.today)
    else:
        discard(a.id)
