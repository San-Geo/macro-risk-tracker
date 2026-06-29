#!/usr/bin/env python3
"""The overnight-event scout.

Distinct from the rating agent. The rating agent answers a FIXED question set
(re-rate the 46 known indicators). The scout asks an OPEN question: "did something
material happen that the tracker doesn't already capture?"

For each material development it finds (via grounded web search) it triages into one of:
  - existing_indicator : already captured -> the rating agent should re-rate it
  - story_gap          : fits an existing story but no indicator captures it
                         -> proposes a NEW indicator + rubric
  - new_risk           : fits no existing story -> proposes a NEW story stub

CRITICAL: the scout PROPOSES, it never mutates. Everything lands in a review queue
(data/scout_queue.json) with status "pending". A human approves or dismisses; only
then does anything reach the config. This preserves the tracker's human-final design.

  python src/scout.py                      # run a scan, update the queue
  python src/scout.py --list               # show pending proposals
  python src/scout.py --status <id> dismissed|approved
  python src/scout.py --snippet <id>       # print a paste-ready YAML snippet to merge
"""
import argparse, datetime, hashlib, json, os, re, time, urllib.request, urllib.error
import yaml

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
SCOUT_MODEL = os.environ.get("SCOUT_MODEL", "claude-sonnet-4-6")
QUEUE_PATH = os.path.join(ROOT, "data", "scout_queue.json")
DASH_PATH = os.path.join(ROOT, "dashboard", "scout_queue.json")
API_URL = "https://api.anthropic.com/v1/messages"
CLASSES = {"existing_indicator", "story_gap", "new_risk"}


def build_inventory(config):
    lines = []
    for s in config["stories"]:
        inds = ", ".join(i.get("label", i["id"]) for i in s.get("indicators", []))
        lines.append(f"- [{s['id']} | Set {s['set']}] {s['name']} :: indicators: {inds}")
    return "\n".join(lines)


def _slug(text):
    return re.sub(r"[^a-z0-9]+", "-", (text or "").lower()).strip("-")[:48]


def _id(headline):
    return _slug(headline) + "-" + hashlib.sha1((headline or "").encode()).hexdigest()[:6]


def load_queue():
    if os.path.exists(QUEUE_PATH):
        try:
            with open(QUEUE_PATH) as f:
                return json.load(f)
        except Exception:
            pass
    return {"items": {}}


def save_queue(q):
    for p in (QUEUE_PATH, DASH_PATH):
        os.makedirs(os.path.dirname(p), exist_ok=True)
        with open(p, "w") as f:
            json.dump(q, f, indent=2)


def _extract_json_array(text):
    text = re.sub(r"^```(json)?|```$", "", text.strip(), flags=re.MULTILINE).strip()
    try:
        d = json.loads(text)
        return d if isinstance(d, list) else d.get("items", d.get("developments", []))
    except Exception:
        pass
    start = text.find("[")
    if start == -1:
        return []
    frag = text[start:]
    try:
        return json.loads(frag)
    except Exception:
        pass
    # salvage a truncated array: keep complete objects, drop the dangling tail, re-close
    last = frag.rfind("}")
    if last != -1:
        try:
            return json.loads(frag[:last + 1] + "]")
        except Exception:
            pass
    return []


def discover(api_key, date, inventory, days=7, max_items=6, model=None):
    """Call the model with web search; return a list of triaged candidate dicts."""
    prompt = (
        f"You are a macro-risk SCOUT. Today is {date}. Find NEW, material global "
        f"macro / economic / financial / geopolitical developments from roughly the last "
        f"{days} days that a risk tracker should react to, and triage each against the "
        f"EXISTING tracker below.\n\nEXISTING STORIES AND INDICATORS:\n{inventory}\n\n"
        "Use web_search to find recent developments from credible sources (major newswires, "
        "central banks, IMF/IEA/FAO, official releases). Ignore routine noise; include only "
        "items of medium or high materiality. For each, choose EXACTLY ONE classification:\n"
        '- "existing_indicator": already captured -> give target_story and target_indicator.\n'
        '- "story_gap": fits an existing story but no indicator captures it -> give target_story '
        'and proposed_indicator {label, type:"band"|"value", rubric, sources:[...], suggested_weight}.\n'
        '- "new_risk": fits no existing story -> give proposed_story {name, why, proposed_level (1-10), '
        'set, indicators:[{label, type, rubric, sources, suggested_weight}]}.\n\n'
        "Base everything on what you actually find; cite source URLs with dates. "
        f"Return ONLY a JSON array of up to {max_items} objects, each:\n"
        '{"headline":"...","summary":"<=2 sentences","as_of":"YYYY-MM-DD","sources":["url"],'
        '"materiality":"medium|high","classification":"...","target_story":"<id or name, if any>",'
        '"target_indicator":"<id, if existing_indicator>","proposed_indicator":{...},'
        '"proposed_story":{...},"rationale":"why it matters / why this class"}'
    )
    body = json.dumps({
        "model": model or SCOUT_MODEL, "max_tokens": 8000,
        "tools": [{"type": "web_search_20250305", "name": "web_search", "max_uses": 6}],
        "messages": [{"role": "user", "content": prompt}],
    }).encode()
    req = urllib.request.Request(API_URL, data=body, headers={
        "content-type": "application/json", "x-api-key": api_key,
        "anthropic-version": "2023-06-01"})
    data = None
    for attempt in range(4):
        try:
            with urllib.request.urlopen(req, timeout=180) as r:
                data = json.loads(r.read().decode())
            break
        except urllib.error.HTTPError as e:
            # the scout runs right after the agent's burst, so 429s are common; back off and retry
            if e.code in (429, 529) and attempt < 3:
                time.sleep(2 ** attempt + 2)
                continue
            raise
    if data is None:
        raise RuntimeError("no response from API")
    text = "".join(b.get("text", "") for b in data.get("content", []) if b.get("type") == "text")
    return _extract_json_array(text)


def run_scout(config, api_key, date, days=7, max_items=6, discover_fn=discover):
    """Discover + triage + merge into the queue (dedup, never overwrite human status)."""
    inventory = build_inventory(config)
    q = load_queue()
    items = q.get("items", {})
    new_count = 0
    try:
        candidates = discover_fn(api_key, date, inventory, days, max_items)
    except Exception as e:
        q["last_error"] = str(e)
        q["generated"] = date
        save_queue(q)
        return q
    for c in candidates or []:
        cls = c.get("classification")
        if cls not in CLASSES:
            continue
        if str(c.get("materiality", "")).lower() not in ("medium", "high"):
            continue
        cid = _id(c.get("headline", ""))
        if cid in items:
            # keep human status/first_seen; refresh evidence fields only
            for k in ("summary", "as_of", "sources", "rationale", "materiality"):
                if c.get(k):
                    items[cid][k] = c[k]
            items[cid]["last_seen"] = date
            continue
        c["status"] = "pending"
        c["first_seen"] = date
        c["last_seen"] = date
        c["id"] = cid
        items[cid] = c
        new_count += 1
    q["items"] = items
    q["generated"] = date
    q["model"] = SCOUT_MODEL
    q["new_count"] = new_count
    q["pending_count"] = sum(1 for v in items.values() if v.get("status") == "pending")
    q.pop("last_error", None)
    save_queue(q)
    return q


def set_status(cid, status):
    q = load_queue()
    if cid not in q.get("items", {}):
        print(f"  no such proposal: {cid}")
        return
    q["items"][cid]["status"] = status
    q["pending_count"] = sum(1 for v in q["items"].values() if v.get("status") == "pending")
    save_queue(q)
    print(f"  {cid} -> {status}")


def snippet(cid):
    """Emit a paste-ready YAML snippet for an approved proposal."""
    q = load_queue()
    it = q.get("items", {}).get(cid)
    if not it:
        print(f"  no such proposal: {cid}")
        return
    cls = it["classification"]
    if cls == "story_gap" and it.get("proposed_indicator"):
        pi = it["proposed_indicator"]
        print(f"# Add under story '{it.get('target_story')}' in config/stories.yaml:")
        print(yaml.dump([{
            "id": _slug(pi.get("label", "new_indicator")).replace("-", "_"),
            "label": pi.get("label"), "source": "manual",
            "direction": "higher_worse", "good": 0, "warn": 1,
            "baseline_value": 0, "baseline_band": 0,
            "weight": pi.get("suggested_weight", 1.0), "cadence": "event",
        }], sort_keys=False))
        print("# And add the rubric to config/framework.yaml:")
        print(yaml.dump({_slug(pi.get("label", "new")).replace("-", "_"): {
            "type": pi.get("type", "band"), "query": it.get("headline"),
            "rubric": pi.get("rubric"), "sources": pi.get("sources", [])}}, sort_keys=False))
    elif cls == "new_risk" and it.get("proposed_story"):
        ps = it["proposed_story"]
        print("# Review, then add as a new story in config/stories.yaml (set base_level deliberately):")
        print(yaml.dump([{
            "id": _slug(ps.get("name", "new_story")).replace("-", "_"),
            "name": ps.get("name"), "set": ps.get("set", 4),
            "base_level": ps.get("proposed_level", 5),
            "indicators": [{"label": i.get("label"), "type": i.get("type", "band"),
                            "rubric": i.get("rubric")} for i in ps.get("indicators", [])],
        }], sort_keys=False))
    else:
        print(f"# {cid} is '{cls}': re-rate {it.get('target_indicator') or it.get('target_story')} "
              "(no new config needed).")


STORIES_PATH = os.path.join(ROOT, "config", "stories.yaml")
FRAMEWORK_PATH = os.path.join(ROOT, "config", "framework.yaml")
BRIEFS_PATH = os.path.join(ROOT, "config", "briefs.yaml")
SELFTEST_PATH = os.path.join(ROOT, "tests", "selftest.py")


def _q(s):  # make a string safe to drop inside a double-quoted YAML scalar
    return str(s or "").replace('"', "'").replace("\n", " ").strip()


def _existing_ids():
    with open(STORIES_PATH) as f:
        cfg = yaml.safe_load(f)
    sids = {s["id"] for s in cfg["stories"]}
    iids = {i["id"] for s in cfg["stories"] for i in s["indicators"]}
    return sids, iids


def _uniq(base, taken):
    base = base or "item"
    cid, n = base, 2
    while cid in taken:
        cid = f"{base}_{n}"
        n += 1
    return cid


def _ind_block(iid, label, weight, note):
    return (f"      - id: {iid}\n"
            f"        label: \"{_q(label)}\"\n"
            f"        source: \"manual\"\n"
            f"        cadence: event\n"
            f"        direction: higher_worse\n"
            f"        good: 0\n        warn: 1\n"
            f"        baseline_value: 0\n        baseline_band: 0\n"
            f"        weight: {float(weight or 1.0)}\n"
            f"        note: \"{_q(note)}\"\n")


def _framework_block(iid, query, rubric, sources):
    out = [f"  {iid}:", "    type: band",
           f"    query: \"{_q(query)}\"",
           f"    rubric: \"{_q(rubric)}\"", "    sources:"]
    for u in (sources or ["https://www.reuters.com"]):
        out.append(f"      - {_q(u)}")
    return "\n".join(out) + "\n"


def _append(path, text):
    with open(path) as f:
        cur = f.read()
    if not cur.endswith("\n"):
        cur += "\n"
    with open(path, "w") as f:
        f.write(cur + text)


def _insert_indicator(story_id, block):
    with open(STORIES_PATH) as f:
        lines = f.readlines()
    start = next((i for i, ln in enumerate(lines)
                  if re.match(rf"^  - id: {re.escape(story_id)}\s*$", ln)), None)
    if start is None:
        raise ValueError(f"target story '{story_id}' not found")
    j = next((k for k in range(start + 1, len(lines))
              if re.match(r"^  - id: ", lines[k])), len(lines))
    while j > start + 1 and lines[j - 1].strip() == "":
        j -= 1
    lines[j:j] = [block]
    with open(STORIES_PATH, "w") as f:
        f.writelines(lines)


def apply(cid):
    import shutil, subprocess, sys as _sys
    q = load_queue()
    it = q.get("items", {}).get(cid)
    if not it:
        print(f"  no such proposal: {cid}")
        return
    cls = it["classification"]
    if cls == "existing_indicator":
        it["status"] = "applied"
        save_queue(q)
        print(f"  '{cls}': nothing to merge - the rating agent re-rates "
              f"{it.get('target_indicator') or it.get('target_story')}. Marked applied.")
        return

    backups = {p: p + ".bak" for p in (STORIES_PATH, FRAMEWORK_PATH, BRIEFS_PATH)
               if os.path.exists(p)}
    for src, dst in backups.items():
        shutil.copy(src, dst)
    try:
        sids, iids = _existing_ids()
        if cls == "story_gap":
            pi = it.get("proposed_indicator") or {}
            iid = _uniq(_slug(pi.get("label", "indicator")).replace("-", "_"), iids)
            _insert_indicator(it["target_story"],
                              _ind_block(iid, pi.get("label"), pi.get("suggested_weight"),
                                         f"Added via scout proposal {cid}."))
            _append(FRAMEWORK_PATH, _framework_block(iid, it.get("headline"),
                                                     pi.get("rubric"), pi.get("sources")))
        elif cls == "new_risk":
            ps = it.get("proposed_story") or {}
            sid = _uniq(_slug(ps.get("name", "story")).replace("-", "_"), sids)
            level = max(1, min(10, int(ps.get("proposed_level", 5))))
            inds = ps.get("indicators") or [{"label": ps.get("name", "status"),
                                             "rubric": "0 = benign; 1 = watch; 2 = stress"}]
            blocks, fw = [], []
            for ind in inds:
                iid = _uniq(_slug(ind.get("label", "indicator")).replace("-", "_"), iids)
                iids.add(iid)
                blocks.append(_ind_block(iid, ind.get("label"), ind.get("suggested_weight"),
                                         f"Added via scout proposal {cid}."))
                fw.append(_framework_block(iid, ind.get("label"),
                                           ind.get("rubric"), ind.get("sources")))
            story = (f"\n  - id: {sid}\n    set: {ps.get('set', 4)}\n"
                     f"    name: \"{_q(ps.get('name'))}\"\n    base_level: {level}\n"
                     f"    indicators:\n" + "".join(blocks))
            _append(STORIES_PATH, story)
            for b in fw:
                _append(FRAMEWORK_PATH, b)
            if os.path.exists(BRIEFS_PATH) and ps.get("why"):
                _append(BRIEFS_PATH, f"  {sid}:\n    summary: \"DRAFT \u2014 {_q(ps.get('why'))}\"\n")
        else:
            raise ValueError(f"cannot apply classification '{cls}'")

        yaml.safe_load(open(STORIES_PATH))     # must still parse
        yaml.safe_load(open(FRAMEWORK_PATH))
        rc = subprocess.run([_sys.executable, SELFTEST_PATH], capture_output=True, text=True)
        if rc.returncode != 0:
            raise RuntimeError("self-test failed after merge:\n" + (rc.stdout or "")[-800:])
    except Exception as e:
        for src, dst in backups.items():       # roll back everything
            shutil.copy(dst, src)
        for dst in backups.values():
            os.remove(dst)
        print(f"  apply FAILED, rolled back cleanly: {e}")
        return

    for dst in backups.values():
        os.remove(dst)
    it["status"] = "applied"
    save_queue(q)
    print(f"  applied '{cls}' and self-test PASSED. Commit config/ to deploy.")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--list", action="store_true")
    ap.add_argument("--status", nargs=2, metavar=("ID", "STATUS"))
    ap.add_argument("--apply", metavar="ID", help="merge an approved proposal into config (with self-test + rollback)")
    ap.add_argument("--snippet", metavar="ID")
    ap.add_argument("--days", type=int, default=7)
    ap.add_argument("--date", default=datetime.date.today().isoformat())
    args = ap.parse_args()

    if args.status:
        return set_status(args.status[0], args.status[1])
    if args.apply:
        return apply(args.apply)
    if args.snippet:
        return snippet(args.snippet)
    if args.list:
        q = load_queue()
        pend = [v for v in q.get("items", {}).values() if v.get("status") == "pending"]
        print(f"{len(pend)} pending proposal(s):")
        for it in sorted(pend, key=lambda x: x.get("materiality", ""), reverse=True):
            print(f"  [{it.get('materiality','?').upper():6}] {it.get('classification'):18} "
                  f"{it.get('headline','')[:70]}  ({it['id']})")
        return

    key = os.environ.get("ANTHROPIC_API_KEY")
    if not key:
        print("ANTHROPIC_API_KEY not set; scout needs it to search. Skipping.")
        return
    with open(os.path.join(ROOT, "config", "stories.yaml")) as f:
        config = yaml.safe_load(f)
    q = run_scout(config, key, args.date, args.days)
    print(f"Scout: {q.get('new_count', 0)} new, {q.get('pending_count', 0)} pending total.")


if __name__ == "__main__":
    main()
