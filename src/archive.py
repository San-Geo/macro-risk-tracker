"""Permanent, dated archive of what the tracker saw and said - for later comparison
and pattern-finding.

Before this, three things were overwritten every run and only survived in git
history: the agent's evidence (facts, sources, reasoning), the daily note, and the
overall/set scores. This module appends them to dated files that are never rewritten
(except to replace a same-day re-run), and freezes a monthly copy of the living brief.

    data/archive/daily/YYYY-MM.jsonl   one line per run date: overall, sets, breakdown,
                                       every story's raw score/level/band, the daily note
    data/archive/agent/YYYY.jsonl      one line per indicator per weekly agent pass: value,
                                       confidence, fact, rationale, dissent, sources ...
    dashboard/briefs/archive/          living_brief_YYYY-MM-DD.html (first run of each
                                       month) + index.html listing snapshots and editions

JSON Lines = one JSON object per line: easy to load in Python/pandas/Excel Power Query
and to diff on GitHub. About 6-7 MB a year in total.

main.py calls run() at the end of every run; it never raises into the run.
"""
import glob
import html
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)

ARCH = os.path.join(ROOT, "data", "archive")
DAILY_DIR = os.path.join(ARCH, "daily")
AGENT_DIR = os.path.join(ARCH, "agent")
SNAP_DIR = os.path.join(ROOT, "dashboard", "briefs", "archive")
EDITIONS_JSON = os.path.join(ROOT, "dashboard", "briefs", "editions", "editions.json")
STATUS_JSON = os.path.join(ROOT, "dashboard", "briefs", "editions", "status.json")


# ---------------------------------------------------------------- daily record
def daily_record(latest):
    """The compact, permanent record of one run date (from a latest.json dict)."""
    agg = latest.get("aggregates") or {}
    levels = {}
    for s in latest.get("stories", []) or []:
        levels[s["id"]] = {"raw": s.get("raw_level"), "level": s.get("level"), "band": s.get("band")}
    return {
        "date": latest.get("date"),
        "generated_at": latest.get("generated_at"),
        "method_version": latest.get("method_version"),
        "overall": agg.get("overall"),
        "sets": {str(k): v for k, v in agg.items() if k != "overall"},
        "breakdown": latest.get("overall_breakdown"),
        "n_high": sum(1 for v in levels.values() if (v["level"] or 0) >= 7),
        "levels": levels,
        "narrative": latest.get("narrative") or "",
        "offline": bool(latest.get("offline")),
        "health": {k: (latest.get("data_health") or {}).get(k)
                   for k in ("feeds_ok", "feeds_total", "agent_flags", "ledger_ok")
                   if k in (latest.get("data_health") or {})},
    }


def _read_jsonl(path):
    out = []
    if os.path.exists(path):
        with open(path) as f:
            for line in f:
                line = line.strip()
                if line:
                    try:
                        out.append(json.loads(line))
                    except Exception:
                        continue  # one bad line never loses the rest
    return out


def _write_jsonl(path, rows):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False, sort_keys=True) + "\n")
    os.replace(tmp, path)


def record_daily(latest):
    rec = daily_record(latest)
    if not rec["date"]:
        return None
    path = os.path.join(DAILY_DIR, rec["date"][:7] + ".jsonl")
    rows = [r for r in _read_jsonl(path) if r.get("date") != rec["date"]]  # same-day re-run replaces
    rows.append(rec)
    rows.sort(key=lambda r: r.get("date") or "")
    _write_jsonl(path, rows)
    return path


def fill_gaps(upto_date, hist_path=None):
    """Any run date that is in data/history.csv but missing from the archive (e.g. days
    before this module existed, or a run whose archive step failed) gets a record
    rebuilt from the stored raw story scores. Marked "rebuilt": the daily note for
    those days is not recoverable this way, and the scores use today's rules."""
    import csv
    import score
    hist_path = hist_path or os.path.join(ROOT, "data", "history.csv")
    if not os.path.exists(hist_path):
        return 0
    have = set()
    for p in glob.glob(os.path.join(DAILY_DIR, "*.jsonl")):
        have.update(r.get("date") for r in _read_jsonl(p))
    if not have:
        return 0  # a brand-new archive starts from today; nothing to repair
    first = min(have)
    by_date = {}
    with open(hist_path, newline="") as f:
        for r in csv.DictReader(f):
            d = r.get("date")
            if d and first < d < upto_date and d not in have:
                by_date.setdefault(d, {})[r["story_id"]] = r
    n = 0
    for d, rows in sorted(by_date.items()):
        levels, by_set = {}, {}
        for sid, r in rows.items():
            try:
                raw = float(r.get("raw_level") or r["level"])
            except (TypeError, ValueError):
                continue
            lvl = score.round_half_up(raw)
            levels[sid] = {"raw": raw, "level": lvl, "band": score.band_name(lvl)}
            by_set.setdefault(str(r.get("set")), []).append(raw)
        if not levels:
            continue
        brk = score.aggregate_overall([v["raw"] for v in levels.values()])
        rec = {"date": d, "generated_at": None, "method_version": score.METHODOLOGY_VERSION,
               "overall": brk["overall"],
               "sets": {k: round(sum(v) / len(v) + 1e-9, 1) for k, v in by_set.items()},
               "breakdown": brk, "n_high": sum(1 for v in levels.values() if v["level"] >= 7),
               "levels": levels, "narrative": "", "health": {}, "rebuilt": True}
        path = os.path.join(DAILY_DIR, d[:7] + ".jsonl")
        rows_ = _read_jsonl(path) + [rec]
        rows_.sort(key=lambda r: r.get("date") or "")
        _write_jsonl(path, rows_)
        n += 1
    return n


# ---------------------------------------------------------------- agent evidence
def record_agent_pass(alog):
    """Append one weekly agent pass (one line per indicator). Idempotent: a pass
    already archived (same 'generated' timestamp) is skipped."""
    gen = alog.get("generated")
    items = alog.get("assessments") or {}
    if not gen or not items:
        return 0
    path = os.path.join(AGENT_DIR, gen[:4] + ".jsonl")
    rows = _read_jsonl(path)
    if any(r.get("pass") == gen for r in rows):
        return 0
    flags = set(alog.get("review_flags") or [])
    for ind, a in sorted(items.items()):
        row = {"pass": gen, "date": alog.get("date") or gen[:10], "model": alog.get("model"),
               "indicator": ind, "flagged": ind in flags}
        row.update({k: v for k, v in a.items() if k not in ("prior",)})  # prior = last pass, already archived
        rows.append(row)
    rows.sort(key=lambda r: (r.get("pass") or "", r.get("indicator") or ""))
    _write_jsonl(path, rows)
    return len(items)


# ---------------------------------------------------------------- monthly snapshot
def snapshot_month(latest, force=False):
    """Freeze the living brief on the first run of each month."""
    date = latest.get("date")
    if not date:
        return None
    month = date[:7]
    if not force and glob.glob(os.path.join(SNAP_DIR, f"living_brief_{month}-*.html")):
        return None
    import build_brief
    return build_brief.build(latest=latest, outdir=SNAP_DIR, basename=f"living_brief_{date}", snapshot=True)


# ---------------------------------------------------------------- index page
def _load_json(path, default):
    try:
        with open(path) as f:
            return json.load(f)
    except Exception:
        return default


def write_index():
    e = lambda s: html.escape(str(s if s is not None else ""), quote=True)  # noqa: E731
    eds = [x for x in _load_json(EDITIONS_JSON, {}).get("editions", []) if x.get("status") == "published"]
    eds.sort(key=lambda x: x.get("published", ""), reverse=True)
    status = _load_json(STATUS_JSON, {})
    snaps = sorted(glob.glob(os.path.join(SNAP_DIR, "living_brief_*.html")), reverse=True)
    rows_e = "".join(
        f'<li><a href="../{e(x["pdf"])}">{e(x["title"])}</a> <span class="m">published {e(x.get("published"))}'
        f' · data as of {e(x.get("data_as_of"))}'
        + (f' · overall {e(x["overall"])}' if x.get("overall") is not None else "")
        + (f' · <a href="../{e(x["docx"])}">Word</a>' if x.get("docx") else "")
        + (f' · <a href="../{e(x["html"])}">web</a>' if x.get("html") else "")
        + (f' · revision {e(x["revision"])} ({e(x.get("revised"))})' if x.get("revision") else "")
        + (f' · <a href="../{e(x["first_printing"]["pdf"])}">first printing</a>'
           if (x.get("first_printing") or {}).get("pdf") else "")
        + "</span></li>" for x in eds) or "<li>None yet.</li>"
    rows_s = "".join(
        f'<li><a href="{e(os.path.basename(p))}">{e(os.path.basename(p)[13:23])}</a></li>' for p in snaps) \
        or "<li>The first snapshot is taken on the first run of next month.</li>"
    nxt = ""
    if status:
        nxt = (f'<p class="m">Next edition: {e(status.get("summary", ""))} '
               f'(checked {e(status.get("checked", ""))}).</p>')
    page = f"""<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1"><title>Brief Archive</title>
<style>
:root{{--bg:#f4f6f9;--card:#fff;--line:#e6e9ee;--text:#161a1f;--muted:#677182;--accent:#1F4E79}}
@media (prefers-color-scheme:dark){{:root{{--bg:#0e1116;--card:#161b22;--line:#262d37;--text:#e7ebf0;--muted:#9aa6b4;--accent:#5b9bd5}}}}
body{{margin:0;background:var(--bg);color:var(--text);font:15px/1.6 -apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,Helvetica,Arial,sans-serif}}
main{{max-width:760px;margin:0 auto;padding:20px 16px}}
a{{color:var(--accent)}} h1{{font-size:22px;margin:0 0 4px}} h2{{font-size:17px;margin:24px 0 8px}}
.card{{background:var(--card);border:1px solid var(--line);border-radius:10px;padding:12px 18px}}
ul{{margin:0;padding-left:18px}} .m{{color:var(--muted);font-size:13px}}
</style></head><body><main>
<h1>Brief archive</h1>
<p class="m"><a href="../../">Tracker</a> · <a href="../living_brief.html">Today’s living brief</a></p>
<h2>Editions</h2><div class="card"><ul>{rows_e}</ul></div>{nxt}
<h2>Monthly snapshots of the living brief</h2>
<p class="m">Frozen on the first tracker run of each month. Levels are shown as published that day.</p>
<div class="card"><ul>{rows_s}</ul></div>
<p class="m">The full machine-readable history (daily scores, notes and the AI agent's evidence) is in the
repository under data/archive/.</p>
</main></body></html>"""
    os.makedirs(SNAP_DIR, exist_ok=True)
    with open(os.path.join(SNAP_DIR, "index.html"), "w") as f:
        f.write(page)


# ---------------------------------------------------------------- entry point
def run(latest, alog=None):
    """Called by main.py after latest.json is written. Returns a short summary."""
    done = {}
    for name, fn in (("gaps", lambda: fill_gaps(latest.get("date") or "")),
                     ("daily", lambda: record_daily(latest)),
                     ("agent", lambda: record_agent_pass(alog or {})),
                     ("snapshot", lambda: snapshot_month(latest)),
                     ("index", write_index)):
        try:
            done[name] = fn()
        except Exception as ex:  # one part failing never stops the others
            done[name] = f"error: {ex}"
            print(f"::warning title=Archive ({name}) skipped::{ex}")
    return done


if __name__ == "__main__":
    with open(os.path.join(ROOT, "dashboard", "latest.json")) as f:
        lt = json.load(f)
    al = _load_json(os.path.join(ROOT, "data", "agent_assessments.json"), {})
    print(run(lt, al))
