"""Feed guard: carry forward the last good value, and hold implausible values.

Two failure modes the scorer used to handle badly:
  1. A feed FAILS -> the indicator silently fell back to its June starting value,
     which by construction reads as "normal". Now the last good value is carried
     forward with its real as-of date and marked "carried".
  2. A feed returns NONSENSE (a unit switch, a bad print) -> it went straight into
     the score. Now a value outside its plausible range, or a jump far beyond what
     the market does in a day, is held at the last good value until the next run
     confirms it.

Rules live in config/feed_checks.yaml. State lives in data/last_good.json.
Never raises; a guard failure leaves the fetched values untouched.
"""
import datetime
import json
import os

import yaml

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
CFG_PATH = os.path.join(ROOT, "config", "feed_checks.yaml")
STATE_PATH = os.path.join(ROOT, "data", "last_good.json")


def _load(path, default):
    try:
        with open(path) as f:
            return (yaml.safe_load(f) if path.endswith((".yaml", ".yml")) else json.load(f)) or default
    except Exception:
        return default


def _jump_ok(rule, last, new):
    mj = (rule or {}).get("max_jump") or {}
    if last is None:
        return True
    if "abs" in mj and abs(new - last) > float(mj["abs"]):
        return False
    if "rel" in mj and last != 0 and abs(new - last) / abs(last) > float(mj["rel"]):
        return False
    return True


def check(fetched, today, cfg=None, state=None, save=True):
    """Mutates `fetched` ({id: {'value','as_of'}}) in place. Returns a report:
    {'carried': [ids], 'held': [{'id','value','last','reason'}], 'confirmed': [ids]}."""
    report = {"carried": [], "held": [], "confirmed": []}
    try:
        cfg = cfg if cfg is not None else _load(CFG_PATH, {})
        state = state if state is not None else _load(STATE_PATH, {})
        if not state and save:   # first run: bootstrap last good values from history
            state = seed_from_history(os.path.join(ROOT, "data", "indicator_history.csv"))
        rules = cfg.get("indicators") or {}
        dflt = cfg.get("defaults") or {}
        window = int(dflt.get("jump_window_days", 10))
        today_d = datetime.date.fromisoformat(str(today)[:10])
        for iid, dv in fetched.items():
            rule = rules.get(iid)
            lg = state.get(iid) or {}
            v = dv.get("value")
            if v is None:
                if lg.get("value") is not None:
                    dv.update(value=lg["value"], as_of=lg.get("as_of"), carried="feed failed")
                    report["carried"].append(iid)
                continue
            v = float(v)
            reason, kind = None, None
            if rule:
                lo, hi = rule.get("min"), rule.get("max")
                if (lo is not None and v < lo) or (hi is not None and v > hi):
                    reason, kind = f"outside plausible range [{lo}, {hi}]", "range"
                else:
                    recent = False
                    try:
                        recent = (today_d - datetime.date.fromisoformat(lg.get("seen", "")[:10])).days <= window
                    except Exception:
                        pass
                    if recent and not _jump_ok(rule, lg.get("value"), v):
                        reason, kind = f"jump from {lg.get('value')} exceeds max_jump {rule.get('max_jump')}", "jump"
            if reason:
                pend = lg.get("pending") or {}
                # A jump is confirmed when the NEXT run's read sits near the held one
                # (the market really moved). An out-of-range value is never confirmed.
                if (kind == "jump" and pend.get("value") is not None and pend.get("seen") != str(today_d)
                        and _jump_ok(rule, pend["value"], v)):
                    report["confirmed"].append(iid)
                    reason = None
                else:
                    lg["pending"] = {"value": v, "seen": str(today_d), "reason": reason}
                    state[iid] = lg
                    if lg.get("value") is not None:
                        report["held"].append({"id": iid, "value": v, "last": lg["value"], "reason": reason})
                        dv.update(value=lg["value"], as_of=lg.get("as_of"), held=f"{v} held: {reason}")
                    else:
                        report["held"].append({"id": iid, "value": v, "last": None, "reason": reason})
                        dv.update(value=None, held=f"{v} rejected: {reason}")
                    continue
            state[iid] = {"value": v, "as_of": dv.get("as_of"), "seen": str(today_d)}
        if save:
            os.makedirs(os.path.dirname(STATE_PATH), exist_ok=True)
            with open(STATE_PATH, "w") as f:
                json.dump(state, f, indent=1, sort_keys=True)
    except Exception as e:  # never break a run
        report["error"] = str(e)[:200]
    return report


def seed_from_history(ih_path, out_path=STATE_PATH):
    """One-time bootstrap: last good values from data/indicator_history.csv."""
    import csv
    state = {}
    if not os.path.exists(ih_path):
        return state
    with open(ih_path, newline="") as f:
        for r in csv.DictReader(f):
            if r.get("provenance") in ("Agent", "Baseline", "Manual"):
                continue
            try:
                state[r["indicator_id"]] = {"value": float(r["value"]), "as_of": r.get("as_of") or r["date"],
                                            "seen": r["date"]}
            except (TypeError, ValueError):
                continue
    with open(out_path, "w") as f:
        json.dump(state, f, indent=1, sort_keys=True)
    return state
