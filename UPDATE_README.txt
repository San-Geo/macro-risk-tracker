UPDATE BUNDLE - preserves history (no data/ folder). PLAIN <-> EXPERT READING MODE.
A global toggle (top-right button) switches the whole tracker between plain-English and
the current expert view. Defaults to Plain for first-time/public readers; the choice is
remembered per device. Expert mode is exactly today's view.
 - config/plain.yaml (NEW): plain set names + a plain label and one-line "what it is /
   why it matters" gist for all 21 stories. EDIT THIS to reword anything - it never
   touches scoring or numbers.
 - src/main.py + src/report.py: load plain.yaml into latest.json (payload.plain).
 - dashboard/index.html:
     * Plain/Expert button + persistence (mirrors the dark-mode toggle).
     * Plain mode adds a "state of the world" header: a normal-anchored overall (with a
       calm->crisis strip), a one-sentence plain summary, and a "what changed" list -
       ALL generated deterministically from the scored board, so they can't drift from
       the numbers.
     * Plain set/story names, a gist line under each story, and a plain question above
       each panel (e.g. validation -> "Can you trust this gauge?").
     * Help modal explains the toggle.
NOTE: per-indicator labels (the 47 rows inside each story) are unchanged for now - the
story gist carries the meaning in Plain mode; plain indicator labels are a clean next step.
APPLY: upload src/, dashboard/, and config/ (so config/plain.yaml ships). No workflow change.
