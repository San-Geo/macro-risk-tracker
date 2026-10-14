"""Unit tests for the tracker's rules. Stdlib unittest - no extra packages.

    python -m unittest discover -s tests -p "test_*.py" -v

Each test pins a behaviour that was once wrong or that a past fix depends on, so a
future change that breaks it shows as a red cross on the commit.
"""
import datetime
import json
import os
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))

import score  # noqa: E402
import feedguard  # noqa: E402
import portwatch  # noqa: E402
import agent  # noqa: E402
import grader  # noqa: E402
import ledger  # noqa: E402
import narrative  # noqa: E402


class Scoring(unittest.TestCase):
    def test_half_up(self):
        # methodology 3.0: 6.5 -> 7 and 4.5 -> 5 (Python's round() gave 6 and 4)
        self.assertEqual([score.round_half_up(x) for x in (4.5, 5.5, 6.5, 7.5, 6.49)], [5, 6, 7, 8, 6])

    def test_story_level_uses_half_up(self):
        story = {"id": "x", "name": "x", "set": 1, "base_level": 6, "indicators": [
            {"id": "i", "label": "i", "source": "manual", "cadence": "event", "direction": "higher_worse",
             "good": 0, "warn": 1, "baseline_value": 1, "baseline_band": 1, "weight": 1.0}]}
        r = score.score_story(story, {"i": 2})
        self.assertEqual((r["raw_level"], r["level"], r["band"]), (6.5, 7, "High"))

    def test_overall_is_smooth(self):
        # one story moving 6.5 -> 6.75 must not jump the overall by a fixed step
        base = [7.5, 7, 7, 7, 6.5, 6.5, 6.5, 6.5] + [5.0] * 13
        bumped = list(base); bumped[4] = 6.75
        d = score.aggregate_overall(bumped)["overall"] - score.aggregate_overall(base)["overall"]
        self.assertLess(d, 0.2)

    def test_overall_bounds(self):
        self.assertEqual(score.aggregate_overall([1.0] * 21)["overall"], 1.0)
        self.assertLessEqual(score.aggregate_overall([10.0] * 21)["overall"], 10.0)

    def test_soft_high_count(self):
        self.assertAlmostEqual(score.soft_high_count([6.0, 6.5, 7.0, 9.0]), 2.5)


class FeedGuard(unittest.TestCase):
    CFG = {"defaults": {"jump_window_days": 10}, "indicators": {
        "vix": {"min": 5, "max": 150, "max_jump": {"rel": 2.0}},
        "copper_price": {"min": 1, "max": 30, "max_jump": {"rel": 0.3}}}}

    def test_failed_feed_carries_last_good(self):
        st = {"oil_price": {"value": 93.0, "as_of": "2026-10-12", "seen": "2026-10-12"}}
        f = {"oil_price": {"value": None, "as_of": None}}
        rep = feedguard.check(f, "2026-10-13", self.CFG, st, save=False)
        self.assertEqual(f["oil_price"]["value"], 93.0)
        self.assertIn("oil_price", rep["carried"])

    def test_unit_switch_is_held_forever(self):
        st = {"copper_price": {"value": 6.7, "as_of": "2026-10-12", "seen": "2026-10-12"}}
        for day, v in (("2026-10-13", 672.0), ("2026-10-14", 675.0)):
            f = {"copper_price": {"value": v, "as_of": day}}
            feedguard.check(f, day, self.CFG, st, save=False)
            self.assertEqual(f["copper_price"]["value"], 6.7)

    def test_real_spike_confirmed_next_run(self):
        st = {"vix": {"value": 15.0, "as_of": "2026-10-12", "seen": "2026-10-12"}}
        f = {"vix": {"value": 50.0, "as_of": "2026-10-13"}}
        feedguard.check(f, "2026-10-13", self.CFG, st, save=False)
        self.assertEqual(f["vix"]["value"], 15.0)
        f = {"vix": {"value": 48.0, "as_of": "2026-10-14"}}
        rep = feedguard.check(f, "2026-10-14", self.CFG, st, save=False)
        self.assertEqual(f["vix"]["value"], 48.0)
        self.assertIn("vix", rep["confirmed"])


class PortWatchRules(unittest.TestCase):
    CFG = {"closed_below": 0.25, "normal_above": 0.80,
           "rules": {"hormuz_redsea_status": ["hormuz", "bab_el_mandeb"], "hormuz_fertilizer": ["hormuz"]}}

    def r(self, ratio):
        return {"name": "x", "avg7": 1, "baseline": 90, "ratio": ratio, "as_of": "2026-10-04"}

    def test_closed_by_measurement(self):
        v = {"hormuz_redsea_status": 1, "hormuz_fertilizer": 0}
        portwatch.apply(v, {"hormuz": self.r(0.03), "bab_el_mandeb": self.r(0.43)}, set(), self.CFG)
        self.assertEqual(v, {"hormuz_redsea_status": 2, "hormuz_fertilizer": 2})

    def test_near_normal_caps_agent_at_1(self):
        v = {"hormuz_redsea_status": 2, "hormuz_fertilizer": 2}
        portwatch.apply(v, {"hormuz": self.r(0.95), "bab_el_mandeb": self.r(0.9)}, set(), self.CFG)
        self.assertEqual(v, {"hormuz_redsea_status": 1, "hormuz_fertilizer": 1})

    def test_human_pin_wins(self):
        v = {"hormuz_redsea_status": 0, "hormuz_fertilizer": 0}
        portwatch.apply(v, {"hormuz": self.r(0.03), "bab_el_mandeb": self.r(0.03)}, {"hormuz_fertilizer"}, self.CFG)
        self.assertEqual(v["hormuz_fertilizer"], 0)


class AgentGuards(unittest.TestCase):
    def test_as_of_range_keyed_on_start(self):
        self.assertEqual(agent._as_of_key("2026-03-27 to 2026-10"), (2026, 3, 27))

    def test_salvage_recovers_sources(self):
        raw = ('{"value": 2, "confidence": "high", "as_of": "2026-10-12", "fact": "it said "x" here", '
               '"rationale": "r", "sources": ["https://a.org/1", "https://b.org/cut')
        out = agent._extract_json(raw)
        self.assertEqual(out["sources"], ["https://a.org/1"])


class Grading(unittest.TestCase):
    RUB = {"window_days_after_close": 30, "stories": {"s": {"risk": "r",
           "materialized": [{"id": "M1", "test": "t"}], "contained": [{"id": "C1", "test": "t"}]}}}
    EP = {"story_id": "s", "opened": "2026-07-01", "closed": "2026-07-20"}

    def test_grade_computed_from_tests(self):
        raw = {"tests": [{"id": "M1", "met": False}, {"id": "C1", "met": True, "onset": "2026-07-05",
                                                       "source": "https://x.org"}], "confidence": "medium"}
        self.assertEqual(grader.evaluate(raw, self.EP, self.RUB)["grade"], "contained")

    def test_unsourced_test_not_met(self):
        raw = {"tests": [{"id": "M1", "met": True, "onset": "2026-07-05", "source": ""},
                         {"id": "C1", "met": False}], "confidence": "high"}
        self.assertEqual(grader.evaluate(raw, self.EP, self.RUB)["grade"], "faded")

    def test_concurrent_timing(self):
        raw = {"tests": [{"id": "M1", "met": True, "onset": "2026-02-28", "source": "https://x.org"},
                         {"id": "C1", "met": False}], "confidence": "high"}
        ev = grader.evaluate(raw, self.EP, self.RUB)
        self.assertEqual((ev["grade"], ev["timing"]), ("materialized", "concurrent"))


class Ledger(unittest.TestCase):
    def test_close_needs_five_runs_below(self):
        series = [("2026-10-0%d" % d, 7) for d in range(1, 5)] + [("2026-10-05", 6), ("2026-10-06", 6)]
        self.assertEqual(ledger._runs_below(series, "2026-10-07", 6), 3)

    def test_owner_grade_csv(self):
        with tempfile.TemporaryDirectory() as d:
            ledger.LEDGER_PATH = os.path.join(d, "l.json")
            ledger.DASH_LEDGER = os.path.join(d, "dl.json")
            ledger.save_ledger({"episodes": [{"id": "e1", "status": "closed", "grade": None}]})
            csvp = os.path.join(d, "g.csv")
            with open(csvp, "w") as f:
                f.write("episode_id,grade,note,timing\ne1,faded,note,\nnope,faded,x,\n")
            msgs = ledger.apply_owner_grades(csvp)
            e = ledger.load_ledger()["episodes"][0]
            self.assertEqual((e["grade"], e["grade_source"]), ("faded", "owner"))
            self.assertEqual(len(msgs), 1)


class Narrative(unittest.TestCase):
    def test_band_word_corrected(self):
        today = {"aggregates": {"overall": 7.1}, "stories": [{"level": 7, "band": "High"}]}
        text, fixes = narrative.enforce_band_words("Risk is elevated at 7.1 today.", today)
        self.assertIn("high at 7.1", text)  # case of the original word is kept


if __name__ == "__main__":
    unittest.main()
