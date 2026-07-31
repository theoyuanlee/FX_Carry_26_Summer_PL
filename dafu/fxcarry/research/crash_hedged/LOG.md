# Crash-hedged carry — research log

Direction D-B. Protocol pre-registered in
`docs/tutorials/pdf/fx_crash_hedged_carry_tutorial.pdf` §9 (written 2026-07-21,
before any result). Own data only (`data/raw/` parquets); the team panel is not
an input. Append-only; newest entries at the bottom.

## 2026-07-21 — setup and data inventory

- Data verified: `fx_vol_daily.parquet` is long format (ticker/date/field/value,
  16.0M rows), 19 pairs, quote types V/25R/25B/10R/10B/5R/5B, tenors
  1W/1M/2M/3M/6M/9M/1Y/18M/2Y, fields PX_LAST/PX_BID/PX_ASK, BGN source.
  V1M start dates: AUD 1993-12, JPY 1995-12, GBP/CHF 1996-05, most EM ~1999,
  HUF 2005-03. End 2026-07-15. Spot/fwd-points/tbill parquets share the schema.
- Pairs: AUDUSD EURUSD GBPUSD NZDUSD + USD{CAD CHF CZK DKK HUF INR JPY KRW MXN
  NOK PLN SEK SGD TWD ZAR}. INR/KRW/TWD have vol but need forward-tenor checks
  (NDF conventions) before entering the universe.
- Worked-example anchor (tutorial Ex. 1-3, USDJPY 2026-06-30): S=162.55,
  F=162.1415, JPY carry -3.02%/yr, smile 25p/10p/5p = 8.94/10.57/11.60,
  strikes 159.40/156.00/153.54, rolled premium ~4.66/1.75/0.85 %/yr,
  ATM(DNS) K=162.18 premium ~10.93%/yr. Pipeline must reproduce these to 4dp
  (pre-registered validation).
- Decisions taken (tutorial §4-§5): smile-BF approximation (no market-strangle
  calibration), robustness at 10d not 5d; pips-delta closed form in examples,
  premium-adjusted via root-finding in code where the pair convention requires;
  headline at mid premia, bid-side (ask-vol) stress as the cost bracket.
- Open questions before construction: (a) exact Jurek portfolio construction
  details (hedge ratio, which leg hedged, financing, roll timing) — paper read
  dispatched; (b) BEKR hedged-trade construction — dispatched; (c) fxcarry
  library interfaces for the unhedged benchmark — module read dispatched;
  (d) which pairs' quotes are premium-adjusted-delta convention (expect USD-base
  pairs incl. all USDXXX; verify against Castagna/Clark tables during build).

## 2026-07-21 (later) — optmath built; validation caught two real issues

- `optmath.py` written (GK forward form, smile-from-quotes, strike-from-delta
  pips closed form + premium-adjusted Brent root, DNS-ATM both conventions,
  per-pair convention table). `check_optmath.py` runs the pre-registered
  worked-example checks.
- The checks did their job, twice:
  1. **Sign bug**: first version multiplied the strike exponent by cp; d1
     already carries the option-type sign. Symptom: put strikes ABOVE forward,
     premia non-monotone. Caught immediately by the strike/monotonicity checks;
     the independent premium-adjusted root-finder landing at 159.36 confirmed
     the pips path was the broken one.
  2. **Rate-role subtlety**: the pips-delta discount uses the BASE-currency
     rate (USD for USDJPY): N(-d1) = delta * e^{r_base tau}. The original quick
     calc that seeded the tutorial examples used the quote (JPY) rate — a
     ~1-cent strike / 0.2bp premium effect at 25d. Module does it correctly;
     tutorial examples and check targets re-synced to the module (25d K 159.41,
     prem 0.390%/mo; 10d 156.01/0.146; 5d 153.55/0.071; ATM 162.18/0.913).
- All checks pass: strikes/premia to target, put-call parity ~1e-15, premia
  monotone in moneyness, PA-vs-pips 25d strike gap -0.03% (small, as theory
  says). Tutorial PDF recompiled with the synced numbers.
- Note for the write-up: PA-vs-pips gap grows in the wings; convention table in
  `optmath.pair_conventions` is still the rule-of-thumb version pending the
  Jurek/BEKR appendix reads.

## 2026-07-21 (later) — BEKR construction extracted (NBER w14054 rev2, Sep 2010)

Read via agent, page cites in the agent report. What the pipeline inherits:

- **Signal/sizing**: per currency, sign of forward premium — sell 1/F_t FCU
  forward if F_t >= S_t else buy (eq. 4, p. 5); payoff z_{t+1} = w_t(F_t −
  S_{t+1}); portfolio = equally weighted 1/n_t across currencies, monthly.
  This is the same family as fxcarry's BER-style `ew_strategy_return`
  (weight = sign(signal)/N), NOT a rank sort — good, the simplest book is the
  paper-faithful one.
- **Hedge**: option notional exactly matches forward notional (1/F_t FCU):
  F_t >= S_t → short forward + BUY CALL on FCU; F_t < S_t → long forward +
  BUY PUT (p. 8, eq. 14). Premium paid at t, financed to t+1 at the USD rate
  (eqs. 10-11). Floor via put-call-forward parity: h_{t+1} = −P_t(1+r_t)/F_t
  (resp. −C_t(1+r_t)/F_t) — always negative but bounded (eq. 16). USE AS A
  PIPELINE VALIDATION IDENTITY: realized hedged payoff must equal h when ITM.
- **Their ATM arm on JPM data** (the arm our data mirrors): 1M ATM-FORWARD
  implied vols, GK prices, 10 ccys vs USD, Feb 1995–Jul 2009. Decision: our
  BEKR/ATM arm uses ATMF strikes (K = F), not DNS — faithful to the paper;
  DNS-vs-ATMF gap at 1M is ~0.03% of F, immaterial but logged.
- **Benchmarks to compare against** (Table 5, USD, 1987-2009, 6 CME ccys,
  no TC): unhedged EW mean 2.96%/yr, SR 0.476, skew −0.71; ATM-hedged mean
  1.58%/yr, SR 0.449, skew +0.72. Signature to look for: hedging at ATM
  roughly halves the mean and FLIPS SKEW POSITIVE. Ex-crisis (to Jul 2008):
  3.48% vs 1.80%.
- **Option TC**: CME spread ≈ 5.2% of premium; half-spread markup cut hedged
  mean 1.58% → 1.21%. Ours: reprice at ask vols as the stress arm (better
  than a premium markup — we have real two-sided vol quotes).
- **Their SDF argument** (for the write-up, not the pipeline): hedged floor
  E^N(h) = −1.05%/month small ⇒ peso-state loss small ⇒ implied peso-state
  SDF ratio M'/E(M) ≈ 93 (se 48) at disaster prob 0.0014/mo. The wedge with
  Jurek is strike placement: near-ATM (they argue OTM options "sparsely
  traded and relatively expensive", p. 22-23, fn 10 acknowledges Jurek).

## 2026-07-21 (later) — pipeline design decision: standalone, simple-return, paper-faithful

Library interface read (agent) found: (1) the research scripts' `fxcarry.api`
path lives on branch `feature/shrinkage-carry-v2`, not main — importing it on
the current checkout fails; (2) the library's signal path is log-return,
lagged-weight, proportional/rank machinery, while BEKR (and, per its fn 10,
Jurek) build per-currency SIGN books with SIMPLE-return payoffs, where option
payoffs also live naturally (max(K−S,0) does not decompose in logs).

Decision: `research/crash_hedged/` is a standalone pipeline — reads
spot/fwd/vol/tbill parquets directly, BEKR-faithful simple-return accounting,
no branch switching, no library import. It mirrors library conventions
exactly where they are data facts: POINT_SCALE {JPY 100, HUF 100, KRW 1.0,
IDR 100, default 1e4} (constants.py:106-118, incl. the 07-19 KRW fix),
USD-per-FCU quoted set {AUD, EUR, GBP, NZD} inverted with bid/ask side swap.
Universe: start from the research scripts' 15-name UNIVERSE (AUD CAD CHF CZK
DKK EUR GBP HUF JPY NOK NZD PLN SEK SGD ZAR) + MXN if its spot/fwd pass the
same checks; KRW/INR/TWD held out pending NDF-convention verification.
Sample: earliest month with >=8 full 1M smiles (expected ~1996-99) to
2026-06. Rationale logged so the choice is inspectable; the library remains
the reference for any log-return cross-check.

## 2026-07-21 (later) — data layer built; coverage facts revise the sample plan

`build_panel.py` -> `out/monthly_panel.parquet` (6,723 rows, 16 ccys — the
15-name research universe + MXN; KRW/INR/TWD held out). Coverage facts:

- ATM history is long (AUD from 1993) but **25d/10d RR/BF only start
  2003-10** (majors: AUD CAD EUR GBP JPY NZD PLN SGD ZAR, +MXN 2005-03) and
  **2006-01** for CHF CZK DKK HUF NOK SEK. The 1996-99 start imagined at
  setup does not exist for smiles in this pull.
- **5-delta wings are too patchy for a headline arm** (30-130 months per
  pair, holes everywhere). 5d is dropped even from robustness; the tutorial
  already pre-committed robustness to 10d, so no protocol change.
- Revised samples: headline 2006-01 -> 2026-06 (16 pairs, balanced,
  ATM+25d+10d complete); early-start robustness 2003-10 on the 10-pair
  subset; BEKR ATM-only arm additionally runs on the longer ATM history.
- Sanity note: month-end sampling via union-index resample initially made
  coverage look far worse (complete-smile flag required 5d); per-component
  counts diagnosed it. The panel keeps 5d columns for reference only.

## 2026-07-21 (later) — engine built, validated, run; results written up

- `hedged_carry.py`: unhedged sign book + Jurek crash-neutral ladder
  (10d/25d/ATM, native-orientation strikes headline, uniform as robustness)
  + BEKR ATMF overlay; EQL and SPR weights; G10 and ALL16 universes.
- Validation (`validate.py`): ALL CHECKS PASS — anchor row, floor identity
  EXACT in all 959 ITM leg-months, moneyness nesting, premium monotonicity,
  settlement offset. Two bugs caught pre-results: engine initially read
  quoted deltas in $/FCU orientation (fixed to native; the uniform variant
  kept as the Jurek-faithful robustness arm); validate's own vol-side sign
  and a Timedelta-vs-offset comparison.
- Headline (2006-01..2026-06, 246 mo, mid vols): G10 EQL unhedged 0.70%/yr
  SR 0.13; give-up 18%/26%/30% at 10d/25d/ATM, all NW |t|<0.6; ATM-hedged
  Sharpe 0.15 BEATS unhedged; skew -0.21 -> +1.0; maxDD -14.3% -> -7.2%.
  BEKR ATMF give-up 30.0% ~= Jurek ATM 29.7% (construction wedge nil).
  ALL16 EQL give-up 30/44/59%; SPR 25/51/79%. ASK-VOL STRESS: G10 give-up
  55/88/87% — execution side decides the BEKR-vs-Jurek verdict.
  Events: hedges paid Sep/Oct-08, Sep-11, Jan-15; re-strike cost Nov-08
  (DHL sequence risk). 10d book premium ~0.5-1.5%/yr at mid.
- Deliverable: docs/notes/pdf/crash_hedged_results.pdf (4 pp + figures
  fig_ch_* in docs/tutorials/latex/figures/). Next steps queued in the
  report: dollar-neutral variants, quarterly 3M hedging, spanning vs team
  book, per-currency EM insurance decomposition (link to D-E).

## 2026-07-21 (later) — KRW added (the free pull); INR/TWD blocked on forwards

- Free-pull scoping: own `fwd_points_1m_daily` holds KRW1M but NO INR/TWD
  forwards (Bloomberg serves them under NDF roots IRN/NTN, never pulled).
  Conversely THB/MYR/PHP have forwards but no vol surfaces. So the only
  cost-free addition is KRW.
- KRW convention checks passed: scale 1.0 (library, test-guarded); forward-
  implied carry tracks KWCDC-USD differential (corr +0.57) with a ~1%/yr gap
  = the documented onshore/offshore NDF basis (07-19 decision log) — the
  forward prices the *investable* carry, which is what we want. Smile sane
  (ATM 10.5%, RR crash-positive).
- Pipeline rerun with 17 names, ALL CHECKS PASS unchanged. Universe label
  ALL16 -> ALL. KRW profile: 271 leg-months, long only 48% of months,
  +1.55%/yr carry when long, 10d insurance 1.82%/yr — a HALF-carry name;
  aggregates barely move (ALL EQL give-up 32/44/61% vs 30/44/59% before).
  Confirms: the insurable high-carry EM story cannot be reached from data
  on disk; it needs the BRL/TRY/CNH/THB/ILS vol pull + IRN/NTN forwards.

## 2026-07-21 (night) — tutorial rev. 2: the ownership update; plan for 07-22

- Tutorial updated to match the as-built pipeline (user request, ahead of
  tonight's terminal pull and tomorrow-noon presentation): exact Jurek
  crash-neutral sizing + floor (eqs. 8-9 in the doc), BEKR overlay formula,
  the delta-orientation subtlety, a new worked Example 3 that rebuilds the
  stored JPY 2026-06 leg row by hand (delta 0.2589, qty 1.3504, floor
  -2.130%, realized hedged -0.365% — matches parquet to 4dp), a new
  pipeline/gates/ownership section incl. the executed-vs-preregistered
  deltas, and a status note preserving §9 as written. PDF shipped.
- Plan for 2026-07-22 morning, once the user's pull lands in data/raw/
  (long format, any filename): ingest new pairs (BRL TRY CNH THB ILS vol +
  spot + NDF forwards; IRN/NTN forwards for INR/TWD), rerun panel + engine +
  ALL GATES, build the per-currency EM carry-vs-insurance table (the
  centerpiece exhibit), add dollar-neutral variants, quarterly 3M hedging
  (using the 3M pulls), spanning vs the team book, update the results note.
  Target: everything regenerated and written up before noon.

## 2026-07-21 (night) - tutorial rev. 3: retemplated, data-shape section, smile figure

- Tutorial rebuilt on the stat31450 lecture-notes template (12pt, underlined
  headings, Definition/Example/Remark environments; graphicx+booktabs added).
- New application-side content per user request: a raw-data section with the
  four input files' shapes and REAL rows (USDJPY 2026-06-30 incl. two-sided
  RR quotes), ticker grammar, and the curated monthly-panel shape with real
  JPY/AUD rows; a real smile figure (make_smile_figure.py ->
  fig_smile_usdjpy.pdf): calm 2026-06-30 vs crisis 2008-10-31 in delta space
  (ATM 7.8 -> 31.4, 10dRR -2.0 -> -17.4) + strike-space panel with F and the
  Example-1 hedge strikes marked; strikes cross-check Example 1 exactly.
- B-L now cites FINM 32000 Lecture 4 (binary-call CDF, identity, failure
  modes) alongside FINM 37301 Lec 4 slides 26-28; reading pointers moved
  into Remark[Reading] blocks matching the template's own pattern.
- All rev.2 content ported (as-implemented construction, ownership Example,
  gates, execution deltas, preserved pre-registration). Clean compile,
  shipped to docs/tutorials/pdf/.

## 2026-07-21 (night) - tutorial rev. 4: self-contained, plain language

User direction: derivations written out in full (lecture notes cited as
companions only), simple intuitive prose per the humanizer guide. Rewritten
end to end on the stat31450 template:

- Derived in the document itself: put-call parity (replication), GK via the
  risk-neutral expectation (integral worked), pips delta (with the
  density-ratio cancellation shown), premium-adjusted delta (K/F e^{-r*t}
  N(d2), algebra shown), strike-from-delta inversion, DNS-ATM strike,
  smile reconstruction, Breeden-Litzenberger both ways (butterfly limit +
  differentiate-under-the-integral), overlay algebra, decomposition, and
  Jurek's sizing from its two design conditions (flat when ITM;
  delta-matched at initiation).
- New content: B-L density FIGURE built from our own smiles
  (fig_bl_density.pdf; calm P(yen move < -4% in 1M) = 7.8% vs 30.0% on
  2008-10-31; both densities integrate to 1.0000; construction caveats
  stated: flat-tail extrapolation, clipped negative lobes at joins - the
  first uniform-grid attempt had a wrong non-uniform second difference,
  caught by the mass check). ITM worked example (AUD Sep->Oct 2008:
  unhedged -15.66%, hedged = floor exactly at -5.65%, premium 1.14%).
  Papers' benchmark table (Jurek Table VII, BEKR Table 5). Four exercises
  with answers (E2 AUD: sigma 8.374, K 0.6806, prem 0.365%/mo; E4
  aggregation -> 1.05%/yr).
- Density code persisted into make_smile_figure.py (regenerates both
  figures). Clean compile, 17 pages, shipped.

## 2026-07-22 (terminal machine) — EM pull done; the story is complete

- Pulled via xbbg/blpapi (pull_em_options.py): 50 vol tickers (USD{BRL,TRY,
  CNH,THB,ILS} x V/25R/25B/10R/10B x 1M/3M BGN, bid/ask/last) + spot + NDF
  forwards (BCN/TRY/CNH/ILS/THB/IRN/NTN 1M+3M) -> fx_vol_em_daily.parquet,
  spot_fwd_em_daily.parquet. Coverage: BRL/TRY smiles from 2005-11/12, THB
  2003-10, ILS 2006-01, CNH 2011-02; forwards from ~1998.
- Forward-point scales validated by implied-carry reconciliation:
  BRL/TRY/CNH/ILS 1e4, THB/INR 1e2, TWD 1.0 (whole-TWD NDF points; implied
  carry -2.1%/yr vs TAIBOR-USD -0.6%: TWD NDF basis, like KRW's, larger --
  the forward prices investable carry). Logged before ingestion.
- Panel rebuilt: 24 currencies, 9,258 rows. Engine rerun. ALL GATES PASS
  (floor identity exact in 1,337 ITM leg-months; G10 numbers unchanged --
  regression check).
- EM results (15 insurable non-G10, 2006-01..2026-06): EQL unhedged 1.74%/yr
  SR 0.36; give-up 26/49/76% at 10d/25d/ATM (t -1.9 each). SPR unhedged
  3.58%/yr SR 0.40; give-up 15/50/84%, t -2.08 (25d) and -2.33 (ATM) --
  FIRST SIGNIFICANT crash-premium estimates in the project. Ask-vol stress:
  SPR give-up 39/87/112% (hedged EM negative at the ask).
- Per-currency centerpiece (out/per_currency.csv): TRY 16.8% carry when
  long, 0.9% realized, 10d give-up NEGATIVE (-0.3%/yr -- its crashes
  overdelivered vs its own smile); BRL keeps 3.9%/yr fully 10d-hedged;
  ZAR pays most (1.1%/yr at 10d, 63% of its mean); 25d give-ups run
  2-4x the 10d ones everywhere: the EM premium is near-the-money crash
  pay, the deep tail is cheap.
- Results note rev. 2 shipped (docs/notes/pdf/crash_hedged_results.pdf,
  6 pp): EM ladder replaces satellites table, per-currency section added,
  verdict rewritten to the two-regime story. MiKTeX installed per-user on
  this machine for the compile.
- Still open (data on disk, queued): $N variants, quarterly 3M hedge,
  spanning vs team book, EMBI-beta regression of insurance costs (D-E
  bridge). TO DO before leaving the terminal: dvc add the two new parquets
  + git commit/push so machine A gets data pointers and results.

## 2026-07-22 (late morning) — from verdict to strategy: spread-financed carry

- User reframe: the goal is a strategy that OUTPERFORMS vanilla carry, not a
  measurement. The measurement supplied the trade: EM 25d crash protection
  is overpriced (buyers lose, t~-2), the 10d wing is fair -> SELL the
  25d/10d put spread against each carry leg (strikes = the two quoted
  deltas, no fitted parameters; incremental loss bounded at (K25-K10)/F
  ~2%/leg-month).
- Engine: z_ps arm + z_ps_cross (sell 25d @ bid vol = 2*mid-ask, buy 10d @
  ask vol, mid strikes) + floor_10d stored; ALL GATES STILL PASS.
- Results (2006-01..2026-06): EM SPR spread-financed 4.79%/yr SR 0.46 vs
  vanilla 3.58%/0.40 -> pickup +1.21%/yr, NW t=+3.08 — the only
  construction in the project that beats vanilla with significance. G10
  pickup ~0 (no mispricing there: mechanism self-check). Cost: worst month
  -12.4% vs -10.6%, skew -1.32.
- Execution decides: at FULL indicative BGN spread the pickup inverts to
  -1.57%/yr (t=-4.2). Linear in fill -> break-even at ~43% of the quoted
  two-sided spread (SPR; EQL needs ~20%, not robust). Handed to the desk
  with the hurdle measured, not assumed.
- Tested and rejected: floor-sized leverage (10d floor is -4..-6%/mo, sane
  stress budgets de-lever; strategy_table.csv). No per-currency mining on
  top (SPR weighting is the pre-specified tilt).
- Results note updated with the strategy section (table: mid vs full-spread
  vs vanilla). Shipped to docs/notes/pdf/crash_hedged_results.pdf.

## 2026-07-22 (pre-noon) — sample policy + the presentability question

- USER POLICY, binding for all research from now on: post-2008 data only.
  House reading: sample starts 2008-01-01 (matches research/slope_carry.py
  convention), which KEEPS the 2008 crash in sample — conservative for a
  sold-crash-spread strategy. Strictly-after (2009-01) reported alongside.
  Strategy table re-baselined to 2008-start; measurement sections still
  carry 2006-start labels — full re-baseline queued post-presentation
  (spot checks: conclusions insensitive).
- Post-2008 strategy numbers (EM SPR): vanilla 2.60%/yr SR 0.29;
  spread-financed 3.73%/0.35; pickup +1.13%/yr t=+2.61, overlay standalone
  SR 0.61 (2009 start: +1.34%, t=+3.32, SR 0.78). Crossed: -1.49% t=-3.84
  -> break-even fill ~43% of quoted spread (52% from 2009). G10 pickup
  +0.15% t=0.39 (mechanism check holds on the new window).
- Presentability resolution: the book Sharpe (0.29->0.35) is NOT the
  headline and should not be presented as such; an unlevered overlay
  cannot move book Sharpe much. The presentable object is the OVERLAY as
  its own P&L: t=2.6 with 2008 in sample, standalone SR 0.61 ~= 2x the
  carry book itself, bounded band loss ~2%/leg-month, scalable 2-3x.
  Note updated: "the overlay is the product, not the book Sharpe."

## 2026-07-22 — premium-gap weighting: tested once, does not beat SPR

Pre-specified rule (no tuning): leg weight = quoted 25d-10d premium gap,
observable at trade date (ps_carry_pickup column). EM book, 2008-01 start:
GAP strategy 2.72%/yr SR 0.35 vs SPR strategy 3.73%/yr SR 0.35; head-to-head
GAP-SPR = -1.02%/yr (t=-0.94, ns). Same Sharpe, less return: gap-weighting
overloads TRY (widest quoted gap, weakest realized leg) and dilutes BRL/MXN
carry. Verdict: SPR stands as the strategy weighting; GAP recorded as
tested-and-not-better. One run, as committed - no iteration.

## 2026-07-22 — forward-side costs added (house model, own quoted spreads)

Sorted top/bottom-5 book, net of forward costs (maintained notional rolls at
the quoted POINTS half-spread, weight changes pay the OUTRIGHT half-spread;
spreads from own PX_BID/PX_ASK, incl. the new EM pull). Measured drag
~0.85-0.87%/yr. NET results: 2008+: vanilla 3.18%/yr SR 0.38 -> strategy
4.38%/yr SR 0.43. 2009+: vanilla 4.27%/0.55 -> strategy 5.76%/0.62. Pickup
identical to gross (+1.20% t 2.64 / +1.49% t 3.51) — forward costs cancel
between arms by construction; only the option fill (break-even ~43% of
quoted option spread) remains. Option side of strategy nets is still mid —
at a 25% fill the net-net pickup is ~+0.5-0.7%/yr.

## 2026-07-22 — replication consolidated: strategy.py

All ad-hoc session runs (sorted book, forward costs, GAP test) consolidated
into research/crash_hedged/strategy.py -> out/strategy_results.csv, with
REGRESSION ANCHORS asserting the logged numbers (net vanilla 3.18%/0.38,
strategy 4.38%/0.43, pickup +1.20% t 2.64, 2008+) so drift fails loudly.
Results note strategy table replaced with the net sorted-book version +
provenance line. Run order for full replication: build_panel.py ->
hedged_carry.py -> validate.py (must PASS) -> analysis.py -> strategy.py.

## 2026-07-22 (afternoon) — library integration, cleanup, and the readable notebook

- Generic option math promoted into src/fxcarry/options.py beside the
  existing black_forward: smile_vol, strike_from_delta (pips convention;
  premium-adjusted dropped as unused, gap was ~0.03% of strike), and
  delta_neutral_strike. tests/test_options.py carries the USDJPY anchors
  (K25 159.41, prem 0.390%/mo); full suite 113 passed.
- constants.py: BRL/TRY/CNH/ILS added to the catalog; INR/TWD forward
  tickers corrected to their NDF roots (IRN/NTN — the plain tickers never
  load); POINT_SCALE += INR 100, THB 100, TWD 1.0; VOL_CURRENCIES += the
  five pulled pairs; fwd_ticker() now derives roots from the catalog so
  multi-tenor NDF tickers build correctly. Catalog-size test updated 26->30.
- Swept per the unused-code rule: optmath.py (duplicated the library),
  check_optmath.py (superseded by tests/test_options.py), make_smile_figure.py
  (never ran; the notebook draws the smile now). Engine and validate rewired
  to fxcarry.options; ALL CHECKS PASS and REGRESSION ANCHORS OK after the
  refactor.
- notebooks/04_crash_hedged_carry.ipynb: the human-readable replication.
  Ten steps from raw quotes to the net strategy table, executed end to end,
  with two in-notebook cross-checks that assert agreement with the pipeline
  (one leg-month to 1e-10; the final net numbers vs strategy_results.csv).
  Humanizer skill installed to .claude/skills/humanizer and applied to the
  prose (tell scan clean).
- Still open: retemplating the D-B tutorial onto the stat31450 template with
  the smile figure and FINM 32000 Breeden-Litzenberger citations (request
  predates the terminal move; the notebook covers the plain-language need).

## 2026-07-22 (evening) — broad-venue expansion: 33 currencies

- User dropped the BER-inherited 19-pair scope. Broad pull
  (pull_broad_options.py): vol surfaces for HKD RUB RON CLP COP IDR MYR PEN
  PHP — ALL exist on this entitlement, including the six the team pull
  reported missing. That "uninsurable six" claim was a pull artifact;
  corrected in the results note and notebook. Spots + NDF forwards
  (CHN/CLN/IHO/PSN roots, RUB/RON outrights) pulled alongside ->
  fx_vol_broad_daily.parquet, spot_fwd_broad_daily.parquet.
- Scales validated (implied-carry method): CLP/COP/IDR/PHP whole-unit (1.0),
  PEN/RUB/RON/HKD/MYR default 1e4. LIBRARY CORRECTION: IDR 100 -> 1.0 (the
  old value was an untestable guess; same failure signature as KRW). Catalog
  += RUB RON CLP COP PEN; IDR fwd root fixed to IHO; fwd_ticker() NDF-aware.
  114 tests pass.
- build_panel now library-driven (constants.point_scale / vol_pair /
  fwd_ticker) and 33 names; RUB hard-capped at 2022-01 signal (freeze).
  Engine rerun, ALL GATES PASS.
- strategy.py: two books — sorted24 (anchors pinned, unchanged: net 3.18/
  4.38, pickup +1.20 t 2.64) and sorted-broad. BROAD RESULTS (net of fwd
  costs): 2008+: vanilla 5.1%/yr SR 0.58 -> strategy 6.5%/yr SR 0.63,
  pickup +1.5% t +2.96. 2009+: 6.1/0.76 -> 7.9/0.83, pickup +1.8% t +3.76.
  Per-currency: IDR 25d-vs-10d sell gap among the widest (2.31 vs 0.96);
  RUB pre-freeze insurance roughly fair.
- Notebook rebuilt on the broad book (asserts vs sorted-broad row), claims
  corrected. Results note updated + recompiled.
- DVC: four parquets now need adding: fx_vol_em_daily, spot_fwd_em_daily,
  fx_vol_broad_daily, spot_fwd_broad_daily.

## 2026-07-22 (late) — grid completion: the universe is now shape-consistent

- pull_grid_completion.py: vol grid for the 14 new pairs extended to the
  original shape ({V,25R,25B,10R,10B,5R,5B} x {1W,1M,2M,3M,6M,9M,1Y,18M,2Y})
  -> fx_vol_grid_daily.parquet (8.1M rows, 740/742 tickers; only PEN 5d@2Y
  unquoted). Forward tenor curves for the 12 new/NDF roots
  -> fwd_points_grid_daily.parquet (91/96; missing only far NDF tenors:
  IHO/IRN/NTN at 18M-2Y and IRN 2W — real market gaps, logged as such).
- Every pair in the 33-name universe now carries the same quote grid,
  subject to each market's own history start. Enables the quarterly 3M
  hedge test and tenor work across the full universe.
- Deliberately not pulled: short rates for new names (needs curated
  per-country tickers; strategy is forward-implied throughout) and
  pre-1995/pre-redenomination history for TRY/RON/RUB/BRL (different
  currency units, not missing data).
- DVC list is now SIX files: fx_vol_em_daily, spot_fwd_em_daily,
  fx_vol_broad_daily, spot_fwd_broad_daily, fx_vol_grid_daily,
  fwd_points_grid_daily.

## 2026-07-22 (night) — the third tutorial: everything above one leg

- Gap review of the reading stack (2 tutorials + FINM 37301 + nb 04): the
  option half is covered twice over, but nothing derives the book layer
  (rank/sign/±1/K and the per-dollar-of-one-side convention), the two cost
  models, the option fill, the inference, or why the pickup is a risk
  premium rather than an anomaly. FINM 37301 stops at volga and defers UIP
  as "supplemental reading not covered in this session", so the economics
  had no textbook behind it either.
- docs/tutorials/latex/fx_spread_financed_carry_tutorial.tex (rev 1, 23pp):
  leg excess return derived from the funded-forward position; UIP + Fama on
  our own panel; the Q-vs-P wedge measured rung by rung; the overlay and its
  bound as a Proposition; book construction and normalization; forward cost
  model + why it cancels from the pickup; fill cost from vega; the
  "is it just more carry" regression; HAC/bootstrap/multiplicity; the
  bounded-disaster peso test. Reading order for the three tutorials in §1.
- make_strategy_figures.py: computes every number the tutorial quotes ->
  out/tutorial_numbers.json, out/tutorial_series.parquet, out/rung_pnl.csv,
  and five figures (fig_sf_payoff/rungs/uip/fill/bound).
- hedged_carry.py: leg_returns now also stores sell_25d, buy_10d, k_25d,
  k_10d, ps_bound (z_ps unchanged; strategy.py anchors still OK).
- validate.py: gate 6 added — the overlay stays inside
  [collected - bound, collected] in all 8232 leg-months (worst slack 2e-17).
- NUMBERS (broad 33-name sorted book, mid vols, net of fwd costs, 2008+):
  vanilla 5.05%/yr SR 0.58, strategy 6.53%/yr SR 0.63, pickup +1.47% t 2.96,
  bootstrap p 0.001; break-even option fill 39% (48% on 2009+).
- TWO CORRECTIONS TO EARLIER WORDING, both now in the tutorial:
  (1) "sell the overpriced 25d, buy the fair 10d" is loose. Owning the 10d
      rung also lost money (-0.42%/yr per leg, -0.13% in G10, -0.53% in EM);
      selling the 25d earned +0.70%. The trade harvests the difference, i.e.
      the smile is too steep between the rungs, not that either is fair.
  (2) The overlay regressed on the vanilla book gives beta 0.18 (t 9.2),
      R^2 0.49, alpha +0.40%/yr with t 1.13 (2009+: +0.64%, t 1.80). About
      three-quarters of the pickup is additional carry exposure; the
      smile-specific residual is positive but not measurable on this sample.
      The standalone-alpha framing does not survive that regression.

## 2026-07-22 (night, cont.) — self-containment pass over all three tutorials

Complaint that drove it: several places said "From Lecture 3, [formula]" and
then used the formula, so the reader had to open the lecture to find the
derivation. Fixed everywhere the result is load-bearing; where a pointer
remains it now says explicitly that it is a second treatment or context.

- Tutorial 1 (conventions): proves phi(d1)/phi(d2) = K/F once, then derives
  vega (hence strict monotonicity of price in sigma, which is what makes
  quoting in vol legitimate) and the spot delta e^{-r*tau} N(w d1) from the
  pricing formula; derives the premium-adjusted delta
  Delta_base% = Delta_pips - V_base% as X d/dX (V/X); the RR/BF-vs-moments
  paragraph is now marked as context. New remark up front on what a citation
  means. 14 -> 15pp.
- Tutorial 2 (crash-hedged): E^Q[X_T] = F is now derived from the zero-cost
  forward instead of asserted as "no-arbitrage says"; Q itself is stated as a
  definition rather than a result. 21pp.
- Tutorial 3 (spread-financed): vega derived (was quoted); the SDF identity
  derived from E[m R] = 1 by differencing two returns; the Newey-West
  estimator written out with the truncation weights instead of named. New
  §1.3 with the outside-reading table. 23 -> 25pp.

Reading list correction (from checking what nb 02 actually contains):
BER's SDF + peso material is already in notebooks/02_ber_replication.ipynb
§3-4, including eqs 22-23 estimated on our own option surface (z* ~ -3% for
carry, eta 0.085 vs 0.021). So the outside reading is Jurek §2.2 + Table VII
(45 min, because our results note asserts *his* findings), a re-read of nb 02
§3-4 (30 min), and bekr2011 §2 only if the peso conclusion is presented as
established rather than as our own estimate. CGZ, DHL, LRV and the BER survey
are skippable.

## 2026-07-22 (night, cont.) — tutorial 2 rev 5: universe is 33, not 19

Driven by nb 04, which already runs on the broad book. Stale facts fixed:
- Data section: six files -> ten, in four pulls, 30.6M rows, table rebuilt
  with per-file row/ticker counts. Grid-completion pull noted (740/742
  tickers; only PEN 5d@2Y unquoted).
- "Nineteen pairs is my request list" remark rewritten: the list has been
  extended twice, THB was the first warning, and the "uninsurable six"
  (IDR COP CLP MYR PEN PHP) claim is retracted in full - all six quote.
- 19 vol pairs -> 33 (four XXXUSD + 29 USD-base); 24 currencies -> 33 in the
  papers section; panel 9,258 rows/24 ccy -> 12,174/33.
- Coverage remark rewritten from the data: 13 names complete from 2003-10,
  MXN 2005-03, BRL/TRY end-2005, nine more 2006-01 (25 names, hence the
  start), stragglers to CNH 2011-02; 32 of 33 live at 2026-06 (RUB stopped
  2022-01). 5d quotes on 1,289 of 12,174 rows. Seven NDF roots named.
- Pipeline list: optmath.py and make_smile_figure.py removed (both swept
  07-22); options live in the library; figures come from nb 04; strategy.py
  and make_strategy_figures.py pointed at the companion tutorial.
- Gates: five -> six; ITM leg-months 959 -> 1,716.
- Exercise 4 re-answered on the current universe: unhedged 1.21%/yr over 246
  months, 10d-hedged 0.81%, give-up 33% (was "1.05%" on 17 names). New
  exercise 5 contrasts G10 (0.71 -> 0.58, give-up 18%), which is the same
  "the wedge is an EM phenomenon" conclusion the third tutorial reaches.
- Pre-registration untouched, and the status remark now says so explicitly.
22pp.

## 2026-07-22 (notebook alignment pass over nb 04)

Trigger: a reader question, "why does 25-delta being further right mean
overpriced?" It does not, and notebook 04 was the one artifact still saying
it did. The 07-22 correction at the "TWO CORRECTIONS TO EARLIER WORDING"
entry above had been carried into the tutorial but never into the notebook.

- SHARPENING OF CORRECTION (1). Normalize each give-up by the premium paid
  and the ranking between the rungs INVERTS. EM buyers lost ~35% of what
  they spent on 10d cover against ~21% on 25d; the 25d share is the larger
  one for only 4/24 EM names and 4/9 G10. Per dollar of premium the 10d wing
  is the MORE marked-up contract, not the fair one. The 25d's wider give-up
  in %/yr is largely a size effect: EM premia 5.19%/yr (25d) vs 1.82% (10d),
  a 2.9x ratio. So "sell the dear rung, buy the fair rung" is wrong in both
  directions; both rungs carry a positive give-up and the trade harvests the
  difference between them.
- BOOK-LEVEL DECOMPOSITION (broad 33-name sorted book, mid vols, net of fwd
  costs, 2008-01..2026-06), now in nb 04 Step 6 as a table:
  plain 5.05%/yr SR 0.58 worst -10.3%; sell 25d with NO wing 7.87%/yr
  SR 0.65 worst -16.6%; spread 6.53%/yr SR 0.63 worst -12.2%. The wing costs
  1.35%/yr and buys back 4.4 points of worst month. The strategy is that
  exchange, i.e. a risk decision, not a relative-value one.
- CORRECTION (2) was also missing from the notebook. Recomputed on the
  current 33-name book: overlay on plain carry gives beta 0.18 (t 9.3),
  R^2 0.49, alpha +0.56%/yr t 1.64 (2008+) and +0.78%/yr t 2.23 (2009+).
  Higher than the +0.40/+0.64 logged earlier because that run predated the
  broad-venue expansion. Now in Step 10: read the 1.5% as a better carry
  book, not a separate return source.
- G10 "fairly priced" was being asserted as "sits on zero" off the new chart.
  G10 sd runs 5-9x its mean (JPY is the dearest 10d cover in the sample at
  +1.42%/yr, above every EM name; NOK and CAD sit at -1.2%). Restated as
  "no measurable tilt on average", and the chart now draws the G10 and EM
  group means as diamonds so the claim is checkable against the scatter.
- Also added to nb 04 this pass: Step 2 CIP/fwd_disc derivation in FINM 37301
  Lecture 1 notation (F = S P*/P, fwd_disc = ln(P/P*) = (r*-r)tau) with the
  implied-r* table; carry-vs-worst-month scatter (corr -0.65, slope -1.32);
  the give-up dumbbell; "rung" defined on first use in Step 4.
- Tutorial checked and left alone: it already carries correction (1), and its
  "G10 close to fairly priced" is a group-average statement in context.
- FOLLOW-UP (same pass, reader question "what does the flip tell us"): the
  give-up chart in nb 04 is now TWO panels, %/yr and % of premium paid, so
  the denominator flip is visible instead of asserted. EM aggregate markup
  is 29% of premium at 10d vs 18% at 25d (rate up 1.6x going out), while
  premium paid falls 5.19 -> 1.82%/yr (size down 2.9x), hence give-up
  dollars down 1.7x. Money in the smile sits near the money.
- NEW NUMBER: selling the WING alone is dominated. Broad sorted book, net,
  2008+: sell 10d only 6.40%/yr SR 0.62 worst -14.7% skew -1.43, versus the
  spread 6.53%/0.63/-12.2%/-1.01. Higher markup rate, worse outcome on every
  axis. This is the argument for owning the 10d rather than selling it, and
  it needs both denominators to see. Table now in nb 04 Step 6.
- NAKED ARM ADDED TO nb 04 (Step 9b) with the risk case against it. Broad
  sorted book, net, 2008+: naked 25d sale 7.87%/yr SR 0.65 Sortino 0.68 skew
  -1.58 kurt 4.86 worst -16.6% CVaR5 -9.28% maxDD -25.3%; spread 6.53/0.63/
  0.76/-1.01/2.54/-12.2%/-7.34%/-22.5%; plain 5.05/0.58/0.76/-0.70/2.10/
  -10.3%/-5.85%/-18.7%.
- KEY NEW NUMBER: levered to a common worst month (plain carry's -10.3%) the
  naked sale earns 4.91%/yr, BELOW plain carry's 5.05%, while the spread
  earns 5.53%. Return per unit of CVaR5: naked 0.85 < plain 0.86 < spread
  0.89. So the naked sale's higher headline is leverage on the tail, not
  edge, and Sharpe (0.65 vs 0.63) is the wrong statistic to decide it on.
  The wing costs 1.34%/yr and converts a measured tail into a contractual
  one, (K25-K10)/F per leg-month.
