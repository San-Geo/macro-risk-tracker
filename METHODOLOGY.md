# Methodology

**Version 1.0 — 2026.** This document explains exactly how the Global Macro Risk Tracker turns
data and current events into a 1–10 risk level for each story, what the numbers mean, and — just
as importantly — what they do *not* mean. It is meant to be read by a skeptical professional.

## 1. What this is, and what it isn't

**It is** a transparent, rules-based scoring system that combines (a) live market/economic data and
(b) AI-assisted, rubric-bound readings of slow-moving current events, into a comparable 1–10 risk
level per story, with a full audit trail.

**It is not** a statistical model, a forecast, or investment advice. The 1–10 levels are *structured
judgment*: expert-anchored base levels nudged by explicit, weighted indicators. They express "how
much attention does this risk warrant right now," not a probability or a price target. Two informed
people could reasonably disagree on a level by a point or two; that is expected.

## 2. Scoring math (deterministic and auditable)

Every level is produced by fixed arithmetic — no AI sets a number directly.

1. **Indicator band.** Each indicator maps to a band: **0 = benign, 1 = watch, 2 = stress**, using
   a direction and two thresholds (`good`, `warn`). For a "higher-is-worse" indicator, value ≤ good
   → 0, ≤ warn → 1, else 2 (reversed for "lower-is-worse").
2. **Delta.** Each indicator nudges its story by `delta = weight × (band − baseline_band) / 2`. An
   indicator sitting at its baseline contributes zero; weight sets how much a move matters.
3. **Story level.** `level = clamp( base_level + Σ deltas , 1, 10 )`, rounded to an integer. The
   `base_level` is the expert-anchored starting point from the published research.
4. **Bands of the level.** 1–2 Low, 3–4 Moderate, 5–6 Elevated, 7–8 High, 9–10 Severe.
5. **Aggregates.** Each set's score and the overall score are simple averages of story levels.

A key invariant, enforced by the CI self-test: each indicator's `baseline_band` must equal the band
its `baseline_value` maps to. This guarantees the day-zero levels reproduce the published reports.

## 3. Two kinds of indicators

- **Market / data indicators** (e.g. VIX, the MOVE index, SOFR–EFFR spread, HY/IG credit spreads,
  WTI, copper, unemployment) are fetched automatically from public feeds. They update every run and
  require no judgment.
- **Judgment indicators** (e.g. Taiwan tension, the status of the Strait of Hormuz, China export
  curbs, government stability) have no clean numeric feed. These are set by the rating agent against
  a fixed rubric (Section 4), or pinned by a human.

## 4. The rating agent and its trust model

For each judgment indicator the agent: (1) **searches** authoritative sources for the current status;
(2) **classifies** that evidence strictly against a fixed rubric in `config/framework.yaml`
(documented in `FRAMEWORK.md`) — a 0/1/2 band, or the latest published number; (3) **logs** the
value, a confidence level, a one-line rationale, and source links to `data/agent_assessments.json`.

Safeguards that make this trustworthy rather than a black box:
- **Grounded** — ratings must come from a live web search of named sources, not the model's memory.
- **Auditable** — every rating, with its reasoning and sources, is recorded for every run.
- **Conservative** — a low-confidence result never flips the number; it keeps the prior value and is
  flagged for human review.
- **Cross-checked** — the highest-weight indicators are rated twice and any disagreement is treated
  as low-confidence and flagged (Section 6).
- **Human-final** — anything pinned in `manual_input.csv` overrides the agent and is never changed.

## 5. Data sources

Market data: U.S. Treasury/FRED series (St. Louis Fed) and public market quotes (e.g. CBOE VIX, ICE
BofAML MOVE, COMEX/NYMEX futures). Judgment indicators: the authoritative bodies listed per indicator
in `FRAMEWORK.md` (IMF, FAO, IEA, USGS, SEC, the Federal Reserve, central banks, and major
newswires), verified by the agent at rating time. Each indicator on the dashboard shows its as-of
date and a link to its source.

## 6. Agent cross-checking (high-stakes ratings)

Indicators whose weight makes them most able to move a meter are rated **twice** by the agent. If the
two independent readings disagree, the indicator is marked low-confidence and added to the review
queue rather than applied on a single, possibly-wrong reading. This reduces the chance that one bad
search silently moves a level. The threshold weight is configurable (`AGENT_CROSSCHECK_MIN_WEIGHT`).

## 7. Backtest scope and honesty

The backtest replays *documented historical values of the market/data indicators* (e.g. the 2020
COVID dash-for-cash and the 2022 rate/MOVE shock) through the exact live scoring engine. It shows the
rules respond sensibly to real stress — the basis trade and clearinghouse stories climb with VIX and
the MOVE index, credit stories with spreads, the consumer story with unemployment.

**Its limits, stated plainly:** only the market/data indicators are varied. The judgment indicators
have no historical series and are **held at baseline**, so a backtested level reflects *only* the
market-driven component of a story. The backtest therefore validates the engine's *mechanics* on the
part of the system that can be validated; it is a partial, lower-bound check, **not** a claim that the
tracker would have predicted these events. Some indicator→story mappings (e.g. the AI-capex story
proxied by IG spreads) are also anachronistic before the story existed, and should be read as
"the rule responds," not "the risk existed then."

## 8. Limitations

- Levels are judgment, not probability or forecast; treat ±1–2 as noise.
- Thresholds and base levels are calibrated to the 2026 regime and embed the authors' priors.
- The agent can misread a situation; the audit log, low-confidence flagging, cross-checking, and human
  override exist precisely because it is not infallible.
- Public data can be revised, delayed, or briefly unavailable; the data-health line flags when a feed
  has fallen back to baseline.
- Aggregates are unweighted averages and can mask a single severe story — always read the stories.
- This is informational analysis only, not investment, legal, tax, or financial advice.

## Changelog

- **1.0** — Initial published methodology: deterministic scoring, agent rubric + trust model, market
  backtest, cross-checking, data-health and provenance.
