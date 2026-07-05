UPDATE BUNDLE - preserves history (no data/ folder). SCOPE STATEMENT + MAINSTREAM CONTEXT DIALS.
Purpose: pre-empt the fairest criticism of a published dashboard ("this ignores mainstream
macro") by owning the scope explicitly and displaying the famous dials for contrast.
 1. config/context.yaml (NEW): five famous gauges - VIX, 10y-2y curve, high-yield spread,
    Chicago Fed NFCI, unemployment - all keyless FRED series. DISPLAY ONLY: fetched into a
    separate payload field that never touches the scoring values (enforced by structure,
    not promise). Edit this file to add/remove dials.
 2. Dashboard: a slim "Context - the mainstream dials" strip under the overall area in
    BOTH modes, each pill with a plain tooltip, its as-of date, and a link to the FRED
    series. The header states "displayed for contrast - never part of the score". When
    the mainstream dials read calm while the structural gauge reads elevated, that
    divergence is now visible evidence of the tracker's thesis rather than a critic's
    gotcha. Strip hides gracefully when values are unavailable (e.g. offline).
 3. Scope statement: a new "What this is - and isn't" section at the TOP of the help
    modal (deliberate lens / attention-not-probability / curated-not-frozen coverage),
    plus a one-line version at the bottom of the Plain-mode gist header.
 4. src/main.py + src/report.py: context fetch (5 extra FRED calls per run, free) and
    payload plumbing.
No scoring change, no methodology version bump - the score is byte-identical.
APPLY: upload config/, src/, and dashboard/. No workflow change.
