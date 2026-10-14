"""Resolution ledger - the tracker's public track record.

THE MACHINE KEEPS THE RECORD; THE HUMAN PASSES JUDGMENT.

Deterministic part (runs automatically, no AI):
  * When a story's level enters High (>= OPEN_LEVEL) an EPISODE opens. The opening
    date is reconstructed from history.csv (the first day of the current unbroken
    High streak), so backfill is exact, not guessed.
  * While High, the episode tracks its peak level and days elapsed.
  * When the story drops back below High it starts COOLING. The episode only
    CLOSES after CLOSE_AFTER_RUNS consecutive runs below High (one full weekly
    agent cycle), then waits for a human grade. A one- or two-day dip below the
    line is noise, not an outcome - without this rule a story hovering around 7
    produces a string of one-week "episodes" that each need grading.

Grading (what happened next?):
  * Each closed episode gets one of:
      materialized - the risk this story warned about actually happened
      contained    - real stress occurred but was absorbed/managed
      faded        - the pressure receded without a materialized event
  * AUTOMATIC (src/grader.py): once the follow-through window after closing has
    passed, two independent agents mark the story's tests in config/grading.yaml;
    code computes the grade; it is applied only if both agree. Otherwise it waits
    for the owner.
  * OWNER (always wins, never overwritten): a row in grades.csv
    (episode_id,grade,note), or the Actions tab form (grade_episode / grade /
    grade_note), or locally:  python src/ledger.py --grade <id> <grade> [--note "..."]

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
CLOSE_AFTER_RUNS = 5  # consecutive runs below High before an episode closes

GRADES = ("materialized", "contained", "faded")


def load_ledger():
    if os.path.exists(LEDGER_PATH):
        with open(LEDGER_PATH) as f:
            txt = f.read()
        try:
            return json.loads(txt)
        except json.JSONDecodeError as e:
            # Fail LOUDLY with the exact spot: a silent skip once froze the public
            # track record for 12 weeks over one missing comma from a hand edit.
            raise ValueError(f"data/resolution_ledger.json is not valid JSON (line {e.lineno}, "
                             f"column {e.colno}: {e.msg}) - usually a missing comma after a hand "
                             f"edit. Grade from the Actions tab instead of editing the file.") from e
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


def _runs_below(series, date, level_today):
    """How many consecutive runs (ending today) the story has been below High.
    Computed from history.csv so a same-day rerun can never double-count."""
    by_date = dict(series)
    by_date[date] = level_today
    n = 0
    for d in sorted(by_date, reverse=True):
        if d > date:
            continue
        if by_date[d] >= OPEN_LEVEL:
            break
        n += 1
    return n


def update_ledger(result, date, history_path):
    """Open/refresh/cool/close episodes from the scored board. Never touches grades."""
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
                ep.pop("cooling", None)
                if level > ep["peak_level"]:
                    ep["peak_level"], ep["peak_date"] = level, date
        elif ep is not None:
            n = _runs_below(_story_series(history_path, s["id"]), date, level)
            if n >= CLOSE_AFTER_RUNS:
                ep.pop("cooling", None)
                ep["status"] = "closed"
                ep["closed"] = date
                ep["close_level"] = level
            else:
                ep["cooling"] = {"runs_below": n, "of": CLOSE_AFTER_RUNS, "level": level}
    led["close_rule"] = (f"An episode opens when a story reaches {OPEN_LEVEL}+ and closes after "
                         f"{CLOSE_AFTER_RUNS} consecutive runs below {OPEN_LEVEL}.")
    save_ledger(led)
    return led


def set_meta(meta):
    """Merge display metadata (e.g. the grading window) into the ledger file."""
    led = load_ledger()
    if any(led.get(k) != v for k, v in meta.items()):
        led.update(meta)
        save_ledger(led)


def _set_owner_grade(e, grade_value, note):
    e["grade"] = grade_value
    e["grade_note"] = note or e.get("grade_note")
    e["grade_source"] = "owner"
    e["grade_timing"] = e.get("grade_timing") if grade_value == "materialized" else None
    e["graded_on"] = __import__("datetime").date.today().isoformat()
    if (e.get("auto_grade") or {}).get("status") == "needs_owner":
        e["auto_grade"]["status"] = "resolved_by_owner"


def apply_owner_grades(csv_path):
    """Apply grades.csv (episode_id,grade,note[,timing]). Idempotent - rows stay in the
    file and are re-applied each run, so an owner grade always wins over the auto-
    grader. Bad rows are reported as warnings and skipped; they never break a run."""
    if not os.path.exists(csv_path):
        return []
    led = load_ledger()
    by_id = {e["id"]: e for e in led["episodes"]}
    msgs, changed = [], False
    with open(csv_path, newline="") as f:
        for n, row in enumerate(csv.DictReader(f), start=2):
            eid = (row.get("episode_id") or "").strip()
            if not eid or eid.startswith("#"):
                continue
            g = (row.get("grade") or "").strip().lower()
            if eid.startswith("miss-"):
                m = next((x for x in led.get("misses", []) if x.get("id") == eid), None)
                if m is None:
                    msgs.append(f"grades.csv line {n}: no possible miss '{eid}'")
                elif g not in ("confirmed", "rejected"):
                    msgs.append(f"grades.csv line {n}: a miss is 'confirmed' or 'rejected'")
                elif m.get("status") != g or (row.get("note") or "").strip() != (m.get("owner_note") or ""):
                    m["status"], m["owner_note"] = g, (row.get("note") or "").strip()
                    changed = True
                continue
            note = (row.get("note") or "").strip() or None
            timing = (row.get("timing") or "").strip().lower() or None
            e = by_id.get(eid)
            if e is None:
                msgs.append(f"grades.csv line {n}: no episode '{eid}' - check the ID on the dashboard")
                continue
            if g not in GRADES:
                msgs.append(f"grades.csv line {n}: grade must be one of {', '.join(GRADES)}")
                continue
            if e.get("status") != "closed":
                msgs.append(f"grades.csv line {n}: {eid} is still open - graded after it closes")
                continue
            if timing not in (None, "lead", "concurrent"):
                msgs.append(f"grades.csv line {n}: timing must be lead or concurrent (or blank)")
                timing = None
            if (e.get("grade") != g or e.get("grade_source") != "owner"
                    or (note and e.get("grade_note") != note)
                    or (timing and e.get("grade_timing") != timing)):
                _set_owner_grade(e, g, note)
                if g == "materialized" and timing:
                    e["grade_timing"] = timing
                changed = True
    if changed:
        save_ledger(led)
    return msgs


def _band_diffs(ih_rows, story_id, d_prev, d):
    a = ih_rows.get((story_id, d_prev), {})
    b = ih_rows.get((story_id, d), {})
    return [(k, a[k], v) for k, v in b.items() if k in a and a[k][1] != v[1]]


def annotate_triggers(history_path, ih_path, labels):
    """Deterministic, no AI: record which indicator moves opened and closed each
    episode, and flag a BRIEF CROSSING - a week or less at High, opened by an
    indicator that flipped back when it dropped. Those are kept in the record but
    marked, so later base-rate analysis can treat them as boundary noise."""
    if not os.path.exists(ih_path):
        return
    ih_rows = {}
    with open(ih_path, newline="") as f:
        for r in csv.DictReader(f):
            ih_rows.setdefault((r["story_id"], r["date"]), {})[r["indicator_id"]] = (r["value"], r["band"])
    dates = sorted({d for (_, d) in ih_rows})
    led = load_ledger()
    changed = False
    for e in led["episodes"]:
        if e.get("triggers") and (e.get("status") == "open" or "close" in e["triggers"]):
            continue
        sid, trig = e["story_id"], {}
        if e["opened"] in dates and dates.index(e["opened"]) > 0:
            d0 = dates[dates.index(e["opened"]) - 1]
            trig["open"] = [f"{labels.get(k, k)}: {a[0]} -> {b[0]} (band {a[1]} -> {b[1]})"
                            for k, a, b in _band_diffs(ih_rows, sid, d0, e["opened"])]
            open_ids = {k for k, _, _ in _band_diffs(ih_rows, sid, d0, e["opened"])}
        else:
            open_ids = set()
        if e.get("status") == "closed":
            later = [d for d in dates if d > e["last_seen"]]
            if later:
                dd = later[0]
                diffs = _band_diffs(ih_rows, sid, e["last_seen"], dd)
                trig["close"] = [f"{labels.get(k, k)}: {a[0]} -> {b[0]} (band {a[1]} -> {b[1]})"
                                 for k, a, b in diffs]
                days = (__import__("datetime").date.fromisoformat(e["last_seen"]) -
                        __import__("datetime").date.fromisoformat(e["opened"])).days + 1
                e["brief_crossing"] = bool(days <= 7 and open_ids & {k for k, _, _ in diffs})
        if trig and trig != e.get("triggers"):
            e["triggers"] = trig
            changed = True
    if changed:
        save_ledger(led)


def grade(episode_id, grade_value, note=None):
    if grade_value not in GRADES:
        raise SystemExit(f"grade must be one of {GRADES}")
    led = load_ledger()
    for e in led["episodes"]:
        if e["id"] == episode_id:
            if e.get("status") != "closed":
                raise SystemExit(f"{episode_id} is still open - episodes are graded after they close.")
            _set_owner_grade(e, grade_value, note)
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
