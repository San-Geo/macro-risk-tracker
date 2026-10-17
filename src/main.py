#!/usr/bin/env python3
"""Global Macro Risk Tracker - daily run.

  python src/main.py                 # fetch live data + AI narrative (needs keys/network)
  python src/main.py --offline       # use baseline/manual values (no network) - try this first
  python src/main.py --no-ai         # skip the Claude narrative (templated summary instead)

Outputs:
  data/history.csv              append-only daily log
  data/latest.json              machine-readable snapshot
  dashboard/latest.json         same, served next to the webpage
  output/macro_risk_tracker.xlsx  formula-driven Excel model
"""
import argparse, csv, json, os, sys, datetime
import yaml

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
import score, fetch, narrative, report, agent, enrich, alerts, consistency  # noqa: E402


def fmt_v(v):
    try:
        f = float(v)
        return str(int(f)) if f.is_integer() else f"{f:g}"
    except (TypeError, ValueError):
        return str(v)


def _source_classes():
    try:
        with open(os.path.join(ROOT, "config", "sources.yaml")) as f:
            return yaml.safe_load(f) or {}
    except Exception:
        return {}


def source_class(url, classes):
    """'official' | 'data_providers' | 'press' | None for a source URL."""
    import urllib.parse
    try:
        host = urllib.parse.urlparse(str(url)).netloc.lower().split(":")[0]
    except Exception:
        return None
    host = host[4:] if host.startswith("www.") else host
    for cls in ("official", "data_providers", "press"):
        for d in classes.get(cls) or []:
            d = str(d).lower()
            if host == d or host.endswith("." + d):
                return cls
    return None


def evidence_grade(a, cadence, budget_days, today, classes):
    """Rule-based evidence grade (replaces trust in the model's own 'confidence' label,
    which research shows is overconfident and weakly informative):
      +1 an official, data-provider or major-press source is cited
      +1 the evidence is dated within the indicator's staleness budget
      +1 the citation checker found the number at its cited source
      +1 an independent second read agreed (where one was run)
    A = 3+, B = 2, C = 0-1."""
    pts, why = 0, []
    srcs = a.get("sources") or []
    if any(source_class(u, classes) for u in srcs):
        pts += 1; why.append("authoritative source")
    try:
        k = agent._as_of_key(a.get("as_of"))
        age = (datetime.date.fromisoformat(today) - datetime.date(*k)).days if k else None
    except Exception:
        age = None
    if age is not None and budget_days and age <= budget_days:
        pts += 1; why.append("recent evidence")
    if ((a.get("citecheck") or {}).get("verdict")) == "verified":
        pts += 1; why.append("number verified at source")
    if ((a.get("crosscheck") or {}).get("agree")) is True:
        pts += 1; why.append("second read agreed")
    return ("A" if pts >= 3 else "B" if pts == 2 else "C"), why


def load_config():
    with open(os.path.join(ROOT, "config", "stories.yaml")) as f:
        return yaml.safe_load(f)


def load_manual():
    path = os.path.join(ROOT, "manual_input.csv")
    vals = {}
    if os.path.exists(path):
        with open(path) as f:
            for row in csv.DictReader(f):
                v = (row.get("value") or "").strip()
                if v != "":
                    try:
                        vals[row["indicator_id"].strip()] = float(v)
                    except ValueError:
                        pass
    return vals


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--offline", action="store_true", help="skip network fetch")
    ap.add_argument("--no-ai", action="store_true", help="skip Claude narrative")
    ap.add_argument("--agent", action="store_true",
                    help="run the rating agent now (researches + rates judgment indicators)")
    ap.add_argument("--no-alert", action="store_true", help="don't send band-crossing alerts")
    ap.add_argument("--scout", action="store_true",
                    help="run the overnight-event scout (proposes new indicators/stories)")
    ap.add_argument("--test-alert", action="store_true", help="send a test alert and exit")
    ap.add_argument("--date", default=datetime.date.today().isoformat())
    args = ap.parse_args()

    if args.test_alert:
        print("Sending test alert ...")
        alerts.send_test(os.environ)
        return

    config = load_config()

    values = {}
    fetched = {}
    guard = {}
    if not args.offline:
        print("Fetching live indicators ...")
        fetched = fetch.fetch_all_dated(config)
        # Feed guard: a failed feed carries forward its last good value (not the June
        # starting value), and an implausible value is held until the next run confirms it.
        import feedguard
        guard = feedguard.check(fetched, args.date)
        for iid in guard.get("carried", []):
            print(f"::warning title=Feed carried forward::{iid} - feed failed; using last good value")
        for h in guard.get("held", []):
            print(f"::warning title=Feed value held::{h['id']} = {h['value']} ({h['reason']}); kept {h['last']}")
        values.update({k: dv["value"] for k, dv in fetched.items() if dv["value"] is not None})
        print(f"  got {len(values)} live market/data values")

    # Human overrides: any indicator filled in manual_input.csv is pinned and wins.
    manual = load_manual()
    overrides = set(manual.keys())

    # Agent: research + rate the judgment indicators per config/framework.yaml.
    key = os.environ.get("ANTHROPIC_API_KEY")
    if args.agent and key and not args.offline:
        print("Running rating agent (web-search grounded) ...")
        framework = agent.load_framework()
        agent_values, alog = agent.run_agent(framework, key, args.date, overrides=overrides)
        values.update(agent_values)
        flags = alog.get("review_flags", [])
        print(f"  agent rated {len(agent_values)} indicators; "
              f"{len(flags)} flagged for review: {', '.join(flags) if flags else 'none'}")
    else:
        # Not running the agent this time: reuse its last applied assessments.
        cached = agent.load_applied_values()
        if cached:
            values.update(cached)
            print(f"  reusing {len(cached)} cached agent ratings "
                  f"(run with --agent to refresh)")
        if args.agent and not key:
            print("  --agent requested but ANTHROPIC_API_KEY not set; using cached/baseline.")

    # Hybrid indicators (a slow official feed AND a weekly agent read, e.g. the France
    # spread): use whichever reading is newer; ties go to the official feed.
    hybrid_used = {}
    try:
        _alog = agent.load_log().get("assessments", {})
        for iid, dv in fetched.items():
            a = _alog.get(iid)
            if not a or not a.get("applied") or a.get("value") is None:
                continue
            fk, ak = agent._as_of_key(dv.get("as_of")), agent._as_of_key(a.get("as_of"))
            if dv.get("value") is not None and (not ak or (fk and fk >= ak)):
                values[iid] = dv["value"]          # official feed is as new or newer
            else:
                values[iid] = a["value"]
                hybrid_used[iid] = a
    except Exception as e:
        print(f"  (hybrid selection skipped: {e})")

    values.update(manual)  # human overrides always win

    # Measured strait traffic (IMF PortWatch) sets the chokepoint ratings by rule where
    # the measurement is decisive; the agent's read stands where it is not. Human pins
    # still win. Any failure leaves the agent's ratings untouched.
    pw_readings, measured = {}, {}
    if not args.offline:
        try:
            import portwatch
            pw_readings = portwatch.read(args.date)
            measured = portwatch.apply(values, pw_readings, overrides)
            for r in pw_readings.values():
                print(f"  PortWatch {r['name']}: " + (f"{r['avg7']:g} ships/day vs {r['baseline']:g} normal "
                      f"({r['ratio'] * 100:.0f}%), data to {r['as_of']}" if "ratio" in r else f"unavailable ({r.get('error')})"))
            for ind, m in measured.items():
                print(f"  measured -> {ind} = {m['value']} (agent read {m['agent_value']})")
        except Exception as e:
            print(f"  (PortWatch skipped: {e})")

    # Deterministic citation check (no AI, plain HTTP): verify agent facts against
    # their cited URLs. Runs when the agent just ran, or once as backfill if the
    # stored log has never been checked. Zero API cost; failures never break the run.
    if not args.offline and os.environ.get("CITE_CHECK", "1") not in ("0", "false", "no"):
        try:
            import citecheck
            alog2 = agent.load_log()
            assessments = alog2.get("assessments") or {}
            unchecked = any(a.get("applied") and a.get("sources") and "citecheck" not in a
                            for a in assessments.values())
            if assessments and (args.agent or unchecked):
                print("Citation check: verifying agent facts against cited URLs ...")
                citecheck.run_citecheck(alog2)
                with open(agent.LOG_PATH, "w") as f:
                    json.dump(alog2, f, indent=2)
                counts = {}
                for a in assessments.values():
                    v = (a.get("citecheck") or {}).get("verdict")
                    if v:
                        counts[v] = counts.get(v, 0) + 1
                print(f"  citecheck: {counts}")
        except Exception as e:
            print(f"  (citation check skipped: {e})")

    result = score.score_all(config, values)
    result["date"] = args.date
    if pw_readings:
        result["measured"] = {"source": "IMF PortWatch", "url": "https://portwatch.imf.org",
                              "readings": pw_readings, "applied": measured}
    result["sets"] = config.get("sets", {})

    # Attach per-story background + full-brief link (from config/briefs.yaml).
    briefs_path = os.path.join(ROOT, "config", "briefs.yaml")
    if os.path.exists(briefs_path):
        try:
            with open(briefs_path) as f:
                briefs = yaml.safe_load(f) or {}
            set_pdf = briefs.get("set_pdf", {})
            orig = briefs.get("original_set", {})
            combined = briefs.get("combined_pdf")
            pages = briefs.get("pages", {})
            bmap = briefs.get("stories", {})
            for s in result["stories"]:
                b = bmap.get(s["id"], {})
                if b.get("summary"):
                    s["summary"] = b["summary"]
                if combined:
                    pg = pages.get(s["id"])
                    s["brief_url"] = f"{combined}#page={pg}" if pg else combined
                else:
                    osn = orig.get(s["id"])
                    s["brief_url"] = set_pdf.get(osn) or set_pdf.get(str(osn))
        except Exception as e:
            print(f"  (briefs.yaml skipped: {e})")
    # The CURRENT published edition (dashboard/briefs/editions/editions.json) wins over
    # briefs.yaml: once the owner publishes a new edition, every "full write-up" link,
    # the dashboard's edition link and the living brief switch to it.
    try:
        import edition as _edition
        _cur = _edition.current_edition()
        if _cur:
            _st = _edition.load_json(_edition.STATUS, {})
            result["edition"] = {
                "id": _cur["id"], "title": _cur.get("title"), "published": _cur.get("published"),
                "data_as_of": _cur.get("data_as_of"), "revision": _cur.get("revision"),
                "pdf": "briefs/" + _cur["pdf"] if _cur.get("pdf") else None,
                "html": "briefs/" + _cur["html"] if _cur.get("html") else None,
                "next": _st.get("summary"), "n_stories": len(_cur.get("levels") or {})}
            for s in result["stories"]:
                if _cur.get("html"):
                    s["brief_url"] = f"briefs/{_cur['html']}#{s['id']}"
                elif _cur.get("pdf") and (_cur.get("pages") or {}).get(s["id"]):
                    s["brief_url"] = f"briefs/{_cur['pdf']}#page={_cur['pages'][s['id']]}"
    except Exception as e:
        print(f"  (edition links skipped: {e})")

    # Attach the plain-language layer (config/plain.yaml) for the Plain/Expert toggle.
    plain_path = os.path.join(ROOT, "config", "plain.yaml")
    if os.path.exists(plain_path):
        try:
            with open(plain_path) as f:
                result["plain"] = yaml.safe_load(f) or {}
        except Exception as e:
            print(f"  (plain.yaml skipped: {e})")

    # Educational transmission map (config/playbook.yaml): mechanism-level cause and
    # effect, shown on the dashboard only while a story is at High. Ticker-free by rule.
    pb_path = os.path.join(ROOT, "config", "playbook.yaml")
    if os.path.exists(pb_path):
        try:
            with open(pb_path) as f:
                result["playbook"] = yaml.safe_load(f) or {}
        except Exception as e:
            print(f"  (playbook.yaml skipped: {e})")

    # Mainstream context dials (config/context.yaml): fetched for DISPLAY ONLY.
    # Deliberately kept outside the `values` dict - they can never touch the score.
    ctx_path = os.path.join(ROOT, "config", "context.yaml")
    if os.path.exists(ctx_path) and not args.offline:
        try:
            with open(ctx_path) as f:
                ctx = yaml.safe_load(f) or {}
            items = []
            for dl in ctx.get("dials", []):
                v, dt = fetch.fetch_value_dated(dl.get("source", ""))
                items.append({"id": dl.get("id"), "label": dl.get("label"),
                              "value": v, "as_of": dt, "unit": dl.get("unit", ""),
                              "note": dl.get("note", ""),
                              "url": enrich.source_url(dl.get("source", ""))})
            got = sum(1 for i in items if i["value"] is not None)
            result["context"] = {"intro": ctx.get("intro", ""), "items": items}
            print(f"  context dials: {got}/{len(items)} fetched (display-only)")
        except Exception as e:
            print(f"  (context dials skipped: {e})")

    # Attach the agent's latest assessments (this run or last cached) for the dashboard panel.
    alog = agent.load_log()
    if alog.get("assessments"):
        idmap = {}
        for s in config["stories"]:
            for ind in s.get("indicators", []):
                idmap[ind["id"]] = (ind.get("label", ind["id"]), s["name"], s["set"])
        flags = set(alog.get("review_flags", []))
        src_classes = _source_classes()
        cad_of = {i["id"]: i.get("cadence") for s_ in config["stories"] for i in s_["indicators"]}
        items = []
        for ind_id, a in alog["assessments"].items():
            lbl, story, setno = idmap.get(ind_id, (ind_id, "", 0))
            cc = a.get("crosscheck") or {}
            conf = str(a.get("confidence", "")).lower()
            # Triage tier - kept deliberately small so real items are not buried:
            #   ACT    = held / rejected / disagreed / failed -> needs a human decision
            #   GLANCE = the value moved this run, or the read is weakly evidenced
            #            (recovered from a broken response, or arrived with no sources)
            #   OK     = everything else. Source DISSENT alone no longer flags an item:
            #            it is still shown on the row (annotate, don't reconcile), but it
            #            was putting ~30 of 44 items in the queue every single week.
            why = []
            if cc.get("agree") is False: why.append("second read disagreed")
            if a.get("out_of_range"): why.append("out of plausible range")
            if a.get("vintage") == "rejected": why.append("older-data read rejected")
            if a.get("stale_guard") == "held": why.append("upgrade on old evidence held")
            if conf in ("low", "error"): why.append("low confidence / error - prior kept")
            prior_v, val = a.get("prior"), a.get("value")
            changed = prior_v is not None and val is not None and val != prior_v
            soft = []
            if changed: soft.append(f"changed {fmt_v(prior_v)} -> {fmt_v(val)}")
            if ind_id in measured and measured[ind_id]["value"] != val:
                soft.append(f"board uses the IMF PortWatch measurement ({fmt_v(measured[ind_id]['value'])}) "
                            f"instead of this read")
            if a.get("reversal_guard") == "held":
                soft.append(f"reversal to {fmt_v(a.get('pending'))} held - applied next week only if the next read confirms it")
            if a.get("parse") == "repaired": soft.append("recovered from a malformed reply")
            if not (a.get("sources") or []): soft.append("no sources")
            if changed and (a.get("sources") or []) and not any(source_class(u, src_classes) for u in a["sources"]):
                soft.append("change rests only on non-authoritative sources")
            ev_grade, ev_why = evidence_grade(a, cad_of.get(ind_id), enrich.STALENESS_BUDGET_DAYS.get(cad_of.get(ind_id)) or 90,
                                              args.date, src_classes)
            if why:
                tier = "act"
            elif soft:
                tier = "glance"
            else:
                tier = "ok"
            why += soft
            items.append({
                "id": ind_id, "label": lbl, "story": story, "set": setno,
                "value": a.get("value"), "confidence": a.get("confidence"),
                "applied": a.get("applied"), "note": a.get("note", ""),
                "rationale": a.get("rationale", ""), "sources": (a.get("sources") or [])[:3],
                "as_of": a.get("as_of", ""), "out_of_range": a.get("out_of_range", False),
                "fact": a.get("fact", ""), "dissent": (a.get("dissent") or [])[:4],
                "domain": a.get("domain", ""),
                "crosscheck": a.get("crosscheck"),
                "parse": a.get("parse"),
                "vintage": a.get("vintage"),
                "citecheck": a.get("citecheck"),
                "stale_guard": a.get("stale_guard"),
                "reversal_guard": a.get("reversal_guard"), "pending": a.get("pending"),
                "change_reason": a.get("change_reason") or "",
                "tier": tier, "why": why, "evidence": ev_grade, "evidence_why": ev_why,
            })
        items.sort(key=lambda x: ({"act": 0, "glance": 1, "ok": 2}[x["tier"]], x["set"], x["label"]))
        flags = {it["id"] for it in items if it["tier"] in ("act", "glance")}
        result["agent_review"] = {"generated": alog.get("generated"), "model": alog.get("model"),
                                  "crosscheck": alog.get("crosscheck"),
                                  "review_flags": sorted(flags), "items": items}

    # Whole-picture consistency: deterministic cross-indicator contradiction checks.
    try:
        result["consistency"] = consistency.run(result)
    except Exception as e:
        result["consistency"] = {"checked": 0, "flags": [], "error": str(e)}
    cflags = result["consistency"].get("flags", [])
    if cflags and result.get("agent_review"):
        rf = set(result["agent_review"].get("review_flags", []))
        rated = {it["id"] for it in result["agent_review"].get("items", [])}
        for f in cflags:
            for ind in f.get("indicators", []):
                if ind["id"] in rated:
                    rf.add(ind["id"])
        result["agent_review"]["review_flags"] = sorted(rf)
        for it in result["agent_review"]["items"]:
            if it["id"] in rf and it["tier"] == "ok":
                it["tier"] = "glance"
                it.setdefault("why", []).append("contradicted by a consistency check")
        result["agent_review"]["items"].sort(
            key=lambda x: ({"act": 0, "glance": 1, "ok": 2}[x["tier"]], x["set"], x["label"]))

    hist = os.path.join(ROOT, "data", "history.csv")
    # Phase 1 enrichments (read history BEFORE appending today's row)
    enrich.attach_trends(result, hist, args.date)
    enrich.attach_provenance(result, alog if alog.get("assessments") else None, fetched, args.date)
    result["data_health"] = enrich.data_health(config, fetched, alog, args.date, args.offline)
    if guard:
        dh = result["data_health"]
        dh["carried"] = guard.get("carried", [])
        dh["held"] = guard.get("held", [])
        dh["live_ok"] = sum(1 for dv in fetched.values()
                            if dv.get("value") is not None and not dv.get("carried") and not dv.get("held"))
        dh["fell_back"] = sum(1 for dv in fetched.values() if dv.get("value") is None)
    if pw_readings:
        ok = [r for r in pw_readings.values() if "ratio" in r]
        result["data_health"]["portwatch"] = {"ok": len(ok), "total": len(pw_readings),
                                              "as_of": min((r["as_of"] for r in ok), default=None)}
    # measured indicators: show where the number really came from
    for s_ in result["stories"]:
        for ind in s_["indicators"]:
            dv = fetched.get(ind["id"]) or {}
            if dv.get("carried"):
                ind["carried"] = f"feed failed - last good value from {dv.get('as_of')}"
            if dv.get("held"):
                ind["held"] = dv["held"]
            a = hybrid_used.get(ind["id"])
            if a:
                ind["provenance"] = "Agent"
                ind["source_url"] = (a.get("sources") or [""])[0]
                ind["as_of"] = a.get("as_of")
                ind["hybrid_note"] = "newer than the monthly official figure"
            m = measured.get(ind["id"])
            if m:
                ind["provenance"] = "PortWatch"
                ind["source_url"] = "https://portwatch.imf.org"
                ind["as_of"] = m["as_of"]
                ind["measured_note"] = m["note"]
                ind.pop("stale_for_cadence", None)
    if result.get("agent_review"):
        # count what is actually in the review queue, not every annotated item
        result["data_health"]["agent_flags"] = len(result["agent_review"].get("review_flags", []))

    prev = None
    latest_path = os.path.join(ROOT, "data", "latest.json")
    if os.path.exists(latest_path):
        with open(latest_path) as f:
            prev = json.load(f)

    note, changes = narrative.make_narrative(result, prev, use_ai=not args.no_ai)
    result["narrative"] = note

    report.append_history(result, args.date, hist)
    try:
        import ledger
        led = ledger.update_ledger(result, args.date, hist)
        # Owner grades (grades.csv) always win; bad rows warn but never break the run.
        for m in ledger.apply_owner_grades(os.path.join(ROOT, "grades.csv")):
            print(f"::warning title=grades.csv::{m}")
        try:
            with open(os.path.join(ROOT, "config", "grading.yaml")) as f:
                _gr = yaml.safe_load(f)
            ledger.set_meta({"grading": {"window_days": int(_gr.get("window_days_after_close", 30)),
                                         "rubric_version": str(_gr.get("version", ""))}})
        except Exception as e:
            print(f"  (grading rubric not loaded: {e})")
        labels = {i["id"]: i.get("label", i["id"]) for s_ in config["stories"] for i in s_["indicators"]}
        ledger.annotate_triggers(hist, os.path.join(ROOT, "data", "indicator_history.csv"), labels)
        # Automated grading: weekly, on agent runs only, and only for episodes whose
        # follow-through window has passed. Two independent agents must agree.
        if args.agent and key and not args.offline:
            try:
                import grader
                print("Grading closed Track record episodes (rubric: config/grading.yaml) ...")
                gs = grader.run(key, args.date)
                if gs:
                    print(f"  grader: {gs.get('due', 0)} due, {gs.get('applied', 0)} applied, "
                          f"{gs.get('needs_owner', 0)} need the owner, {gs.get('error', 0)} errors")
                    if gs.get("needs_owner"):
                        print(f"::notice title=Track record::{gs['needs_owner']} episode(s) need your "
                              f"grade - the two agents disagreed or were unsure. See the dashboard.")
            except Exception as e:
                print(f"::warning title=Auto-grader skipped::{e}")
            try:
                import grader
                ms = grader.run_miss_check(key, args.date, [{"id": s_["id"], "name": s_["name"], "level": s_["level"]}
                                                           for s_ in result["stories"]])
                if ms and "checked" in ms:
                    print(f"  miss check: {ms['checked']} stories below High checked, "
                          f"{ms['possible_misses']} possible miss(es) for your review")
                    if ms["possible_misses"]:
                        print(f"::notice title=Track record::{ms['possible_misses']} possible miss(es) need your review")
            except Exception as e:
                print(f"::warning title=Miss check skipped::{e}")
        led = ledger.load_ledger()
        n_open = sum(1 for e in led["episodes"] if e.get("status") == "open")
        n_ungraded = sum(1 for e in led["episodes"] if e.get("status") == "closed" and not e.get("grade"))
        print(f"  resolution ledger: {n_open} episode(s) open, {n_ungraded} awaiting grade")
        result["data_health"]["ledger_ok"] = True
    except Exception as e:
        # LOUD on purpose: shows as a red annotation on the run summary and as a
        # warning on the dashboard health line, instead of a quiet log line.
        print(f"::error title=Resolution ledger NOT updated::{e}")
        result["data_health"]["ledger_ok"] = False
        result["data_health"]["ledger_error"] = str(e)[:300]
    ih = os.path.join(ROOT, "data", "indicator_history.csv")
    report.append_indicator_history(result, args.date, ih)
    report.write_indicator_history_json(ih, os.path.join(ROOT, "dashboard", "indicator_history.json"))
    payload = report.write_json(result, note, args.date, latest_path)
    report.write_json(result, note, args.date, os.path.join(ROOT, "dashboard", "latest.json"))
    xlsx = report.build_workbook(config, result, note, args.date, hist,
                                 os.path.join(ROOT, "output", "macro_risk_tracker.xlsx"))

    agg = result["aggregates"]
    sets_cfg = config.get("sets", {})
    set_str = "  |  ".join(
        f"{(sets_cfg.get(k) or {}).get('short', 'Set '+str(k))} {agg.get(k)}/10"
        for k in sorted(x for x in agg if x != "overall"))
    print(f"\nOverall {agg['overall']}/10  |  {set_str}")
    print(f"Level changes today: {len(changes)}")
    print(f"Wrote: {latest_path}, {hist}, {xlsx}, dashboard/latest.json")

    try:
        import build_brief
        build_brief.build()
    except Exception as e:
        print(f"::warning title=Living brief not rebuilt::{e}")

    # Permanent dated archive (scores, daily note, agent evidence, monthly brief snapshot)
    try:
        import archive
        with open(os.path.join(ROOT, "data", "agent_assessments.json")) as f:
            _alog_disk = json.load(f)
    except Exception:
        _alog_disk = alog if isinstance(alog, dict) else {}
    try:
        _rec = dict(payload if isinstance(payload, dict) else result)
        if args.offline:
            _rec["offline"] = True   # fallback run: baseline values, flagged in the archive
        print(f"  archive: {archive.run(_rec, _alog_disk)}")
    except Exception as e:
        print(f"::warning title=Archive skipped::{e}")
    # Is a new edition due? Free (no API): measures drift since the current edition.
    # The writing itself happens in the separate "edition" workflow.
    try:
        import edition as _edition
        _st = _edition.check(args.date)
        print(f"  next edition: {_st.get('summary')}")
        if _st.get("due"):
            print(f"::notice title=New edition due::{_st.get('summary')} - the monthly edition run will "
                  f"write a draft (or run the 'edition' workflow now).")
        archive.write_index()
    except Exception as e:
        print(f"  (edition check skipped: {e})")

    if not args.no_alert:
        try:
            ha = alerts.maybe_alert_health(result, os.environ, alog=alog,
                                           agent_ran=bool(args.agent and key and not args.offline))
            for p_ in ha.get("problems", []):
                print(f"::warning title=Pipeline problem::{p_}")
            if ha.get("sent"):
                print(f"  failure alert sent: {ha.get('results')}")
        except Exception as e:
            print(f"  (failure alert skipped: {e})")
        a = alerts.maybe_alert(result, prev, os.environ)
        if a.get("sent"):
            print(f"ALERT: {len(a['crossings'])} band crossing(s) sent -> {a['results']}")
        elif a.get("reason") == "no band crossings" and prev:
            print("Alerts: no band crossings since last run.")

    # The scout runs with the weekly agent pass only (it used to run on every run,
    # manual ones included); on other runs its queue is just tidied (old items expire).
    if args.scout and key and not args.offline and not args.agent:
        try:
            import scout
            q = scout.load_queue()
            if q.get("items"):
                n = scout.expire(q, args.date)
                scout.save_queue(q)
                print(f"  scout: not run (weekly with the agent); {n} stale item(s) expired, "
                      f"{q.get('pending_count', 0)} pending")
        except Exception as e:
            print(f"  (scout tidy skipped: {e})")
    if args.scout and key and not args.offline and args.agent:
        import scout
        print("Running overnight-event scout ...")
        q = scout.run_scout(config, key, args.date)
        print(f"  scout: {q.get('new_count', 0)} new, {q.get('pending_count', 0)} pending "
              f"(review on the dashboard, or `python src/scout.py --list`)")

    # Validation harness: calibration vs history + sensitivity of the current board.
    try:
        import validate
        v = validate.main()
    except Exception as e:
        print(f"  (validation skipped: {e})")

    print("\n" + note)


if __name__ == "__main__":
    main()
