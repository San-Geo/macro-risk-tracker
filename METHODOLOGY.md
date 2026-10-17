# Methodology

**Version 1.5 — 2026.** This document explains exactly how the Global Macro Risk Tracker turns
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
3. **Story score and level.** `score = clamp( base_level + Σ deltas , 1, 10 )`, kept unrounded.
   The displayed level is that score rounded **half up** (6.5 → 7). Before scoring method 3.0 the
   code used Python's round-half-to-even, which sent 6.5 to 6 but 7.5 to 8; because weights come in
   halves, 47% of past story-days sat exactly on a .5, so the rule mattered. The `base_level` is the
   expert-anchored starting point (June 2026).
4. **Bands of the level.** 1–2 Low, 3–4 Moderate, 5–6 Elevated, 7–8 High, 9–10 Severe.
5. **Aggregates.** All aggregates use the unrounded story scores and round once at the end.
   Each set's score is the average of its stories. The overall is `0.5 × average of all 21 +
   0.5 × average of the worst 7 + breadth premium`, where the premium is `0.3 × (H − 2)` capped at
   1.5 and `H` counts stories at High smoothly (0 at a score of 6.0 or below, 1 at 7.0 or above,
   proportional between). One indicator step can no longer jump the overall by a fixed amount.
   Comparisons with earlier days use the same rule, so the rounding change never shows as a move.

A key invariant, enforced by the CI self-test: each indicator's `baseline_band` must equal the band
its `baseline_value` maps to. This guarantees the day-zero levels reproduce the published reports.

## 3. Two kinds of indicators

- **Market / data indicators** (e.g. VIX, the MOVE index, SOFR–EFFR spread, HY/IG credit spreads,
  WTI, copper, unemployment) are fetched automatically from public feeds. They update every run and
  require no judgment.
- **Judgment indicators** (e.g. Taiwan tension, the status of the Strait of Hormuz, China export
  curbs, government stability) have no clean numeric feed. These are set by the rating agent against
  a fixed rubric (Section 4), or pinned by a human.
- **Feed safeguards.** If a feed fails, its last good value is carried forward with its real date
  (it used to fall back to the June starting value, which reads as "normal"). A value outside its
  plausible range, or an implausible one-day jump, is held until the next run confirms it
  (`config/feed_checks.yaml`). The France spread also gets a weekly agent reading; the newer of that
  and the OECD monthly figure is used.
- **Measured where possible.** The two Strait of Hormuz / Red Sea ratings are set from the IMF's PortWatch
  ship counts (AIS transits): the latest 7-day average is compared with the same month's normal, and
  below 25% of normal the strait is rated closed by rule, 25-80% contested. The agent only judges whether
  recent attacks make an otherwise near-normal strait "contested", and is the fallback if the feed is
  unavailable or older than three weeks. Caveats: PortWatch updates weekly (2-9 days behind), and ships
  that switch off their transponders - or oil moved by pipeline - are not counted, so it measures
  shipping through the strait, not oil supply.

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
- **Continuous, not amnesiac** — the agent sees last week's applied reading and its evidence, and may
  change it only for a new, dated event or a stated correction (the reason is logged). The independent
  cross-check never sees that prior reading, so it stays a blind second opinion.
- **Reversal confirmation** — a judgment rating that would flip straight back to its previous value within
  three weeks is held until a second consecutive weekly read (or an agreeing independent cross-check)
  confirms it. Replayed over the first 18 weekly runs, this removes all 18 back-and-forth flips at the
  cost of delaying a genuine reversal by one week.
- **Measured anchors** — where a judgment can rest on a measurement, the rubric uses it (e.g. a strait is
  "closed" when commercial transits are below 25% of the pre-crisis baseline - talks and escorts alone do
  not change the rating), and event-based ratings only count events inside a stated recent window.
- **Evidence grade, not self-reported confidence** — each agent read is graded A/B/C by rule: an
  official, data-provider or major-press source (`config/sources.yaml`), evidence within the
  staleness budget, the number verified at its cited source, and an agreeing second read. A value
  change backed only by other sources is flagged for a glance. The scout runs once a week with the
  agent, and its items expire after 30 days.
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
- The overall blends the average with the worst third of stories, so one severe story moves it only
  modestly — always read the stories.
- Most of each story's level is its June 2026 starting point; the page shows how much comes from the
  starting level, from judgment and from data. The backtest replays only the data part.
- This is informational analysis only, not investment, legal, tax, or financial advice.

## 9. Track record and outcome grading

Every time a story reaches High (7+), an **episode** opens automatically; it closes after five
consecutive runs below High, so a one-day dip is not mistaken for an outcome. After a 30-day
follow-through window, each closed episode is graded:

- **materialized** - the specific outcome the story warns about happened inside the window;
- **contained** - real, measurable stress appeared but was absorbed before it became that outcome;
- **faded** - the pressure receded without measurable stress.

A materialized grade also records **timing**: *called ahead* if the outcome began after the episode
opened, *already under way* if it began before - so the record never overstates foresight.

Grading follows the same contract as scoring: **the AI sets inputs, the rules decide.** Each story has
concrete, pre-published tests in `config/grading.yaml` (e.g. "the FAO Food Price Index rises 10% or more
year-on-year"). Two independent agents research the episode and mark each test met or not met, citing a
dated source for every "met". Code then computes the grade from those test results. A grade is applied
automatically only when both agents' results produce the same grade with at least medium confidence;
otherwise the owner decides. The owner can also grade or override any episode, and owner grades are
never overwritten. Episodes of a week or less that were opened by a signal which flipped straight back
are marked **brief crossing**, so base-rate analysis can treat them as boundary noise.

**Misses count too.** Once a month the grader checks every story that is *below* High against its
own materialized tests for the past 30 days. A test met while the tracker sat below High is logged
as a possible miss; the owner confirms or rejects it. The record therefore shows hits, false alarms
and misses side by side.

## 10. Editions and the archive

**Editions.** The Global Macro Intelligence Brief is published in editions. *When* a new edition is
written is decided by fixed rules in `config/editions.yaml`, checked every day for free from the
tracker's own data: never sooner than 3 months after the last edition; between 3 and 6 months only
on **strong** drift (for example 4 or more stories changing band, or the overall score moving a full
point); between 6 and 12 months on **moderate** drift (2 band changes, 5 level changes, a half-point
overall move or 12 indicator band changes); and always at 12 months. Drift is measured from the
tracker's level on the edition's data date to today, so it reflects the world changing, not
differences of method. In practice this gives roughly quarterly editions in turbulent periods,
semi-annual ones in normal times and annual ones when little moves.

When an edition is due, the edition agent writes a **draft** (`src/edition.py`). Each story is
*rewritten* with fresh research if its level or any of its indicators changed band since the last
edition; otherwise it is *refreshed* with a few exact, sourced edits. Threat levels are the
tracker's, inserted by code; the AI only writes the explanation. Every story is then checked by a
second, independent agent against the tracker's data, and by deterministic guards (structure,
sources present, no securities named, nothing that reads as investment advice). Problems are listed
for the owner. A draft never becomes the current edition automatically: the owner reviews and
publishes it. Spending per edition is estimated and capped.

Corrections to a published edition are issued as numbered revisions with a revision history inside
the document; the first printing is kept.

**Archive.** Every run appends to `data/archive/`: the day's overall, set and story scores (unrounded)
and the daily note (`daily/YYYY-MM.jsonl`), and every weekly agent pass with each indicator's value,
confidence, facts, reasoning, dissent and sources (`agent/YYYY.jsonl`). The living brief is frozen on
the first run of each month (`dashboard/briefs/archive/`). Nothing in the archive is rewritten, so
past editions, snapshots and evidence remain comparable with today's.

## Changelog

- **1.5** - Editions on a data-driven schedule, written as drafts by an agent and published by the
  owner; 2026 Edition revision 1 (factual corrections); permanent archive of daily scores, notes and
  agent evidence; monthly living-brief snapshots.

- **1.4** - Scoring method 3.0 (half-up rounding, unrounded aggregation, smooth breadth premium);
  feed carry-forward and plausibility checks; rule-based evidence grades; weekly scout; monthly
  miss check; the page shows how much of the level is starting point, judgment and data.

- **1.3** - Hormuz / Red Sea ratings set from measured IMF PortWatch transit counts where decisive.

- **1.2** - Rating stability: continuity prompt with logged change reasons, reversal confirmation guard,
  measured or time-windowed rubrics for six indicators that had been flipping week to week.

- **1.1** - Track record grading: published per-story rubric, two-agent automatic grading with
  code-computed grades, timing qualifier, brief-crossing flag, one-week episode close rule.

- **1.0** — Initial published methodology: deterministic scoring, agent rubric + trust model, market
  backtest, cross-checking, data-health and provenance.
