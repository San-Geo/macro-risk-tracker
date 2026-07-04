UPDATE BUNDLE - preserves history (no data/ folder). VISUAL FIXES (dashboard/index.html + src/citecheck.py).
1) ANCHOR STRIP ALIGNED: the calm->crisis strip under the headline number is now built
   from the SAME band colors as the rest of the page, with segment boundaries exactly at
   the band cutoffs - so the notch's color always matches the track beneath it. Note the
   strip no longer shows green: the gauge's validated floor (4.7) already rounds into the
   amber band, so green was decoration for territory the tracker cannot visit. The
   "calm"/"crisis" end labels now have tooltips explaining this.
2) TEXT STAYS IN ITS BOX: defensive wrapping (overflow-wrap) on all panels, cards, table
   cells and captions, plus a global <code> style that wraps long apply-command hashes.
   Long URLs, ids, and driver strings can no longer run outside section borders.
3) (from earlier this session) src/citecheck.py: URLs are stripped from fact text before
   numeric candidates are extracted - fixes the self-fulfilling "verified" match against
   an article ID inside the cited link.
APPLY: upload dashboard/ and src/. No config or workflow change.
