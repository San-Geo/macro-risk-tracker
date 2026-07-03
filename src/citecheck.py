"""Deterministic citation checker - no AI involved.

For every APPLIED agent assessment that cites sources, fetch the cited page(s) with a
plain HTTP GET and check whether the applied number (or a distinctive figure from the
FACT text) literally appears there. Three honest verdicts:

  verified    - a key number was found verbatim at a cited URL
  not_found   - page(s) fetched fine, but no key number matched (could be a paywall
                summary, a JS-rendered page, or a PDF - OR a misquoted fact; worth a click)
  unreachable - none of the cited URLs could be fetched (link rot, 403, timeout)

This converts "trust the agent's citation" into "checked against the page". It is a
*confirmation* signal, not a fabrication detector: not_found is a prompt to look, never
proof of error. Zero API cost; stdlib only.
"""
import concurrent.futures as cf
import json
import os
import re
import urllib.request

UA = {"User-Agent": "Mozilla/5.0 (compatible; macro-risk-tracker-citecheck/1.0)"}
TIMEOUT = 12
MAX_URLS_PER_IND = 2
MAX_WORKERS = 8

_YEAR = re.compile(r"^(19|20)\d{2}$")


def _fetch(url):
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
        raw = r.read(1_500_000)  # cap: 1.5MB is plenty for a page of text
    return raw.decode("utf-8", errors="ignore")


def _text(html):
    """Crude but effective: drop script/style, strip tags, collapse whitespace."""
    html = re.sub(r"(?is)<(script|style)[^>]*>.*?</\1>", " ", html)
    txt = re.sub(r"(?s)<[^>]+>", " ", html)
    return re.sub(r"\s+", " ", txt)


def _num_variants(tok):
    """Comma/precision variants of one numeric token: '6.80' also matches '6.8';
    '1450' also matches '1,450'."""
    out = {tok}
    if "." in tok:
        out.add(tok.rstrip("0").rstrip("."))          # 6.80 -> 6.8
    if re.fullmatch(r"\d{4,}", tok):
        out.add(f"{int(tok):,}")                       # 1450 -> 1,450
    out.discard("")
    return out


def _candidates(a):
    """Distinctive numeric tokens to look for: the applied value first (for value-type
    reads), then figures quoted in the FACT. Years and tiny integers are excluded -
    they match everything and verify nothing."""
    cands = []
    v = a.get("value")
    if isinstance(v, (int, float)) and v not in (0, 1, 2):  # bands are unverifiable as numbers
        s = f"{v:g}"
        cands.append(s)
        if isinstance(v, float) and v == int(v):
            cands.append(str(int(v)))
    for tok in re.findall(r"\d{1,3}(?:,\d{3})+(?:\.\d+)?|\d+\.\d+|\d{4,}", a.get("fact", "") or ""):
        plain = tok.replace(",", "")
        if _YEAR.fullmatch(plain):
            continue
        cands.append(plain)
    seen, out = set(), []
    for c in cands:
        if c not in seen:
            seen.add(c)
            out.append(c)
    return out[:6]


def _check_one(a):
    urls = [u for u in (a.get("sources") or []) if str(u).startswith("http")][:MAX_URLS_PER_IND]
    cands = _candidates(a)
    if not urls or not cands:
        return {"verdict": "skipped"}
    reached = False
    for url in urls:
        try:
            page = _fetch(url)
        except Exception:
            continue
        reached = True
        hay = _text(page) + " " + page  # match in visible text OR raw markup
        for c in cands:
            for variant in _num_variants(c):
                if variant in hay:
                    return {"verdict": "verified", "url": url, "matched": variant}
    return {"verdict": "not_found" if reached else "unreachable", "url": urls[0]}


def run_citecheck(log, max_workers=MAX_WORKERS):
    """Mutates log['assessments'][*]['citecheck']. Never raises."""
    todo = {iid: a for iid, a in (log.get("assessments") or {}).items()
            if a.get("applied") and a.get("sources")}
    if not todo:
        return log
    try:
        with cf.ThreadPoolExecutor(max_workers=max_workers) as ex:
            futs = {ex.submit(_check_one, a): iid for iid, a in todo.items()}
            for fut in cf.as_completed(futs, timeout=180):
                iid = futs[fut]
                try:
                    log["assessments"][iid]["citecheck"] = fut.result()
                except Exception:
                    log["assessments"][iid]["citecheck"] = {"verdict": "unreachable"}
    except Exception:
        pass  # a stuck pool must never break the run; partial results stand
    return log


if __name__ == "__main__":
    HERE = os.path.dirname(os.path.abspath(__file__))
    path = os.path.join(os.path.dirname(HERE), "data", "agent_assessments.json")
    with open(path) as f:
        log = json.load(f)
    run_citecheck(log)
    with open(path, "w") as f:
        json.dump(log, f, indent=2)
    counts = {}
    for a in log["assessments"].values():
        v = (a.get("citecheck") or {}).get("verdict", "-")
        counts[v] = counts.get(v, 0) + 1
    print("citecheck:", counts)
