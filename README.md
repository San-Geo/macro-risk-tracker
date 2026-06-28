# Global Macro Risk Tracker

A small, auditable daily tracker for the 21 stories in the Global Macro Intelligence Briefs
(Sets 1, 2 & 3). It reads each story's watchlist indicators, recomputes a **1–10 threat
level** with a transparent rules-based formula, writes a short **daily brief**, and updates
two things you can open:

- **`output/macro_risk_tracker.xlsx`** — a formula-driven Excel model you can edit.
- **`dashboard/index.html`** — a simple webpage (deployable free via GitHub Pages).

> Design principle: **rules move the meter, AI only writes the words, you keep the final say.**
> The scoring is deterministic and visible; the optional AI step only narrates the moves the
> formula already made. This keeps the numbers trustworthy and auditable.

---

## How the score works (plain version)

Each story has a human-set **base level** (the analyst anchor from the brief). Each indicator
is sorted into a **band** — 0 benign / 1 watch / 2 stress — using its direction and two
thresholds (`good`, `warn`). Then:

```
delta       = weight × (current_band − baseline_band) / 2
story level  = clamp( base_level + Σ deltas , 1 , 10 )
```

So live data nudges the anchor up or down, and you can see exactly which indicator moved it.
Everything lives in **`config/stories.yaml`** — edit thresholds, weights, or add indicators there.

---

## Setup in stages (start at Stage 0 — it works in 30 seconds)

### Stage 0 — run it offline, today (no keys, no network)
```bash
pip install -r requirements.txt
python src/main.py --offline --no-ai
```
This uses the baseline + `manual_input.csv` values and produces the spreadsheet, `latest.json`,
and the daily log. To view the webpage locally:
```bash
cd dashboard && python -m http.server 8000   # then open http://localhost:8000
```

### Stage 1 — live market data (still no key)
```bash
python src/main.py --no-ai
```
Pulls the daily indicators from **FRED** (keyless CSV) and **Yahoo** (keyless): SOFR/EFFR,
high-yield & IG spreads, the broad dollar index, real yields, unemployment, mortgage
delinquency, OAT–Bund, plus MOVE, USD/JPY, USD/CNY, and gold. Anything it can't fetch quietly
falls back to the baseline and is marked `(baseline)`.

### Stage 2 — AI-written daily brief (needs a key)
```bash
cp .env.example .env        # then paste your ANTHROPIC_API_KEY into .env
export $(cat .env | xargs)  # or use your shell's env loader
python src/main.py
```
Uses a cheap model (Haiku) to write a 120–180 word brief from the computed numbers. Without a
key it writes a clear templated summary instead — both are fine.

### Stage 3 — automate it daily + publish the page
Push this folder to a GitHub repo. The included **`.github/workflows/daily.yml`** runs every
weekday after the US close, commits the updated data, and (optionally) deploys `dashboard/` to
**GitHub Pages**. Add your `ANTHROPIC_API_KEY` under *Settings → Secrets → Actions*. Enable
Pages under *Settings → Pages → Build and deployment → GitHub Actions*. That's your live page.

---

## Updating the judgement / slow-data indicators

Many indicators have no clean free feed (CMBS office delinquency, rare-earth licensing, BNPL
trends, COFER reserve share, policy events). Update those in **`manual_input.csv`** — the event
ones use a simple 0/1/2 scale. Manual values always override fetched ones. Reviewing these
weekly (and sanity-checking any level change) is the human-in-the-loop step.

---

## Files

```
config/stories.yaml      the backbone: stories, indicators, thresholds, weights, baselines
manual_input.csv         your weekly inputs for no-feed indicators
src/fetch.py             keyless FRED + Yahoo fetch, graceful fallback
src/score.py             the deterministic 1–10 scoring engine
src/narrative.py         optional Claude brief + templated fallback
src/report.py            writes JSON, history.csv, the Excel model, dashboard data
src/main.py              orchestrator (flags: --offline, --no-ai, --date)
dashboard/index.html     the webpage (reads latest.json)
output/macro_risk_tracker.xlsx   generated Excel model (Dashboard / Indicators / Log / Method)
data/history.csv         append-only daily log
.github/workflows/daily.yml      the daily scheduler
```

## Caveats
- Thresholds are sensible **starting points** — calibrate them to your own judgement.
- Cadences differ: market indicators truly move daily; fundamentals are monthly/quarterly;
  policy items are event-driven. The tracker marks anything not freshly updated.
- Informational analysis only — **not investment, legal, or financial advice.**

## Automated rating agent (optional)
`src/agent.py` can rate the judgment indicators for you: it web-searches the current status,
classifies it against the rubric in `config/framework.yaml`, and logs reasoning + sources to
`data/agent_assessments.json`. Low-confidence calls are held back; `manual_input.csv` overrides
always win. Run locally with `python src/main.py --agent` (needs `ANTHROPIC_API_KEY`), or let the
GitHub workflow run it weekly. Human-readable rubric: `FRAMEWORK.md` (regenerate with
`python src/build_framework.py`). See `SETUP_GUIDE.md` Part 4.

## Alerts & CI (Phase 2)
`src/alerts.py` sends a notification only when a story or the overall level crosses a risk band
(Low/Moderate/Elevated/High/Severe) vs the previous run. Configure any of: `ALERT_WEBHOOK_URL`
(Discord/Slack), `TELEGRAM_BOT_TOKEN`+`TELEGRAM_CHAT_ID`, or SMTP email. `ALERT_MIN_LEVEL` tunes
sensitivity. Test with `python src/main.py --test-alert`. `tests/selftest.py` validates the config
(baseline-band integrity, fields, determinism) on every push and before each daily run.

## Backtest & methodology (Phase 4)
`src/backtest.py` replays documented 2020 & 2022 market history through the engine (sample mode) or
real history (`--live`), writing `dashboard/backtest.json` for the dashboard's validation panel — only
market indicators vary; judgment ones are held at baseline (partial validation). `METHODOLOGY.md` is
the versioned methodology + limitations. The agent cross-checks high-weight indicators and flags
disagreement (`AGENT_CROSSCHECK_MIN_WEIGHT`, optional `AGENT_MODEL_2`).
