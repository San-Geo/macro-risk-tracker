"""Deterministic, auditable scoring. No AI, no hidden magic.

band(value)  -> 0 benign / 1 watch / 2 stress  (per direction + thresholds)
delta        = weight * (band - baseline_band) / 2
raw level    = clamp(base_level + sum(deltas), 1, 10)      (unrounded - used for ALL math)
story level  = raw level rounded HALF UP to an integer      (display + bands only)
"""
import math

BANDS = [(2, "Low"), (4, "Moderate"), (6, "Elevated"), (8, "High"), (10, "Severe")]

# Methodology version. BUMP THIS whenever a change alters what a level MEANS
# (aggregation, banding, rubric thresholds, story reframes). Every saved history row
# is stamped with it so trend lines and backtests never silently mix scoring regimes.
METHODOLOGY_VERSION = "3.0"
METHODOLOGY_CHANGELOG = {
    "1.0": "Initial: plain-mean overall; original event rubrics; one-sided China PPI.",
    "2.0": "2026-06: fact-anchored countable event rubrics; two-sided China PPI; "
           "per-domain source authorities; agent sanity ranges + cross-checks; "
           "consistency engine; tail-weighted, correlation-aware overall (replaces the mean).",
    "3.0": "2026-10: story levels round HALF UP (was Python's round-half-to-even, which "
           "sent 6.5 to 6 but 7.5 to 8); every aggregate is computed from UNROUNDED raw "
           "levels and rounded once; the breadth premium uses a smooth count of High "
           "stories instead of a step per story.",
}


def round_half_up(x):
    """Conventional rounding (6.5 -> 7, 4.5 -> 5) - matches the dashboard and Excel."""
    return int(math.floor(float(x) + 0.5))


def level_of(story_row):
    """A story's level under the CURRENT rounding rule, from its unrounded score when
    one is stored. Used wherever today is compared with older records, so the switch
    to half-up rounding (methodology 3.0) is never mistaken for a real move."""
    raw = story_row.get("raw_level") if isinstance(story_row, dict) else None
    if raw not in (None, ""):
        try:
            return max(1, min(10, round_half_up(float(raw))))
        except (TypeError, ValueError):
            pass
    return int(float(story_row["level"]))


def band_for(value, direction, good, warn, center=0.0):
    if value is None:
        return None
    if direction == "two_sided":
        # risk grows as the value departs a neutral center in EITHER direction;
        # good/warn are the half-width thresholds on |value - center|.
        d = abs(value - center)
        if d <= good:
            return 0
        if d <= warn:
            return 1
        return 2
    if direction == "higher_worse":
        if value <= good:
            return 0
        if value <= warn:
            return 1
        return 2
    else:  # lower_worse
        if value >= good:
            return 0
        if value >= warn:
            return 1
        return 2


def band_name(level):
    for ceiling, name in BANDS:
        if level <= ceiling:
            return name
    return "Severe"


def score_story(story, values):
    """values: {indicator_id: number or None}. Returns dict with level + detail."""
    deltas, detail = [], []
    for ind in story["indicators"]:
        v = values.get(ind["id"], ind.get("baseline_value"))
        used_baseline = ind["id"] not in values or values[ind["id"]] is None
        if used_baseline:
            v = ind.get("baseline_value")
        b = band_for(v, ind["direction"], ind["good"], ind["warn"], ind.get("center", 0.0))
        base_b = ind.get("baseline_band", 0)
        d = round(ind["weight"] * ((b if b is not None else base_b) - base_b) / 2.0, 3)
        deltas.append(d)
        detail.append({
            "id": ind["id"], "label": ind["label"], "value": v,
            "band": b, "baseline_band": base_b, "weight": ind["weight"],
            "delta": d, "source": ind["source"], "cadence": ind["cadence"],
            "stale": used_baseline,
        })
    raw = max(1.0, min(10.0, story["base_level"] + sum(deltas)))
    level = max(1, min(10, round_half_up(raw)))
    return {
        "id": story["id"], "name": story["name"], "set": story["set"],
        "base_level": story["base_level"], "raw_level": round(raw, 2),
        "level": level, "band": band_name(level), "indicators": detail,
    }


def soft_high_count(raw_levels):
    """How many stories are 'at High', counted smoothly: a story contributes 0 at a
    raw level of 6.0 or below, 1 at 7.0 or above, and proportionally in between
    (0.5 at exactly 6.5, the High threshold). A one-step move in one indicator can
    no longer jump the overall by a fixed 0.3."""
    return sum(min(1.0, max(0.0, r - 6.0)) for r in raw_levels)


def aggregate_overall(raw_levels):
    """Tail-weighted, correlation-aware overall - computed from UNROUNDED story levels.

    The plain mean of 21 story levels crushed the range toward the centre and
    washed out broad, correlated shocks (a single driver lighting up many stories).
    Instead we blend the breadth average with the WORST CLUSTER (mean of the top
    third of stories) and add a bounded premium when many stories are High at once -
    the signature of a systemic, common-driver episode. A lone spike barely moves it;
    a broad cluster pushes it toward High/Severe. Rounding happens once, at the end.
    """
    raw_levels = [float(x) for x in raw_levels]
    n = len(raw_levels) or 1
    s = sorted(raw_levels, reverse=True)
    k = max(1, round_half_up(n / 3))              # top third = the worst cluster
    mean_all = sum(raw_levels) / n
    tail_mean = sum(s[:k]) / k
    soft_high = soft_high_count(raw_levels)
    premium = min(1.5, 0.3 * max(0.0, soft_high - 2))   # correlated-breadth premium
    overall = max(1.0, min(10.0, round(0.5 * mean_all + 0.5 * tail_mean + premium + 1e-9, 1)))
    return {"overall": overall, "breadth_mean": round(mean_all, 2),
            "tail_mean": round(tail_mean, 2), "tail_k": k,
            "n_high_stories": sum(1 for r in raw_levels if round_half_up(r) >= 7),
            "soft_high": round(soft_high, 2),
            "correlated_premium": round(premium, 2)}


def score_all(config, values):
    stories = [score_story(s, values) for s in config["stories"]]
    by_set = {}
    for s in stories:
        by_set.setdefault(s["set"], []).append(s["raw_level"])
    aggregates = {k: round(sum(v) / len(v) + 1e-9, 1) for k, v in by_set.items()}
    brk = aggregate_overall([s["raw_level"] for s in stories])
    aggregates["overall"] = brk["overall"]
    return {"stories": stories, "aggregates": aggregates, "overall_breakdown": brk}
