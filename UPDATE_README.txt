UPDATE BUNDLE - preserves history (no data/ folder). FITCH ANCHOR PIN (config only).
Your decision: the direct-lending default indicator is now permanently anchored to
FITCH'S INCLUSIVE measure (counts distressed exchanges / liability-management exercises).
 - config/framework.yaml: the rubric names Fitch as the sole applied anchor, forbids
   switching measurement methodologies between runs (the cause of the 2.73 -> 6.0 jump),
   requires retaining the prior Fitch reading when no new print exists, and relegates
   Proskauer / With Intelligence / Moody's to dissent context.
 - config/stories.yaml: the indicator label now reads "(Fitch incl. distressed exchanges)"
   so every reader sees which definition the board is keyed to; the note documents the
   ~2-3pt gap vs the count-based index.
CALIBRATION (checked, unchanged): thresholds 3.0/5.0 read Fitch's scale sensibly -
sub-3% only in benign years, 3-5% elevated, >5% record territory. baseline stays 3.0/band 0.
CONSEQUENCE TO EXPECT: with Fitch at its 6.0% record, this indicator reads band 2 and
Private Credit sits High (8) until Fitch's rate falls below 5 - the honest reading you
chose, now stable across runs. The open ledger episode tracks what happens next.
APPLY: upload config/ only. No src, dashboard, or workflow change.
