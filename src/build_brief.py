#!/usr/bin/env python3
"""Generate the 'living brief' - a readable write-up that always reflects the CURRENT
stories and today's scores.

Unlike the polished 2026 Edition PDF (the curated original), this is rebuilt on every
run from dashboard/latest.json, so it carries today's levels, bands, moves and
indicator readings, and any story the scout adds appears automatically.

Outputs (both rewritten every run):
    dashboard/briefs/living_brief.html   - what the dashboard links to
    dashboard/briefs/living_brief.md     - the same content as plain Markdown

The HTML is written here with the standard library. (It used to be converted from
the Markdown by pandoc, which the GitHub runner does not have - so the linked HTML
silently stopped updating in July while only the .md kept changing.)

Never raises from main.py's point of view: main.py wraps build() in try/except.
    python src/build_brief.py
"""
import datetime
import html
import json
import os
import re

import yaml

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
OUTDIR = os.path.join(ROOT, "dashboard", "briefs")
SAFE_URL = re.compile(r"^(https?://|briefs/|#)", re.I)


def band_name(l):
    return "Low" if l <= 2 else "Moderate" if l <= 4 else "Elevated" if l <= 6 else "High" if l <= 8 else "Severe"


def band_color(l):
    return "#2E7D32" if l <= 2 else "#8BC34A" if l <= 4 else "#F5A623" if l <= 6 else "#E8710A" if l <= 8 else "#C0392B"


def _fmt(v):
    if isinstance(v, bool) or v is None:
        return "-" if v is None else str(v)
    if isinstance(v, (int, float)):
        if float(v).is_integer() and abs(v) < 1e6:
            return str(int(v))
        return f"{v:.2f}" if abs(v) < 10 else f"{v:,.1f}"
    return str(v)


def _esc(s):
    return html.escape(str(s if s is not None else ""), quote=True)


def _md_inline_to_html(s):
    """Escape first, then allow only **bold** - nothing the AI writes can become markup."""
    s = _esc(s)
    return re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", s)


def _narrative_html(text):
    """The daily note is light Markdown (headings, bold, bullets). Render just that."""
    out, in_list = [], False
    for line in (text or "").splitlines():
        t = line.strip()
        if t.startswith(("- ", "* ")):
            if not in_list:
                out.append("<ul>")
                in_list = True
            out.append(f"<li>{_md_inline_to_html(t[2:])}</li>")
            continue
        if in_list:
            out.append("</ul>")
            in_list = False
        if not t:
            continue
        if t.startswith("#"):
            continue  # the page has its own title; skip the note's '# EOD ...' heading
        out.append(f"<p>{_md_inline_to_html(t)}</p>")
    if in_list:
        out.append("</ul>")
    return "\n".join(out)


def _load(latest_path=None):
    with open(os.path.join(ROOT, "config", "stories.yaml")) as f:
        cfg = yaml.safe_load(f)
    stories = cfg["stories"]
    set_names = {str(k): v for k, v in (cfg.get("sets") or {}).items()}
    summaries = {}
    bpath = os.path.join(ROOT, "config", "briefs.yaml")
    if os.path.exists(bpath):
        with open(bpath) as f:
            summaries = (yaml.safe_load(f) or {}).get("stories", {}) or {}
    latest = {}
    lpath = latest_path or os.path.join(ROOT, "dashboard", "latest.json")
    if os.path.exists(lpath):
        try:
            with open(lpath) as f:
                latest = json.load(f)
        except Exception:
            latest = {}
    return stories, set_names, summaries, latest


def _story_view(s, live, summaries):
    """Merge config (always present) with today's scored story (when present)."""
    lvl = live.get("level", s["base_level"])
    inds_live = {i["id"]: i for i in live.get("indicators", []) or []}
    inds = []
    for i in s.get("indicators", []):
        li = inds_live.get(i["id"], {})
        inds.append({"label": li.get("label") or i.get("label", i["id"]),
                     "value": li.get("value"), "band": li.get("band"),
                     "as_of": li.get("as_of") or "", "stale": bool(li.get("stale"))})
    trend = live.get("trend") or {}
    url = live.get("brief_url") or ""
    return {"id": s["id"], "name": s["name"], "set": s["set"], "level": lvl,
            "raw": live.get("raw_level"), "band": live.get("band") or band_name(lvl),
            "summary": live.get("summary") or (summaries.get(s["id"]) or {}).get("summary") or "",
            "trend": trend, "brief_url": url if SAFE_URL.match(url) else "",
            "indicators": inds}


def current_edition_href():
    """Path (relative to dashboard/briefs/) of the newest published edition's PDF."""
    try:
        with open(os.path.join(ROOT, "dashboard", "briefs", "editions", "editions.json")) as f:
            eds = [e for e in json.load(f).get("editions", []) if e.get("status") == "published"]
        if eds:
            cur = max(eds, key=lambda e: e.get("published", ""))
            return cur.get("html") or cur["pdf"]
    except Exception:
        pass
    return "Global_Macro_Intelligence_Brief_2026.pdf"


def _trend_text(t):
    ch = t.get("change")
    if not t or ch is None:
        return ""
    if ch == 0:
        return f"unchanged since {t.get('since', '')}".strip()
    arrow = "▲" if ch > 0 else "▼"
    return f"{arrow} {abs(ch)} since {t.get('since', '')} (was {t.get('prev')})"


def build(latest=None, outdir=None, basename="living_brief", snapshot=False):
    """Write <basename>.html and .md. Defaults = the live page. With snapshot=True and
    an older latest.json dict, writes a frozen monthly copy (archive.py uses this);
    links are then relative to dashboard/briefs/archive/."""
    stories, set_names, summaries, cur = _load()
    latest = cur if latest is None else latest
    outdir = outdir or OUTDIR
    up = "../" if snapshot else ""          # path from the output folder to dashboard/briefs/
    live = {s["id"]: s for s in latest.get("stories", []) or []}
    agg = latest.get("aggregates") or {}
    data_date = latest.get("date") or datetime.date.today().isoformat()
    generated = latest.get("generated_at") or ""
    views = [_story_view(s, live.get(s["id"], {}), summaries) for s in stories]
    by_set = {}
    for v in views:
        by_set.setdefault(str(v["set"]), []).append(v)
    set_keys = sorted(by_set, key=lambda k: (len(k), k))

    def sname(k, short=False):
        d = set_names.get(str(k)) or {}
        return d.get("short" if short else "name") or f"Set {k}"

    overall = agg.get("overall")
    ob = band_name(int(float(overall) + 0.5)) if isinstance(overall, (int, float)) else ""
    n_high = sum(1 for v in views if v["level"] >= 7)
    highs = sorted((v for v in views if v["level"] >= 7), key=lambda v: (-v["level"], v["name"]))

    # ---------------- Markdown ----------------
    if snapshot:
        md_intro = (f"*Frozen snapshot: data as of {data_date}. Levels are shown exactly as the tracker "
                    "published them that day (older days used the scoring rules in force then).*")
    else:
        md_intro = (f"*Data as of {data_date}{' (run ' + generated + ')' if generated else ''}. Rebuilt "
                    "automatically on every tracker run from the live scores. For the full curated "
                    "write-ups, see the current edition.*")
    md = ["# Global Macro Intelligence \u2014 Living Brief" + (f" (snapshot {data_date})" if snapshot else ""),
          "", md_intro, ""]
    if overall is not None:
        md.append(f"**Overall risk {overall}/10 ({ob})** — " + ", ".join(
            f"{sname(k)} {agg.get(k, agg.get(int(k) if k.isdigit() else k, '-'))}" for k in set_keys) + ".")
        md.append("")
    if highs:
        md.append(f"**{n_high} {'story is' if n_high == 1 else 'stories are'} at High or above:** "
                  + "; ".join(f"{v['name']} ({v['level']})" for v in highs) + ".")
        md.append("")
    if latest.get("narrative"):
        md += ["## Today's note", "", latest["narrative"].strip(), ""]
    for k in set_keys:
        md += [f"## Set {k} — {sname(k)}", ""]
        for v in by_set[k]:
            md.append(f"### {v['name']} — {v['level']}/10 ({v['band']})")
            tt = _trend_text(v["trend"])
            if tt:
                md.append(f"*{tt}*")
            md.append("")
            if v["summary"]:
                md += [v["summary"], ""]
            md.append("*Indicators:* " + "; ".join(
                f"{i['label']} = {_fmt(i['value'])}" + (f" (as of {i['as_of']})" if i["as_of"] else "")
                for i in v["indicators"]))
            md.append("")
    md_text = "\n".join(md)

    # ---------------- HTML ----------------
    run_txt = (" \u00B7 run " + _esc(generated)) if generated else ""
    if snapshot:
        sub = (f"Frozen monthly snapshot \u00B7 data as of {_esc(data_date)} \u00B7 levels as published that day "
               f"\u00B7 <a href=\"index.html\">All snapshots &amp; editions</a> \u00B7 <a href=\"../living_brief.html\">Today\u2019s brief</a>")
        title = "Living Brief \u2014 snapshot " + _esc(data_date)
    else:
        sub = (f"Data as of {_esc(data_date)}{run_txt} \u00B7 rebuilt automatically on every tracker run "
               f"\u00B7 <a href=\"../\">Open the tracker</a> \u00B7 <a href=\"{_esc(current_edition_href())}\">Current edition</a> "
               f"\u00B7 <a href=\"archive/index.html\">Past snapshots &amp; editions</a>")
        title = "Living Brief"
    h = []
    h.append(f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{title}</title>
<style>
:root{{--bg:#f4f6f9;--card:#fff;--line:#e6e9ee;--text:#161a1f;--muted:#677182;--accent:#1F4E79;--head:#1F4E79}}
@media (prefers-color-scheme:dark){{:root{{--bg:#0e1116;--card:#161b22;--line:#262d37;--text:#e7ebf0;--muted:#9aa6b4;--accent:#5b9bd5;--head:#0c1422}}}}
*{{box-sizing:border-box}}
body{{margin:0;background:var(--bg);color:var(--text);font:15px/1.55 -apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,Helvetica,Arial,sans-serif}}
header{{background:var(--head);color:#fff;padding:18px 16px}}
header .in,main{{max-width:860px;margin:0 auto}}
header h1{{margin:0;font-size:21px}}
header p{{margin:4px 0 0;opacity:.85;font-size:13px}}
header a{{color:#fff}}
main{{padding:16px}}
a{{color:var(--accent)}}
.card{{background:var(--card);border:1px solid var(--line);border-radius:10px;padding:14px 16px;margin:0 0 12px}}
.agg{{display:flex;flex-wrap:wrap;gap:8px;margin:0 0 12px}}
.agg div{{background:var(--card);border:1px solid var(--line);border-radius:8px;padding:8px 12px;font-size:13px}}
.agg b{{font-size:18px;display:block}}
h2{{font-size:17px;margin:22px 0 10px;padding-bottom:6px;border-bottom:1px solid var(--line)}}
h3{{font-size:15.5px;margin:0;display:flex;gap:10px;align-items:center;flex-wrap:wrap}}
.chip{{display:inline-block;min-width:26px;text-align:center;color:#fff;font-weight:700;border-radius:6px;padding:1px 7px;font-size:13px}}
.muted{{color:var(--muted);font-size:13px}}
.note ul{{margin:6px 0 6px 18px;padding:0}}
.note p{{margin:6px 0}}
table{{width:100%;border-collapse:collapse;font-size:13px;margin-top:8px}}
td{{padding:4px 6px;border-top:1px solid var(--line);vertical-align:top;overflow-wrap:break-word}}
td.v{{white-space:nowrap;text-align:right}}
td.d{{white-space:nowrap;color:var(--muted)}}
.stale{{color:#C0392B;font-size:12px}}
@media (max-width:560px){{td.d{{display:none}}}}
</style></head><body>
<header><div class="in"><h1>Global Macro Intelligence \u2014 Living Brief</h1>
<p>{sub}</p></div></header>
<main>""")
    if overall is not None:
        cells = [f'<div>Overall<b>{_esc(overall)}</b>{_esc(ob)}</div>']
        for k in set_keys:
            val = agg.get(k, agg.get(int(k) if k.isdigit() else k))
            cells.append(f'<div title="{_esc(sname(k))}">{_esc(sname(k, short=True))}<b>{_esc(val if val is not None else "-")}</b></div>')
        h.append(f'<div class="agg">{"".join(cells)}</div>')
    if highs:
        h.append('<div class="card"><b>' + _esc(f"{n_high} {'story is' if n_high == 1 else 'stories are'} at High or above:")
                 + "</b> " + "; ".join(f"{_esc(v['name'])} ({v['level']})" for v in highs) + "</div>")
    if latest.get("narrative"):
        h.append(f'<div class="card note"><b>{"That day\u2019s note" if snapshot else "Today\u2019s note"}</b>{_narrative_html(latest["narrative"])}</div>')
    h.append('<p class="muted">Educational only — not investment advice. Levels are set by fixed '
             'rules from the indicator readings; see the tracker for method and sources.</p>')
    for k in set_keys:
        h.append(f"<h2>Set {_esc(k)} — {_esc(sname(k))}</h2>")
        for v in sorted(by_set[k], key=lambda v: -v["level"]):
            tt = _trend_text(v["trend"])
            tt_html = (" \u00B7 " + _esc(tt)) if tt else ""
            link = (f' <a class="muted" href="{_esc(up + v["brief_url"].removeprefix("briefs/"))}">full write-up \u2197</a>'
                    if v["brief_url"] and not v["brief_url"].startswith("http") else "")
            rows = []
            for i in v["indicators"]:
                stale_html = ' <span class="stale">stale</span>' if i["stale"] else ""
                rows.append(f'<tr><td>{_esc(i["label"])}{stale_html}</td>'
                            f'<td class="v">{_esc(_fmt(i["value"]))}</td><td class="d">{_esc(i["as_of"])}</td></tr>')
            h.append(f'<div class="card" id="{_esc(v["id"])}"><h3><span class="chip" style="background:{band_color(v["level"])}">'
                     f'{v["level"]}</span>{_esc(v["name"])} <span class="muted">{_esc(v["band"])}'
                     f'{tt_html}</span>{link}</h3>'
                     + (f"<p>{_esc(v['summary'])}</p>" if v["summary"] else "")
                     + f'<table>{"".join(rows)}</table></div>')
    h.append("</main></body></html>")
    html_text = "\n".join(h)

    os.makedirs(outdir, exist_ok=True)
    with open(os.path.join(outdir, basename + ".md"), "w") as f:
        f.write(md_text)
    hpath = os.path.join(outdir, basename + ".html")
    with open(hpath, "w") as f:
        f.write(html_text)
    return hpath


if __name__ == "__main__":
    print("Wrote", build())
