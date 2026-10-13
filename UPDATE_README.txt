PORTWATCH + TABLE-LAYOUT BUNDLE - 2026-10-14
============================================
Upload src, config, dashboard, FRAMEWORK.md and METHODOLOGY.md to the repo root,
then Actions -> Run workflow (run_agent unticked, free). No workflow change.

1) MEASURED HORMUZ / RED SEA RATINGS (IMF PortWatch)
   src/portwatch.py + config/portwatch.yaml (new). Every run reads the IMF's daily
   ship counts for Hormuz and Bab el-Mandeb, takes the latest 7-day average and
   compares it with the same month's normal (Hormuz: 2023-2025; Red Sea: 2021-Oct 2023,
   before the Houthi attacks). Below 25% of normal = closed, 25-80% = contested -
   set by rule. Above 80%, the agent decides only whether recent attacks make it
   contested. A manual_input.csv pin still wins. If the feed fails or its data is
   more than 21 days old, the agent's rating is used exactly as before.
   On the page: "Measured: Strait of Hormuz 2.7 ships/day vs 92 normal (3%) ..." under
   the indicator, source "PortWatch", and a PortWatch status in the health line.
   The normal-level figures are cached in data/portwatch_baseline.json (created by
   the first run; one small query per month after that).

   CHECK AFTER THE FIRST RUN: the log of "Run tracker" should show two lines starting
   "PortWatch Strait of Hormuz: ..." and "PortWatch Bab el-Mandeb (Red Sea): ...".
   If they say "unavailable", nothing changes on the board - send me the line.

2) STORY TABLES
   Column headers and short cells (Band, delta, Cadence, Source) no longer break
   letter by letter; dates stay whole; the Indicator column wraps at word breaks
   only. Wide tables still scroll sideways on phones.
