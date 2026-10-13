FIX BUNDLE - 2026-10-13
=======================
Upload these folders/files to the repo root (GitHub -> Add file -> Upload files ->
drag in src, config, data, dashboard and FRAMEWORK.md). They replace existing files.
Then paste daily.yml into .github/workflows/daily.yml (uploads can't reach .github/).
Then Actions -> daily-risk-tracker -> Run workflow (leave run_agent unticked = free)
to publish. If a run is already in progress, wait for it to finish first.

WHAT CHANGED
data/resolution_ledger.json  Rebuilt from history.csv (the old file had a missing comma
                             and had been frozen since Jul 22). 13 episodes: 5 open,
                             8 closed awaiting grade. Japan's "faded" grade is shown as
                             withdrawn (it never closed under the one-week rule).
src/ledger.py                Episodes close only after 5 consecutive runs below High
                             ("cooling" in between). A broken file now fails loudly.
src/main.py                  Ledger failure = red annotation + dashboard warning.
                             Review queue: dissent alone no longer flags (~33 -> ~10/week);
                             recovered/unsourced reads and real changes do.
src/narrative.py             The brief explains moves ONLY with indicators that changed band.
src/agent.py                 Recovers sources from cut-off replies; token headroom (billed
                             only if used); "A to B" as-of ranges keyed on A; a band can't
                             RISE on evidence >90 days old (held for review); prompt asks
                             for current conditions; API error text is logged.
config/framework.yaml        truce_status: Jan 10 2027 expiry; entity listings no longer
                             double-counted (they belong to re_blacklist).
dashboard/index.html         Footer/help "—" text, "\203A" headings, raw ** in the brief,
                             countdown (11:37 UTC + "queued at GitHub"), tab links, favicon,
                             one VIX number, review-table columns, ledger IDs + cooling.
daily.yml                    Agent catch-up if last pass is 7+ days old; grade episodes from
                             the Run workflow form; a new run waits instead of cancelling;
                             Pages actions bumped to v5 (Node 24).

GRADING AN EPISODE
Actions -> daily-risk-tracker -> Run workflow -> paste the ID shown under the episode
on the dashboard's Track record -> pick a grade -> add a one-line note -> Run.
