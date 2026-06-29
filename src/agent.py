"""The grounded rating agent.

For each judgment indicator defined in config/framework.yaml it:
  1. calls Claude with the server-side web_search tool to find CURRENT status,
  2. classifies strictly per the rubric (band 0/1/2, or a latest value),
  3. records value + confidence + rationale + sources to data/agent_assessments.json.

Trust model (why this is safe):
  - The agent never invents a free-form score. It maps real, searched evidence
    onto a fixed, human-written rubric (config/framework.yaml).
  - Every rating is logged with its reasoning and source links -> fully auditable.
  - Low-confidence calls do NOT flip the number; they retain the prior value and
    are flagged for human review.
  - Human overrides (manual_input.csv) are applied AFTER the agent and always win.
  - The deterministic engine still does all the math; the agent only sets inputs.

No SDK; uses stdlib urllib like narrative.py.
"""
import json, os, re, time, urllib.request, urllib.error, datetime
import concurrent.futures
import yaml

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
AGENT_MODEL = os.environ.get("AGENT_MODEL", "claude-sonnet-4-6")
LOG_PATH = os.path.join(ROOT, "data", "agent_assessments.json")
FRAMEWORK_PATH = os.path.join(ROOT, "config", "framework.yaml")
API_URL = "https://api.anthropic.com/v1/messages"


def load_framework():
    with open(FRAMEWORK_PATH) as f:
        return yaml.safe_load(f).get("indicators", {})


def load_log():
    if os.path.exists(LOG_PATH):
        try:
            with open(LOG_PATH) as f:
                return json.load(f)
        except Exception:
            pass
    return {"assessments": {}}


def load_weights():
    """{indicator_id: weight} from stories.yaml, for cross-check targeting."""
    try:
        with open(os.path.join(ROOT, "config", "stories.yaml")) as f:
            cfg = yaml.safe_load(f)
        return {ind["id"]: ind.get("weight", 0)
                for s in cfg["stories"] for ind in s["indicators"]}
    except Exception:
        return {}


def _disagree(a, b, kind, tol=0.2):
    """True if two independent readings differ enough to distrust them."""
    if a is None or b is None:
        return True
    if kind == "band":
        return int(round(a)) != int(round(b))
    if (a > 0) != (b > 0):
        return True
    denom = max(abs(a), abs(b), 1e-9)
    return abs(a - b) / denom > tol


def load_applied_values():
    """Values from the last agent run that were actually applied -> used on
    non-agent days so the agent's judgment persists between refreshes."""
    log = load_log()
    out = {}
    for ind_id, a in log.get("assessments", {}).items():
        if a.get("applied") and a.get("value") is not None:
            out[ind_id] = a["value"]
    return out


def _extract_json(text):
    text = text.strip()
    text = re.sub(r"^```(json)?|```$", "", text, flags=re.MULTILINE).strip()
    try:
        return json.loads(text)
    except Exception:
        m = re.findall(r"\{.*\}", text, flags=re.DOTALL)
        if m:
            return json.loads(m[-1])
        raise


def _coerce(value, kind):
    if value is None:
        return None
    if kind == "band":
        return max(0, min(2, int(round(float(value)))))
    return float(value)


def assess_one(ind_id, spec, api_key, date, prior=None, model=None):
    kind = spec.get("type", "band")
    sources = ", ".join(spec.get("sources", [])) or "reputable primary sources"
    if kind == "band":
        out_rule = ('Return "value" as the integer 0, 1, or 2 that the rubric '
                    "matches. Do not assign the most severe level (2) without clear evidence.")
    else:
        out_rule = ('Return "value" as a single number: the latest published figure '
                    "in the indicator's natural units (no text, no % sign).")
    prompt = (
        f"You are a macro-risk research agent. Today is {date}. Determine the CURRENT "
        f"real-world status of ONE indicator and classify it STRICTLY by the rubric.\n\n"
        f"INDICATOR: {spec.get('query', ind_id)}\n"
        f"RUBRIC: {spec.get('rubric','')}\n"
        f"PREFER THESE SOURCES: {sources}\n\n"
        "Use the web_search tool to find the most recent authoritative information "
        "BEFORE answering. Base the rating only on what you actually find; do not guess. "
        f"{out_rule} If you cannot find clear, recent evidence, set confidence to \"low\".\n\n"
        "Respond with ONLY this JSON (no other text):\n"
        '{"value": <number>, "confidence": "low|medium|high", '
        '"as_of": "<YYYY-MM-DD or period>", '
        '"rationale": "<=2 sentences citing what you found>", "sources": ["<url>", ...]}'
    )
    body = json.dumps({
        "model": model or AGENT_MODEL,
        "max_tokens": 1024,
        "tools": [{"type": "web_search_20250305", "name": "web_search", "max_uses": 4}],
        "messages": [{"role": "user", "content": prompt}],
    }).encode()
    req = urllib.request.Request(
        API_URL, data=body,
        headers={"content-type": "application/json", "x-api-key": api_key,
                 "anthropic-version": "2023-06-01"})
    data = None
    for attempt in range(4):
        try:
            with urllib.request.urlopen(req, timeout=120) as r:
                data = json.loads(r.read().decode())
            break
        except urllib.error.HTTPError as e:
            # back off and retry on rate-limit (429) / overloaded (529); re-raise anything else
            if e.code in (429, 529) and attempt < 3:
                time.sleep(2 ** attempt + 1)
                continue
            raise
    if data is None:
        raise RuntimeError("no response from API")
    text = "".join(b.get("text", "") for b in data.get("content", []) if b.get("type") == "text")
    parsed = _extract_json(text)
    parsed["value"] = _coerce(parsed.get("value"), kind)
    parsed.setdefault("confidence", "low")
    parsed.setdefault("rationale", "")
    parsed.setdefault("sources", [])
    parsed["type"] = kind
    return parsed


def _in_range(value, spec):
    """Plausibility gate. Returns (ok, reason). Band values must be 0-2; value
    indicators must fall within the [min,max] declared in framework.yaml (if any)."""
    if value is None:
        return True, ""
    if str(spec.get("type", "band")) == "band":
        if value < 0 or value > 2:
            return False, f"band reading {value} is outside 0-2"
        return True, ""
    lo, hi = spec.get("min"), spec.get("max")
    if lo is not None and value < lo:
        return False, f"reading {value} below the plausible floor ({lo})"
    if hi is not None and value > hi:
        return False, f"reading {value} above the plausible ceiling ({hi})"
    return True, ""


def run_agent(framework, api_key, date, overrides=None, only_ids=None, pause=0.5):
    """Assess each framework indicator. Returns (values_to_apply, log_dict)."""
    overrides = overrides or set()
    prior_log = load_log().get("assessments", {})
    assessments, values, review = {}, {}, []
    weights = load_weights()
    xcheck_min = float(os.environ.get("AGENT_CROSSCHECK_MIN_WEIGHT", "1.5") or 1.5)
    model2 = os.environ.get("AGENT_MODEL_2")  # optional second model for the check

    # 1) Overrides and carry-forwards are instant; only the rest need a (slow) web call.
    to_assess = []
    for ind_id, spec in framework.items():
        if only_ids and ind_id not in only_ids:
            if ind_id in prior_log:
                assessments[ind_id] = prior_log[ind_id]
                if prior_log[ind_id].get("applied") and prior_log[ind_id].get("value") is not None:
                    values[ind_id] = prior_log[ind_id]["value"]
            continue
        if ind_id in overrides:
            assessments[ind_id] = {"value": None, "confidence": "n/a", "applied": False,
                                   "note": "pinned by human override (manual_input.csv)",
                                   "rationale": "", "sources": [], "as_of": date}
            continue
        to_assess.append(ind_id)

    # 2) Assess concurrently - each indicator is an independent web-search call, so a small
    #    worker pool cuts wall-time several-fold. Tune politeness with AGENT_CONCURRENCY.
    def _work(ind_id):
        spec = framework[ind_id]
        prior = prior_log.get(ind_id)
        a = assess_one(ind_id, spec, api_key, date, prior)
        # Cross-check the highest-weight indicators with a second independent read.
        if weights.get(ind_id, 0) >= xcheck_min and a.get("value") is not None:
            try:
                b = assess_one(ind_id, spec, api_key, date, prior, model=model2)
                disagree = _disagree(a.get("value"), b.get("value"), spec.get("type", "band"))
                a["crosscheck"] = {"second_value": b.get("value"), "agree": not disagree}
                if disagree:
                    a["confidence"] = "low"  # demote -> handled conservatively below
                    a["crosscheck"]["note"] = "two reads disagreed"
                    a["rationale"] = ((a.get("rationale", "") +
                        f" [cross-check: two reads disagreed ({a.get('value')} vs "
                        f"{b.get('value')}); held for review]").strip())
            except Exception as e:
                a["crosscheck"] = {"error": str(e)}
        return a

    workers = max(1, int(os.environ.get("AGENT_CONCURRENCY", "4") or 4))
    results = {}
    if to_assess:
        with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as ex:
            futs = {ex.submit(_work, iid): iid for iid in to_assess}
            for fut in concurrent.futures.as_completed(futs):
                iid = futs[fut]
                try:
                    results[iid] = fut.result()
                except Exception as e:
                    results[iid] = {"__error__": str(e)}

    # 3) Apply confidence gating in framework order (deterministic, no network).
    sanity_on = os.environ.get("AGENT_SANITY", "1") not in ("0", "false", "no")
    for ind_id in to_assess:
        prior = prior_log.get(ind_id)
        a = results.get(ind_id)
        if a is None or "__error__" in a:
            keep = (prior or {}).get("value")
            assessments[ind_id] = {"value": keep, "confidence": "error", "applied": keep is not None,
                                   "note": f"agent error, kept prior: {(a or {}).get('__error__', 'no result')}",
                                   "rationale": "", "sources": [], "as_of": date, "prior": keep}
            if keep is not None:
                values[ind_id] = keep
            review.append(ind_id)
            continue
        # Sanity range check: a reading outside plausible bounds is almost certainly a
        # bad parse/hallucination, so auto-correct by holding the last trusted value.
        if sanity_on:
            ok, why = _in_range(a.get("value"), framework[ind_id])
            if not ok:
                a["out_of_range"] = True
                a["confidence"] = "low"  # routes into the hold-at-last-trusted-value path below
                a["rationale"] = ((a.get("rationale", "") +
                    f" [sanity check: {why}; auto-held at last trusted value]").strip())
        conf = str(a.get("confidence", "low")).lower()
        if conf == "low" or a.get("value") is None:
            # don't flip on weak evidence: retain prior applied value if we have one
            if prior and prior.get("value") is not None:
                a["value"], a["applied"] = prior["value"], True
                a["note"] = "low confidence; retained prior value"
            else:
                a["applied"] = False
                a["note"] = "low confidence; left at baseline"
            review.append(ind_id)
        else:
            a["applied"] = True
            a["note"] = "applied"
            if prior and prior.get("value") is not None and a["value"] != prior["value"]:
                review.append(ind_id)  # surface every change for the human to glance at
        if a.get("applied") and a.get("value") is not None:
            values[ind_id] = a["value"]
        a["prior"] = (prior or {}).get("value")
        assessments[ind_id] = a

    log = {"generated": datetime.datetime.now(datetime.timezone.utc).isoformat(), "date": date,
           "model": AGENT_MODEL, "assessments": assessments, "review_flags": sorted(set(review))}
    os.makedirs(os.path.dirname(LOG_PATH), exist_ok=True)
    with open(LOG_PATH, "w") as f:
        json.dump(log, f, indent=2)
    return values, log
