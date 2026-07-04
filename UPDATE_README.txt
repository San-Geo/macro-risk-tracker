UPDATE BUNDLE - preserves history (no data/ folder). WORKFLOW HARDENING (CI race + re-run fix).
Your run was healthy (19/19 feeds; citation checker's live debut: 12 verified, 6 not
found, 10 unreachable, 14 skipped). Two pieces of CI plumbing failed around it:
 1. PUSH RACE (.github/workflows/daily.yml): the bot's push was rejected because the
    branch moved during the run (your web-UI uploads land as commits). The commit step
    now rebases onto the latest main and retries up to 3x, with freshly generated data
    files winning any conflict. The old error message wrongly blamed permissions; the
    new one distinguishes a permissions problem from a moving branch.
 2. RE-RUN ARTIFACT CLASH (.github/workflows/daily.yml): re-running a failed run leaves
    the first attempt's "github-pages" artifact behind and deploy-pages refuses
    duplicates. Artifacts are now named uniquely per run AND attempt, so re-runs deploy
    cleanly. (Fresh runs were never affected.)
 3. HISTORY IDEMPOTENCE (src/report.py): story-level history.csv now replaces same-date
    rows on re-run instead of duplicating them (indicator history already did this).
    Today's duplicate 2026-07-03 rows in your history.csv will be self-healed by the
    next run's rewrite of that date.
APPLY: paste the new .github/workflows/daily.yml in the web editor, upload src/.
Then trigger a FRESH "Run workflow" (unticked, free) rather than re-running the failed
one - it will push, deploy, and persist the citation-check results + indicator history.
