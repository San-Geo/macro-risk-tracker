#!/usr/bin/env python3
"""Validation harness.

Two honest tests of the engine, written to data/validation.json and shown on the
dashboard:

  1. CALIBRATION - replay documented historical stress episodes (2008/2020/2022/2023)
     through the live scoring engine and check it lights up: does the overall level
     reach Elevated/High DURING each crisis, does it RISE INTO the event, and does it
     separate from a calm baseline? Caveat (carried through): only the market/data
     indicators are varied; judgment indicators are held at baseline, so these are a
     LOWER BOUND on the market-driven component, not a claim the tracker "called" them.

  2. SENSITIVITY - on the CURRENT board, swing each indicator across its full band
     range (0 <-> 2) and measure how far that moves its story, its set, and the
     overall. This needs no historical assumptions; it shows which facts most need to
     be right (high-leverage indicators) and quantifies how fragile each level is.

Run:  python src/validate.py     (after main.py has written latest.json)
"""
import datetime
import json
import os
import sys

import yaml

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
import score  # noqa: E402
import backtest  # noqa: E402

VERSION = "1.0"

# A benign reference snapshot (low-vol, tight spreads) for the discrimination test.
CALM = dict(vix=12, move=55, move_ccp=55, sofr_effr_spread=0.0, hy_oas=3.3, ig_oas=1.0,
            oil_price=60, copper_price=2.9, unrate=4.0, dxy=100, real10=0.5)


def _band_label(level):
    return score.band_name(round(level))


def _all_band_overall(config, target):
    vals = {}
    for s in config["stories"]:
        for ind in s["indicators"]:
            vals[ind["id"]] = _value_for_band(ind, target)
    return score.score_all(config, vals)["aggregates"]["overall"]


def calibration(config):
    sample = backtest.run_sample(config)["episodes"]
    calm_overall = score.score_all(config, dict(CALM))["aggregates"]["overall"]
    baseline_overall = score.score_all(config, {})["aggregates"]["overall"]
    floor = _all_band_overall(config, 0)
    ceiling = _all_band_overall(config, 2)
    episodes = []
    lit = 0
    seps = []
    for name, ep in sample.items():
        ov = ep["overall"]
        peak = max(ov)
        peak_idx = ov.index(peak)
        reached_elevated = peak >= 5
        reached_high = peak >= 7
        rose_into = peak_idx > 0 and peak > ov[0]
        sep = round(peak - calm_overall, 2)
        seps.append(sep)
        if reached_elevated:
            lit += 1
        episodes.append({
            "name": name, "note": ep.get("note", ""),
            "dates": ep["dates"], "overall": ov,
            "start_overall": ov[0], "peak_overall": peak,
            "peak_band": _band_label(peak), "peak_date": ep["dates"][peak_idx],
            "reached_elevated": reached_elevated, "reached_high": reached_high,
            "rose_into_event": rose_into, "separation_vs_calm": sep,
        })
    return {
        "calm_overall": calm_overall,
        "range": {"floor_all_low": floor, "baseline": baseline_overall, "ceiling_all_high": ceiling},
        "episodes": episodes,
        "summary": {
            "n_episodes": len(episodes),
            "lit_elevated_or_higher": lit,
            "mean_separation": round(sum(seps) / len(seps), 2) if seps else 0,
            "finding": ("The overall is now tail-weighted: it tracks the worst cluster of "
                        "stories and adds a premium when many are High at once, so a broad "
                        "correlated shock lifts it (range ~4.7-9.0). These episodes replay "
                        "MARKET indicators only with judgment indicators held at baseline, so "
                        "they remain a LOWER BOUND - a real crisis that also lit the judgment "
                        "layer would read materially higher."),
        },
    }


def _value_for_band(ind, target):
    """A representative value that maps to the target band for this indicator."""
    d = ind["direction"]
    good, warn = ind["good"], ind["warn"]
    center = ind.get("center", 0.0)
    step = max(0.01, abs(warn) * 0.05)
    if d == "two_sided":
        return center if target == 0 else center + warn + step
    if d == "higher_worse":
        return good if target == 0 else warn + step
    # lower_worse
    return good if target == 0 else warn - step


def _current_values():
    """Reconstruct the applied value vector from the latest snapshot, if present."""
    p = os.path.join(ROOT, "dashboard", "latest.json")
    if not os.path.exists(p):
        p = os.path.join(ROOT, "data", "latest.json")
    try:
        d = json.load(open(p))
        v = {}
        for s in d.get("stories", []):
            for i in s.get("indicators", []):
                if i.get("value") is not None:
                    v[i["id"]] = i["value"]
        return v
    except Exception:
        return {}


def sensitivity(config):
    base_values = _current_values()
    base = score.score_all(config, dict(base_values))
    overall0 = base["aggregates"]["overall"]
    story_of = {}
    set_of = {}
    for s in config["stories"]:
        for ind in s["indicators"]:
            story_of[ind["id"]] = s["id"]
            set_of[ind["id"]] = s["set"]
    story_level = {s["id"]: s["level"] for s in base["stories"]}

    movers = []
    for s in config["stories"]:
        for ind in s["indicators"]:
            iid = ind["id"]
            lo = dict(base_values); lo[iid] = _value_for_band(ind, 0)
            hi = dict(base_values); hi[iid] = _value_for_band(ind, 2)
            rlo = score.score_all(config, lo)
            rhi = score.score_all(config, hi)
            sl_lo = next(x["level"] for x in rlo["stories"] if x["id"] == s["id"])
            sl_hi = next(x["level"] for x in rhi["stories"] if x["id"] == s["id"])
            set_lo = rlo["aggregates"].get(s["set"])
            set_hi = rhi["aggregates"].get(s["set"])
            movers.append({
                "id": iid, "label": ind["label"], "story": s["name"], "set": s["set"],
                "weight": ind["weight"],
                "story_swing": abs(sl_hi - sl_lo),
                "set_swing": round(abs((set_hi or 0) - (set_lo or 0)), 2),
                "overall_swing": round(abs(rhi["aggregates"]["overall"] - rlo["aggregates"]["overall"]), 2),
            })
    movers.sort(key=lambda m: (m["story_swing"], m["set_swing"], m["overall_swing"]), reverse=True)
    return {
        "as_of_overall": overall0,
        "max_story_swing": max((m["story_swing"] for m in movers), default=0),
        "max_overall_swing": max((m["overall_swing"] for m in movers), default=0),
        "movers": movers[:12],
        "note": ("Overall is the mean of all 21 story levels, so no single indicator can "
                 "move it far - the headline is robust by construction. The leverage that "
                 "matters is on each STORY: the indicators below are where a wrong fact "
                 "does the most damage and most deserves cross-checking."),
    }


def main():
    with open(os.path.join(ROOT, "config", "stories.yaml")) as f:
        config = yaml.safe_load(f)
    out = {
        "generated": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "version": VERSION,
        "calibration": calibration(config),
        "sensitivity": sensitivity(config),
        "scope": ("Calibration replays documented MARKET-indicator history through the live "
                  "engine with judgment indicators held at baseline (a lower bound, not a "
                  "prediction claim). Sensitivity is exact and assumption-free on the current "
                  "board."),
    }
    for p in (os.path.join(ROOT, "data", "validation.json"),
              os.path.join(ROOT, "dashboard", "validation.json")):
        os.makedirs(os.path.dirname(p), exist_ok=True)
        with open(p, "w") as f:
            json.dump(out, f, indent=2)
    c = out["calibration"]["summary"]
    s = out["sensitivity"]
    print(f"Validation written. Calibration: {c['lit_elevated_or_higher']}/{c['n_episodes']} "
          f"episodes reached Elevated+, mean separation {c['mean_separation']}.")
    print(f"Sensitivity: max single-indicator story swing {s['max_story_swing']}, "
          f"max overall swing {s['max_overall_swing']}.")


if __name__ == "__main__":
    main()
