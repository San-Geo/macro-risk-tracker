STRESS-TEST FIXES - 2026-10-14
==============================
1. Upload everything in this zip to the repo root (src, config, dashboard, data, tests,
   FRAMEWORK.md, METHODOLOGY.md, requirements.txt).
2. Paste daily.yml into .github/workflows/daily.yml (actions now pinned to exact commits).
3. Create a NEW file .github/workflows/check.yml (Add file -> Create new file, type that
   path as the name) and paste check.yml into it.
4. Actions -> daily-risk-tracker -> Run workflow (free). The new "check" workflow also runs
   on your upload and should show a green tick within a minute.

WHAT YOU WILL SEE
- Overall moves from 7.1 to about 7.6: scoring method 3.0 rounds half up, so China price
  spillover, AI build-out financing and Food & fertilizer (each at exactly 6.5) read 7/High.
  Their Track record episodes open today. Trends and alerts compare like with like, so the
  switch itself is not reported as a "move".
- Headline card: "What sets today's level": starting level / judgment / data.
- Each story shows its unrounded score and the same split.
- Review panel: an A/B/C evidence grade per agent read; changes backed only by
  non-authoritative sources are flagged.
- Track record: a "Misses" section once the monthly check finds something.

FILES
score.py        method 3.0: half-up, unrounded aggregates, smooth breadth premium
feedguard.py    NEW - carry forward last good value; hold implausible values (feed_checks.yaml)
main.py         wiring: feed guard, freshest France spread, evidence grade, weekly scout,
                miss check, failure alerts
grader.py       monthly miss check (primary agent only; you confirm each miss in grades.csv
                with "confirmed" or "rejected")
ledger.py       miss confirmations from grades.csv
enrich/alerts/narrative.py   compare past and present under the same rounding rule;
                alerts now also report pipeline failures (if an alert channel is set)
scout.py        runs weekly only; items expire after 30 days; the page loads the newest 10
report.py       Excel model now matches the engine (method 3.0 + two-sided PPI band fix)
portwatch.py    normal shown as a whole number; IMF attribution line
config/framework.yaml   NEW agent read: weekly France-Germany spread
config/sources.yaml     NEW - which domains count as authoritative (edit freely)
config/feed_checks.yaml NEW - plausible ranges and maximum daily moves per feed
dashboard/index.html    all loaded text sanitized (no AI-written code can run); new displays
tests/          NEW - 19 unit tests + a file-format check, run by check.yml on every push
requirements.txt        exact package versions
