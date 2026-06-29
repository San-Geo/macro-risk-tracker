#!/usr/bin/env python3
"""Config self-test. Run:  python tests/selftest.py   (exit 0 = pass, 1 = fail)

Catches the bugs that would silently corrupt the tracker:
  - baseline_band that does NOT match the band baseline_value maps to
    (this would make day-zero levels disagree with the published reports)
  - missing/!malformed indicator fields or bad good/warn ordering
  - duplicate ids; framework rubric/source gaps
  - non-deterministic scoring
Designed to run in CI on every push.
"""
import os, sys, yaml

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(ROOT, "src"))
import score  # noqa: E402

FAILS, WARNS = [], []


def fail(msg): FAILS.append(msg)
def warn(msg): WARNS.append(msg)


def load(name):
    with open(os.path.join(ROOT, "config", name)) as f:
        return yaml.safe_load(f)


def main():
    stories = load("stories.yaml")["stories"]
    framework = (load("framework.yaml") or {}).get("indicators", {})

    seen_story, seen_ind = set(), {}
    REQ = ["id", "label", "source", "direction", "good", "warn",
           "baseline_value", "baseline_band", "weight", "cadence"]

    for s in stories:
        if s["id"] in seen_story:
            fail(f"duplicate story id: {s['id']}")
        seen_story.add(s["id"])
        if not isinstance(s.get("base_level"), int) or not (1 <= s["base_level"] <= 10):
            fail(f"{s['id']}: base_level must be int 1-10")

        for ind in s.get("indicators", []):
            iid = ind.get("id", "?")
            for k in REQ:
                if k not in ind:
                    fail(f"{s['id']}/{iid}: missing field '{k}'")
            if iid in seen_ind:
                fail(f"duplicate indicator id: {iid} (in {s['id']} and {seen_ind[iid]})")
            seen_ind[iid] = s["id"]
            if any(k not in ind for k in REQ):
                continue

            d, good, warn_t = ind["direction"], ind["good"], ind["warn"]
            if d not in ("higher_worse", "lower_worse"):
                fail(f"{iid}: bad direction '{d}'")
                continue
            if d == "higher_worse" and not good < warn_t:
                fail(f"{iid}: higher_worse needs good < warn (got {good}, {warn_t})")
            if d == "lower_worse" and not good > warn_t:
                fail(f"{iid}: lower_worse needs good > warn (got {good}, {warn_t})")

            # THE key check: baseline_band must equal the band baseline_value maps to.
            computed = score.band_for(ind["baseline_value"], d, good, warn_t)
            if computed != ind["baseline_band"]:
                fail(f"{iid}: baseline_band={ind['baseline_band']} but baseline_value "
                     f"{ind['baseline_value']} maps to band {computed} "
                     f"-> day-zero level would be wrong")

        # end-to-end: at baseline (empty values) the story must score its base_level
        scored = score.score_story(s, {})
        if scored["level"] != s["base_level"]:
            fail(f"{s['id']}: baseline level {scored['level']} != base_level {s['base_level']}")

    # framework coverage / quality
    for fid, spec in framework.items():
        if fid not in seen_ind:
            fail(f"framework indicator '{fid}' is not a real indicator in stories.yaml")
        if not spec.get("sources"):
            fail(f"framework '{fid}': no sources listed")
        if spec.get("type", "band") == "band":
            r = spec.get("rubric", "")
            if not all(t in r for t in ("0", "1", "2")):
                fail(f"framework '{fid}': band rubric must define 0/1/2")
    # warn (not fail) if a manual indicator has no agent rubric
    for iid, sid in seen_ind.items():
        src = next(i["source"] for st in stories for i in st["indicators"] if i["id"] == iid)
        if src == "manual" and iid not in framework:
            warn(f"manual indicator '{iid}' has no framework rubric (agent can't rate it)")

    # determinism: same inputs -> same outputs
    r1 = score.score_all({"stories": stories}, {})
    r2 = score.score_all({"stories": stories}, {})
    if r1 != r2:
        fail("scoring is not deterministic")

    # consistency rules must reference real indicator IDs and valid ops/fields
    all_ind_ids = {i["id"] for st in stories for i in st["indicators"]}
    cpath = os.path.join(ROOT, "config", "consistency.yaml")
    if os.path.exists(cpath):
        import consistency as _cons
        for rule in _cons.load_rules(cpath):
            rid = rule.get("id", "?")
            for c in rule.get("when", []):
                if c.get("indicator") not in all_ind_ids:
                    fail(f"consistency rule '{rid}': unknown indicator '{c.get('indicator')}'")
                if c.get("field", "band") not in ("band", "value"):
                    fail(f"consistency rule '{rid}': field must be band|value")
                if c.get("op") not in _cons.OPS:
                    fail(f"consistency rule '{rid}': bad op '{c.get('op')}'")

    n_ind = len(seen_ind)
    print(f"Checked {len(stories)} stories, {n_ind} indicators, {len(framework)} framework rubrics.")
    for w in WARNS:
        print("  WARN:", w)
    if FAILS:
        print(f"\nFAILED ({len(FAILS)}):")
        for m in FAILS:
            print("  -", m)
        sys.exit(1)
    print("\nAll config checks PASSED.")


if __name__ == "__main__":
    main()
