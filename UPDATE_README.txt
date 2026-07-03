UPDATE BUNDLE - preserves history (no data/ folder). SIGNAL-TO-NOISE BATCH (audit #2 + cleanup).
1) VINTAGE GUARD (src/agent.py): if a new agent read is based on OLDER source data than
   the prior applied value and differs, the newer vintage is KEPT and the read is flagged
   "older data rejected". Fixes the live bug where subprime auto moved 6.11 (Mar data) ->
   6.80 (Feb data). Tolerant date parsing (YYYY-MM-DD / YYYY-MM / YYYY-Qn / embedded);
   skips safely when dates are unparseable.
2) STALENESS BUDGETS (src/enrich.py + dashboard): each indicator's data age is checked
   against its cadence (daily 10d, monthly 60d, quarterly 150d, annual 430d). Overdue
   data gets an amber hourglass next to its As-of with a plain tooltip. Your Feb subprime
   and CMBS rows will now announce themselves.
3) SCOUT DEDUP (src/scout.py + dashboard): proposals now merge by TARGET (story+indicator
   / proposed name), not headline wording - re-worded reports become one card with a
   "seen N x" chip. The dashboard also groups your EXISTING queue the same way and
   collapses re-rate proposals older than the last agent run into a "superseded" fold
   (the agent has re-researched those since). Your 42-item queue will render as a handful.
4) REVIEW TRIAGE (src/main.py + dashboard): flagged items are tiered. "Action needed"
   (disagreed / out-of-range / vintage-rejected / low-confidence / failed) is the 2-minute
   check; "changed or annotated" is a collapsed informational fold. Header shows
   "N need action" instead of one big number.
5) MOF DATE FIX (src/fetch.py): western slash-dates normalize to ISO (2026/7/2 -> 2026-07-02).
6) RUBRICS TIGHTENED (config/framework.yaml): regional_bank_stress and license_flow -
   the two indicators ASI1 disagreed on twice running - now have countable thresholds
   (FDIC failure counts / asset sizes; licence breadth / processing times), same style
   as the Hormuz fix that ended those disagreements.
APPLY: upload src/, config/, and dashboard/. No workflow change.
