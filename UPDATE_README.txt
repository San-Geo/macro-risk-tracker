UPDATE BUNDLE - preserves history (no data/ folder). DIRECT OFFICIAL FEEDS (audit item #1).
Three previously agent-read numbers are now DIRECT keyless feeds - no AI in the loop:
  jgb30             -> Japan MOF official daily constant-maturity JGB CSV ("MOF")
  stablecoin_supply -> DefiLlama free stablecoins API, total USD-pegged supply $bn ("DefiLlama")
  peg_deviation     -> same DefiLlama call, |price-1| of the LARGEST USD stablecoin ("DefiLlama")
Why: your last run showed the agent EXTRAPOLATING supply ($325bn vs DefiLlama's ~$311bn)
and using 6-day-stale JGB data. Feeds remove hallucination risk, upgrade cadence to daily,
free ~3 agent calls/run, and make the values verifiable by anyone.
Changes:
 - src/fetch.py: mof_jgb_latest (era-date parsing R/H/S, holiday-gap tolerant, fallback
   URLs) + DefiLlama fetchers (one cached HTTP call serves both indicators). All failure
   modes degrade to None -> indicator falls back to baseline + shows on data-health,
   same as every other feed.
 - config/stories.yaml: the 3 indicators now point at the new sources (all daily cadence).
 - config/framework.yaml: their agent rubrics removed (44 remain); header comment restored.
 - src/agent.py: cached agent values are filtered to CURRENT framework indicators, so the
   old agent-rated values for these 3 in your existing agent_assessments.json cannot
   override the live feeds on non-agent days.
 - src/enrich.py + dashboard tooltip: "MOF" and "DefiLlama" provenance with source links.
Data-health now counts 19 live feeds (was 16).
HONEST NOTE: this sandbox has no network, so the two new parsers were validated against
realistic fixtures (exact CSV/JSON shapes, holiday gaps, era dates, missing prices), not
the live endpoints. First scheduled run confirms them; if either endpoint differs, the
indicator harmlessly reads "Baseline" on the data-health line and nothing else breaks.
APPLY: upload src/, config/, and dashboard/. No workflow change.
