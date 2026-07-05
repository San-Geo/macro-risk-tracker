UPDATE BUNDLE - preserves history (no data/ folder). DESIGN A: TABBED LAYOUT (dashboard/index.html only).
The dashboard is restructured into four intent-based tabs behind a sticky nav bar:
  TODAY   - gist header, mainstream context dials, heat map (tiles now OPEN their story),
            "High right now" cards, data health, brief links, daily summary. A 60-second read.
  STORIES - all 21 stories as tap-to-expand accordions (level chip, trend arrow, set pill);
            full indicator tables, sparklines, sources, and escalation notes inside.
  TRUST   - consistency, backtest, validation, and the track record.
  UNDER THE HOOD - scout queue + agent review (the full transparency layer).
Details:
 - The overall risk chip sits in the sticky nav - always visible while browsing.
 - URL hash tracks the tab (#trust is shareable); last tab remembered per device;
   Plain/Expert composes with tabs unchanged.
 - MOBILE FIXES from review: the title banner now scrolls away (only the nav bar sticks);
   nav labels shorten on phones so all four tabs fit without scrolling; story tables get
   scroll shadows + a "table scrolls sideways" hint on mobile, and the Cadence column is
   hidden on small screens (data age still shows via the As-of hourglass).
 - One codebase serves desktop and mobile responsively (no separate mobile site - by
   design, to prevent version drift). The single-page sticky-nav variant remains one
   flag away in the code (LAYOUT const) if ever wanted.
No scoring, config, or workflow change - byte-identical numbers.
APPLY: upload dashboard/ only.
