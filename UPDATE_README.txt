UPDATE BUNDLE - preserves history (no data/ folder). Adds the "whole-picture" layer.
NEW FILES: src/consistency.py, config/consistency.yaml
CHANGED: config/framework.yaml (china_ppi + hormuz rubrics tightened),
         src/main.py (+report.py) wire the consistency engine into latest.json,
         dashboard/index.html (new "Consistency checks" panel),
         tests/selftest.py (guards consistency rules against typo'd indicator IDs).
WHAT IT DOES: after scoring, deterministic rules in config/consistency.yaml
cross-check the whole board and flag internal contradictions (e.g. sea lane rated
closed while oil is benign; positive China PPI vs the deflation thesis). Flags only
- never silent rewrites. Add/edit rules freely; selftest validates them.
APPLY: upload src/ + config/ + dashboard/ as usual. No workflow change this round.
