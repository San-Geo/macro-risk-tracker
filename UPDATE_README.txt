UPDATE BUNDLE - preserves history (no data/ folder). INDEPENDENT CROSS-CHECK via ASI1.
The cross-check (run on high-weight indicators) can now use a genuinely different
provider, so two reads no longer share one model's blind spots.
 - src/agent.py: provider-routed rating. assess_one(..., provider="anthropic"|"asi1").
   ASI1 = OpenAI-compatible endpoint https://api.asi1.ai/v1/chat/completions.
   The cross-check uses AGENT_MODEL_2; if it starts with "asi1" it calls ASI1 with
   ASI1_API_KEY. Records which model/provider did the check.
 - .github/workflows/daily.yml: passes AGENT_MODEL_2 (repo VARIABLE) and ASI1_API_KEY
   (repo SECRET).
 - src/main.py + dashboard/index.html: agent review shows "checked by asi1" (agree) or
   "asi1 disagreed" (held for review).

SETUP (important - the key does NOT go in AGENT_MODEL_2):
  1. Repo -> Settings -> Secrets and variables -> Actions:
       Secret  ASI1_API_KEY   = <your ASI1 key>
       Variable AGENT_MODEL_2 = asi1        (model name; 'asi1' is the agentic default)
  2. Edit .github/workflows/daily.yml on GitHub with the attached version.
APPLY: upload src/ and dashboard/; edit the workflow. Then run it.

NOTE / honest limitation: ASI1 does its own research and has no Anthropic-style web
search tool to pass, so its read may be less web-grounded per call. It still provides
real model/training independence (catches shared blind spots). Expect somewhat MORE
disagreements -> more indicators held for review; that is the conservative, correct
behaviour, not a bug.
