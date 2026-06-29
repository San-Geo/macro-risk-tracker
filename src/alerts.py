"""Band-crossing alerts.

Fires ONLY when a story (or the overall aggregate) crosses into a different risk
*band* (Low / Moderate / Elevated / High / Severe) versus the previous run - not on
every small wiggle. So you can ignore the tracker until it actually pings you.

Channels (configure via env / GitHub Actions secrets; all optional):
  ALERT_WEBHOOK_URL     Discord, Slack, or any JSON webhook (auto-detected)
  ALERT_STYLE           force "discord" | "slack" | "generic" (optional)
  TELEGRAM_BOT_TOKEN + TELEGRAM_CHAT_ID     Telegram bot
  SMTP_HOST/SMTP_PORT/SMTP_USER/SMTP_PASS/ALERT_EMAIL_TO   email (optional)
  ALERT_MIN_LEVEL       only alert if the new OR old level >= this (default 0 = all)

Never raises into the run: every send is wrapped so a failed alert can't break a refresh.
"""
import json, os, smtplib, urllib.request
from email.mime.text import MIMEText

BANDS = [(2, "Low"), (4, "Moderate"), (6, "Elevated"), (8, "High"), (10, "Severe")]


def band_name(level):
    for ceiling, name in BANDS:
        if level <= ceiling:
            return name
    return "Severe"


def detect_crossings(today, prev, min_level=0):
    """Return list of band crossings (stories + overall) vs the previous run."""
    if not prev:
        return []
    prev_levels = {s["id"]: s["level"] for s in prev.get("stories", [])}
    out = []
    for s in today["stories"]:
        old = prev_levels.get(s["id"])
        if old is None:
            continue
        nb, ob = band_name(s["level"]), band_name(old)
        if nb != ob and (s["level"] >= min_level or old >= min_level):
            out.append({"kind": "story", "name": s["name"], "set": s["set"],
                        "old": old, "new": s["level"], "old_band": ob, "new_band": nb,
                        "dir": "up" if s["level"] > old else "down"})
    # overall aggregate
    o_new = today["aggregates"]["overall"]
    o_old = (prev.get("aggregates") or {}).get("overall")
    if o_old is not None:
        nb, ob = band_name(round(o_new)), band_name(round(o_old))
        if nb != ob:
            out.append({"kind": "overall", "name": "OVERALL", "set": "-",
                        "old": o_old, "new": o_new, "old_band": ob, "new_band": nb,
                        "dir": "up" if o_new > o_old else "down"})
    return out


def format_message(crossings, today):
    arrow = {"up": "\u25B2", "down": "\u25BC"}
    head = f"Macro Risk Tracker - {today.get('date','')}: {len(crossings)} band crossing(s)"
    lines = [head, ""]
    for c in sorted(crossings, key=lambda x: (x["kind"] != "overall", -x["new"])):
        lines.append(f"{arrow[c['dir']]} {c['name']} ({c['old']}->{c['new']}/10): "
                     f"{c['old_band']} -> {c['new_band']}")
    agg = today["aggregates"]
    set_keys = sorted(k for k in agg if k != "overall")
    set_str = " ".join(f"S{k} {agg.get(k,'-')}" for k in set_keys)
    lines += ["", f"Overall {agg['overall']}/10 | {set_str}"]
    return "\n".join(lines)


def _post_json(url, payload, timeout=15):
    req = urllib.request.Request(url, data=json.dumps(payload).encode(),
                                 headers={"content-type": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.status


def _send_webhook(url, text, style=None):
    style = style or ("discord" if "discord" in url else "slack" if "slack" in url else "generic")
    if style == "discord":
        payload = {"content": text[:1990]}
    elif style == "slack":
        payload = {"text": text}
    else:
        payload = {"text": text, "content": text}
    return _post_json(url, payload)


def _send_telegram(token, chat_id, text):
    return _post_json(f"https://api.telegram.org/bot{token}/sendMessage",
                      {"chat_id": chat_id, "text": text})


def _send_email(env, text, subject):
    msg = MIMEText(text)
    msg["Subject"] = subject
    msg["From"] = env.get("SMTP_USER", "tracker@localhost")
    msg["To"] = env["ALERT_EMAIL_TO"]
    host, port = env["SMTP_HOST"], int(env.get("SMTP_PORT", "587"))
    with smtplib.SMTP(host, port, timeout=20) as s:
        s.starttls()
        if env.get("SMTP_USER"):
            s.login(env["SMTP_USER"], env.get("SMTP_PASS", ""))
        s.sendmail(msg["From"], [env["ALERT_EMAIL_TO"]], msg.as_string())
    return "sent"


def send_all(text, env, subject="Macro Risk Tracker alert"):
    """Send to every configured channel. Returns list of (channel, result)."""
    results = []
    url = env.get("ALERT_WEBHOOK_URL")
    if url:
        try:
            results.append(("webhook", _send_webhook(url, text, env.get("ALERT_STYLE"))))
        except Exception as e:
            results.append(("webhook", f"error: {e}"))
    if env.get("TELEGRAM_BOT_TOKEN") and env.get("TELEGRAM_CHAT_ID"):
        try:
            results.append(("telegram", _send_telegram(env["TELEGRAM_BOT_TOKEN"],
                                                       env["TELEGRAM_CHAT_ID"], text)))
        except Exception as e:
            results.append(("telegram", f"error: {e}"))
    if env.get("SMTP_HOST") and env.get("ALERT_EMAIL_TO"):
        try:
            results.append(("email", _send_email(env, text, subject)))
        except Exception as e:
            results.append(("email", f"error: {e}"))
    return results


def channels_configured(env):
    return bool(env.get("ALERT_WEBHOOK_URL")
                or (env.get("TELEGRAM_BOT_TOKEN") and env.get("TELEGRAM_CHAT_ID"))
                or (env.get("SMTP_HOST") and env.get("ALERT_EMAIL_TO")))


def maybe_alert(today, prev, env):
    """Detect crossings and notify. Safe no-op if no channel configured / no crossings."""
    if not channels_configured(env):
        return {"sent": False, "reason": "no channel configured", "crossings": []}
    min_level = int(env.get("ALERT_MIN_LEVEL", "0") or 0)
    crossings = detect_crossings(today, prev, min_level)
    if not crossings:
        return {"sent": False, "reason": "no band crossings", "crossings": []}
    text = format_message(crossings, today)
    results = send_all(text, env)
    return {"sent": True, "results": results, "crossings": crossings, "message": text}


def send_test(env):
    if not channels_configured(env):
        print("  no alert channel configured (set ALERT_WEBHOOK_URL or Telegram/SMTP).")
        return
    res = send_all("Macro Risk Tracker: test alert. Channels are working.", env,
                   subject="Macro Risk Tracker test")
    print("  test alert ->", res)
