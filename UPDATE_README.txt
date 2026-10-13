RATING-STABILITY BUNDLE - 2026-10-13
====================================
Upload src, config, dashboard, FRAMEWORK.md and METHODOLOGY.md to the repo root.
No workflow change this time. Takes effect at the next agent run (Monday).

WHY: across 18 weekly agent runs, 18 judgment ratings flipped straight back the next
week on the same facts (Hormuz closed/contested six times while the strait stayed
shut). Those flips opened and closed Track record episodes that were pure noise.

WHAT CHANGED
config/framework.yaml  Six rubrics rewritten with measurable or time-windowed rules:
  hormuz_redsea_status / hormuz_fertilizer - rated by measured transits vs baseline
     (<25% = closed); talks, memoranda and escorts no longer cap the rating.
  water_dispute - only events in the last 90 days can make it a crisis.
  new_imf_programs - counts only Board-approved new programs + actual defaults.
  drought_chip_farm - a rationing order counts only while in force / last 90 days.
  cable_incidents - cuts older than 90 days that were repaired no longer count.
src/agent.py   Continuity: the agent sees last week's reading and must give a logged
               change_reason to change it (the cross-check stays blind).
               Reversal guard: a band rating that flips back within 21 days is held
               until the next weekly read confirms it (or the cross-check agrees).
src/main.py    Held reversals show in the review queue with the reason.
dashboard      "reversal awaiting confirmation" tag and the agent's CHANGE reason.
FRAMEWORK.md / METHODOLOGY.md   regenerated / documented (methodology v1.2).

