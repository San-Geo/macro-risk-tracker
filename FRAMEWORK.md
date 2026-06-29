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

**Rubric.** 0 = implementation on schedule, no delay; 1 = partial delay, phased relief, or notable industry pushback; 2 = mandate delayed, carved out, or paused.

**What the agent searches.** SEC US Treasury central clearing mandate 2026 2027 timeline status delay

**Authoritative sources.** https://www.sec.gov, https://www.dtcc.com, https://www.risk.net

### 30-year JGB yield (%)  

*Story:* Japan fiscal / JGB / carry trade  
*Indicator id:* `jgb30`  
*Type:* value  
*Bands from thresholds:* good ≤ 3.4, warn ≈ 3.9  
*Weight on the meter:* 1.0  

**Rubric.** Report the latest 30-year Japanese Government Bond yield as a percent (e.g. 3.4).

**What the agent searches.** Japan 30-year JGB yield today percent

**Authoritative sources.** https://www.investing.com/rates-bonds/japan-30-year-bond-yield, https://tradingeconomics.com/japan/government-bond-yield

### Takaichi plan financing clarity (0 ok / 1 unclear / 2 disorderly)  

*Story:* Japan fiscal / JGB / carry trade  
*Indicator id:* `plan_financing`  
*Type:* band  
*Weight on the meter:* 1.0  

**Rubric.** 0 = funding path clear and market-accepted; 1 = financing unclear or causing yield pressure; 2 = disorderly (sharp yield spike or failed/under-covered auctions).

**What the agent searches.** Japan Takaichi fiscal stimulus plan financing JGB issuance market reaction

**Authoritative sources.** https://www.reuters.com/markets/asia, https://www.bloomberg.com/markets

### Direct-lending default rate (%)  

*Story:* Private credit's opaque expansion  
*Indicator id:* `direct_lending_default`  
*Type:* value  
*Bands from thresholds:* good ≤ 3.0, warn ≈ 5.0  
*Weight on the meter:* 1.5  

**Rubric.** Report the latest direct-lending / private-credit default rate as a percent (e.g. 3.0).

**What the agent searches.** private credit direct lending default rate latest 2026 percent

**Authoritative sources.** https://www.imf.org/en/Publications/GFSR, https://pitchbook.com, https://www.ft.com

### Large-fund redemption gates (0 none / 1 isolated / 2 widespread)  

*Story:* Private credit's opaque expansion  
*Indicator id:* `redemption_gates`  
*Type:* band  
*Weight on the meter:* 1.0  

**Rubric.** 0 = no redemption gating; 1 = isolated funds limiting redemptions; 2 = widespread gating across large funds.

**What the agent searches.** private credit fund redemption gates limits 2026

**Authoritative sources.** https://www.ft.com, https://www.bloomberg.com

### Largest stablecoin max peg deviation (%)  

*Story:* Stablecoins & Treasury demand  
*Indicator id:* `peg_deviation`  
*Type:* value  
*Bands from thresholds:* good ≤ 0.5, warn ≈ 2.0  
*Weight on the meter:* 1.5  

**Rubric.** Report the largest recent peg deviation of a major stablecoin as a percent away from $1 (e.g. 0.1).

**What the agent searches.** largest stablecoin USDT USDC peg deviation depeg percent latest

**Authoritative sources.** https://www.coindesk.com, https://defillama.com/stablecoins

### Total USD stablecoin supply ($bn)  

*Story:* Stablecoins & Treasury demand  
*Indicator id:* `stablecoin_supply`  
*Type:* value  
*Bands from thresholds:* good ≤ 350, warn ≈ 600  
*Weight on the meter:* 0.5  

**Rubric.** Report total USD stablecoin supply in billions of dollars (e.g. 280).

**What the agent searches.** total stablecoin market cap supply USD billions latest

**Authoritative sources.** https://defillama.com/stablecoins, https://www.theblock.co/data/stablecoins

### GENIUS implementation friction (0 smooth / 1 gaps / 2 problems)  

*Story:* Stablecoins & Treasury demand  
*Indicator id:* `genius_impl`  
*Type:* band  
*Weight on the meter:* 0.5  

**Rubric.** 0 = smooth implementation; 1 = gaps or compliance friction; 2 = significant problems or a major non-compliant failure.

**What the agent searches.** GENIUS Act stablecoin regulation implementation 2026 status issues

**Authoritative sources.** https://www.sec.gov, https://www.federalreserve.gov, https://www.coindesk.com/policy

### Treasury-clearing rollout stress (0 smooth / 1 friction / 2 problems)  

*Story:* Clearinghouses (financial chokepoint)  
*Indicator id:* `treasury_clearing_rollout`  
*Type:* band  
*Weight on the meter:* 0.5  

**Rubric.** 0 = smooth, on track; 1 = friction / capacity concerns; 2 = significant problems or disorderly rollout.

**What the agent searches.** US Treasury central clearing implementation capacity readiness 2026 2027

**Authoritative sources.** https://www.sec.gov, https://www.dtcc.com, https://www.risk.net


## Set 2 — Credit, Consumers & Valuations

### AI capex-vs-revenue gap concern (0 closing / 1 wide / 2 widening fast)  

*Story:* AI build-out circular financing  
*Indicator id:* `ai_revenue_gap`  
*Type:* band  
*Weight on the meter:* 1.0  

**Rubric.** 0 = gap closing / revenue catching up; 1 = wide but stable gap; 2 = gap widening fast or clear monetization disappointment.

**What the agent searches.** AI capex versus revenue gap monetization concern 2026 hyperscaler

**Authoritative sources.** https://www.theinformation.com, https://www.ft.com, https://www.sequoiacap.com

### GPU-backed debt refinancing stress (0 none / 1 signs / 2 acute)  

*Story:* AI build-out circular financing  
*Indicator id:* `gpu_refi_stress`  
*Type:* band  
*Weight on the meter:* 1.0  

**Rubric.** 0 = none; 1 = early signs of strain; 2 = acute refinancing stress or a notable default.

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

**Rubric.** 0 = calm; 1 = isolated regional-bank stress; 2 = a cluster of failures or sharp deposit flight.

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

**Rubric.** 0 = stable; 1 = rising delinquencies; 2 = sharp spike or major BNPL lender distress.

**What the agent searches.** buy now pay later BNPL delinquency trend 2026 Affirm Klarna

**Authoritative sources.** https://www.richmondfed.org, https://www.cfpb.gov, https://www.ft.com

### Insurer non-renewals / exits (0 stable / 1 rising / 2 accelerating)  

*Story:* Insurance retreat  
*Indicator id:* `insurer_exits`  
*Type:* band  
*Weight on the meter:* 1.0  

**Rubric.** 0 = stable; 1 = rising non-renewals/exits; 2 = accelerating withdrawals across multiple states.

**What the agent searches.** home insurer non-renewals market exits states 2026

**Authoritative sources.** https://www.naic.org, https://www.insurancejournal.com

### Catastrophe-loss pressure (0 normal / 1 elevated / 2 severe season)  

*Story:* Insurance retreat  
*Indicator id:* `cat_losses`  
*Type:* band  
*Weight on the meter:* 1.0  

**Rubric.** 0 = normal season; 1 = elevated catastrophe losses; 2 = a severe / record loss season underway.

**What the agent searches.** insured catastrophe losses severe season 2026 hurricane wildfire

**Authoritative sources.** https://www.aon.com/reinsurance, https://www.munichre.com, https://www.swissre.com/institute/


## Set 3 — Sovereigns & the Monetary Order

### New IMF programs / missed coupons (0 calm / 1 rising / 2 cluster)  

*Story:* Developing-world debt crisis  
*Indicator id:* `new_imf_programs`  
*Type:* band  
*Weight on the meter:* 1.0  

**Rubric.** 0 = calm, no new distress; 1 = rising (new IMF programs or missed coupons appearing); 2 = a cluster of sovereign defaults/programs at once.

**What the agent searches.** IMF new program emerging market default missed coupon 2026

**Authoritative sources.** https://www.imf.org/en/News, https://www.worldbank.org

### Govt stability (0 stable / 1 fragile / 2 collapse-or-snap-election)  

*Story:* France / eurozone fragility  
*Indicator id:* `govt_stability`  
*Type:* band  
*Weight on the meter:* 1.0  

**Rubric.** 0 = stable government; 1 = fragile (minority govt, budget fights); 2 = collapse, snap election called, or presidential crisis.

**What the agent searches.** France government stability budget no-confidence snap election latest

**Authoritative sources.** https://www.lemonde.fr/en/, https://www.reuters.com/world/europe

### Rating action (0 stable / 1 negative outlook / 2 downgrade)  

*Story:* France / eurozone fragility  
*Indicator id:* `rating_action`  
*Type:* band  
*Weight on the meter:* 1.0  

**Rubric.** 0 = stable outlook; 1 = negative outlook or watch; 2 = an actual downgrade.

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

**Rubric.** 0 = none; 1 = new talk/agreements on non-dollar settlement or asset-freeze threats; 2 = a major new reserve freeze or settlement shift.

**What the agent searches.** reserve weaponization sanctions asset freeze non-dollar settlement latest 2026

**Authoritative sources.** https://www.reuters.com, https://www.atlanticcouncil.org

### Social Security / pension reform shock (0 none / 1 debate / 2 cuts)  

*Story:* Pensions / demographics  
*Indicator id:* `ss_reform_news`  
*Type:* band  
*Weight on the meter:* 1.0  

**Rubric.** 0 = no change; 1 = active reform debate or trust-fund warnings; 2 = concrete benefit cuts or an emergency measure.

**What the agent searches.** US Social Security trust fund reform benefit cut pension news 2026

**Authoritative sources.** https://www.ssa.gov/oact/, https://www.crfb.org

### Pension-fund leverage event, UK-2022 type (0 none / 1 stress / 2 blowup)  

*Story:* Pensions / demographics  
*Indicator id:* `pension_leverage_event`  
*Type:* band  
*Weight on the meter:* 1.0  

**Rubric.** 0 = none; 1 = visible pension-leverage stress; 2 = a UK-2022-style forced-selling blow-up.

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

### China PPI YoY (%) - more negative is worse  

*Story:* China's exported deflation  
*Indicator id:* `china_ppi`  
*Type:* value  
*Bands from thresholds:* good ≤ -1.0, warn ≈ -3.0  
*Weight on the meter:* 1.0  

**Rubric.** Report the latest China PPI year-on-year change as a percent (negative = deflation, e.g. -2.5).

**What the agent searches.** China PPI producer price index year-on-year latest percent

**Authoritative sources.** https://www.stats.gov.cn/english/, https://tradingeconomics.com/china/producer-prices-change

### New tariff/anti-dumping actions (0 calm / 1 rising / 2 escalating)  

*Story:* China's exported deflation  
*Indicator id:* `trade_actions`  
*Type:* band  
*Weight on the meter:* 1.0  

**Rubric.** 0 = calm; 1 = rising tariff/anti-dumping actions; 2 = escalating trade-war cycle with major new measures.

**What the agent searches.** new tariffs anti-dumping China export trade measures latest 2026

**Authoritative sources.** https://www.reuters.com/business, https://www.wto.org

### Rare-earth export license flow (0 flowing / 1 slowing / 2 frozen)  

*Story:* Critical minerals as a weapon  
*Indicator id:* `license_flow`  
*Type:* band  
*Weight on the meter:* 1.5  

**Rubric.** 0 = licenses flowing normally; 1 = slowing/selective approvals; 2 = effectively frozen or new broad restrictions.

**What the agent searches.** China rare earth magnet export licenses approvals status 2026

**Authoritative sources.** https://www.reuters.com/markets/commodities, https://www.csis.org

### Nov-2025 pause status (0 extended / 1 expiring / 2 lapsed)  

*Story:* Critical minerals as a weapon  
*Indicator id:* `truce_status`  
*Type:* band  
*Weight on the meter:* 1.0  

**Rubric.** 0 = truce extended/holding; 1 = truce expiring or fraying; 2 = truce lapsed / controls reimposed.

**What the agent searches.** US China rare earth trade truce November 2025 status extended expired

**Authoritative sources.** https://www.reuters.com, https://www.csis.org

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

**Rubric.** 0 = baseline tension; 1 = elevated (large drills, incidents, sharp escalation in rhetoric); 2 = crisis (blockade, clash, mobilization).

**What the agent searches.** Taiwan Strait China military tension drills incidents latest 2026

**Authoritative sources.** https://www.reuters.com/world/asia-pacific, https://www.csis.org/programs/china-power-project

### Export-control escalation (0 stable / 1 tightening / 2 retaliation)  

*Story:* The lithography (ASML) chokepoint  
*Indicator id:* `export_controls`  
*Type:* band  
*Weight on the meter:* 0.5  

**Rubric.** 0 = stable regime; 1 = tightening controls; 2 = major new controls or Chinese retaliation.

**What the agent searches.** semiconductor export controls ASML China escalation retaliation 2026

**Authoritative sources.** https://www.bis.doc.gov, https://www.csis.org, https://www.reuters.com/technology

### Single-point concentration (0 easing / 1 high / 2 extreme)  

*Story:* The lithography (ASML) chokepoint  
*Indicator id:* `fab_concentration`  
*Type:* band  
*Weight on the meter:* 0.5  

**Rubric.** 0 = meaningful diversification progressing; 1 = still highly concentrated; 2 = concentration worsening / diversification stalled.

**What the agent searches.** advanced chip fab geographic diversification Taiwan TSMC US Japan 2026

**Authoritative sources.** https://www.tsmc.com, https://www.semiconductors.org, https://www.reuters.com/technology

### Hormuz/Red Sea status (0 open / 1 contested / 2 closed)  

*Story:* Sea lanes & undersea cables  
*Indicator id:* `hormuz_redsea_status`  
*Type:* band  
*Weight on the meter:* 1.0  

**Rubric.** 0 = open and normal; 1 = contested (attacks, partial disruption, fragile ceasefire); 2 = effectively closed/blockaded.

**What the agent searches.** Strait of Hormuz Red Sea shipping status open closed ceasefire latest 2026

**Authoritative sources.** https://www.reuters.com/world/middle-east, https://www.imo.org, https://www.cfr.org

### Undersea cable incidents (0 none / 1 threatened / 2 cut)  

*Story:* Sea lanes & undersea cables  
*Indicator id:* `cable_incidents`  
*Type:* band  
*Weight on the meter:* 0.5  

**Rubric.** 0 = none; 1 = threats or minor incidents; 2 = a major cable cut causing outages.

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

**Rubric.** 0 = none; 1 = several states weighing moratoria / rising backlash; 2 = widespread bans or major project cancellations.

**What the agent searches.** data center moratorium ban state legislation electricity backlash 2026

**Authoritative sources.** https://www.utilitydive.com, https://www.datacenterdynamics.com

### AI power-demand pressure (0 easing / 1 tight / 2 acute)  

*Story:* AI power & the grid bottleneck  
*Indicator id:* `ai_power_pressure`  
*Type:* band  
*Weight on the meter:* 1.0  

**Rubric.** 0 = easing (demand slowing / supply catching up); 1 = tight; 2 = acute shortfall (curtailments, emergencies).

**What the agent searches.** data center power demand growth grid shortfall vs slowdown 2026

**Authoritative sources.** https://www.iea.org, https://www.woodmac.com, https://www.spglobal.com/commodityinsights

### Major mine disruptions (0 none / 1 some / 2 cluster)  

*Story:* Copper & the electrification deficit  
*Indicator id:* `mine_disruptions`  
*Type:* band  
*Weight on the meter:* 1.0  

**Rubric.** 0 = none; 1 = some disruptions; 2 = a cluster of major outages tightening supply.

**What the agent searches.** major copper mine disruption outage strike 2026 Grasberg Kamoa

**Authoritative sources.** https://www.mining.com, https://www.reuters.com/markets/commodities

### Deficit timing (0 surplus / 1 balanced / 2 deficit)  

*Story:* Copper & the electrification deficit  
*Indicator id:* `copper_deficit_timing`  
*Type:* band  
*Weight on the meter:* 0.5  

**Rubric.** 0 = surplus / well supplied; 1 = roughly balanced; 2 = in deficit (inventories drawing down).

**What the agent searches.** copper market balance surplus deficit ICSG forecast 2026

**Authoritative sources.** https://icsg.org, https://www.spglobal.com/commodityinsights

### Drought in a chip/farm hub (0 none / 1 emerging / 2 acute)  

*Story:* Water - the underpriced input  
*Indicator id:* `drought_chip_farm`  
*Type:* band  
*Weight on the meter:* 1.0  

**Rubric.** 0 = no significant drought in key hubs; 1 = emerging drought in a chip/farm hub; 2 = acute drought disrupting chips or major crops.

**What the agent searches.** drought Taiwan US Southwest major farming region chip fab water 2026

**Authoritative sources.** https://droughtmonitor.unl.edu, https://www.reuters.com, https://www.wri.org

### Key reservoir / basin stress (0 normal / 1 low / 2 critical)  

*Story:* Water - the underpriced input  
*Indicator id:* `reservoir_stress`  
*Type:* band  
*Weight on the meter:* 0.5  

**Rubric.** 0 = normal levels; 1 = low / below average; 2 = critical (near dead-pool or emergency cuts).

**What the agent searches.** Lake Mead Colorado River reservoir levels key basins latest 2026

**Authoritative sources.** https://www.usbr.gov/lc/region/g4000/hourly/levels.html, https://water.weather.gov

### Transboundary water dispute escalation (0 calm / 1 tense / 2 crisis)  

*Story:* Water - the underpriced input  
*Indicator id:* `water_dispute`  
*Type:* band  
*Weight on the meter:* 0.5  

**Rubric.** 0 = calm; 1 = tense / negotiations stalled; 2 = open crisis or unilateral action.

**What the agent searches.** transboundary water dispute Nile GERD Indus escalation 2026

**Authoritative sources.** https://www.aljazeera.com, https://www.reuters.com/world

### Food-price trend (0 falling / 1 elevated / 2 spiking)  

*Story:* Food & fertilizer fragility  
*Indicator id:* `fao_food_trend`  
*Type:* band  
*Weight on the meter:* 0.5  

**Rubric.** 0 = falling/stable; 1 = elevated and rising; 2 = spiking sharply.

**What the agent searches.** FAO Food Price Index latest direction rising falling 2026

**Authoritative sources.** https://www.fao.org/worldfoodsituation/foodpricesindex, https://www.fao.org

### China fertilizer export curbs (0 lifted / 1 in place / 2 tightened)  

*Story:* Food & fertilizer fragility  
*Indicator id:* `china_export_curbs`  
*Type:* band  
*Weight on the meter:* 1.0  

**Rubric.** 0 = curbs lifted / normal exports; 1 = curbs in place; 2 = curbs tightened or extended.

**What the agent searches.** China fertilizer export restrictions urea phosphate quota status 2026

**Authoritative sources.** https://www.foodsecurityportal.org, https://blogs.worldbank.org

### Hormuz/Gulf disruption to fertilizer inputs (0 clear / 1 disrupted / 2 cut)  

*Story:* Food & fertilizer fragility  
*Indicator id:* `hormuz_fertilizer`  
*Type:* band  
*Weight on the meter:* 1.0  

**Rubric.** 0 = inputs flowing normally; 1 = disrupted/elevated risk; 2 = inputs effectively cut by closure.

**What the agent searches.** Strait of Hormuz sulfur ammonia fertilizer shipping disruption 2026

**Authoritative sources.** https://www.fao.org, https://blogs.worldbank.org, https://www.reuters.com/markets/commodities

