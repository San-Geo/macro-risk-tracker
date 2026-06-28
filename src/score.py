"""Deterministic, auditable scoring. No AI, no hidden magic.

band(value)  -> 0 benign / 1 watch / 2 stress  (per direction + thresholds)
delta        = weight * (band - baseline_band) / 2
story level  = clamp(base_level + sum(deltas), 1, 10)
"""

BANDS = [(2, "Low"), (4, "Moderate"), (6, "Elevated"), (8, "High"), (10, "Severe")]


def band_for(value, direction, good, warn):
    if value is None:
        return None
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
        b = band_for(v, ind["direction"], ind["good"], ind["warn"])
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


def score_all(config, values):
    stories = [score_story(s, values) for s in config["stories"]]
    by_set = {}
    for s in stories:
        by_set.setdefault(s["set"], []).append(s["level"])
    aggregates = {k: round(sum(v) / len(v), 1) for k, v in by_set.items()}
    aggregates["overall"] = round(sum(s["level"] for s in stories) / len(stories), 1)
    return {"stories": stories, "aggregates": aggregates}
