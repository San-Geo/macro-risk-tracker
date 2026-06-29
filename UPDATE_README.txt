UPDATE BUNDLE - preserves history (no data/ folder).
NEW: automatic sanity check. Any agent reading outside an indicator's plausible
range (set in config/framework.yaml as min/max; band indicators are auto-limited
to 0-2) is treated as a misread, HELD at the last trusted value automatically, and
shown in Agent review as "auto-corrected / out of range". No manual step needed.
Toggle with the AGENT_SANITY env var (default on; set to 0 to disable).
Apply: upload src/ + config/ as usual; edit .github/workflows/daily.yml on GitHub.
