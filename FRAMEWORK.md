# Indicator Rating Framework

This is the evidence-based rubric the automated agent follows when it rates each judgment indicator. The agent never invents a score: it searches authoritative sources for the **current** status, maps that evidence onto the fixed rubric below, and logs its reasoning and links for every rating. The deterministic engine then turns the ratings into 1–10 threat levels. Humans can override any value at any time (see *Overriding the agent*).

## How a rating becomes a threat level

- **Band indicators** are rated **0 = benign, 1 = watch, 2 = stress** per the rubric.
- **Value indicators** are the latest published number; the story's `good`/`warn` thresholds in `stories.yaml` convert that number into a band.
- Each band becomes a small +/- nudge on the story's base level (weighted), so the final 1–10 level moves only as far as the evidence justifies.
- **Market indicators** (copper, oil, VIX, MOVE) are *not* agent-rated — they come from live price feeds.

## Trust & safety design

1. **Grounded** — every rating must come from a live web search of named sources.
2. **Auditable** — value, confidence, a one-line rationale, and source URLs are logged to `data/agent_assessments.json` for every indicator, every run.
3. **Conservative** — a low-confidence result never flips the number; it keeps the prior value and is flagged for human review.
4. **Human-final** — anything you pin in `manual_input.csv` overrides the agent.

## Overriding the agent

Open `manual_input.csv` and put a number in the `value` column for any indicator to **pin** it; leave it blank to let the agent decide. Band indicators take 0/1/2; value indicators take the raw number. Pinned indicators are skipped by the agent (and noted as overridden in the audit log).

---

## Set 1 — Funding & Leverage

### SEC central clearing on track (0 ok / 1 slipping / 2 delayed)  

*Story:* Treasury basis trade (hidden leverage)  
*Indicator id:* `clearing_status`  
*Type:* band  
*Weight on the meter:* 1.0  

**Rubric.** 0 = ON TRACK: SEC compliance dates unchanged (cash 2026-12-31, repo 2027-06-30), no new extension sought. 1 = SLIPPING: an official extension granted, OR exemptive-relief requests pending, OR readiness surveys show <60% of firms confident of meeting the deadline. 2 = DELAYED: a SECOND formal deadline extension announced, or a deadline passed without compliance. Cite the SEC order or an industry readiness survey.

**What the agent searches.** SEC US Treasury central clearing mandate 2026 2027 timeline status delay

**Authoritative sources.** https://www.sec.gov, https://www.dtcc.com, https://www.risk.net

### Takaichi plan financing clarity (0 ok / 1 unclear / 2 disorderly)  

*Story:* Japan fiscal / JGB / carry trade  
*Indicator id:* `plan_financing`  
*Type:* band  
*Weight on the meter:* 1.0  

**Rubric.** Judge by the JGB market's reaction to the fiscal plan. 0 = OK: 10y JGB yield stable and supplementary budget specifies funding, auctions well covered (bid-to-cover >3). 1 = UNCLEAR: funding path unspecified OR 10y JGB yield up >25bps on fiscal news but auctions still clearing. 2 = DISORDERLY: a failed/tailing JGB auction (bid-to-cover <2 or a long tail), an emergency BOJ operation, or a >50bps yield spike on fiscal concern. Cite the auction result or yield move.

**What the agent searches.** Japan Takaichi fiscal stimulus plan financing JGB issuance market reaction

**Authoritative sources.** https://www.reuters.com/markets/asia, https://www.bloomberg.com/markets

### Direct-lending default rate (%, Fitch incl. distressed exchanges)  

*Story:* Private credit's opaque expansion  
*Indicator id:* `direct_lending_default`  
*Type:* value  
*Bands from thresholds:* good ≤ 3.0, warn ≈ 5.0  
*Weight on the meter:* 1.5  

**Rubric.** Report the latest US direct-lending/private-credit default rate as a percent, ANCHORED TO FITCH'S INCLUSIVE MEASURE (the Fitch rate that counts distressed exchanges and liability-management exercises; April 2026 record = 6.0). DO NOT switch measurement anchors between runs: if no new Fitch print is available for the period, retain the prior Fitch reading rather than substituting a different methodology. Report Proskauer's count-based index (typically 2-3 points lower), With Intelligence, and Moody's estimates as DISSENT context only, never as the applied value. State the Fitch publication month in as_of.

**What the agent searches.** Fitch US private credit direct lending default rate including distressed exchanges latest percent

**Authoritative sources.** https://www.fitchratings.com, https://www.forbes.com, https://www.ft.com

### Large-fund redemption gates (0 none / 1 isolated / 2 widespread)  

*Story:* Private credit's opaque expansion  
*Indicator id:* `redemption_gates`  
*Type:* band  
*Weight on the meter:* 1.0  

**Rubric.** COUNT named private-credit/BDC funds with redemption gates or quarterly repurchase caps active in the same quarter. 0 = NONE. 1 = ISOLATED: 1-2 funds gating. 2 = WIDESPREAD: >=3 of the largest funds, or gated funds with combined AUM > $100bn. Name the funds and the quarter.

**What the agent searches.** private credit fund redemption gates limits 2026

**Authoritative sources.** https://www.ft.com, https://www.bloomberg.com

### GENIUS implementation friction (0 smooth / 1 gaps / 2 problems)  

*Story:* Stablecoins & Treasury demand  
*Indicator id:* `genius_impl`  
*Type:* band  
*Weight on the meter:* 0.5  

**Rubric.** Track GENIUS Act stablecoin rulemaking vs the statutory 2026-07-18 deadline. 0 = SMOOTH: final rules issued on schedule, no major agency divergence. 1 = GAPS: rules still in proposed/comment stage near the deadline, OR documented inter-agency divergence (e.g. OCC vs FDIC). 2 = PROBLEMS: deadline missed without final rules, a court stay, or a compliance-failure event. Cite the rule status.

**What the agent searches.** GENIUS Act stablecoin regulation implementation 2026 status issues

**Authoritative sources.** https://www.sec.gov, https://www.federalreserve.gov, https://www.coindesk.com/policy

### Treasury-clearing rollout stress (0 smooth / 1 friction / 2 problems)  

*Story:* Clearinghouses (financial chokepoint)  
*Indicator id:* `treasury_clearing_rollout`  
*Type:* band  
*Weight on the meter:* 0.5  

**Rubric.** Track UST central-clearing readiness vs deadlines (cash 2026-12-31, repo 2027-06-30). 0 = SMOOTH: on track, broad readiness. 1 = FRICTION: documentation backlog, pending exemptive relief, or readiness surveys <60% confident. 2 = PROBLEMS: a deadline extension, a major participant unable to comply, or an operational failure in testing. Cite TBAC/SEC/industry survey.

**What the agent searches.** US Treasury central clearing implementation capacity readiness 2026 2027

**Authoritative sources.** https://www.sec.gov, https://www.dtcc.com, https://www.risk.net


## Set 2 — Credit, Consumers & Valuations

### AI capex-vs-revenue gap concern (0 closing / 1 wide / 2 widening fast)  

*Story:* AI build-out circular financing  
*Indicator id:* `ai_revenue_gap`  
*Type:* band  
*Weight on the meter:* 1.0  

**Rubric.** Compare hyperscaler AI capex growth vs AI-attributable revenue growth for the latest reported quarter. 0 = CLOSING: AI-revenue growth >= capex growth. 1 = WIDE: capex growth exceeds AI-revenue growth but AI revenue is still accelerating YoY. 2 = WIDENING FAST: capex growth outpaces AND AI-revenue growth decelerates QoQ, or a hyperscaler raises capex while cutting its AI-revenue outlook. Cite the capex and AI-revenue figures.

**What the agent searches.** AI capex versus revenue gap monetization concern 2026 hyperscaler

**Authoritative sources.** https://www.theinformation.com, https://www.ft.com, https://www.sequoiacap.com

### GPU-backed debt refinancing stress (0 none / 1 signs / 2 acute)  

*Story:* AI build-out circular financing  
*Indicator id:* `gpu_refi_stress`  
*Type:* band  
*Weight on the meter:* 1.0  

**Rubric.** 0 = NONE: GPU/data-center-backed debt refinancing normally. 1 = SIGNS: banks offloading AI/data-center debt at a discount, a named borrower facing a refinancing wall, or a rating watch on GPU-backed paper. 2 = ACUTE: a confirmed default, distressed exchange, or failed refinancing of GPU-backed debt. Name the issuer.

**What the agent searches.** GPU-backed debt data center financing refinancing stress 2026

**Authoritative sources.** https://www.ft.com, https://www.bloomberg.com, https://www.moodys.com

### CMBS office delinquency rate (%)  

*Story:* CRE maturity wall / regional banks  
*Indicator id:* `cmbs_office_delinq`  
*Type:* value  
*Bands from thresholds:* good ≤ 8.0, warn ≈ 12.0  
*Weight on the meter:* 1.0  

**Rubric.** Report the latest CMBS office delinquency rate as a percent (e.g. 12.3).

**What the agent searches.** CMBS office delinquency rate latest percent Trepp 2026

**Authoritative sources.** https://www.trepp.com/trepptalk, https://www.commercialsearch.com

### Regional-bank CRE stress (0 calm / 1 isolated / 2 cluster)  

*Story:* CRE maturity wall / regional banks  
*Indicator id:* `regional_bank_stress`  
*Type:* band  
*Weight on the meter:* 1.5  

**Rubric.** Count US bank failures on the FDIC failed-bank list in the trailing 6 months where FDIC/Fed/OCC materials or credible reporting cite CRE/real-estate exposure as a contributing factor. 0 = CALM: zero such failures AND no new public enforcement action or supervisory statement citing regional-bank CRE concentration in the trailing 6 months. 1 = ISOLATED: 1-2 such failures (each <$10bn assets), OR >=1 new public enforcement action/consent order citing CRE concentration. 2 = CLUSTER: >=3 such failures in 6 months, OR any single CRE-linked failure >$10bn assets, OR a coordinated supervisory action (e.g. interagency statement, emergency facility) aimed at regional-bank CRE stress.

**What the agent searches.** regional bank commercial real estate stress failures 2026

**Authoritative sources.** https://www.fdic.gov, https://www.federalreserve.gov, https://www.spglobal.com

### Subprime auto 60+ day delinquency (%)  

*Story:* Hidden consumer debt  
*Indicator id:* `subprime_auto_dpd`  
*Type:* value  
*Bands from thresholds:* good ≤ 5.5, warn ≈ 6.5  
*Weight on the meter:* 1.0  

**Rubric.** Report the latest subprime auto 60+ day delinquency rate as a percent (e.g. 6.2).

**What the agent searches.** subprime auto loan 60+ day delinquency rate latest percent 2026

**Authoritative sources.** https://www.fitchratings.com, https://www.coxautoinc.com/market-insights/

### BNPL delinquency trend (0 stable / 1 rising / 2 spiking)  

*Story:* Hidden consumer debt  
*Indicator id:* `bnpl_delinq`  
*Type:* band  
*Weight on the meter:* 0.5  

**Rubric.** Use a reported BNPL delinquency series (Affirm 30+ DPD, LendingTree survey, Fed brief). 0 = STABLE: delinquency flat or down YoY. 1 = RISING: late-payment/delinquency up YoY but provider charge-offs contained (<3%). 2 = SPIKING: a named provider's 30+ DPD up >100bps YoY, or charge-offs >5%. Cite the figure.

**What the agent searches.** buy now pay later BNPL delinquency trend 2026 Affirm Klarna

**Authoritative sources.** https://www.richmondfed.org, https://www.cfpb.gov, https://www.ft.com

### Insurer non-renewals / exits (0 stable / 1 rising / 2 accelerating)  

*Story:* Insurance retreat  
*Indicator id:* `insurer_exits`  
*Type:* band  
*Weight on the meter:* 1.0  

**Rubric.** COUNT US states with active insurer market exits or non-renewal waves. 0 = STABLE: isolated, <5 states, stable outlook. 1 = RISING: elevated across 5-15 states but some markets stabilizing. 2 = ACCELERATING: >15 states, OR a top-10 insurer fully exiting a major state market. Cite state DOI / AM Best.

**What the agent searches.** home insurer non-renewals market exits states 2026

**Authoritative sources.** https://www.naic.org, https://www.insurancejournal.com

### Catastrophe-loss pressure (0 normal / 1 elevated / 2 severe season)  

*Story:* Insurance retreat  
*Indicator id:* `cat_losses`  
*Type:* band  
*Weight on the meter:* 1.0  

**Rubric.** Use YTD insured-catastrophe-loss totals vs the 10-year average (Gallagher Re/Aon/Swiss Re). 0 = NORMAL: YTD <= 10y average and no single event >$10bn. 1 = ELEVATED: YTD above the 10y average, OR one event >$10bn. 2 = SEVERE SEASON: YTD >150% of average, OR a single event >$30bn. Cite the figure and source.

**What the agent searches.** insured catastrophe losses severe season 2026 hurricane wildfire

**Authoritative sources.** https://www.aon.com/reinsurance, https://www.munichre.com, https://www.swissre.com/institute/


## Set 3 — Sovereigns & the Monetary Order

### New IMF programs / missed coupons (0 calm / 1 rising / 2 cluster)  

*Story:* Developing-world debt crisis  
*Indicator id:* `new_imf_programs`  
*Type:* band  
*Weight on the meter:* 1.0  

**Rubric.** COUNT distinct sovereigns in the trailing 6 months (state the exact window) that EITHER (a) had a NEW IMF lending arrangement APPROVED BY THE IMF EXECUTIVE BOARD (count SBA, EFF, ECF, RFI or RCF emergency financing; do NOT count staff-level agreements, reviews, augmentations or extensions of existing programs, or non-financing instruments such as PCI or PSI), OR (b) newly missed an external bond or loan payment beyond its grace period, announced a standstill, or launched a distressed exchange. Count each country once. 0 = CALM: none. 1 = RISING: 1-2 countries. 2 = CLUSTER: 3 or more. List every country counted with its event and date.

**What the agent searches.** IMF Executive Board approves new arrangement 2026; sovereign missed coupon default distressed exchange 2026

**Authoritative sources.** https://www.imf.org/en/News, https://www.worldbank.org

### Govt stability (0 stable / 1 fragile / 2 collapse-or-snap-election)  

*Story:* France / eurozone fragility  
*Indicator id:* `govt_stability`  
*Type:* band  
*Weight on the meter:* 1.0  

**Rubric.** 0 = STABLE: government holds a working majority. 1 = FRAGILE: minority/hung parliament relying on Article 49.3 or surviving no-confidence votes, but governing. 2 = COLLAPSE: government fell on a confidence vote, PM resigned, or a snap election/dissolution was called. State the latest vote/event and date.

**What the agent searches.** France government stability budget no-confidence snap election latest

**Authoritative sources.** https://www.lemonde.fr/en/, https://www.reuters.com/world/europe

### Rating action (0 stable / 1 negative outlook / 2 downgrade)  

*Story:* France / eurozone fragility  
*Indicator id:* `rating_action`  
*Type:* band  
*Weight on the meter:* 1.0  

**Rubric.** Use the most recent action from S&P/Moody's/Fitch. 0 = STABLE: all stable outlooks, no recent cut. 1 = NEGATIVE OUTLOOK: at least one agency on negative outlook/watch. 2 = DOWNGRADE: an actual rating cut in the trailing 12 months. Cite the agency, date, and rating.

**What the agent searches.** France sovereign credit rating outlook S&P Moody's Fitch latest

**Authoritative sources.** https://www.spglobal.com/ratings, https://www.fitchratings.com, https://www.moodys.com

### USD share of FX reserves (%, IMF COFER)  

*Story:* Gold / de-dollarization  
*Indicator id:* `dollar_reserve_share`  
*Type:* value  
*Bands from thresholds:* good ≤ 57.0, warn ≈ 54.0  
*Weight on the meter:* 1.0  

**Rubric.** Report the latest USD share of allocated global FX reserves as a percent (e.g. 56.8).

**What the agent searches.** US dollar share global FX reserves IMF COFER latest percent

**Authoritative sources.** https://data.imf.org/cofer, https://www.imf.org

### Reserve-weaponization / settlement shift (0 none / 1 talk / 2 action)  

*Story:* Gold / de-dollarization  
*Indicator id:* `weaponization_event`  
*Type:* band  
*Weight on the meter:* 1.0  

**Rubric.** 0 = NONE: no new reserve freeze or settlement-system shift. 1 = TALK: new non-dollar settlement agreements/launches (BRICS Pay, gold-unit) or official rhetoric, but no new sovereign reserve seizure. 2 = ACTION: a new sovereign reserve freeze/seizure, OR a major economy operationally moving reserve settlement off USD. Name the event.

**What the agent searches.** reserve weaponization sanctions asset freeze non-dollar settlement latest 2026

**Authoritative sources.** https://www.reuters.com, https://www.atlanticcouncil.org

### Social Security / pension reform shock (0 none / 1 debate / 2 cuts)  

*Story:* Pensions / demographics  
*Indicator id:* `ss_reform_news`  
*Type:* band  
*Weight on the meter:* 1.0  

**Rubric.** Track US Social Security/pension legislative status. 0 = NONE: no change to trust-fund outlook or reform activity. 1 = DEBATE: trustees report worsens the depletion date or reform actively debated, but no enacted cuts. 2 = CUTS: an automatic benefit reduction triggered, or legislation enacting cuts. Cite the trustees report or bill.

**What the agent searches.** US Social Security trust fund reform benefit cut pension news 2026

**Authoritative sources.** https://www.ssa.gov/oact/, https://www.crfb.org

### Pension-fund leverage event, UK-2022 type (0 none / 1 stress / 2 blowup)  

*Story:* Pensions / demographics  
*Indicator id:* `pension_leverage_event`  
*Type:* band  
*Weight on the meter:* 1.0  

**Rubric.** 0 = NONE: LDI buffers adequate, no margin stress (cite TPR/ESMA). 1 = STRESS: a regulator flags LDI/pension liquidity risk, or a margin-call episode without forced selling. 2 = BLOWUP: forced gilt/bond selling by pension/LDI funds, or a central-bank intervention to halt it. State the episode.

**What the agent searches.** pension fund leverage LDI margin crisis 2026

**Authoritative sources.** https://www.bankofengland.co.uk, https://www.ft.com, https://www.pionline.com

### Large public-pension funded ratio (%)  

*Story:* Pensions / demographics  
*Indicator id:* `funded_ratio`  
*Type:* value  
*Bands from thresholds:* good ≤ 80, warn ≈ 70  
*Weight on the meter:* 0.5  

**Rubric.** Report a representative large US public-pension funded ratio as a percent (e.g. 78).

**What the agent searches.** large US public pension funded ratio latest percent 2026

**Authoritative sources.** https://www.milliman.com, https://equable.org


## Set 4 — Geoeconomics & Trade Weapons

### China PPI YoY (%) - large swing either way is worse  

*Story:* China's price spillover (deflation or cost-push)  
*Indicator id:* `china_ppi`  
*Type:* value  
*Bands from thresholds:* good ≤ 2.0, warn ≈ 4.0  
*Weight on the meter:* 1.0  

**Rubric.** Report China PPI year-on-year as a SIGNED percent EXACTLY as published by the National Bureau of Statistics (NBS), keeping the sign. This indicator is TWO-SIDED: a large move in EITHER direction is a price-spillover shock - deep deflation (very negative) exports disinflation, sharp cost-push inflation (very positive) exports input-cost pressure. Just report the signed number and the release month; the engine scores it on the SIZE of the move, not the sign. State the figure, the month, and the NBS release date. If you cannot confirm a clearly signed official figure, return low confidence so the prior is held.

**What the agent searches.** China PPI producer price index year-on-year latest percent NBS

**Authoritative sources.** https://www.stats.gov.cn/english/, https://tradingeconomics.com/china/producer-prices-change

### New tariff/anti-dumping actions (0 calm / 1 rising / 2 escalating)  

*Story:* China's price spillover (deflation or cost-push)  
*Indicator id:* `trade_actions`  
*Type:* band  
*Weight on the meter:* 1.0  

**Rubric.** COUNT new major-economy trade measures (tariffs, anti-dumping, export bans) in the trailing 3 months. 0 = CALM: none. 1 = RISING: 1-3 new measures but within a managed truce. 2 = ESCALATING: >=4 new measures, OR a broad tariff round (>=10% across a sector), OR an explicit truce breakdown. List the measures.

**What the agent searches.** new tariffs anti-dumping China export trade measures latest 2026

**Authoritative sources.** https://www.reuters.com/business, https://www.wto.org

### Rare-earth export license flow (0 flowing / 1 slowing / 2 frozen)  

*Story:* Critical minerals as a weapon  
*Indicator id:* `license_flow`  
*Type:* band  
*Weight on the meter:* 1.5  

**Rubric.** Judge China's rare-earth export licensing regime by APPROVAL BREADTH and PROCESSING TIME per MOFCOM announcements and credible trade reporting. 0 = FLOWING: general/blanket licences cover most export volume AND typical approvals <30 days, no new categories restricted in the trailing 3 months. 1 = SLOWING: case-by-case or whitelist licensing (approvals limited to named producers/end-users), OR typical processing >30 days, OR a new category added to the control list in the trailing 3 months. 2 = FROZEN: categorical denials to a country/sector, OR no new licences issued for >30 days, OR an announced suspension of export licensing.

**What the agent searches.** China rare earth magnet export licenses approvals status 2026

**Authoritative sources.** https://www.reuters.com/markets/commodities, https://www.csis.org

### Nov-2025 pause status (0 extended / 1 expiring / 2 lapsed)  

*Story:* Critical minerals as a weapon  
*Indicator id:* `truce_status`  
*Type:* band  
*Weight on the meter:* 1.0  

**Rubric.** Track the US-China minerals truce itself (agreed Nov 2025; extended on 2026-09-23 to a nominal expiry of 2027-01-10 - use any later extension if one is announced). 0 = EXTENDED/holding: in force, more than 90 days to expiry, no formal breach. 1 = EXPIRING/fraying: 90 days or fewer to expiry with no renewal announced, OR either government formally accuses the other of breaching truce terms, OR an official assessment finds licensing of truce-covered minerals materially below committed volumes. 2 = LAPSED: truce expired or formally abandoned / controls reimposed. Entity-list additions (MOFCOM listings of named firms) are scored separately by re_blacklist and must NOT be counted here.

**What the agent searches.** US China rare earth trade truce status extension expiry January 10 2027 breach

**Authoritative sources.** https://www.reuters.com, https://www.csis.org

### US domestic RE producer blacklist (0 none / 1 entity-specific ban / 2 sector-wide ban)  

*Story:* Critical minerals as a weapon  
*Indicator id:* `re_blacklist`  
*Type:* band  
*Weight on the meter:* 1.0  

**Rubric.** Count the FACT, do not interpret severity. 0 = NO US domestic rare-earth producer is on China's MOFCOM export-control / entity list. 1 = ENTITY-SPECIFIC: one or more named US producers are listed (e.g. MP Materials, USA Rare Earth) but the restriction is firm-specific. 2 = SECTOR-WIDE: the listing is broadened to a categorical ban covering the US rare-earth sector or all dual-use transfers to US producers as a class. State which firms are listed and the listing date.

**What the agent searches.** China MOFCOM export control entity list US rare earth producers MP Materials USA Rare Earth

**Authoritative sources.** https://www.mofcom.gov.cn, https://www.reuters.com, https://www.csis.org

### Ex-China heavy rare-earth price premium (x China)  

*Story:* Critical minerals as a weapon  
*Indicator id:* `hree_premium`  
*Type:* value  
*Bands from thresholds:* good ≤ 2.0, warn ≈ 4.0  
*Weight on the meter:* 0.5  

**Rubric.** Report the approximate ex-China heavy-rare-earth price premium as a multiple of the China price (e.g. 3.0).

**What the agent searches.** heavy rare earth ex-China price premium multiple 2026

**Authoritative sources.** https://www.fastmarkets.com, https://adamasintel.com

### Taiwan / cross-strait tension (0 calm / 1 elevated / 2 crisis)  

*Story:* The lithography (ASML) chokepoint  
*Indicator id:* `taiwan_tension`  
*Type:* band  
*Weight on the meter:* 1.5  

**Rubric.** 0 = CALM: routine activity. 1 = ELEVATED: large-scale PLA drills, blockade rehearsals, or assertive patrols, but no kinetic clash or blockade. 2 = CRISIS: an actual blockade, a kinetic clash, or full mobilization. State the latest military event and date.

**What the agent searches.** Taiwan Strait China military tension drills incidents latest 2026

**Authoritative sources.** https://www.reuters.com/world/asia-pacific, https://www.csis.org/programs/china-power-project

### Export-control escalation (0 stable / 1 tightening / 2 retaliation)  

*Story:* The lithography (ASML) chokepoint  
*Indicator id:* `export_controls`  
*Type:* band  
*Weight on the meter:* 0.5  

**Rubric.** COUNT active semiconductor export-control escalations (trailing 3 months). 0 = STABLE: no new measures. 1 = TIGHTENING: new US/allied controls OR new entity-list additions. 2 = RETALIATION: the target country enacts countermeasures (counter-controls, legal retaliation, equipment bans). List the measures on each side.

**What the agent searches.** semiconductor export controls ASML China escalation retaliation 2026

**Authoritative sources.** https://www.bis.doc.gov, https://www.csis.org, https://www.reuters.com/technology

### Single-point concentration (0 easing / 1 high / 2 extreme)  

*Story:* The lithography (ASML) chokepoint  
*Indicator id:* `fab_concentration`  
*Type:* band  
*Weight on the meter:* 0.5  

**Rubric.** Measure the share of leading-edge (<=3nm) capacity outside Taiwan. 0 = EASING: >25% outside Taiwan and rising. 1 = HIGH: 10-25% outside Taiwan; diversification underway but Taiwan dominant. 2 = EXTREME: <10% outside Taiwan AND no operational overseas leading-edge fab. Cite capacity figures.

**What the agent searches.** advanced chip fab geographic diversification Taiwan TSMC US Japan 2026

**Authoritative sources.** https://www.tsmc.com, https://www.semiconductors.org, https://www.reuters.com/technology

### Hormuz/Red Sea status (0 open / 1 contested / 2 closed)  

*Story:* Sea lanes & undersea cables  
*Indicator id:* `hormuz_redsea_status`  
*Type:* band  
*Weight on the meter:* 1.0  

**Rubric.** Rate the WORSE of the two chokepoints - the Strait of Hormuz and the Red Sea / Bab el-Mandeb - by MEASURED traffic, not by diplomacy. Step 1: find the latest 7-day average of commercial transits (IMF PortWatch preferred; Lloyd's List, Kpler or Windward otherwise) and the pre-crisis baseline (Hormuz about 85-100 per day; Bab el-Mandeb about 70 per day before November 2023). Step 2: compute traffic as a percent of baseline. 2 = CLOSED: below 25% of baseline. 1 = CONTESTED: 25-80% of baseline, OR attacks on shipping, mining, or declared transit restrictions in the last 30 days while traffic stays above 25%. 0 = OPEN: above 80% of baseline and no attacks in the last 30 days. Talks, memoranda, ceasefire announcements and naval escorts do NOT change the rating by themselves - only measured traffic and actual attacks do. State the transit figure, its date and source, and the baseline used.

**What the agent searches.** Strait of Hormuz daily transits IMF PortWatch Lloyd's List latest week; Red Sea Bab el-Mandeb transits; attacks on shipping

**Authoritative sources.** https://portwatch.imf.org, https://www.reuters.com/world/middle-east, https://www.imo.org, https://www.cfr.org

### Undersea cable incidents (0 none / 1 threatened / 2 cut)  

*Story:* Sea lanes & undersea cables  
*Indicator id:* `cable_incidents`  
*Type:* band  
*Weight on the meter:* 0.5  

**Rubric.** 0 = NONE: no damage to major submarine cables in the last 90 days and none currently unrepaired. 1 = THREATENED: credible official threats, or anchor-dragging or damage incidents in the last 90 days, or a cut in the last 90 days that has since been repaired. 2 = CUT: at least one major cable is severed and unrepaired TODAY, causing connectivity loss, or multiple simultaneous cuts in the last 30 days. Cuts more than 90 days old that have been repaired do not count. Name the cable(s) and the date.

**What the agent searches.** undersea submarine cable damage cut Red Sea Hormuz Baltic latest 2026

**Authoritative sources.** https://www.submarinecablemap.com, https://www.reuters.com/technology, https://www.lloydslist.com


## Set 5 — Physical & Resource Limits

### Grid interconnection wait (months)  

*Story:* AI power & the grid bottleneck  
*Indicator id:* `interconnection_months`  
*Type:* value  
*Bands from thresholds:* good ≤ 36, warn ≈ 50  
*Weight on the meter:* 0.5  

**Rubric.** Report the latest median grid interconnection wait in months (e.g. 54).

**What the agent searches.** US grid interconnection queue wait time median months latest LBNL

**Authoritative sources.** https://emp.lbl.gov/queues, https://www.ferc.gov

### Data-center moratoria / backlash (0 none / 1 spreading / 2 widespread)  

*Story:* AI power & the grid bottleneck  
*Indicator id:* `dc_moratoria`  
*Type:* band  
*Weight on the meter:* 1.0  

**Rubric.** COUNT jurisdictions with enacted data-center moratoria or construction pauses. 0 = NONE. 1 = SPREADING: bills introduced or local pauses in 1-10 jurisdictions. 2 = WIDESPREAD: a statewide moratorium enacted, OR >10 jurisdictions with enacted pauses/cancellations. List the jurisdictions.

**What the agent searches.** data center moratorium ban state legislation electricity backlash 2026

**Authoritative sources.** https://www.utilitydive.com, https://www.datacenterdynamics.com

### AI power-demand pressure (0 easing / 1 tight / 2 acute)  

*Story:* AI power & the grid bottleneck  
*Indicator id:* `ai_power_pressure`  
*Type:* band  
*Weight on the meter:* 1.0  

**Rubric.** Use grid-operator/IEA evidence on data-center power. 0 = EASING: interconnection queues shortening, no curtailment. 1 = TIGHT: queues long and lengthening, projects delayed for power, but no forced curtailment. 2 = ACUTE: confirmed curtailment of data-center load, a declared grid emergency, or a power-scarcity-driven moratorium. Cite IEA/grid operator.

**What the agent searches.** data center power demand growth grid shortfall vs slowdown 2026

**Authoritative sources.** https://www.iea.org, https://www.woodmac.com, https://www.spglobal.com/commodityinsights

### Major mine disruptions (0 none / 1 some / 2 cluster)  

*Story:* Copper & the electrification deficit  
*Indicator id:* `mine_disruptions`  
*Type:* band  
*Weight on the meter:* 1.0  

**Rubric.** COUNT top-20-by-output copper mines with confirmed production cuts/outages currently active. 0 = NONE. 1 = SOME: 1-2 mines with reduced output. 2 = CLUSTER: >=3 major mines disrupted, OR lost output large enough that institutions forecast a market deficit. Name the mines.

**What the agent searches.** major copper mine disruption outage strike 2026 Grasberg Kamoa

**Authoritative sources.** https://www.mining.com, https://www.reuters.com/markets/commodities

### Deficit timing (0 surplus / 1 balanced / 2 deficit)  

*Story:* Copper & the electrification deficit  
*Indicator id:* `copper_deficit_timing`  
*Type:* band  
*Weight on the meter:* 0.5  

**Rubric.** Use the latest ICSG (or MS/JPM/ING consensus) refined-copper balance forecast for the current year. 0 = SURPLUS: official forecast a surplus. 1 = BALANCED: forecast within +/-100kt of balance. 2 = DEFICIT: forecast a refined deficit. Cite the ICSG forecast and number.

**What the agent searches.** copper market balance surplus deficit ICSG forecast 2026

**Authoritative sources.** https://icsg.org, https://www.spglobal.com/commodityinsights

### Drought in a chip/farm hub (0 none / 1 emerging / 2 acute)  

*Story:* Water - the underpriced input  
*Indicator id:* `drought_chip_farm`  
*Type:* band  
*Weight on the meter:* 1.0  

**Rubric.** Use a drought monitor for a named chip or farm hub (US Southwest, Taiwan, others). Rate CURRENT conditions. 0 = NONE: normal precipitation and snowpack. 1 = EMERGING: 'severe' (D2) drought, or snowpack 20-50% below normal, or an earlier rationing order that has since been lifted, with no production impact now. 2 = ACUTE: 'extreme' or 'exceptional' (D3-D4) drought now, OR a water-rationing order or production curtailment at a fab or farm region that is IN FORCE today or was imposed in the last 90 days. Cite the monitor, and the date of any order and whether it is still in force.

**What the agent searches.** drought Taiwan US Southwest major farming region chip fab water 2026

**Authoritative sources.** https://droughtmonitor.unl.edu, https://www.reuters.com, https://www.wri.org

### Key reservoir / basin stress (0 normal / 1 low / 2 critical)  

*Story:* Water - the underpriced input  
*Indicator id:* `reservoir_stress`  
*Type:* band  
*Weight on the meter:* 0.5  

**Rubric.** Track a key reservoir (e.g. Lake Mead) level vs its critical threshold. 0 = NORMAL: storage >50% of capacity. 1 = LOW: 30-50% of capacity, or below the date-average. 2 = CRITICAL: <30% of capacity, OR within 15 feet of a power-generation/dead-pool threshold. Cite the USBR level.

**What the agent searches.** Lake Mead Colorado River reservoir levels key basins latest 2026

**Authoritative sources.** https://www.usbr.gov/lc/region/g4000/hourly/levels.html, https://water.weather.gov

### Transboundary water dispute escalation (0 calm / 1 tense / 2 crisis)  

*Story:* Water - the underpriced input  
*Indicator id:* `water_dispute`  
*Type:* band  
*Weight on the meter:* 0.5  

**Rubric.** Track named transboundary river disputes (Indus, Nile/GERD, Mekong, Tigris-Euphrates and others). Rate on DATED events. 2 = CRISIS: within the last 90 days, an armed clash over water, a deliberate cut-off or major flow manipulation actually carried out, or an explicit threat of war tied to a dam or river by a head of state or government, defence minister or foreign minister. 1 = TENSE: a treaty is suspended, in abeyance or formally contested (a standing condition), or level-2 events occurred more than 90 days ago without resolution. 0 = CALM: treaties functioning and no such events in the last 12 months. Older events are background - do not score them again as if new. Name the dispute and give the date of the most recent qualifying event.

**What the agent searches.** transboundary water dispute Nile GERD Indus escalation 2026

**Authoritative sources.** https://www.aljazeera.com, https://www.reuters.com/world

### Food-price trend (0 falling / 1 elevated / 2 spiking)  

*Story:* Food & fertilizer fragility  
*Indicator id:* `fao_food_trend`  
*Type:* band  
*Weight on the meter:* 0.5  

**Rubric.** Use the FAO Food Price Index (monthly). 0 = FALLING: index down MoM and YoY. 1 = ELEVATED: index rising or at a multi-year high but MoM change <3%. 2 = SPIKING: MoM increase >=5%, or a 3-month rise >=10%. Cite the index value and month.

**What the agent searches.** FAO Food Price Index latest direction rising falling 2026

**Authoritative sources.** https://www.fao.org/worldfoodsituation/foodpricesindex, https://www.fao.org

### China fertilizer export curbs (0 lifted / 1 in place / 2 tightened)  

*Story:* Food & fertilizer fragility  
*Indicator id:* `china_export_curbs`  
*Type:* band  
*Weight on the meter:* 1.0  

**Rubric.** 0 = LIFTED: no active Chinese fertilizer export restrictions. 1 = IN PLACE: existing quotas/suspensions continue unchanged (e.g. phosphate suspension, urea quota). 2 = TIGHTENED: a NEW or broadened restriction in the trailing 3 months (added product, lower quota, longer suspension). Cite NDRC/customs and the specific measure.

**What the agent searches.** China fertilizer export restrictions urea phosphate quota status 2026

**Authoritative sources.** https://www.foodsecurityportal.org, https://blogs.worldbank.org

### Hormuz/Gulf disruption to fertilizer inputs (0 clear / 1 disrupted / 2 cut)  

*Story:* Food & fertilizer fragility  
*Indicator id:* `hormuz_fertilizer`  
*Type:* band  
*Weight on the meter:* 1.0  

**Rubric.** Rate Gulf fertilizer, sulfur and ammonia flows through the Strait of Hormuz using the SAME transit measure as hormuz_redsea_status (Hormuz only), so the two reads cannot disagree about the strait. 2 = CUT: Hormuz commercial transits below 25% of the pre-crisis baseline (latest 7-day average; baseline about 85-100 per day). 1 = DISRUPTED: transits 25-80% of baseline, OR documented Gulf fertilizer, sulfur or ammonia loadings below 50% of normal in the latest month reported. 0 = FLOWING: transits above 80% of baseline and Gulf fertilizer loadings near normal. Diplomacy, naval escorts and insurance costs do not change the rating by themselves. State the transit figure, its date, source and the baseline used.

**What the agent searches.** Strait of Hormuz daily transits IMF PortWatch latest; Gulf sulfur ammonia urea loadings latest month

**Authoritative sources.** https://portwatch.imf.org, https://www.fao.org, https://blogs.worldbank.org, https://www.reuters.com/markets/commodities

