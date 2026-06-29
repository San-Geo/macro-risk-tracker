"""Deterministic cross-indicator consistency checks.

The rating agent grades each indicator on its own. This module looks at the
WHOLE scored picture and flags internal contradictions using explicit rules
from config/consistency.yaml (e.g. "sea lane closed but oil benign").

Design stance: rules FLAG, they do not silently rewrite ratings. A contradiction
means the evidence is genuinely ambiguous about which read is wrong, so the
disciplined output is a flag for the deterministic engine + human to resolve -
not a fabricated correction. This keeps the tool's "rules move the meter, human
signs off" contract intact.
"""
import os
import yaml

OPS = {
    ">":  lambda a, b: a > b,
    ">=": lambda a, b: a >= b,
    "<":  lambda a, b: a < b,
    "<=": lambda a, b: a <= b,
    "==": lambda a, b: a == b,
    "!=": lambda a, b: a != b,
}


def load_rules(path):
    if not os.path.exists(path):
        return []
    with open(path) as f:
        return (yaml.safe_load(f) or {}).get("rules", []) or []


def build_index(result):
    """Map indicator_id -> {band, value, label, story} from a scored result."""
    idx = {}
    for s in result.get("stories", []):
        for i in s.get("indicators", []):
            idx[i["id"]] = {
                "band": i.get("band"),
                "value": i.get("value"),
                "label": i.get("label", i["id"]),
                "story": s.get("name", ""),
            }
    return idx


def _condition_holds(cond, idx):
    rec = idx.get(cond["indicator"])
    if rec is None:
        return False
    field = cond.get("field", "band")
    actual = rec.get(field)
    if actual is None:
        return False
    op = OPS.get(cond["op"])
    if op is None:
        return False
    try:
        return op(actual, cond["value"])
    except TypeError:
        return False


def check(result, rules):
    """Return a list of fired-rule dicts (deterministic, order-stable)."""
    idx = build_index(result)
    fired = []
    for r in rules:
        conds = r.get("when", [])
        if not conds:
            continue
        if all(_condition_holds(c, idx) for c in conds):
            involved = []
            for c in conds:
                rec = idx.get(c["indicator"], {})
                involved.append({
                    "id": c["indicator"],
                    "label": rec.get("label", c["indicator"]),
                    "story": rec.get("story", ""),
                    "band": rec.get("band"),
                    "value": rec.get("value"),
                })
            fired.append({
                "id": r["id"],
                "name": r.get("name", r["id"]),
                "message": " ".join((r.get("flag", "") or "").split()),
                "severity": r.get("severity", "medium"),
                "indicators": involved,
            })
    sev_order = {"high": 0, "medium": 1, "low": 2}
    fired.sort(key=lambda f: (sev_order.get(f["severity"], 1), f["id"]))
    return fired


def run(result, path=None):
    """Convenience: load rules and check. Returns {'generated_for', 'flags':[...]}"""
    if path is None:
        here = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        path = os.path.join(here, "config", "consistency.yaml")
    rules = load_rules(path)
    return {"checked": len(rules), "flags": check(result, rules)}
