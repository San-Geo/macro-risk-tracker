"""Fetch latest indicator values. Stdlib only (urllib). Keyless sources.

- fred:CODE          -> https://fred.stlouisfed.org/graph/fredgraph.csv?id=CODE (no key)
- fred_spread:A:B    -> latest(A) - latest(B), aligned on the last common date
- market:SYMBOL      -> Yahoo chart API (no key); e.g. ^MOVE, JPY=X, CNY=X, GC=F
- manual             -> not fetched here (see manual_input.csv)

Any failure returns None so the scorer falls back to the baseline/last value.
Be a polite citizen: short timeouts, no hammering.
"""
import csv, io, json, urllib.request, urllib.error

UA = {"User-Agent": "macro-risk-tracker/1.0 (personal use)"}
TIMEOUT = 15


def _get(url):
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
        return r.read().decode("utf-8", "replace")


def fred_series(code):
    """Return list of (date, value) ascending, skipping '.' missing rows."""
    url = f"https://fred.stlouisfed.org/graph/fredgraph.csv?id={code}"
    rows = []
    for row in csv.reader(io.StringIO(_get(url))):
        if not row or row[0].lower() in ("date", "observation_date"):
            continue
        d, raw = row[0], row[-1].strip()
        if raw in (".", ""):
            continue
        try:
            rows.append((d, float(raw)))
        except ValueError:
            pass
    return rows


def fred_latest(code):
    s = fred_series(code)
    return s[-1][1] if s else None


def fred_spread(a, b):
    sa, sb = dict(fred_series(a)), dict(fred_series(b))
    common = sorted(set(sa) & set(sb))
    if not common:
        return None
    d = common[-1]
    return round(sa[d] - sb[d], 4)


def market_latest(symbol):
    url = (f"https://query1.finance.yahoo.com/v8/finance/chart/{urllib.parse.quote(symbol)}"
           f"?range=5d&interval=1d")
    data = json.loads(_get(url))
    res = data["chart"]["result"][0]
    closes = [c for c in res["indicators"]["quote"][0]["close"] if c is not None]
    if closes:
        return round(closes[-1], 4)
    return res["meta"].get("regularMarketPrice")


def fetch_value(source):
    try:
        if source.startswith("fred_spread:"):
            _, a, b = source.split(":")
            return fred_spread(a, b)
        if source.startswith("fred:"):
            return fred_latest(source.split(":", 1)[1])
        if source.startswith("market:"):
            return market_latest(source.split(":", 1)[1])
    except (urllib.error.URLError, KeyError, ValueError, TimeoutError, Exception):
        return None
    return None  # manual or unknown


def fetch_all(config):
    """Returns {indicator_id: value or None} for all auto sources."""
    out = {}
    for s in config["stories"]:
        for ind in s["indicators"]:
            src = ind["source"]
            if src == "manual":
                continue
            out[ind["id"]] = fetch_value(src)
    return out
