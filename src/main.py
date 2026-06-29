#!/usr/bin/env python3
"""Global Macro Risk Tracker - daily run.

  python src/main.py                 # fetch live data + AI narrative (needs keys/network)
  python src/main.py --offline       # use baseline/manual values (no network) - try this first
  python src/main.py --no-ai         # skip the Claude narrative (templated summary instead)

Outputs:
  data/history.csv              append-only daily log
  data/latest.json              machine-readable snapshot
  dashboard/latest.json         same, served next to the webpage
  output/macro_risk_tracker.xlsx  formula-driven Excel model
"""
import argparse, csv, json, os, sys, datetime
import yaml

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
import score, fetch, narrative, report, agent, enrich, alerts, consistency  # noqa: E402


def load_config():
    with open(os.path.join(ROOT, "config", "stories.yaml")) as f:
        return yaml.safe_load(f)


def load_manual():
    path = os.path.join(ROOT, "manual_input.csv")
    vals = {}
    if os.path.exists(path):
        with open(path) as f:
            for row in csv.DictReader(f):
                v = (row.get("value") or "").strip()
                if v != "":
                    try:
                        vals[row["indicator_id"].strip()] = float(v)
                    except ValueError:
                        pass
    return vals


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--offline", action="store_true", help="skip network fetch")
    ap.add_argument("--no-ai", action="store_true", help="skip Claude narrative")
    ap.add_argument("--agent", action="store_true",
                    help="run the rating agent now (researches + rates judgment indicators)")
    ap.add_argument("--no-alert", action="store_true", help="don't send band-crossing alerts")
    ap.add_argument("--scout", action="store_true",
                    help="run the overnight-event scout (proposes new indicators/stories)")
    ap.add_argument("--test-alert", action="store_true", help="send a test alert and exit")
    ap.add_argument("--date", default=datetime.date.today().isoformat())
    args = ap.parse_args()

    if args.test_alert:
        print("Sending test alert ...")
        alerts.send_test(os.environ)
        return

    config = load_config()

    values = {}
    fetched = {}
    if not args.offline:
        print("Fetching live indicators ...")
        fetched = fetch.fetch_all_dated(config)
        values.update({k: dv["value"] for k, dv in fetched.items() if dv["value"] is not None})
        print(f"  got {len(values)} live market/data values")

    # Human overrides: any indicator filled in manual_input.csv is pinned and wins.
    manual = load_manual()
    overrides = set(manual.keys())

    # Agent: research + rate the judgment indicators per config/framework.yaml.
    key = os.environ.get("ANTHROPIC_API_KEY")
    if args.agent and key and not args.offline:
        print("Running rating agent (web-search grounded) ...")
        framework = agent.load_framework()
        agent_values, alog = agent.run_agent(framework, key, args.date, overrides=overrides)
        values.update(agent_values)
        flags = alog.get("review_flags", [])
        print(f"  agent rated {len(agent_values)} indicators; "
              f"{len(flags)} flagged for review: {', '.join(flags) if flags else 'none'}")
    else:
        # Not running the agent this time: reuse its last applied assessments.
        cached = agent.load_applied_values()
        if cached:
            values.update(cached)
            print(f"  reusing {len(cached)} cached agent ratings "
                  f"(run with --agent to refresh)")
        if args.agent and not key:
            print("  --agent requested but ANTHROPIC_API_KEY not set; using cached/baseline.")

    values.update(manual)  # human overrides always win

    result = score.score_all(config, values)
    result["date"] = args.date
    result["sets"] = config.get("sets", {})

    # Attach per-story background + full-brief link (from config/briefs.yaml).
    briefs_path = os.path.join(ROOT, "config", "briefs.yaml")
    if os.path.exists(briefs_path):
        try:
            with open(briefs_path) as f:
                briefs = yaml.safe_load(f) or {}
            set_pdf = briefs.get("set_pdf", {})
            orig = briefs.get("original_set", {})
            combined = briefs.get("combined_pdf")
            pages = briefs.get("pages", {})
            bmap = briefs.get("stories", {})
            for s in result["stories"]:
                b = bmap.get(s["id"], {})
                if b.get("summary"):
                    s["summary"] = b["summary"]
                if combined:
                    pg = pages.get(s["id"])
                    s["brief_url"] = f"{combined}#page={pg}" if pg else combined
                else:
                    osn = orig.get(s["id"])
                    s["brief_url"] = set_pdf.get(osn) or set_pdf.get(str(osn))
        except Exception as e:
            print(f"  (briefs.yaml skipped: {e})")

    # Attach the agent's latest assessments (this run or last cached) for the dashboard panel.
    alog = agent.load_log()
    if alog.get("assessments"):
        idmap = {}
        for s in config["stories"]:
            for ind in s.get("indicators", []):
                idmap[ind["id"]] = (ind.get("label", ind["id"]), s["name"], s["set"])
        flags = set(alog.get("review_flags", []))
        items = []
        for ind_id, a in alog["assessments"].items():
            lbl, story, setno = idmap.get(ind_id, (ind_id, "", 0))
            items.append({
                "id": ind_id, "label": lbl, "story": story, "set": setno,
                "value": a.get("value"), "confidence": a.get("confidence"),
                "applied": a.get("applied"), "note": a.get("note", ""),
                "rationale": a.get("rationale", ""), "sources": (a.get("sources") or [])[:3],
                "as_of": a.get("as_of", ""), "out_of_range": a.get("out_of_range", False),
                "fact": a.get("fact", ""), "dissent": (a.get("dissent") or [])[:4],
                "domain": a.get("domain", ""),
            })
        items.sort(key=lambda x: (x["id"] not in flags, x["set"], x["label"]))
        result["agent_review"] = {"generated": alog.get("generated"), "model": alog.get("model"),
                                  "review_flags": sorted(flags), "items": items}

    # Whole-picture consistency: deterministic cross-indicator contradiction checks.
    try:
        result["consistency"] = consistency.run(result)
    except Exception as e:
        result["consistency"] = {"checked": 0, "flags": [], "error": str(e)}
    cflags = result["consistency"].get("flags", [])
    if cflags and result.get("agent_review"):
        rf = set(result["agent_review"].get("review_flags", []))
        rated = {it["id"] for it in result["agent_review"].get("items", [])}
        for f in cflags:
            for ind in f.get("indicators", []):
                if ind["id"] in rated:
                    rf.add(ind["id"])
        result["agent_review"]["review_flags"] = sorted(rf)
        result["agent_review"]["items"].sort(key=lambda x: (x["id"] not in rf, x["set"], x["label"]))

    hist = os.path.join(ROOT, "data", "history.csv")
    # Phase 1 enrichments (read history BEFORE appending today's row)
    enrich.attach_trends(result, hist, args.date)
    enrich.attach_provenance(result, alog if alog.get("assessments") else None, fetched, args.date)
    result["data_health"] = enrich.data_health(config, fetched, alog, args.date, args.offline)

    prev = None
    latest_path = os.path.join(ROOT, "data", "latest.json")
    if os.path.exists(latest_path):
        with open(latest_path) as f:
            prev = json.load(f)

    note, changes = narrative.make_narrative(result, prev, use_ai=not args.no_ai)
    result["narrative"] = note

    report.append_history(result, args.date, hist)
    payload = report.write_json(result, note, args.date, latest_path)
    report.write_json(result, note, args.date, os.path.join(ROOT, "dashboard", "latest.json"))
    xlsx = report.build_workbook(config, result, note, args.date, hist,
                                 os.path.join(ROOT, "output", "macro_risk_tracker.xlsx"))

    agg = result["aggregates"]
    sets_cfg = config.get("sets", {})
    set_str = "  |  ".join(
        f"{(sets_cfg.get(k) or {}).get('short', 'Set '+str(k))} {agg.get(k)}/10"
        for k in sorted(x for x in agg if x != "overall"))
    print(f"\nOverall {agg['overall']}/10  |  {set_str}")
    print(f"Level changes today: {len(changes)}")
    print(f"Wrote: {latest_path}, {hist}, {xlsx}, dashboard/latest.json")

    try:
        import build_brief
        build_brief.build()
    except Exception as e:
        print(f"  (living brief skipped: {e})")

    if not args.no_alert:
        a = alerts.maybe_alert(result, prev, os.environ)
        if a.get("sent"):
            print(f"ALERT: {len(a['crossings'])} band crossing(s) sent -> {a['results']}")
        elif a.get("reason") == "no band crossings" and prev:
            print("Alerts: no band crossings since last run.")

    if args.scout and key and not args.offline:
        import scout
        print("Running overnight-event scout ...")
        q = scout.run_scout(config, key, args.date)
        print(f"  scout: {q.get('new_count', 0)} new, {q.get('pending_count', 0)} pending "
              f"(review on the dashboard, or `python src/scout.py --list`)")

    # Validation harness: calibration vs history + sensitivity of the current board.
    try:
        import validate
        v = validate.main()
    except Exception as e:
        print(f"  (validation skipped: {e})")

    print("\n" + note)


if __name__ == "__main__":
    main()
