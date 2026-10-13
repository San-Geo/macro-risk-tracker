AUTO-GRADING BUNDLE - 2026-10-13
================================
1. Open grades.csv here and review the 5 rows (the walkthrough grades). Delete any row
   you disagree with - that episode is then graded automatically instead.
2. Upload everything to the repo root (Add file -> Upload files -> drag in src, config,
   dashboard, grades.csv, METHODOLOGY.md).
3. Paste daily.yml into .github/workflows/daily.yml.
4. Actions -> Run workflow (run_agent unticked = free) to publish.

HOW GRADING WORKS NOW
- An episode closes after 5 runs below High. 30 days later (follow-through window)
  it becomes due.
- On the weekly agent run, two independent agents (Claude + ASI1) mark the story's
  tests in config/grading.yaml as met / not met, each with a dated source.
- Code computes the grade from those tests. If both agents' tests give the same
  grade with at least medium confidence, it is applied ("auto-graded, confirmed").
  Otherwise the dashboard shows "owner decides" with both readings.
- YOUR grade always wins: add a row to grades.csv (episode_id,grade,note,timing)
  or use the Run workflow form. Rows in grades.csv are re-applied every run.
- Timing (only for materialized): concurrent = already under way when the episode
  opened; lead = happened after. Brief crossings (<= 1 week, same signal flipped
  back) are tagged automatically.

FILES
src/grader.py (new)        the two-agent grader; the AI never picks the grade
config/grading.yaml (new)  the rubric: 21 stories x concrete materialized/contained tests
grades.csv (new)           owner grades (pre-filled with the walkthrough)
src/ledger.py              grades.csv, triggers + brief-crossing flag, owner precedence
src/main.py                wires grading into the weekly agent run
src/agent.py               shared cross-check routing (no behaviour change)
src/narrative.py           the brief must use the exact number of High stories
dashboard/index.html       Track record shows auto / owner / watching / owner-decides
METHODOLOGY.md             new section 9 on grading (v1.1)
daily.yml                  GRADER_MODEL setting + updated notes
