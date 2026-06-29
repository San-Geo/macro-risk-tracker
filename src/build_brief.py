#!/usr/bin/env python3
"""Generate a 'living brief' that always reflects the CURRENT set of stories.

Unlike the three polished Set PDFs (the curated originals), this is regenerated on
every run from config + the latest levels, so any story the scout adds appears
automatically with its background. Output: dashboard/briefs/living_brief.md
(and .html if pandoc is available). main.py calls this at the end of each run.
"""
import datetime, json, os, subprocess, sys
import yaml

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)


def band_name(l):
    return "Low" if l <= 2 else "Moderate" if l <= 4 else "Elevated" if l <= 6 else "High" if l <= 8 else "Severe"


def build():
    with open(os.path.join(ROOT, "config", "stories.yaml")) as f:
        stories = yaml.safe_load(f)["stories"]
    briefs = {}
    bpath = os.path.join(ROOT, "config", "briefs.yaml")
    if os.path.exists(bpath):
        briefs = (yaml.safe_load(open(bpath)) or {}).get("stories", {})
    levels = {}
    lpath = os.path.join(ROOT, "dashboard", "latest.json")
    if os.path.exists(lpath):
        try:
            d = json.load(open(lpath))
            levels = {s["id"]: s for s in d.get("stories", [])}
            agg = d.get("aggregates", {})
        except Exception:
            agg = {}
    else:
        agg = {}

    set_names = (yaml.safe_load(open(os.path.join(ROOT, "config", "stories.yaml"))).get("sets") or {})
    out = ["# Global Macro Intelligence — Living Brief",
           f"\n*Auto-generated {datetime.date.today().isoformat()} from the live tracker. "
           "This always reflects the current set of stories (including any the scout has added). "
           "For the full curated write-ups, see the combined 2026 Edition brief.*\n"]
    if agg:
        sk = sorted(k for k in agg if k != "overall")
        ss = ", ".join(f"{(set_names.get(k) or {}).get('short', 'Set '+str(k))} {agg.get(k,'-')}" for k in sk)
        out.append(f"**Overall risk {agg.get('overall','-')}/10** — {ss}.\n")
    by_set = {}
    for s in stories:
        by_set.setdefault(s["set"], []).append(s)
    for st in sorted(by_set):
        nm = (set_names.get(st) or {}).get("name", f"Set {st}")
        out.append(f"\n## Set {st} — {nm}\n")
        for s in by_set[st]:
            lv = levels.get(s["id"], {})
            lvl = lv.get("level", s["base_level"])
            out.append(f"### {s['name']} — {lvl}/10 ({band_name(lvl)})\n")
            summ = briefs.get(s["id"], {}).get("summary")
            if summ:
                out.append(summ + "\n")
            inds = ", ".join(i.get("label", i["id"]) for i in s.get("indicators", []))
            out.append(f"*Indicators watched:* {inds}\n")
    md = "\n".join(out)
    outdir = os.path.join(ROOT, "dashboard", "briefs")
    os.makedirs(outdir, exist_ok=True)
    mdpath = os.path.join(outdir, "living_brief.md")
    with open(mdpath, "w") as f:
        f.write(md)
    # optional HTML (nice for linking) if pandoc is around
    try:
        subprocess.run(["pandoc", mdpath, "-o", os.path.join(outdir, "living_brief.html"),
                        "-s", "--metadata", "title=Living Brief"],
                       check=True, capture_output=True)
    except Exception:
        pass
    return mdpath


if __name__ == "__main__":
    print("Wrote", build())
