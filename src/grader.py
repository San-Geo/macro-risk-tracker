"""Automated track-record grading, double-checked by an independent second agent.

THE AI ONLY SETS INPUTS; THE RULES DECIDE - same contract as the scoring engine.

For each closed episode whose follow-through window has passed:
  1. The PRIMARY agent (Claude + web search) researches what happened and marks every
     test in config/grading.yaml for that story as met / not met, each "met" with a
     dated, sourced piece of evidence.
  2. A SECOND, independent agent (ASI1 when AGENT_MODEL_2=asi1, else a second read)
     does the same, blind to the first.
  3. Code - not the AI - turns each set of test results into a grade using the
     rubric's decision order (any M met -> materialized, else any C -> contained,
     else faded) and a timing qualifier (lead / concurrent).
  4. If both agents' results give the SAME grade, each with at least medium
     confidence, the grade is applied and published as "auto-graded, confirmed".
     Anything else - disagreement, low confidence, failed research - is parked as
     "needs owner" with both readings shown on the dashboard.

Owner grades (grades.csv or the Actions form) always win and are never overwritten.
Runs only on agent runs (weekly), and only for episodes that are actually due.
"""
import datetime
import json
import os
import re
import sys

import yaml

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
import agent   # noqa: E402
import ledger  # noqa: E402

RUBRIC_PATH = os.path.join(ROOT, "config", "grading.yaml")
GRADER_MODEL = os.environ.get("GRADER_MODEL") or agent.AGENT_MODEL
MAX_PER_RUN = int(os.environ.get("GRADER_MAX_PER_RUN", "4") or 4)
MAX_ATTEMPTS = 3
CONF_RANK = {"low": 0, "medium": 1, "high": 2}


def load_rubric(path=RUBRIC_PATH):
    with open(path) as f:
        return yaml.safe_load(f)


def _date(s):
    k = agent._as_of_key(s)
    if not k:
        return None
    try:
        return datetime.date(*k)
    except ValueError:
        return None


def window_end(ep, rubric):
    closed = datetime.date.fromisoformat(ep["closed"])
    return closed + datetime.timedelta(days=int(rubric.get("window_days_after_close", 30)))


def is_due(ep, rubric, today):
    """Closed, not yet graded by anyone, window passed, not parked for the owner."""
    if ep.get("status") != "closed" or ep.get("grade"):
        return False
    ag = ep.get("auto_grade") or {}
    if ag.get("status") == "needs_owner":
        return False
    if ag.get("status") == "error" and ag.get("attempts", 0) >= MAX_ATTEMPTS:
        return False
    return today >= window_end(ep, rubric)


def build_prompt(ep, rubric, story_cfg, today):
    s_rub = rubric["stories"][ep["story_id"]]
    w_end = window_end(ep, rubric)
    tests = "\n".join(f"  {t['id']} (materialized): {t['test']}" for t in s_rub["materialized"])
    tests += "\n" + "\n".join(f"  {t['id']} (contained): {t['test']}" for t in s_rub["contained"])
    rules = "\n".join(f"- {r}" for r in rubric.get("evidence_rules", []))
    trig = ep.get("triggers") or {}
    ids = [t["id"] for t in s_rub["materialized"] + s_rub["contained"]]
    return (
        f"You are grading the public track record of a macro-risk tracker. Today is {today}.\n\n"
        f"STORY: {ep['story']}\nWHAT THIS STORY WARNS ABOUT: {s_rub['risk']}\n\n"
        f"EPISODE: the tracker rated this story High from {ep['opened']} to {ep['last_seen']} "
        f"(peak {ep['peak_level']}/10). It dropped below High and the episode closed on {ep['closed']}.\n"
        f"Signals at the time (context only - do NOT grade with them): "
        f"{'; '.join(ep.get('drivers_at_open') or []) or 'n/a'}"
        f"{'; opened when: ' + '; '.join(trig.get('open', [])) if trig.get('open') else ''}\n\n"
        f"EVALUATION WINDOW: {ep['opened']} to {w_end.isoformat()} inclusive.\n\n"
        f"YOUR JOB: research what ACTUALLY happened in the real world and decide, for EVERY test "
        f"below, whether it was met inside the window. Do not choose a grade - the grade is "
        f"computed from your test decisions by fixed rules.\n\nTESTS:\n{tests}\n\n"
        f"EVIDENCE RULES:\n{rules}\n\n"
        "For each test marked met, give 'onset' = the date the qualifying condition BEGAN "
        "(it may be before the window if the condition was still in force inside it), a one-"
        "sentence 'evidence', and a 'source' URL. A test you cannot source is NOT met.\n"
        "Confidence: 'high' = every decision rests on primary/official sources and none is "
        "borderline; 'medium' = the decisive test is clearly sourced but another decision is "
        "borderline; 'low' = the decisive test could not be verified or sources conflict.\n"
        "'note' is one plain-English sentence (max 30 words) saying what happened, for the "
        "public record. Do not use the words materialized, contained or faded in it.\n\n"
        "Respond with ONLY a single-line, valid, minified JSON object and nothing else. Inside "
        "string values use single quotes only - NEVER the double-quote character:\n"
        '{"tests": [{"id": "<test id>", "met": true|false, "onset": "<YYYY-MM-DD or empty>", '
        '"evidence": "<one sentence or empty>", "source": "<url or empty>"}], '
        '"confidence": "low|medium|high", "summary": "<=2 sentences", "note": "<=30 words"}\n'
        f"Include all of these test ids exactly once: {', '.join(ids)}."
    )


def _parse(text):
    text = (text or "").strip()
    text = re.sub(r"^```(json)?|```$", "", text, flags=re.MULTILINE).strip()
    m = re.search(r"\{.*\}", text, flags=re.DOTALL)
    block = m.group(0) if m else text
    for cand in (block, re.sub(r",\s*([}\]])", r"\1", block)):
        try:
            return json.loads(cand)
        except Exception:
            continue
    raise ValueError("grader reply was not valid JSON")


def evaluate(raw, ep, rubric):
    """Deterministic: validate the agent's test calls, then compute grade + timing.
    The agent never picks the grade."""
    s_rub = rubric["stories"][ep["story_id"]]
    kinds = {t["id"]: "M" for t in s_rub["materialized"]}
    kinds.update({t["id"]: "C" for t in s_rub["contained"]})
    opened = datetime.date.fromisoformat(ep["opened"])
    w_end = window_end(ep, rubric)
    got = {}
    for t in raw.get("tests") or []:
        tid = str(t.get("id", "")).strip().upper()
        if tid in kinds and tid not in got:
            got[tid] = t
    tests, notes = [], []
    for tid, kind in kinds.items():
        t = got.get(tid) or {}
        met = t.get("met") is True or str(t.get("met")).lower() == "true"
        onset = _date(t.get("onset"))
        src = str(t.get("source") or "").strip()
        if met and not re.match(r"https?://", src):
            met = False
            notes.append(f"{tid}: marked met without a source -> not met")
        if met and onset is None:
            met = False
            notes.append(f"{tid}: marked met without an onset date -> not met")
        if met and onset > w_end:
            met = False
            notes.append(f"{tid}: onset {onset} is after the window -> not met")
        tests.append({"id": tid, "kind": kind, "met": met,
                      "onset": onset.isoformat() if (met and onset) else "",
                      "evidence": str(t.get("evidence") or "")[:300] if met else "",
                      "source": src if met else ""})
    m_met = [t for t in tests if t["kind"] == "M" and t["met"]]
    c_met = [t for t in tests if t["kind"] == "C" and t["met"]]
    if m_met:
        grade = "materialized"
        first = min(datetime.date.fromisoformat(t["onset"]) for t in m_met)
        timing = "lead" if first >= opened else "concurrent"
    elif c_met:
        grade, timing = "contained", None
    else:
        grade, timing = "faded", None
    conf = str(raw.get("confidence", "low")).lower()
    conf = conf if conf in CONF_RANK else "low"
    if len(got) < len(kinds):
        notes.append(f"only {len(got)} of {len(kinds)} tests reported -> confidence low")
        conf = "low"
    return {"grade": grade, "timing": timing, "confidence": conf, "tests": tests,
            "summary": str(raw.get("summary") or "")[:400],
            "note": str(raw.get("note") or "")[:240], "validation": notes}


def _read(ep, rubric, today, provider, key, model):
    prompt = build_prompt(ep, rubric, None, today)
    if provider == "asi1":
        text = agent._call_asi1(prompt, model or "asi1", key, max_tokens=3000)
    else:
        text = agent._call_anthropic(prompt, model or GRADER_MODEL, key, max_uses=8, max_tokens=4000)
    out = evaluate(_parse(text), ep, rubric)
    out["by"] = (model or GRADER_MODEL) if provider == "anthropic" else (model or "asi1")
    out["provider"] = provider
    return out


def decide(primary, check):
    """Apply only on agreement with at least medium confidence on both sides."""
    if primary["grade"] != check["grade"]:
        return False, f"the two agents disagree ({primary['grade']} vs {check['grade']})"
    if min(CONF_RANK[primary["confidence"]], CONF_RANK[check["confidence"]]) < 1:
        return False, "agreement, but at least one read is low confidence"
    return True, "both agents agree"


def grade_episode(ep, rubric, api_key, today):
    xprovider, xkey, xmodel = agent.resolve_crosscheck(api_key)
    primary = _read(ep, rubric, today, "anthropic", api_key, GRADER_MODEL)
    check = _read(ep, rubric, today, xprovider, xkey, xmodel)
    ok, why = decide(primary, check)
    record = {"status": "applied" if ok else "needs_owner", "reason": why,
              "rubric_version": str(rubric.get("version", "")),
              "independent": xprovider != "anthropic",
              "graded_on": today.isoformat(), "primary": primary, "check": check}
    if ok:
        ep["grade"] = primary["grade"]
        ep["grade_timing"] = primary["timing"] or check["timing"]
        ep["grade_note"] = primary["note"] or primary["summary"]
        ep["grade_source"] = "auto"
        ep["graded_on"] = today.isoformat()
        ep["rubric_version"] = record["rubric_version"]
    ep["auto_grade"] = record
    return record


def run(api_key, date_str):
    """Grade every due episode (max MAX_PER_RUN per run). Never raises."""
    if os.environ.get("GRADER_ENABLED", "1") in ("0", "false", "no"):
        print("  (auto-grader disabled by GRADER_ENABLED)")
        return {}
    rubric = load_rubric()
    today = datetime.date.fromisoformat(date_str)
    led = ledger.load_ledger()
    due = [e for e in led["episodes"] if e.get("story_id") in rubric["stories"]
           and is_due(e, rubric, today)]
    summary = {"due": len(due), "applied": 0, "needs_owner": 0, "error": 0}
    for ep in due[:MAX_PER_RUN]:
        try:
            r = grade_episode(ep, rubric, api_key, today)
            summary["applied" if r["status"] == "applied" else "needs_owner"] += 1
            print(f"  grading {ep['id']}: {r['status']} - primary {r['primary']['grade']} "
                  f"({r['primary']['confidence']}), check {r['check']['grade']} "
                  f"({r['check']['confidence']}) by {r['check']['by']}")
        except Exception as e:
            prev = ep.get("auto_grade") or {}
            ep["auto_grade"] = {"status": "error", "error": str(e)[:240],
                                "attempts": prev.get("attempts", 0) + 1,
                                "graded_on": today.isoformat()}
            summary["error"] += 1
            print(f"  grading {ep['id']}: error ({e})")
        ledger.save_ledger(led)  # save after each, so a later failure loses nothing
    if len(due) > MAX_PER_RUN:
        print(f"  ({len(due) - MAX_PER_RUN} more episode(s) due - graded on the next agent run)")
    return summary
