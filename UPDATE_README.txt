UPDATE BUNDLE - preserves history (no data/ folder). METHODOLOGY-VERSION STAMP.
 - src/score.py: METHODOLOGY_VERSION (now "2.0") + METHODOLOGY_CHANGELOG, the single
   source of truth. BUMP it whenever a change alters what a level means.
 - src/report.py: history.csv now carries a `method_version` column; every row is
   stamped. (Old rows without it read as "1.x".) latest.json carries method_version.
 - src/enrich.py: the overall trend now (a) recomputes past overalls with the CURRENT
   tail-weighted aggregator from stored per-story levels - fixing a mean/tail mismatch
   the new aggregation introduced - and (b) flags when a trend comparison spans a
   methodology change (crosses_methodology).
 - dashboard/index.html: shows "methodology v2.0"; when the overall trend crosses a
   version boundary it shows a "methodology changed" warning instead of a misleading
   delta. tests/selftest.py guards that the version is set and documented.
APPLY: upload src/ and dashboard/. Your existing history.csv keeps working - old rows
read as v1.x, new rows are stamped v2.0, and the first cross-version comparison will
flag itself rather than mislead. No workflow change.
