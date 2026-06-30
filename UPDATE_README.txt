UPDATE BUNDLE - preserves history (no data/ folder). SETUP-TOLERANCE for AGENT_MODEL_2.
 - src/agent.py: AGENT_MODEL_2 is now normalised before use, so all of these resolve
   to the model name "asi1": "asi1", "AGENT_MODEL_2=asi1" (KEY=value paste), " `asi1` ",
   '"asi1"', with surrounding spaces/quotes/backticks. This removes the most common
   setup mistake. (Includes the prior parse-failure fix + vars||secrets workflow.)

SETUP - two SEPARATE entries; the Value box holds ONLY the right-hand side:
   Variables tab: Name AGENT_MODEL_2   Value asi1        (model name; not the key)
   Secrets tab:   Name ASI1_API_KEY    Value <your key>  (the long asi1.ai key)
APPLY: upload src/ and dashboard/; the daily.yml from last update is already correct.
