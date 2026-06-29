UPDATE BUNDLE - preserves history (no data/ folder). TASK 2 of 2: per-domain authorities.
NEW FILE: config/domains.yaml - maps each of the 5 mechanism sets to a specialist
FRAMING (how a domain analyst reasons) + a curated list of primary-source AUTHORITIES
(Funding->Fed FSR/OFR/BIS/NY Fed; Credit->FDIC/Fed/Trepp/KBRA/Moody's/S&P; Sovereign->
IMF/World Bank/OECD/Treasury; Geoecon->Reuters/CSIS/ICG/IMF PortWatch/MOFCOM/USTR;
Physical->IEA/EIA/USBR/Drought Monitor/FAO/ICSG/LBNL).
CHANGED:
 - src/agent.py: each indicator is now rated with its set's specialist framing, and the
   prompt prefers indicator-specific sources FIRST, then the domain authorities. Applies
   to both the main read and the cross-check read. The desk is recorded on each rating.
 - src/main.py + dashboard/index.html: agent review shows the specialist "<desk> desk"
   that produced each rating.
 - tests/selftest.py: guards that every story set has a domain entry (framing+authorities).
APPLY: upload src/, config/, dashboard/. No workflow change. Takes effect next agent run.
