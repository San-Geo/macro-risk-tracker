"""Write the daily 'what changed and why it matters' note.

If ANTHROPIC_API_KEY is set and --no-ai is not passed, calls the Claude API
(stdlib urllib, no SDK) to write a short brief. Otherwise produces a clear
templated summary from the rules. The AI never sets the numbers - it only
explains the moves the scoring engine already computed.
"""
import json, os, urllib.request

MODEL = os.environ.get("TRACKER_MODEL", "claude-haiku-4-5-20251001")


def diff_changes(today, yesterday):
    """List stories whose level changed vs the previous run."""
    prev = {s["id"]: s["level"] for s in (yesterday or {}).get("stories", [])}
    changes = []
    for s in today["stories"]:
        old = prev.get(s["id"])
        if old is not None and old != s["level"]:
            movers = [i for i in s["indicators"] if i["delta"] and not i["stale"]]
            changes.append({"name": s["name"], "old": old, "new": s["level"],
                            "band": s["band"], "drivers": movers})
    return changes


def template_narrative(today, changes):
    agg = today["aggregates"]
    set_keys = sorted(x for x in agg if x != "overall")
    set_str = ", ".join(f"Set {k} {agg.get(k,'-')}/10" for k in set_keys)
    lines = [f"As of {today['date']}: overall risk {agg['overall']}/10 ({set_str})."]
    if not changes:
        lines.append("No story changed level versus the previous run. "
                     "Daily market indicators moved within their current bands.")
    else:
        for c in changes:
            arrow = "up" if c["new"] > c["old"] else "down"
            drv = "; ".join(f"{d['label']} now band {d['band']}" for d in c["drivers"][:3]) or "indicator shifts"
            lines.append(f"- {c['name']}: {c['old']} -> {c['new']}/10 ({c['band']}), {arrow}. Driver: {drv}.")
    return "\n".join(lines)


def claude_narrative(today, changes, api_key):
    payload = {
        "today": {"date": today["date"], "aggregates": today["aggregates"]},
        "changes": changes,
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
        "Neutral, precise, no hype.\n\nDATA:\n" + json.dumps(payload, indent=2)
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
            return claude_narrative(today, changes, key), changes
        except Exception as e:
            return template_narrative(today, changes) + f"\n\n(AI narrative unavailable: {e})", changes
    return template_narrative(today, changes), changes
