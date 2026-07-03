"""Fetch latest indicator values. Stdlib only (urllib). Keyless sources.

- fred:CODE          -> https://fred.stlouisfed.org/graph/fredgraph.csv?id=CODE (no key)
- fred_spread:A:B    -> latest(A) - latest(B), aligned on the last common date
- market:SYMBOL      -> Yahoo chart API (no key); e.g. ^MOVE, JPY=X, CNY=X, GC=F
- manual             -> not fetched here (see manual_input.csv)

Any failure returns None so the scorer falls back to the baseline/last value.
Be a polite citizen: short timeouts, no hammering.
"""
import csv, io, json, os, re, time, urllib.request, urllib.error, urllib.parse

UA = {"User-Agent": "Mozilla/5.0 (compatible; macro-risk-tracker/1.0)"}
TIMEOUT = 25


def _get(url):
    last = None
    for attempt in range(3):
        try:
            req = urllib.request.Request(url, headers=UA)
            with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
                return r.read().decode("utf-8", "replace")
        except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError) as e:
            last = e
            time.sleep(1.5 * (attempt + 1))
    raise last if last else RuntimeError("fetch failed")


def fred_series(code):
    """Return list of (date, value) ascending, skipping missing rows.

    Uses the official FRED API when FRED_API_KEY is set (more reliable from
    datacenter IPs like GitHub Actions), otherwise the keyless CSV endpoint.
    """
    key = os.environ.get("FRED_API_KEY")
    if key:
        url = (f"https://api.stlouisfed.org/fred/series/observations?series_id={code}"
               f"&api_key={key}&file_type=json&sort_order=asc")
        try:
            obs = json.loads(_get(url)).get("observations", [])
            rows = []
            for o in obs:
                raw = (o.get("value") or "").strip()
                if raw in (".", ""):
                    continue
                try:
                    rows.append((o.get("date"), float(raw)))
                except ValueError:
                    pass
            if rows:
                return rows
        except Exception:
            pass  # fall through to the keyless CSV endpoint
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


# ---- Japan MOF: official daily JGB constant-maturity yields (keyless CSV) ----
# The CSV uses Japanese era dates (e.g. "R7.6.24" = Reiwa 7 = 2025... era base: R1=2019,
# H1=1989, S1=1926) and "-" for holidays/gaps. We take the last row with a numeric value
# in the requested maturity column.
MOF_JGB_URLS = [
    "https://www.mof.go.jp/english/policy/jgbs/reference/interest_rate/jgbcme.csv",
    "https://www.mof.go.jp/jgbs/reference/interest_rate/jgbcm.csv",
]


def _era_to_iso(datestr):
    m = (datestr or "").strip()
    w = re.match(r"^(\d{4})[./-](\d{1,2})[./-](\d{1,2})$", m)
    if w:  # already a western date -> normalize to ISO
        return f"{int(w.group(1))}-{int(w.group(2)):02d}-{int(w.group(3)):02d}"
    base = {"R": 2018, "H": 1988, "S": 1925}.get(m[:1].upper())
    if not base:
        return m  # unknown format; pass through
    try:
        era_y, mo, dy = m[1:].split(".")
        return f"{base + int(era_y)}-{int(mo):02d}-{int(dy):02d}"
    except Exception:
        return m


def mof_jgb_latest(maturity="30"):
    """(value, iso_date) for the latest official JGB constant-maturity yield."""
    last_err = None
    for url in MOF_JGB_URLS:
        try:
            text = _get(url)
        except Exception as e:
            last_err = e
            continue
        rows = list(csv.reader(io.StringIO(text)))
        # find the header row containing the maturity labels (e.g. "30Y" or "30")
        col = None
        for r in rows[:6]:
            for j, cell in enumerate(r):
                c = cell.strip().upper().replace("YEAR", "Y").replace(" ", "")
                if c in (f"{maturity}Y", maturity):
                    col = j
                    break
            if col is not None:
                break
        if col is None:
            continue
        for r in reversed(rows):
            if len(r) > col:
                cell = r[col].strip()
                try:
                    return (round(float(cell), 3), _era_to_iso(r[0]))
                except ValueError:
                    continue
    if last_err:
        raise last_err
    raise ValueError("MOF JGB: maturity column not found")


# ---- DefiLlama: free stablecoin aggregates (keyless JSON) ----
# One HTTP call serves both indicators (total supply + largest-coin peg deviation),
# cached per process/run.
LLAMA_STABLES_URL = "https://stablecoins.llama.fi/stablecoins?includePrices=true"
_llama_cache = {}


def _llama_stables():
    if "data" not in _llama_cache:
        _llama_cache["data"] = json.loads(_get(LLAMA_STABLES_URL))
    return _llama_cache["data"]


def _usd_circ(asset):
    c = asset.get("circulating") or {}
    v = c.get("peggedUSD")
    return float(v) if isinstance(v, (int, float)) else 0.0


def llama_stablecoin_total_bn():
    """Total circulating USD-pegged stablecoin supply, in $bn."""
    assets = _llama_stables().get("peggedAssets", [])
    total = sum(_usd_circ(a) for a in assets if a.get("pegType") == "peggedUSD")
    return round(total / 1e9, 1) if total > 0 else None


def llama_largest_peg_dev_pct():
    """Absolute peg deviation (%) of the LARGEST USD stablecoin (usually USDT)."""
    assets = [a for a in _llama_stables().get("peggedAssets", [])
              if a.get("pegType") == "peggedUSD"]
    if not assets:
        return None
    big = max(assets, key=_usd_circ)
    price = big.get("price")
    if not isinstance(price, (int, float)) or price <= 0:
        return None
    return round(abs(price - 1.0) * 100, 2)


def fetch_value(source):
    try:
        if source.startswith("fred_spread:"):
            _, a, b = source.split(":")
            return fred_spread(a, b)
        if source.startswith("fred:"):
            return fred_latest(source.split(":", 1)[1])
        if source.startswith("market:"):
            return market_latest(source.split(":", 1)[1])
        if source.startswith("mof_jgb:"):
            return mof_jgb_latest(source.split(":", 1)[1])[0]
        if source == "llama:stablecoin_total_bn":
            return llama_stablecoin_total_bn()
        if source == "llama:largest_peg_dev":
            return llama_largest_peg_dev_pct()
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


def fred_latest_dated(code):
    s = fred_series(code)
    return (s[-1][1], s[-1][0]) if s else (None, None)


def fred_spread_dated(a, b):
    sa, sb = dict(fred_series(a)), dict(fred_series(b))
    common = sorted(set(sa) & set(sb))
    if not common:
        return (None, None)
    d = common[-1]
    return (round(sa[d] - sb[d], 4), d)


def market_latest_dated(symbol):
    import datetime as _dt
    url = (f"https://query1.finance.yahoo.com/v8/finance/chart/{urllib.parse.quote(symbol)}"
           f"?range=5d&interval=1d")
    data = json.loads(_get(url))
    res = data["chart"]["result"][0]
    ts = res.get("timestamp") or []
    closes = res["indicators"]["quote"][0]["close"]
    for i in range(len(closes) - 1, -1, -1):
        if closes[i] is not None:
            d = (_dt.datetime.utcfromtimestamp(ts[i]).date().isoformat()
                 if i < len(ts) else None)
            return (round(closes[i], 4), d)
    return (res["meta"].get("regularMarketPrice"), None)


def market_series(symbol, rng="10y"):
    """Return [(date, close)] daily history from Yahoo (ascending)."""
    import datetime as _dt
    url = (f"https://query1.finance.yahoo.com/v8/finance/chart/{urllib.parse.quote(symbol)}"
           f"?range={rng}&interval=1d")
    data = json.loads(_get(url))
    res = data["chart"]["result"][0]
    ts = res.get("timestamp") or []
    closes = res["indicators"]["quote"][0]["close"]
    out = []
    for t, c in zip(ts, closes):
        if c is not None:
            out.append((_dt.datetime.utcfromtimestamp(t).date().isoformat(), round(c, 4)))
    return out


def fetch_value_dated(source):
    """Like fetch_value but returns (value, as_of_date)."""
    import datetime as _dt
    try:
        if source.startswith("fred_spread:"):
            _, a, b = source.split(":")
            return fred_spread_dated(a, b)
        if source.startswith("fred:"):
            return fred_latest_dated(source.split(":", 1)[1])
        if source.startswith("market:"):
            return market_latest_dated(source.split(":", 1)[1])
        if source.startswith("mof_jgb:"):
            return mof_jgb_latest(source.split(":", 1)[1])
        if source == "llama:stablecoin_total_bn":
            return (llama_stablecoin_total_bn(), _dt.date.today().isoformat())
        if source == "llama:largest_peg_dev":
            return (llama_largest_peg_dev_pct(), _dt.date.today().isoformat())
    except Exception:
        return (None, None)
    return (None, None)


def fetch_all_dated(config):
    """Returns {indicator_id: {'value': v, 'as_of': date}} for all auto sources."""
    out = {}
    for s in config["stories"]:
        for ind in s["indicators"]:
            src = ind["source"]
            if src == "manual":
                continue
            v, d = fetch_value_dated(src)
            out[ind["id"]] = {"value": v, "as_of": d}
    return out
