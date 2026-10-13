"""IMF PortWatch strait traffic -> measured chokepoint ratings.

MEASUREMENT BEATS JUDGMENT WHERE A MEASUREMENT EXISTS. The agent kept flipping the
Hormuz rating between "closed" and "contested" on the same facts while traffic sat
at 1-11% of normal. This module reads the IMF's daily AIS transit counts, compares
the latest 7-day average with the same month's normal, and sets the rating by rule
(config/portwatch.yaml). The agent is still used for the one thing a ship count
cannot tell you - whether there were attacks - when traffic is above 80% of normal,
and as the fallback whenever the feed is unavailable or stale.

Stdlib only. Never raises: any failure returns {} and the board uses the agent's
rating exactly as before.

    python src/portwatch.py          # print the current readings (for checking)
"""
import datetime
import json
import os
import sys
import time
import urllib.parse

import yaml

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
import fetch  # noqa: E402  (reuses its polite _get with retries/timeouts)

CFG_PATH = os.path.join(ROOT, "config", "portwatch.yaml")
CACHE_PATH = os.path.join(ROOT, "data", "portwatch_baseline.json")


def load_cfg():
    with open(CFG_PATH) as f:
        return yaml.safe_load(f)


def _query(cfg, params, tries=3):
    """One ArcGIS query. The service shares a per-minute quota across all its users,
    so a quota error waits and retries rather than failing the run."""
    url = cfg["service"] + "?" + urllib.parse.urlencode({**params, "f": "json"})
    last = None
    for i in range(tries):
        try:
            data = json.loads(fetch._get(url))
        except Exception as e:
            last = e
            time.sleep(5 * (i + 1))
            continue
        if "error" in data:
            last = RuntimeError(str(data["error"].get("message") or data["error"])[:200])
            time.sleep(25 * (i + 1))  # quota resets each minute
            continue
        return data.get("features") or []
    raise last or RuntimeError("PortWatch query failed")


def _date(v):
    """DateOnly fields come back as 'YYYY-MM-DD'; tolerate epoch milliseconds too."""
    if isinstance(v, (int, float)):
        return datetime.datetime.fromtimestamp(v / 1000, datetime.timezone.utc).date()
    return datetime.date.fromisoformat(str(v)[:10])


def recent(cfg, portid, n=14):
    feats = _query(cfg, {"where": f"portid='{portid}'", "outFields": "date,n_total",
                         "orderByFields": "date DESC", "resultRecordCount": n,
                         "returnGeometry": "false"})
    rows = []
    for f in feats:
        a = f.get("attributes") or {}
        if a.get("date") is not None and a.get("n_total") is not None:
            rows.append((_date(a["date"]), int(a["n_total"])))
    return sorted(rows, reverse=True)


def _baseline_years(cp, month):
    years = list(cp.get("baseline_years") or [])
    last = cp.get("baseline_last_month")
    if last:
        ly, lm = (int(x) for x in str(last).split("-"))
        years = [y for y in years if (y, month) <= (ly, lm)]
    return years


def baseline(cfg, cp, month, cache):
    """Average daily transits for this calendar month in the chokepoint's normal years.
    Historical, so cached forever in data/portwatch_baseline.json (one query per month)."""
    key = f"{cp['portid']}:{month}:{','.join(map(str, _baseline_years(cp, month)))}"
    if key in cache:
        return cache[key]
    years = _baseline_years(cp, month)
    if not years:
        return None
    feats = _query(cfg, {
        "where": f"portid='{cp['portid']}' AND month={month} AND year IN ({','.join(map(str, years))})",
        "outStatistics": json.dumps([{"statisticType": "avg", "onStatisticField": "n_total",
                                      "outStatisticFieldName": "avg_total"}]),
    })
    val = None
    if feats:
        a = feats[0].get("attributes") or {}
        val = a.get("avg_total", a.get("AVG_TOTAL"))
    if val is not None:
        cache[key] = round(float(val), 2)
    return cache.get(key)


def read(today, cfg=None):
    """Measured readings per chokepoint. Never raises; a failed strait is omitted."""
    cfg = cfg or load_cfg()
    if not cfg.get("enabled", True):
        return {}
    try:
        with open(CACHE_PATH) as f:
            cache = json.load(f)
    except Exception:
        cache = {}
    today = datetime.date.fromisoformat(str(today)[:10])
    out = {}
    for key, cp in cfg["chokepoints"].items():
        try:
            rows = recent(cfg, cp["portid"])
            if not rows:
                raise RuntimeError("no rows returned")
            latest = rows[0][0]
            age = (today - latest).days
            win = [n for d, n in rows if (latest - d).days < int(cfg.get("window_days", 7))]
            if age > int(cfg.get("max_age_days", 21)):
                raise RuntimeError(f"newest data is {age} days old")
            if len(win) < int(cfg.get("min_days", 5)):
                raise RuntimeError(f"only {len(win)} days in the last week")
            avg7 = sum(win) / len(win)
            base = baseline(cfg, cp, latest.month, cache)
            if base is None or base < float(cfg.get("min_baseline", 20)):
                raise RuntimeError(f"no usable normal for month {latest.month}")
            out[key] = {"name": cp["name"], "avg7": round(avg7, 1), "baseline": base,
                        "ratio": round(avg7 / base, 3), "as_of": latest.isoformat(),
                        "days": len(win)}
        except Exception as e:
            out[key] = {"name": cp["name"], "error": str(e)[:200]}
    try:
        os.makedirs(os.path.dirname(CACHE_PATH), exist_ok=True)
        with open(CACHE_PATH, "w") as f:
            json.dump(cache, f, indent=1, sort_keys=True)
    except Exception:
        pass
    return out


def _band(ratio, cfg):
    if ratio < float(cfg.get("closed_below", 0.25)):
        return 2
    if ratio <= float(cfg.get("normal_above", 0.80)):
        return 1
    return None  # traffic near normal: the agent judges attacks (0 or 1)


def apply(values, readings, pinned, cfg=None):
    """Set the chokepoint indicators from the measurement. Returns {indicator: detail}.

    Per indicator, every listed chokepoint gives 2 (<25% of normal), 1 (25-80%) or
    'agent decides' (>80%). The WORSE reading wins. If all listed straits are near
    normal, the agent's rating stands but is capped at 1 (the measurement rules out
    a closure). If a strait could not be measured, the agent's rating is kept unless
    the measured ones already show stress."""
    cfg = cfg or load_cfg()
    applied = {}
    for ind, keys in (cfg.get("rules") or {}).items():
        if ind in pinned:
            continue
        got = {k: readings[k] for k in keys if k in readings and "ratio" in readings[k]}
        if not got:
            continue
        bands = [_band(r["ratio"], cfg) for r in got.values()]
        agent_v = values.get(ind)
        if any(b == 2 for b in bands):
            new = 2
        elif any(b == 1 for b in bands):
            new = 1
        elif len(got) == len(keys):
            new = min(agent_v, 1) if agent_v is not None else None
        else:
            new = None
        if new is None:
            continue
        values[ind] = new
        applied[ind] = {"value": new, "agent_value": agent_v,
                        "as_of": min(r["as_of"] for r in got.values()),
                        "readings": {k: {kk: got[k][kk] for kk in ("name", "avg7", "baseline", "ratio", "as_of")}
                                     for k in got},
                        "note": "; ".join(f"{r['name']} {r['avg7']:g} ships/day vs {r['baseline']:g} normal "
                                          f"({r['ratio'] * 100:.0f}%)" for r in got.values())}
    return applied


if __name__ == "__main__":
    r = read(datetime.date.today())
    print(json.dumps(r, indent=1))
