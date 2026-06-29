"""Phase 1 enrichments: per-story trend + sparkline, indicator provenance,
and a data-health summary. All read-only/derived; no scoring logic here."""
import csv, os, datetime
import score


def load_history(path):
    """Return ({story_id: [(date, level), ...]}, {date: method_version}) ascending."""
    series, versions = {}, {}
    if not os.path.exists(path):
        return series, versions
    with open(path) as f:
        for row in csv.DictReader(f):
            try:
                lvl = int(float(row["level"]))
            except (ValueError, KeyError):
                continue
            series.setdefault(row["story_id"], []).append((row["date"], lvl))
            # rows written before versioning have no column -> "1.x" (pre-stamp)
            versions[row["date"]] = (row.get("method_version") or "1.x")
    for k in series:
        series[k].sort(key=lambda x: x[0])
    return series, versions


def _on_or_before(hist, cutoff):
    chosen = None
    for d, l in hist:
        if d <= cutoff:
            chosen = (d, l)
        else:
            break
    return chosen


def attach_trends(result, history_path, today_date, window_days=7, spark_n=16):
    """Add story['trend'] (vs ~window_days ago) and story['spark'] (recent levels).
    Reads history BEFORE today's row is appended, so it compares to prior runs."""
    hist, versions = load_history(history_path)
    today = datetime.date.fromisoformat(today_date)
    cutoff = (today - datetime.timedelta(days=window_days)).isoformat()
    for s in result["stories"]:
        h = hist.get(s["id"], [])
        spark = ([l for _, l in h] + [s["level"]])[-spark_n:]
        s["spark"] = spark
        ref = _on_or_before(h, cutoff) or (h[0] if h else None)
        s["trend"] = ({"prev": ref[1], "since": ref[0], "change": s["level"] - ref[1]}
                      if ref else None)

    # overall aggregate trend: recompute each past date's overall with the CURRENT
    # aggregator (history stores per-story levels), so the series is self-consistent.
    bydate = {}
    for h in hist.values():
        for d, l in h:
            bydate.setdefault(d, []).append(l)
    overall_series = sorted((d, score.aggregate_overall(v)["overall"]) for d, v in bydate.items())
    refagg = None
    for d, a in overall_series:
        if d <= cutoff:
            refagg = (d, a)
    if refagg is None and overall_series:
        refagg = overall_series[0]
    if refagg:
        cur_ver = getattr(score, "METHODOLOGY_VERSION", "1.0")
        ref_ver = versions.get(refagg[0], "1.x")
        result["aggregates_trend"] = {
            "overall": {"prev": round(refagg[1], 1), "since": refagg[0],
                        "change": round(result["aggregates"]["overall"] - refagg[1], 1),
                        "crosses_methodology": ref_ver != cur_ver,
                        "ref_version": ref_ver, "version": cur_ver}}
    return result


def source_url(source):
    if source.startswith("fred_spread:"):
        return f"https://fred.stlouisfed.org/series/{source.split(':')[1]}"
    if source.startswith("fred:"):
        return f"https://fred.stlouisfed.org/series/{source.split(':', 1)[1]}"
    if source.startswith("market:"):
        return f"https://finance.yahoo.com/quote/{source.split(':', 1)[1]}"
    return ""


def source_kind(source):
    if source.startswith("fred"):
        return "FRED"
    if source.startswith("market:"):
        return "Market"
    return "Agent/manual"


def attach_provenance(result, agent_log, fetched, today_date):
    """Add as_of + source_url + provenance kind to every indicator."""
    assess = (agent_log or {}).get("assessments", {})
    fetched = fetched or {}
    for s in result["stories"]:
        for ind in s["indicators"]:
            src, iid = ind["source"], ind["id"]
            url, as_of, kind = source_url(src), "", source_kind(src)
            dv = fetched.get(iid)
            if dv and dv.get("value") is not None:
                as_of = dv.get("as_of") or today_date
            a = assess.get(iid)
            if a and src == "manual":
                kind = "Agent"
                if a.get("sources"):
                    url = a["sources"][0]
                as_of = a.get("as_of") or as_of
            if ind.get("stale") and not as_of:
                kind = "Baseline"
            ind["source_url"], ind["as_of"], ind["provenance"] = url, as_of, kind
    return result


def data_health(config, fetched, agent_log, today_date, offline):
    auto_total = sum(1 for s in config["stories"] for ind in s["indicators"]
                     if ind["source"] != "manual")
    if offline:
        live_ok, fell = 0, auto_total
    else:
        live_ok = sum(1 for dv in (fetched or {}).values() if dv.get("value") is not None)
        fell = auto_total - live_ok
    ag, days, flags = None, None, 0
    if agent_log and agent_log.get("generated"):
        try:
            ag = agent_log["generated"][:10]
            days = (datetime.date.fromisoformat(today_date) - datetime.date.fromisoformat(ag)).days
            flags = len(agent_log.get("review_flags", []))
        except Exception:
            pass
    return {"live_ok": live_ok, "live_total": auto_total, "fell_back": fell,
            "agent_last": ag, "agent_days_ago": days, "agent_flags": flags,
            "offline": bool(offline)}
