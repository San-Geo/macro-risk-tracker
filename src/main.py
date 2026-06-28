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
import score, fetch, narrative, report  # noqa: E402


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
    ap.add_argument("--date", default=datetime.date.today().isoformat())
    args = ap.parse_args()

    config = load_config()

    values = {}
    if not args.offline:
        print("Fetching live indicators ...")
        values.update({k: v for k, v in fetch.fetch_all(config).items() if v is not None})
        print(f"  got {len(values)} live values")
    values.update(load_manual())  # manual overrides win

    result = score.score_all(config, values)
    result["date"] = args.date

    hist = os.path.join(ROOT, "data", "history.csv")
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
    print(f"\nOverall {agg['overall']}/10  |  Set 1 {agg.get(1)}/10  |  Set 2 {agg.get(2)}/10  |  Set 3 {agg.get(3)}/10")
    print(f"Level changes today: {len(changes)}")
    print(f"Wrote: {latest_path}, {hist}, {xlsx}, dashboard/latest.json")
    print("\n" + note)


if __name__ == "__main__":
    main()
