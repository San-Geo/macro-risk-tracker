"""Deterministic, auditable scoring. No AI, no hidden magic.

band(value)  -> 0 benign / 1 watch / 2 stress  (per direction + thresholds)
delta        = weight * (band - baseline_band) / 2
story level  = clamp(base_level + sum(deltas), 1, 10)
"""

BANDS = [(2, "Low"), (4, "Moderate"), (6, "Elevated"), (8, "High"), (10, "Severe")]

# Methodology version. BUMP THIS whenever a change alters what a level MEANS
# (aggregation, banding, rubric thresholds, story reframes). Every saved history row
# is stamped with it so trend lines and backtests never silently mix scoring regimes.
METHODOLOGY_VERSION = "2.0"
METHODOLOGY_CHANGELOG = {
    "1.0": "Initial: plain-mean overall; original event rubrics; one-sided China PPI.",
    "2.0": "2026-06: fact-anchored countable event rubrics; two-sided China PPI; "
           "per-domain source authorities; agent sanity ranges + cross-checks; "
           "consistency engine; tail-weighted, correlation-aware overall (replaces the mean).",
}


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
    raw = story["base_level"] + sum(deltas)
    level = max(1, min(10, int(round(raw))))
    return {
        "id": story["id"], "name": story["name"], "set": story["set"],
        "base_level": story["base_level"], "raw_level": round(raw, 2),
        "level": level, "band": band_name(level), "indicators": detail,
    }


def aggregate_overall(levels):
    """Tail-weighted, correlation-aware overall.

    The plain mean of 21 story levels crushed the range toward the centre and
    washed out broad, correlated shocks (a single driver lighting up many stories).
    Instead we blend the breadth average with the WORST CLUSTER (mean of the top
    third of stories) and add a bounded premium when many stories are High at once -
    the signature of a systemic, common-driver episode. A lone spike barely moves it;
    a broad cluster pushes it toward High/Severe.
    """
    n = len(levels) or 1
    s = sorted(levels, reverse=True)
    k = max(1, round(n / 3))                       # top third = the worst cluster
    mean_all = sum(levels) / n
    tail_mean = sum(s[:k]) / k
    n_high = sum(1 for x in levels if x >= 7)
    premium = min(1.5, 0.3 * max(0, n_high - 2))   # correlated-breadth premium
    overall = max(1, min(10, round(0.5 * mean_all + 0.5 * tail_mean + premium, 1)))
    return {"overall": overall, "breadth_mean": round(mean_all, 1),
            "tail_mean": round(tail_mean, 1), "tail_k": k,
            "n_high_stories": n_high, "correlated_premium": round(premium, 1)}


def score_all(config, values):
    stories = [score_story(s, values) for s in config["stories"]]
    by_set = {}
    for s in stories:
        by_set.setdefault(s["set"], []).append(s["level"])
    aggregates = {k: round(sum(v) / len(v), 1) for k, v in by_set.items()}
    brk = aggregate_overall([s["level"] for s in stories])
    aggregates["overall"] = brk["overall"]
    return {"stories": stories, "aggregates": aggregates, "overall_breakdown": brk}
