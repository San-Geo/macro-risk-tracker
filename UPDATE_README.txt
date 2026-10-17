EDITIONS + ARCHIVE + 2026 EDITION REVISION 1 - 2026-10-16
==========================================================
1. Upload the zip's folders (src, config, tests, dashboard, data) and METHODOLOGY.md at the
   repo root. This also includes the living-brief fix from the previous bundle.
2. Create ONE new workflow file: Add file > Create new file, name it
   .github/workflows/edition.yml and paste the contents of edition.yml (sent separately).
   daily.yml is unchanged.
3. Optional: add a repository variable EDITION_MODEL to choose the model (default
   claude-sonnet-4-6). It uses the same ANTHROPIC_API_KEY secret.

WHAT YOU GET
- 2026 Edition, revision 1: 13 factual corrections, 6 new cross-story connections, cleaned
  sources, and a revision history at the back. Threat levels and story pages are unchanged,
  so every "full write-up" link still lands on the right page. The first printing is kept
  in dashboard/briefs/editions/2026/.
- Archive (data/archive/): daily scores and notes since 28 Jun, plus every weekly agent
  pass (facts, sources, reasoning) since 29 Jun, backfilled from git history. Monthly
  frozen copies of the living brief: dashboard/briefs/archive/ (linked from the
  dashboard as "Past editions & snapshots").
- Editions on a data-driven schedule (config/editions.yaml, METHODOLOGY section 10):
  checked daily for free; the "edition" workflow writes a DRAFT on the 2nd of each month
  only when one is due. You publish it from Actions > edition > Run workflow >
  action = publish, edition_id = (shown in the run summary). Nothing auto-publishes.

A NEW EDITION IS ALREADY DUE (quarterly: 4 stories changed band since June and the overall
rose 1.1). Suggested timing: after Monday's agent run (19 Oct), so France's spread reading
is current. Then: Actions > edition > Run workflow > action = write. Expect roughly
$3-6 of API use (hard cap $12). Or just let the 2 Nov scheduled run do it.

CHECK AFTER THE NEXT DAILY RUN
- The log of "Run tracker" shows "archive: {...}" and "next edition: due now ...".
- The dashboard's Brief line shows "2026 Edition (21 stories · rev. 1)" and a
  "Past editions & snapshots" link.
