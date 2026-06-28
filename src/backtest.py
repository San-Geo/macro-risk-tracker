#!/usr/bin/env python3
"""Backtest / validation.

Replays historical values of the MARKET/DATA indicators through the exact live
scoring engine, to show the rules respond sensibly to real stress.

  python src/backtest.py            # baked sample: documented values, 2020 & 2022 (no network)
  python src/backtest.py --live --start 2019-06-01 --end 2026-06-01
                                    # pull real history from the configured feeds and replay

HONEST SCOPE (shown on the dashboard too): only the market/data indicators are
varied; the judgment indicators (geopolitics, etc.) are held at baseline, because
they have no historical series to replay. So a backtested level reflects ONLY the
market-driven component of a story - it is a partial, lower-bound validation of the
engine's mechanics, NOT a claim that the tracker would have "called" these episodes.
"""
import argparse, datetime, json, os, sys
import yaml

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
import score, fetch  # noqa: E402

VERSION = "1.0"

# Indicators varied in the baked sample (documented, regime-independent mappings).
PERTURBED = ["vix", "move", "move_ccp", "sofr_effr_spread", "hy_oas", "ig_oas",
             "oil_price", "copper_price", "unrate", "dxy", "real10"]

# Documented monthly readings (approximate published values) for two episodes.
# Sources: CBOE VIX, ICE BofA OAS series (FRED BAMLH0A0HYM2 / BAMLC0A0CM),
# ICE BofAML MOVE, EIA/WTI, COMEX copper, BLS UNRATE, Fed broad USD index, DFII10.
SAMPLE = {
  "COVID crash (2020)": {
    "note": "Funding stress + volatility spike. Clearinghouses, the basis trade, "
            "credit and the unemployment-linked consumer story respond hard.",
    "points": [
      ("2020-01-31", dict(vix=13, move=58, move_ccp=58, sofr_effr_spread=0.02, hy_oas=3.6, ig_oas=1.0, oil_price=57, copper_price=2.80, unrate=3.6, dxy=118, real10=0.1)),
      ("2020-02-29", dict(vix=40, move=78, move_ccp=78, sofr_effr_spread=0.03, hy_oas=5.0, ig_oas=1.3, oil_price=50, copper_price=2.60, unrate=3.5, dxy=119, real10=0.0)),
      ("2020-03-31", dict(vix=54, move=150, move_ccp=150, sofr_effr_spread=0.15, hy_oas=9.0, ig_oas=3.0, oil_price=30, copper_price=2.20, unrate=4.4, dxy=127, real10=-0.2)),
      ("2020-04-30", dict(vix=34, move=70, move_ccp=70, sofr_effr_spread=0.05, hy_oas=8.0, ig_oas=2.5, oil_price=17, copper_price=2.35, unrate=14.8, dxy=126, real10=-0.4)),
      ("2020-05-31", dict(vix=28, move=60, move_ccp=60, sofr_effr_spread=0.01, hy_oas=6.5, ig_oas=2.0, oil_price=35, copper_price=2.45, unrate=13.3, dxy=125, real10=-0.5)),
      ("2020-06-30", dict(vix=30, move=55, move_ccp=55, sofr_effr_spread=0.01, hy_oas=6.4, ig_oas=1.6, oil_price=39, copper_price=2.70, unrate=11.1, dxy=123, real10=-0.6)),
    ],
  },
  "Rate & inflation shock (2022)": {
    "note": "Rates volatility (MOVE) elevated all year, peaking with the Oct-2022 "
            "UK gilt/LDI crisis; oil and the strong dollar add stress.",
    "points": [
      ("2022-01-31", dict(vix=24, move=80, move_ccp=80, sofr_effr_spread=0.0, hy_oas=3.3, ig_oas=1.0, oil_price=88, copper_price=4.40, unrate=4.0, dxy=116, real10=-0.6)),
      ("2022-03-31", dict(vix=30, move=120, move_ccp=120, sofr_effr_spread=0.0, hy_oas=3.4, ig_oas=1.3, oil_price=108, copper_price=4.70, unrate=3.6, dxy=118, real10=-0.5)),
      ("2022-06-30", dict(vix=34, move=136, move_ccp=136, sofr_effr_spread=0.0, hy_oas=5.7, ig_oas=1.6, oil_price=106, copper_price=3.70, unrate=3.6, dxy=121, real10=0.65)),
      ("2022-09-30", dict(vix=32, move=148, move_ccp=148, sofr_effr_spread=0.0, hy_oas=5.5, ig_oas=1.6, oil_price=79, copper_price=3.40, unrate=3.5, dxy=128, real10=1.0)),
      ("2022-10-31", dict(vix=26, move=157, move_ccp=157, sofr_effr_spread=0.0, hy_oas=4.9, ig_oas=1.5, oil_price=87, copper_price=3.50, unrate=3.7, dxy=126, real10=1.5)),
      ("2022-12-31", dict(vix=22, move=120, move_ccp=120, sofr_effr_spread=0.0, hy_oas=4.7, ig_oas=1.3, oil_price=80, copper_price=3.80, unrate=3.5, dxy=121, real10=1.5)),
    ],
  },
}

SCOPE = ("Replays documented historical values of the market/data indicators through "
         "the live scoring engine. Judgment indicators are held at baseline (they have "
         "no historical series), so these levels reflect ONLY the market-driven component "
         "of each story - a partial validation of the engine's mechanics, not a claim the "
         "tracker would have predicted these events.")


def _replay(config, points):
    dates, overall, stories = [], [], {}
    for d, vals in points:
        res = score.score_all(config, dict(vals))
        dates.append(d)
        overall.append(res["aggregates"]["overall"])
        for s in res["stories"]:
            stories.setdefault(s["id"], {"name": s["name"], "set": s["set"], "levels": []})
            stories[s["id"]]["levels"].append(s["level"])
    return {"dates": dates, "overall": overall, "stories": stories}


def run_sample(config):
    episodes = {}
    for name, ep in SAMPLE.items():
        r = _replay(config, ep["points"])
        r["note"] = ep["note"]
        episodes[name] = r
    return {"generated": datetime.datetime.now(datetime.timezone.utc).isoformat(), "version": VERSION,
            "mode": "sample", "scope": SCOPE, "perturbed": PERTURBED, "episodes": episodes}


# ---- live mode (pulls real history from the configured feeds) ----
def _series_for(source):
    """Return {date: value} history for a fred/market source (None for manual)."""
    try:
        if source.startswith("fred_spread:"):
            _, a, b = source.split(":")
            sa, sb = dict(fetch.fred_series(a)), dict(fetch.fred_series(b))
            return {d: round(sa[d] - sb[d], 4) for d in (set(sa) & set(sb))}
        if source.startswith("fred:"):
            return dict(fetch.fred_series(source.split(":", 1)[1]))
        if source.startswith("market:"):
            return dict(fetch.market_series(source.split(":", 1)[1]))
    except Exception:
        return {}
    return {}


def _asof(series, date):
    keys = [k for k in series if k <= date]
    return series[max(keys)] if keys else None


def run_live(config, start, end, step_days=7):
    cache = {}
    for s in config["stories"]:
        for ind in s["indicators"]:
            if ind["source"] != "manual" and ind["id"] not in cache:
                cache[ind["id"]] = _series_for(ind["source"])
    d0 = datetime.date.fromisoformat(start)
    d1 = datetime.date.fromisoformat(end)
    points, day = [], d0
    while day <= d1:
        ds = day.isoformat()
        vals = {iid: _asof(ser, ds) for iid, ser in cache.items() if _asof(ser, ds) is not None}
        points.append((ds, vals))
        day += datetime.timedelta(days=step_days)
    r = _replay(config, points)
    r["note"] = f"Live replay {start} to {end} from configured feeds."
    perturbed = sorted(cache.keys())
    return {"generated": datetime.datetime.now(datetime.timezone.utc).isoformat(), "version": VERSION,
            "mode": "live", "scope": SCOPE, "perturbed": perturbed,
            "episodes": {f"Live {start[:4]}\u2013{end[:4]}": r}}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--live", action="store_true", help="pull real history and replay")
    ap.add_argument("--start", default="2019-06-01")
    ap.add_argument("--end", default=datetime.date.today().isoformat())
    ap.add_argument("--step", type=int, default=7)
    args = ap.parse_args()

    with open(os.path.join(ROOT, "config", "stories.yaml")) as f:
        config = yaml.safe_load(f)

    out = run_live(config, args.start, args.end, args.step) if args.live else run_sample(config)
    for p in (os.path.join(ROOT, "data", "backtest.json"),
              os.path.join(ROOT, "dashboard", "backtest.json")):
        os.makedirs(os.path.dirname(p), exist_ok=True)
        with open(p, "w") as f:
            json.dump(out, f, indent=2)
    eps = out["episodes"]
    print(f"Backtest ({out['mode']}) written: {len(eps)} episode(s).")
    for name, ep in eps.items():
        peak = max(ep["overall"]) if ep["overall"] else "-"
        print(f"  {name}: {len(ep['dates'])} points, overall peak {peak}/10")


if __name__ == "__main__":
    main()
