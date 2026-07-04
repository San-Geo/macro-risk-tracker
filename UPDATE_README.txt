UPDATE BUNDLE - preserves history (no data/ folder). RESOLUTION LEDGER (audit item #5 - the last one).
THE MACHINE KEEPS THE RECORD; THE HUMAN PASSES JUDGMENT.
 - src/ledger.py (NEW): whenever a story ENTERS High (>=7), an episode opens
   automatically - the opening date is reconstructed from history.csv (first day of
   the current unbroken High streak), with the driving indicators snapshotted. While
   High it tracks peak and duration; when the story drops back below High the episode
   CLOSES automatically and waits for YOUR grade. The machine never grades and never
   deletes - it cannot forget a call.
 - Grades (human-only, after close): materialized / contained / faded.
     python src/ledger.py --list
     python src/ledger.py --grade <episode_id> <grade> --note "why"
   Or (web-UI workflow): edit the "grade" and "grade_note" fields of the episode in
   data/resolution_ledger.json and commit.
 - src/main.py: updates the ledger every run; log line shows open/awaiting counts.
 - dashboard/index.html: new "Track record" panel (plain question: "When this tracker
   said High - what actually happened next?") showing open episodes with day counts
   and entry drivers, closed episodes with grade badges, and an honest caveat that the
   record proves nothing until it accumulates - which is exactly why it starts now.
ON YOUR FIRST RUN: expect ~3 episodes to open automatically (Japan carry trade, rare
earths, AI power - all High since 2026-07-03 per your history), correctly backdated.
Storage: data/resolution_ledger.json (committed by the workflow like other data).
APPLY: upload src/ and dashboard/. No config or workflow change.
