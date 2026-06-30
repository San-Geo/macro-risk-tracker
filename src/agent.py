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


def load_ind_sets():
    """{indicator_id: set_number} from stories.yaml, for domain routing."""
    try:
        with open(os.path.join(ROOT, "config", "stories.yaml")) as f:
            cfg = yaml.safe_load(f)
        return {ind["id"]: s.get("set")
                for s in cfg["stories"] for ind in s["indicators"]}
    except Exception:
        return {}


def load_domains():
    """{set_number: {label, framing, authorities}} from config/domains.yaml."""
    try:
        with open(os.path.join(ROOT, "config", "domains.yaml")) as f:
            return (yaml.safe_load(f) or {}).get("domains", {}) or {}
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


def _salvage_fields(text):
    """Last resort when the JSON won't parse (usually a raw double-quote embedded in
    the 'fact' prose). The load-bearing 'value' sits first in the schema and is a bare
    number, so a targeted regex recovers the SCORE even when the prose is broken -
    the read stays usable instead of being discarded."""
    out = {}
    m = re.search(r'"value"\s*:\s*(-?\d+(?:\.\d+)?)', text)
    if m:
        out["value"] = float(m.group(1))
    m = re.search(r'"confidence"\s*:\s*"?(low|medium|high)"?', text, re.I)
    if m:
        out["confidence"] = m.group(1).lower()
    m = re.search(r'"as_of"\s*:\s*"([^"]+)"', text)
    if m:
        out["as_of"] = m.group(1)
    keys = "value|confidence|as_of|fact|rationale|dissent|sources"
    for fld in ("fact", "rationale"):
        m = re.search(r'"%s"\s*:\s*"(.*?)"\s*,\s*"(?:%s)"\s*:' % (fld, keys), text, re.DOTALL)
        if m:
            out[fld] = m.group(1).replace('"', "'")
    if "value" in out:
        out["parse"] = "repaired"
    return out


def _extract_json(text):
    text = text.strip()
    text = re.sub(r"^```(json)?|```$", "", text, flags=re.MULTILINE).strip()
    block = text
    m = re.search(r"\{.*\}", text, flags=re.DOTALL)
    if m:
        block = m.group(0)
    for candidate in (text, block):
        try:
            return json.loads(candidate)
        except Exception:
            pass
    # light repair: drop trailing commas, normalise smart quotes, then retry
    repaired = re.sub(r",\s*([}\]])", r"\1", block)
    repaired = (repaired.replace("\u201c", '"').replace("\u201d", '"')
                        .replace("\u2018", "'").replace("\u2019", "'"))
    try:
        return json.loads(repaired)
    except Exception:
        pass
    # field salvage guarantees the score survives a broken-quote response
    salv = _salvage_fields(text)
    if "value" in salv:
        return salv
    raise ValueError("could not parse or salvage agent JSON")


def _coerce(value, kind):
    if value is None:
        return None
    if kind == "band":
        return max(0, min(2, int(round(float(value)))))
    return float(value)


ASI1_URL = "https://api.asi1.ai/v1/chat/completions"


def _build_prompt(spec, date, domain, kind):
    domain = domain or {}
    auth = list(spec.get("authorities") or spec.get("sources") or [])
    auth += [s for s in (domain.get("authorities") or []) if s not in auth]
    sources = ", ".join(auth) or "reputable primary sources"
    framing = domain.get("framing", "").strip()
    framing_line = (framing + "\n\n") if framing else ""
    if kind == "band":
        out_rule = ('Return "value" as the integer 0, 1, or 2 that the rubric '
                    "matches. Do not assign the most severe level (2) without clear evidence.")
    else:
        out_rule = ('Return "value" as a single number: the latest published figure '
                    "in the indicator's natural units (no text, no % sign).")
    return (
        f"You are a macro-risk research agent. Today is {date}. Determine the CURRENT "
        f"real-world status of ONE indicator and classify it STRICTLY by the rubric.\n\n"
        f"{framing_line}"
        f"INDICATOR: {spec.get('query', '')}\n"
        f"RUBRIC: {spec.get('rubric','')}\n"
        f"PREFER THESE PRIMARY SOURCES: {sources}\n\n"
        "Research the most recent authoritative information BEFORE answering (use web "
        "search/tools if available). Base the rating ONLY on what you actually find; do not guess.\n"
        "Work in two separate steps so fact and interpretation never blur:\n"
        " (1) FACT: pin down the single load-bearing measured fact - the number or "
        "observable status, with its PRIMARY source and date. Quote it plainly.\n"
        " (2) MAP: apply the rubric to that fact mechanically.\n"
        "If authoritative sources MATERIALLY DISAGREE (different numbers, or different "
        "characterisations of the same event), do NOT silently pick one: put your best "
        "single reading in \"value\" and record each competing reading in \"dissent\" "
        "with its source. Leave \"dissent\" as [] only when sources broadly agree.\n"
        f"{out_rule} If you cannot find clear, recent evidence, set confidence to \"low\".\n\n"
        "Respond with ONLY a single-line, valid, minified JSON object and nothing else. "
        "Inside string values use single quotes only - NEVER the double-quote character - "
        "so the JSON always parses:\n"
        '{"value": <number>, "confidence": "low|medium|high", '
        '"as_of": "<YYYY-MM-DD or period>", '
        '"fact": "<the load-bearing fact verbatim, with primary source + date>", '
        '"rationale": "<=2 sentences: how that fact maps to the rubric>", '
        '"dissent": [{"view": "<competing reading and who reports it>", "source": "<url>"}], '
        '"sources": ["<url>", ...]}'
    )


def _post_json(req, timeout=120):
    last = None
    for attempt in range(4):
        try:
            with urllib.request.urlopen(req, timeout=timeout) as r:
                return json.loads(r.read().decode())
        except urllib.error.HTTPError as e:
            if e.code in (429, 529, 503) and attempt < 3:
                time.sleep(2 ** attempt + 1)
                continue
            raise
        except (urllib.error.URLError, TimeoutError) as e:
            last = e
            if attempt < 3:
                time.sleep(2 ** attempt + 1)
                continue
            raise
    if last:
        raise last
    raise RuntimeError("no response from API")


def _call_anthropic(prompt, model, api_key):
    body = json.dumps({
        "model": model or AGENT_MODEL, "max_tokens": 1400,
        "tools": [{"type": "web_search_20250305", "name": "web_search", "max_uses": 4}],
        "messages": [{"role": "user", "content": prompt}],
    }).encode()
    req = urllib.request.Request(
        API_URL, data=body,
        headers={"content-type": "application/json", "x-api-key": api_key,
                 "anthropic-version": "2023-06-01"})
    data = _post_json(req)
    return "".join(b.get("text", "") for b in data.get("content", []) if b.get("type") == "text")


def _call_asi1(prompt, model, api_key):
    """ASI1 (asi1.ai) is an OpenAI-compatible, agentic endpoint - a genuinely
    independent provider for the cross-check. It does its own research; there is no
    Anthropic-style web_search tool to pass."""
    body = json.dumps({
        "model": model or "asi1", "max_tokens": 1500, "temperature": 0, "stream": False,
        "messages": [{"role": "user", "content": prompt}],
    }).encode()
    req = urllib.request.Request(
        ASI1_URL, data=body,
        headers={"Content-Type": "application/json", "Accept": "application/json",
                 "Authorization": f"Bearer {api_key}"})
    data = _post_json(req)
    ch = (data.get("choices") or [{}])[0]
    return (ch.get("message") or {}).get("content", "") or ""


def _finalize(parsed, kind):
    parsed["value"] = _coerce(parsed.get("value"), kind)
    parsed.setdefault("confidence", "low")
    parsed.setdefault("rationale", "")
    parsed.setdefault("sources", [])
    parsed.setdefault("fact", "")
    dissent = parsed.get("dissent") or []
    if not isinstance(dissent, list):
        dissent = []
    parsed["dissent"] = dissent
    if dissent and str(parsed.get("confidence", "")).lower() == "high":
        parsed["confidence"] = "medium"
    parsed["type"] = kind
    return parsed

def assess_one(ind_id, spec, api_key, date, prior=None, model=None, domain=None, provider="anthropic"):
    kind = spec.get("type", "band")
    prompt = _build_prompt(spec, date, domain, kind)
    if provider == "asi1":
        text = _call_asi1(prompt, model or "asi1", api_key)
    else:
        text = _call_anthropic(prompt, model, api_key)
    return _finalize(_extract_json(text), kind)


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
    ind_sets = load_ind_sets()
    domains = load_domains()
    xcheck_min = float(os.environ.get("AGENT_CROSSCHECK_MIN_WEIGHT", "1.5") or 1.5)
    # Second-opinion routing for the cross-check. AGENT_MODEL_2 names the model;
    # an "asi1*" model uses the ASI1 provider (key in ASI1_API_KEY) for genuine
    # cross-provider independence. Anything else stays on Anthropic.
    # Tolerate common mis-entries: a value pasted as "AGENT_MODEL_2=asi1" (KEY=value
    # form) or wrapped in quotes/backticks/spaces -> reduce to just the model name.
    m2 = (os.environ.get("AGENT_MODEL_2") or "").strip().strip("`\"'").strip()
    if "=" in m2:
        m2 = m2.split("=")[-1].strip().strip("`\"'").strip()
    if m2 and m2.lower().startswith("asi1"):
        asi1_key = os.environ.get("ASI1_API_KEY")
        if asi1_key:
            xprovider, xkey, xmodel = "asi1", asi1_key, m2
        else:
            xprovider, xkey, xmodel = "anthropic", api_key, None
            print("  (AGENT_MODEL_2 is asi1 but ASI1_API_KEY is unset; "
                  "cross-check falls back to the primary model)")
    elif m2:
        xprovider, xkey, xmodel = "anthropic", api_key, m2
    else:
        xprovider, xkey, xmodel = "anthropic", api_key, None

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
        domain = domains.get(ind_sets.get(ind_id)) or {}
        a = assess_one(ind_id, spec, api_key, date, prior, domain=domain)
        if domain.get("label"):
            a["domain"] = domain["label"]
        # Cross-check the highest-weight indicators with a second independent read.
        if weights.get(ind_id, 0) >= xcheck_min and a.get("value") is not None:
            try:
                b = assess_one(ind_id, spec, xkey, date, prior, model=xmodel,
                               domain=domain, provider=xprovider)
                disagree = _disagree(a.get("value"), b.get("value"), spec.get("type", "band"))
                checker = (xmodel or AGENT_MODEL) if xprovider == "anthropic" else xmodel
                a["crosscheck"] = {"second_value": b.get("value"), "agree": not disagree,
                                   "by": checker, "provider": xprovider}
                if disagree:
                    a["confidence"] = "low"  # demote -> handled conservatively below
                    a["crosscheck"]["note"] = "two reads disagreed"
                    a["rationale"] = ((a.get("rationale", "") +
                        f" [cross-check ({checker}): two reads disagreed ({a.get('value')} vs "
                        f"{b.get('value')}); held for review]").strip())
            except Exception as e:
                a["crosscheck"] = {"error": str(e), "provider": xprovider}
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
        if a.get("dissent"):
            review.append(ind_id)  # sources disagree -> surface the annotated divergence
        a["prior"] = (prior or {}).get("value")
        assessments[ind_id] = a

    log = {"generated": datetime.datetime.now(datetime.timezone.utc).isoformat(), "date": date,
           "model": AGENT_MODEL, "assessments": assessments, "review_flags": sorted(set(review)),
           "crosscheck": {"provider": xprovider, "model": (xmodel or AGENT_MODEL),
                          "independent": xprovider != "anthropic"}}
    os.makedirs(os.path.dirname(LOG_PATH), exist_ok=True)
    with open(LOG_PATH, "w") as f:
        json.dump(log, f, indent=2)
    return values, log
