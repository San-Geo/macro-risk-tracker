UPDATE BUNDLE - preserves history (no data/ folder). CITECHECK FIX (one file: src/citecheck.py).
Bug found on your live board: the truce_status fact showed "verified, matched 3357974" -
that number is the ARTICLE ID inside the cited URL, which trivially "verifies" against the
page's own address. Fix: URLs are stripped from the fact text before numeric candidates
are extracted, so verification can only match genuine figures from the fact.
Effect on your board: truce_status will flip from a false "verified" to an honest verdict
on the next run's re-check (agent day, or delete its "citecheck" field to force backfill).
All other verified tags on your board matched real figures (2.73, 6.8, 4.5, 0.2, 83.7,
4.2) and are unaffected.
APPLY: upload src/ only. No config, dashboard, or workflow change.
