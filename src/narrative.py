"""Write the daily 'what changed and why it matters' note.

If ANTHROPIC_API_KEY is set and --no-ai is not passed, calls the Claude API
(stdlib urllib, no SDK) to write a short brief. Otherwise produces a clear
templated summary from the rules. The AI never sets the numbers - it only
explains the moves the scoring engine already computed.

BAND WORDS ARE THE ENGINE'S, NOT THE AI'S. The model is told the correct band
word for the overall score, and whatever it writes is then corrected by a
deterministic post-pass (enforce_band_words) before the text is stored. Same
philosophy as the rest of the tracker: rules decide, the AI only explains.
"""
import json, math, os, re, urllib.request

MODEL = os.environ.get("TRACKER_MODEL", "claude-haiku-4-5-20251001")

BANDS = ("Low", "Moderate", "Elevated", "High", "Severe")
_BANDS_RE = "|".join(BANDS)
# Only used if a level is absent from today's board; the live mapping below is
# learned from the engine's own output so this can never silently drift.
_FALLBACK_BANDS = {0: "Low", 1: "Low", 2: "Low", 3: "Moderate", 4: "Moderate",
                   5: "Elevated", 6: "Elevated", 7: "High", 8: "High",
                   9: "Severe",10: "Severe"}


def _round_half_up(x):
    """Match the dashboard's Math.round (JS rounds .5 up; Python's round() does not)."""
    return int(math.floor(float(x) + 0.5))


def band_for_level(today, level_int):
    """The engine's own band word for an integer level.

    Learned from today's scored stories wherever possible, so the wording can
    never drift from score.py; the static table is a last resort only.
    """
    lvl = max(0, min(10, int(level_int)))
    for s in today.get("stories", []) or []:
        if s.get("level") == lvl and s.get("band"):
            return s["band"]
    return _FALLBACK_BANDS.get(lvl, "")


def overall_band(today):
    """Band word for the overall score (7.1 -> 'High', 6.2 -> 'Elevated')."""
    try:
        return band_for_level(today, _round_half_up(today["aggregates"]["overall"]))
    except Exception:
        return ""


def _match_case(original, correct):
    if original.islower():
        return correct.lower()
    if original.isupper():
        return correct.upper()
    return correct


def enforce_band_words(text, today):
    """Correct any band word the AI attached to a level. Returns (text, fixes).

    DELIBERATELY SURGICAL. Only two shapes are touched:
      1. a band word bound to a score that is genuinely one of today's aggregates
         ("elevated at 7.1", "7.1 (Elevated)")
      2. a band word bound to an integer story level in an explicit level/band
         form ("8/High", "(Level 8, High)", "(7/10, High)")
    Everything else is left alone, so prose like "three stories at High" or
    "high-yield OAS 2.73" can never be rewritten.
    """
    if not text:
        return text, []
    fixes = []
    agg = (today or {}).get("aggregates", {}) or {}
    # decimals that really are scores on this board (overall + set scores)
    scores = {}
    for v in agg.values():
        try:
            scores[f"{float(v):g}"] = _round_half_up(v)
        except (TypeError, ValueError):
            continue

    def _fix_word_then_num(m):
        word, mid, num = m.group(1), m.group(2), m.group(3)
        if num not in scores:
            return m.group(0)
        correct = band_for_level(today, scores[num])
        if correct and correct.lower() != word.lower():
            fixes.append(f"'{word} {mid.strip()} {num}' -> '{_match_case(word, correct)}'")
            return _match_case(word, correct) + mid + num
        return m.group(0)

    def _fix_num_then_word(m):
        num, mid, word = m.group(1), m.group(2), m.group(3)
        if num not in scores:
            return m.group(0)
        correct = band_for_level(today, scores[num])
        if correct and correct.lower() != word.lower():
            fixes.append(f"'{num}{mid}{word}' -> '{_match_case(word, correct)}'")
            return num + mid + _match_case(word, correct)
        return m.group(0)

    def _fix_level_then_word(m):
        num, mid, word = m.group(1), m.group(2), m.group(3)
        lvl = int(num)
        correct = band_for_level(today, lvl)
        if correct and correct.lower() != word.lower():
            fixes.append(f"'{num}{mid}{word}' -> '{_match_case(word, correct)}'")
            return num + mid + _match_case(word, correct)
        return m.group(0)

    # 1a. "elevated at 7.1" / "high of 6.8"
    text = re.sub(rf"\b({_BANDS_RE})\b(\s+(?:at|of)\s+)(\d+\.\d+)",
                  _fix_word_then_num, text, flags=re.I)
    # 1b. "7.1 (Elevated)" / "7.1/10, elevated"
    text = re.sub(rf"(\d+\.\d+)(\s*(?:/10)?\s*[\(/,]\s*)({_BANDS_RE})\b",
                  _fix_num_then_word, text, flags=re.I)
    # 2. "(8/High)" / "(Level 8, High)" / "(7/10, High)" - integer levels only,
    #    never a fragment of a decimal (lookarounds bar 7.1 -> "1, High").
    text = re.sub(rf"(?<![\d.])(\d{{1,2}})(?![\d.])(\s*(?:/10)?\s*[,/]\s*)({_BANDS_RE})\b",
                  _fix_level_then_word, text, flags=re.I)
    return text, fixes


def _fmt(v):
    try:
        f = float(v)
        return str(int(f)) if f.is_integer() else f"{f:g}"
    except (TypeError, ValueError):
        return str(v)


def diff_changes(today, yesterday):
    """List stories whose level changed vs the previous run, with the indicators
    that ACTUALLY moved.

    A story level only moves when one of its indicators changes band, so the
    drivers are exactly the indicators whose band differs from the previous run.
    (The old version passed every indicator sitting away from its baseline,
    which let the AI attribute a move to something that had not changed - e.g.
    a June blacklist blamed for an October move.)"""
    prev_stories = {s["id"]: s for s in (yesterday or {}).get("stories", [])}
    # the agent's own load-bearing fact, so the brief can say WHAT happened
    facts = {it["id"]: (it.get("fact") or "")[:260]
             for it in ((today.get("agent_review") or {}).get("items") or [])}
    changes = []
    for s in today["stories"]:
        ps = prev_stories.get(s["id"])
        if ps is None:
            continue
        try:
            import score as _score
            prev_level = _score.level_of(ps)       # same rounding rule as today
        except Exception:
            prev_level = ps.get("level")
        if prev_level == s["level"]:
            continue
        prev_ind = {i["id"]: i for i in ps.get("indicators", [])}
        movers = []
        for i in s["indicators"]:
            pi = prev_ind.get(i["id"])
            if pi is None or pi.get("band") == i.get("band"):
                continue
            movers.append({"label": i["label"], "band": i.get("band"),
                           "old_band": pi.get("band"),
                           "value": _fmt(i.get("value")), "old_value": _fmt(pi.get("value")),
                           "as_of": i.get("as_of") or "",
                           "evidence": facts.get(i["id"], ""),
                           "direction": "up" if (i.get("band") or 0) > (pi.get("band") or 0) else "down"})
        # old_band too: given only the new band, the model wrote "moved from Moderate
        # to Moderate" for a 5 -> 4 move (Elevated -> Moderate) on 2026-10-14.
        changes.append({"name": s["name"], "old": prev_level, "new": s["level"],
                        "old_band": band_for_level(today, prev_level) if prev_level is not None else "",
                        "band": s["band"], "drivers": movers})
    return changes


def template_narrative(today, changes):
    agg = today["aggregates"]
    set_keys = sorted(x for x in agg if x != "overall")
    set_str = ", ".join(f"Set {k} {agg.get(k,'-')}/10" for k in set_keys)
    ob = overall_band(today)
    lines = [f"As of {today['date']}: overall risk {agg['overall']}/10"
             f"{f' ({ob})' if ob else ''} ({set_str})."]
    if not changes:
        lines.append("No story changed level versus the previous run. "
                     "Daily market indicators moved within their current bands.")
    else:
        for c in changes:
            arrow = "up" if c["new"] > c["old"] else "down"
            drv = "; ".join(f"{d['label']} {d['old_value']} -> {d['value']} (band {d['old_band']} -> {d['band']})"
                            for d in c["drivers"][:3]) or "a scoring-rule change (no indicator changed band)"
            lines.append(f"- {c['name']}: {c['old']} -> {c['new']}/10 ({c['band']}), {arrow}. Driver: {drv}.")
    return "\n".join(lines)


def claude_narrative(today, changes, api_key):
    payload = {
        "today": {"date": today["date"], "aggregates": today["aggregates"]},
        # The engine's band word for the overall score - the model must not invent its own.
        "overall_band": overall_band(today),
        "changes": changes,
        # counts are facts too - the model once wrote "four High-rated risks" when there were five
        "n_stories_at_high_or_above": sum(1 for s in today["stories"] if s["level"] >= 7),
        "elevated_or_higher": [
            {"name": s["name"], "level": s["level"], "band": s["band"]}
            for s in today["stories"] if s["level"] >= 5
        ],
    }
    prompt = (
        "You are the analyst for a daily macro-risk tracker. Using ONLY the JSON below "
        "(do not invent numbers or facts), write a concise EOD brief of 120-180 words: "
        "(1) one-sentence headline on overall risk; (2) bullet each story whose level changed, "
        "saying what moved it and the practical risk; (3) one line on the highest-risk story to watch. "
        "Neutral, precise, no hype.\n\n"
        "ATTRIBUTION IS FIXED TOO. Each changed story lists its 'drivers': the complete and ONLY "
        "set of indicators that changed band since the previous run, with old and new values. "
        "Explain each move using ONLY its drivers (and each driver's 'evidence' text, when present). Do not cite any other indicator, event or "
        "number as a cause, and do not add background events that are not in the drivers. If a "
        "story has no drivers, say the move came from a scoring-rule change.\n\n"
        "BAND WORDS ARE FIXED BY THE ENGINE. When you describe the overall score, use EXACTLY "
        "the word given in 'overall_band' - never substitute your own judgement (e.g. if "
        "overall_band is 'High', do not call the score 'elevated'). For each story, use that "
        "story's own 'band' value verbatim; for a changed story, its previous band is 'old_band' "
        "(if old_band equals band, say it moved within that band - never 'from X to X'). If you say how many stories are at High, use "
        "'n_stories_at_high_or_above' exactly and name every one of them. These words have precise numeric thresholds; "
        "choosing a different one misstates the result.\n\nDATA:\n" + json.dumps(payload, indent=2)
    )
    body = json.dumps({
        "model": MODEL, "max_tokens": 700,
        "messages": [{"role": "user", "content": prompt}],
    }).encode()
    req = urllib.request.Request(
        "https://api.anthropic.com/v1/messages", data=body,
        headers={"content-type": "application/json", "x-api-key": api_key,
                 "anthropic-version": "2023-06-01"})
    with urllib.request.urlopen(req, timeout=60) as r:
        data = json.loads(r.read().decode())
    return "".join(b.get("text", "") for b in data.get("content", [])).strip()


def make_narrative(today, yesterday, use_ai=True):
    changes = diff_changes(today, yesterday)
    key = os.environ.get("ANTHROPIC_API_KEY")
    if use_ai and key:
        try:
            text = claude_narrative(today, changes, key)
        except Exception as e:
            text = template_narrative(today, changes) + f"\n\n(AI narrative unavailable: {e})"
    else:
        text = template_narrative(today, changes)
    # Deterministic guard: the engine's band names win, whatever the AI wrote.
    try:
        text, fixes = enforce_band_words(text, today)
        if fixes:
            print(f"  narrative band-word guard corrected {len(fixes)}: " + "; ".join(fixes[:4]))
    except Exception as e:
        print(f"  (band-word guard skipped: {e})")
    return text, changes
