"""Resolution ledger - the tracker's public track record.

THE MACHINE KEEPS THE RECORD; THE HUMAN PASSES JUDGMENT.

Deterministic part (runs automatically, no AI):
  * When a story's level enters High (>= OPEN_LEVEL) an EPISODE opens. The opening
    date is reconstructed from history.csv (the first day of the current unbroken
    High streak), so backfill is exact, not guessed.
  * While High, the episode tracks its peak level and days elapsed.
  * When the story drops back below High, the episode CLOSES automatically and
    waits for a human grade.

Human part (never automated):
  * Grade a closed episode with one of:
      materialized - the risk this story warned about actually happened
      contained    - real stress occurred but was absorbed/managed
      faded        - the pressure receded without a materialized event
    via:  python src/ledger.py --grade <episode_id> <grade> [--note "..."]
    or by editing the "grade"/"grade_note" fields in data/resolution_ledger.json.

Over time this answers the only question a public risk tracker must eventually
answer: when this thing said High, what happened next?
"""
import argparse
import csv
import json
import os

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
LEDGER_PATH = os.path.join(ROOT, "data", "resolution_ledger.json")
DASH_LEDGER = os.path.join(ROOT, "dashboard", "ledger.json")
OPEN_LEVEL = 7  # High and above

GRADES = ("materialized", "contained", "faded")


def load_ledger():
    if os.path.exists(LEDGER_PATH):
        with open(LEDGER_PATH) as f:
            return json.load(f)
    return {"episodes": [], "note": "Record begins with the ledger feature; earlier history was not graded."}


def save_ledger(led):
    os.makedirs(os.path.dirname(LEDGER_PATH), exist_ok=True)
    with open(LEDGER_PATH, "w") as f:
        json.dump(led, f, indent=2)
    os.makedirs(os.path.dirname(DASH_LEDGER), exist_ok=True)
    with open(DASH_LEDGER, "w") as f:
        json.dump(led, f, separators=(",", ":"))


def _story_series(history_path, story_id):
    """[(date, level)] ascending for one story from history.csv."""
    out = []
    if not os.path.exists(history_path):
        return out
    with open(history_path, newline="") as f:
        for row in csv.reader(f):
            if len(row) >= 5 and row[0] != "date" and row[1] == story_id:
                try:
                    out.append((row[0], int(float(row[4]))))
                except ValueError:
                    continue
    return sorted(out)


def _streak_start(series, date):
    """First date of the unbroken >= OPEN_LEVEL streak that includes `date`."""
    start = date
    for d, lvl in reversed(series):
        if d > date:
            continue
        if lvl >= OPEN_LEVEL:
            start = d
        else:
            break
    return start


def update_ledger(result, date, history_path):
    """Open/refresh/close episodes from the scored board. Never touches grades."""
    led = load_ledger()
    eps = led["episodes"]
    open_by_story = {e["story_id"]: e for e in eps if e.get("status") == "open"}

    for s in result["stories"]:
        level = s["level"]
        ep = open_by_story.get(s["id"])
        if level >= OPEN_LEVEL:
            if ep is None:
                series = _story_series(history_path, s["id"])
                opened = _streak_start(series, date)
                drivers = [f"{i['label']}: {i.get('value')} (band {i.get('band')})"
                           for i in s.get("indicators", []) if (i.get("band") or 0) >= 1][:4]
                eps.append({
                    "id": f"{s['id']}-{opened}",
                    "story_id": s["id"], "story": s["name"], "set": s["set"],
                    "opened": opened, "open_level": level,
                    "peak_level": level, "peak_date": date,
                    "last_seen": date, "status": "open",
                    "drivers_at_open": drivers,
                    "closed": None, "grade": None, "grade_note": None,
                })
            else:
                ep["last_seen"] = date
                if level > ep["peak_level"]:
                    ep["peak_level"], ep["peak_date"] = level, date
        elif ep is not None:
            ep["status"] = "closed"
            ep["closed"] = date
            ep["close_level"] = level
    save_ledger(led)
    return led


def grade(episode_id, grade_value, note=None):
    if grade_value not in GRADES:
        raise SystemExit(f"grade must be one of {GRADES}")
    led = load_ledger()
    for e in led["episodes"]:
        if e["id"] == episode_id:
            if e.get("status") != "closed":
                raise SystemExit(f"{episode_id} is still open - episodes are graded after they close.")
            e["grade"] = grade_value
            if note:
                e["grade_note"] = note
            save_ledger(led)
            print(f"graded {episode_id}: {grade_value}")
            return
    raise SystemExit(f"no episode with id {episode_id} (see --list)")


if __name__ == "__main__":
    p = argparse.ArgumentParser(description="Resolution ledger - list or grade episodes")
    p.add_argument("--list", action="store_true")
    p.add_argument("--grade", nargs=2, metavar=("EPISODE_ID", "GRADE"))
    p.add_argument("--note", default=None)
    a = p.parse_args()
    if a.grade:
        grade(a.grade[0], a.grade[1], a.note)
    else:
        led = load_ledger()
        for e in led["episodes"]:
            g = e.get("grade") or ("awaiting grade" if e.get("status") == "closed" else "open")
            print(f"{e['id']:40s} {e['story'][:34]:34s} opened {e['opened']} "
                  f"peak {e['peak_level']} status {e['status']:6s} [{g}]")
