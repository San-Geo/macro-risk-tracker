"""Generate a readable FRAMEWORK.md from config/framework.yaml + config/stories.yaml.

Run:  python src/build_framework.py
This is documentation only; the agent reads the YAML, not the markdown.
"""
import os
import yaml

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)


def main():
    with open(os.path.join(ROOT, "config", "framework.yaml")) as f:
        fw = yaml.safe_load(f).get("indicators", {})
    with open(os.path.join(ROOT, "config", "stories.yaml")) as f:
        stories = yaml.safe_load(f)["stories"]

    # map indicator_id -> (story name, set, label, weight, thresholds)
    meta = {}
    for s in stories:
        for ind in s.get("indicators", []):
            meta[ind["id"]] = {
                "story": s["name"], "set": s["set"], "label": ind.get("label", ind["id"]),
                "good": ind.get("good"), "warn": ind.get("warn"), "weight": ind.get("weight"),
                "source": ind.get("source", ""),
            }

    out = []
    out.append("# Indicator Rating Framework\n")
    out.append("This is the evidence-based rubric the automated agent follows when it rates each "
               "judgment indicator. The agent never invents a score: it searches authoritative "
               "sources for the **current** status, maps that evidence onto the fixed rubric below, "
               "and logs its reasoning and links for every rating. The deterministic engine then "
               "turns the ratings into 1\u201310 threat levels. Humans can override any value at any "
               "time (see *Overriding the agent*).\n")
    out.append("## How a rating becomes a threat level\n")
    out.append("- **Band indicators** are rated **0 = benign, 1 = watch, 2 = stress** per the rubric.\n"
               "- **Value indicators** are the latest published number; the story's `good`/`warn` "
               "thresholds in `stories.yaml` convert that number into a band.\n"
               "- Each band becomes a small +/- nudge on the story's base level (weighted), so the "
               "final 1\u201310 level moves only as far as the evidence justifies.\n"
               "- **Market indicators** (copper, oil, VIX, MOVE) are *not* agent-rated \u2014 they come "
               "from live price feeds.\n")
    out.append("## Trust & safety design\n")
    out.append("1. **Grounded** \u2014 every rating must come from a live web search of named sources.\n"
               "2. **Auditable** \u2014 value, confidence, a one-line rationale, and source URLs are "
               "logged to `data/agent_assessments.json` for every indicator, every run.\n"
               "3. **Conservative** \u2014 a low-confidence result never flips the number; it keeps the "
               "prior value and is flagged for human review.\n"
               "4. **Human-final** \u2014 anything you pin in `manual_input.csv` overrides the agent.\n")
    out.append("## Overriding the agent\n")
    out.append("Open `manual_input.csv` and put a number in the `value` column for any indicator to "
               "**pin** it; leave it blank to let the agent decide. Band indicators take 0/1/2; value "
               "indicators take the raw number. Pinned indicators are skipped by the agent (and noted "
               "as overridden in the audit log).\n")
    out.append("---\n")

    by_set = {1: [], 2: [], 3: []}
    for ind_id, spec in fw.items():
        m = meta.get(ind_id, {})
        by_set.get(m.get("set", 1), by_set[1]).append((ind_id, spec, m))

    set_titles = {1: "Set 1 \u2014 Hidden leverage", 2: "Set 2 \u2014 Extend & pretend",
                  3: "Set 3 \u2014 Chokepoints"}
    for set_no in (1, 2, 3):
        out.append(f"## {set_titles[set_no]}\n")
        for ind_id, spec, m in by_set[set_no]:
            kind = spec.get("type", "band")
            out.append(f"### {m.get('label', ind_id)}  \n")
            out.append(f"*Story:* {m.get('story','')}  ")
            out.append(f"*Indicator id:* `{ind_id}`  ")
            out.append(f"*Type:* {kind}  ")
            if kind == "value" and m.get("good") is not None:
                out.append(f"*Bands from thresholds:* good \u2264 {m['good']}, warn \u2248 {m['warn']}  ")
            if m.get("weight") is not None:
                out.append(f"*Weight on the meter:* {m['weight']}  ")
            out.append("")
            out.append(f"**Rubric.** {spec.get('rubric','')}\n")
            out.append(f"**What the agent searches.** {spec.get('query','')}\n")
            srcs = spec.get("sources", [])
            if srcs:
                out.append("**Authoritative sources.** " + ", ".join(srcs) + "\n")
        out.append("")

    path = os.path.join(ROOT, "FRAMEWORK.md")
    with open(path, "w") as f:
        f.write("\n".join(out))
    print(f"Wrote {path} ({len(fw)} indicators documented).")


if __name__ == "__main__":
    main()
