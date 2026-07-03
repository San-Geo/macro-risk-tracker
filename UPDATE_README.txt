UPDATE BUNDLE - preserves history (no data/ folder). VERIFIABILITY PAIR (audit items #3).
1) DETERMINISTIC CITATION CHECKER (src/citecheck.py, NEW - no AI, zero API cost):
   after each agent run (or once as backfill on your next ANY online run), a plain
   HTTP script fetches each cited URL and looks for the applied number - or a
   distinctive figure from the FACT - verbatim in the page. Verdicts shown as tags
   in Agent review:
     GREEN  "verified at source"  - the number is literally on the cited page
     AMBER  "not found at source" - page fetched, number absent (often paywall/PDF/
                                    JS-rendered; occasionally a misquote; worth a click)
     GREY   "source unreachable"  - link rot / 403 / timeout
   Header shows "N facts machine-verified at their cited source". Years and 0/1/2
   band values are deliberately excluded from matching (they'd match everything).
   Not-found does NOT change any rating or tier - it is a prompt, never a verdict.
   Toggle off with env CITE_CHECK=0 if ever needed.
2) INDICATOR-LEVEL HISTORY (src/report.py + main.py):
   - data/indicator_history.csv (NEW, append-only, idempotent per date): date, indicator,
     story, value, band, provenance, as_of for EVERY indicator on EVERY run. This is the
     raw material for the future public track record and judgment-layer backtests.
   - dashboard/indicator_history.json (auto-generated, last 30 runs per indicator) feeds
     tiny grey sparklines beside each indicator's value - hover for recent values.
     Flat series are suppressed (no noise); sparklines appear as real history accrues.
3) Review items now carry the citecheck verdict through latest.json.
NOTE: your next FREE (unticked) run backfills citation checks on the current facts and
starts the indicator history - both visible immediately, no agent cost. Expect a mix of
verdicts on first pass: paywalled sources (Trepp/Fitch summaries) will read "not found"
or "unreachable" - that is the checker being honest about what it can see.
APPLY: upload src/ and dashboard/. No config or workflow change.
