# `arjun/` — FX Carry Strategy: Robustness, Attribution & Hedging

**Arjun** · UChicago Summer Project Lab with Bank of America (Corporate Treasury / Global Funding).

---

## Overview

This folder contains four phases of work on the FX carry strategy:

**Phase 1 — Exploration (`fx_analysis.ipynb`).** Diagnostics on G10+EM currency performance, drawdowns, correlations, and macro factor exposures.

**Phase 2 — Robustness & attribution (`robustness_audit.ipynb`, `em_carry_attribution.ipynb`).** Stress-testing the team's headline 0.466 net Sharpe and decomposing where the premium actually comes from.

**Phase 3 — Can we hedge it? (`dxy_hedging.ipynb`, `dxy_futures_hedging.ipynb`).** Two notebooks testing whether the book's dollar exposure can be hedged with DXY — first with the spot index, then with the tradable futures contract and fresh Bloomberg data. **Both are nulls, and the reason why is the useful part.**

**Phase 4 — A hedge that works (`duration_hedge.ipynb`).** Screening every tradable instrument in the Bloomberg pull against the book. Duration is the one that survives: the real-time, cost-inclusive overlay lifts net Sharpe from **0.467 to 0.510**, clearing both project bars.

---

## The headline findings

**The 0.466 is real but fragile.** Front-loaded to 2007–2012, underwater 2013–2020, concentrated in ~5 names, and sitting on an isolated parameter peak rather than a plateau.

**The premium is EM, and it is concentrated.** IDR, JPY, MXN, BRL and COP supply ~65% of P&L. Removing JPY alone costs 7.5pp of Sharpe.

**DXY cannot hedge this book — with spot or with futures.** Individual currencies load heavily on the dollar (EUR −1.09, R² 0.85), but the *portfolio* barely does (β = +0.30, R² 3.9%). A carry sort is long some currencies and short others against USD, so the dollar largely cancels between the legs before any hedge is applied. Sweeping every hedge ratio, the best DXY futures position is **no position**.

**Duration does hedge it.** Treasuries rise when the carry book falls — a carry unwind and a flight to quality are the same event. The correlation strengthens in stress (−0.13 calm → **−0.37** in the top VIX quintile) and is negative on 95% of days. Unlike every other candidate, the hedge is a *long* position in an asset that has earned a positive return, rather than a short in something that costs you to sell.

---

## Phase 2 · `robustness_audit.ipynb`

**Question:** How robust is the 0.466 Sharpe under stress?

| Axis | Test | Key finding |
|---|---|---|
| **Time stability** | Rolling 3-year Sharpe, expanding Sharpe, subsample splits | Premium front-loaded to 2007–2012; flat-to-negative 2013–2020; recovering 2021–2026 |
| **Concentration** | Drop-one-currency jackknife (rebuild 27×) | Top 5 names (JPY −0.075, MXN −0.06, CNH −0.05, EUR −0.05, SEK −0.04) carry 80%+ of premium |
| **Parameters** | Sweep vol window, target, rebalance freq, buckets, cap, weighting; 2-D heatmap | 60d × month-end is an isolated peak, not a plateau — overfit risk |
| **Implementation** | Cost multiples (2–5×), execution lag (1–5 days), drawdown anatomy | Edge survives 2–3× cost inflation; max DD ~30% with multi-year recovery |

**Verdict: FRAGILE.** Biggest risk is time decay — the strategy made its money in a specific historical window, and the 2021–2026 recovery is cyclical rather than structural.

**Outputs:** `robustness_jackknife.csv`, `robustness_param_sweeps.csv`, `robustness_window_rebal_heatmap.csv`, `robustness_cost_stress.csv`, `robustness_lag_stress.csv`, `robustness_concentration.csv`, `robustness_scorecard.csv`

---

## Phase 2 · `em_carry_attribution.ipynb`

**Question:** Where does the premium come from — which currencies, and carry vs spot?

Rebuilds G10-only, EM-only and combined books side by side, cross-checks against investable DB indices (DBHVG10U, FXCTEM8), then decomposes the combined book by exact P&L contribution (`w[ccy] × xret[ccy]`, which sums to the book return).

**Findings:** EM-only net Sharpe ~0.47 vs G10-only ~0.12 — the premium is EM. Five names supply ~65% of P&L. JPY earns almost entirely on *spot* (safe-haven appreciation, no carry), while IDR and BRL are carry-heavy. ZAR and TRY are active drags despite positive carry. The source does not rotate much year to year.

**Outputs:** `em_vs_g10_stats.csv`, `attribution_by_currency.csv`, `attribution_by_group.csv`, `attribution_by_year.csv`

---

## Phase 3 · `dxy_hedging.ipynb` — can DXY hedge the dollar exposure?

**Question:** How much of what the carry book does is just the dollar, and can one liquid instrument hedge it?

**The setup that makes this interesting.** Per-currency regressions show enormous dollar exposure — EUR −1.09 (R² 0.85), HUF −1.39, SEK −1.23, every one strongly significant. The obvious conclusion is that the book is drowning in dollar risk.

**It isn't.** At the book level the exposure nearly vanishes:

| Book | β vs DXY | t | R² |
|---|---|---|---|
| G10_net | −0.009 | −0.22 | 0.00003 |
| EM_net | −0.094 | −2.08 | 0.004 |
| ALL_net | **+0.299** | 6.21 | 0.039 |

Three things follow. The G10 book has **no measurable dollar exposure at all** — the tercile sort is dollar-neutral by construction. The EM book has the textbook crash-channel sign but it is tiny, because **DXY contains no EM currencies**. And the combined book's exposure is **positive**, meaning the book is structurally *long* the dollar through its short euro-funding leg — the opposite of the risk we wanted to hedge.

**Hedging it costs Sharpe** (ALL_net 0.454 → 0.390 net of cost), and the exposure is unstable: the rolling beta ranges −0.46 to +1.63 and flips sign. Conditional betas confirm it weakens rather than strengthens in stress (calm 0.386 → stress 0.269). Every sub-period shows a negative delta.

**Why it fails:** a dollar-neutral carry sort has already differenced the dollar away. Restricting to the currencies DXY tracks *best* (R² ≥ 0.40) makes it worse, not better — the sub-book's R² on DXY falls to 1.65%, below the full book's 3.9%. **High per-currency R² is a red herring for hedging a spread.**

**Outputs:** `dxy_regression_full_sample.csv`, `dxy_hedge_stats.csv`, `dxy_rolling_beta.csv`, `dxy_conditional_beta.csv`, `dxy_hedge_by_period.csv`, `dxy_hedge_ratio_sweep.csv`

---

## Phase 3 · `dxy_futures_hedging.ipynb` — does the tradable contract change the answer?

The spot notebook used DXY spot as a proxy for futures P&L. This one tests that assumption with the real contract (`DX1 Curncy`) from a fresh Bloomberg pull, including bid/ask.

**Three things spot could not do:**

1. **Rolls.** `DX1` is a generic front-month series: four times a year it switches contract and the price gaps. That gap is not P&L. On the **78 detected roll days** the futures return sits ~0.34% from spot versus ~0.02% on normal days — **14× noisier**, on predictable dates. Removing them lifts the futures/spot correlation from 0.990 to 0.996.
2. **Roll yield.** Futures price the US-vs-basket interest differential, so a short-DXY hedge earns or pays a carry that spot has no term for. It **changes sign mid-sample**: a short hedge was *paid* ~1–3%/yr through 2008–2016 and *pays out* ~1.5–2.5%/yr from 2017 as the Fed moved above the ECB/BoJ/SNB. Small at this book's beta, but it means **a futures hedge quietly imports a rates bet**.
3. **Real costs.** Quoted bid/ask gives a median half-spread of ~2.3bp, so the hedge can be charged properly rather than assumed frictionless.

**Result — the beta transfers and the verdict holds:**

| | β vs DXY spot | β vs DX1 roll-adj | transfer |
|---|---|---|---|
| ALL_net | +0.2991 | +0.2920 | −2.4% |

| Hedge variant (ALL_net) | Sharpe | Δ |
|---|---|---|
| unhedged | 0.4673 | — |
| static, net of cost | 0.4458 | −0.021 |
| expanding (strict OOS), net | 0.4459 | −0.021 |
| dynamic (lagged β), net | 0.3798 | −0.087 |

**It is not a cost problem.** Five times the spread assumption only moves Sharpe to 0.427. And the hedge-ratio sweep — which uses no estimate at all — peaks at h = −0.05 versus 0.4673 at h = 0, a difference in the third decimal and the *wrong sign* for a hedge. **No size of DXY futures position improves this book.**

**Outputs:** `dxyfut_book_betas.csv`, `dxyfut_hedge_stats.csv`, `dxyfut_hedge_ratio_sweep.csv`, `dxyfut_robustness.csv`, `dxyfut_regime_table.csv`, `dxyfut_basis_rollyield.csv`, `dxyfut_roll_dates.csv`, `dxyfut_return_series.csv`

---

## Phase 4 · `duration_hedge.ipynb` — the hedge that works

**Question:** DXY failed twice. Does *anything* in the Bloomberg pull hedge this book?

Screens 19 tradable instruments — ETF total returns (TLT, EMB, HYG, EMHY, CEMB, GLD, CEW), Treasury and Bund futures, equity, investable VIX indices, commodities. Indicators that cannot be held (VIX, MOVE, JPMVXY, CDS spreads) are excluded.

**The screen has a clean structure.** Almost everything is *positively* correlated with the book, so hedging means shorting it — and every one of those has a positive expected return, so the hedge sells away premium exactly as DXY did. The negatively-correlated alternatives are insurance, and insurance is priced: long VIX futures bleed 10–56%/yr to roll.

**Duration is the exception:** negatively correlated *and* positive own return.

| Instrument | corr | hedge is | own return | ΔSharpe |
|---|---|---|---|---|
| **TLT (UST 20y+)** | **−0.241** | **LONG** | **+2.70%/yr** | **+0.059** |
| XAU / GLD (gold) | −0.086 | LONG | +8.9% / +8.5% | +0.045 / +0.040 |
| FV1 (5y UST fut) | −0.283 | LONG | +0.09% | +0.027 |
| TU1 (2y UST fut) | −0.271 | LONG | +0.05% | +0.027 |
| EMB (EM sovereign) | +0.184 | SHORT | +4.46% | −0.072 |
| SPX | +0.377 | SHORT | +8.12% | −0.132 |
| SPVXSTR (long VIX) | −0.355 | LONG | **−56.4%** | −0.278 |

**The correlation strengthens exactly when it matters:**

| Regime | corr | book return | TLT return |
|---|---|---|---|
| calm (VIX < p20) | −0.130 | +17.9%/yr | −2.1%/yr |
| normal | −0.180 | +8.9%/yr | +0.1%/yr |
| **stress (VIX > p80)** | **−0.374** | **−18.5%/yr** | **+15.5%/yr** |

Rolling 1-year correlation is negative on **95.4%** of days (min −0.57, mean −0.23). Compare DXY, whose beta swung −0.46 to +1.63 and flipped sign repeatedly. **This exposure is stable in a way the dollar exposure never was.**

**Result — clears both bars:**

| Variant | Sharpe | ann vol | max DD | skew | Δ |
|---|---|---|---|---|---|
| unhedged | 0.4673 | 11.20% | −33.2% | −0.648 | — |
| static (in-sample), net | 0.5265 | 10.87% | −32.3% | −0.607 | +0.059 |
| **expanding (real-time), net** | **0.5095** | 10.96% | −32.2% | −0.597 | **+0.042** |

Position is **long 0.18 units of TLT per unit of carry book**. TLT's quoted half-spread is 0.68bp, so costs are effectively invisible (Sharpe changes in the fourth decimal).

### The caveats — state these before anyone asks

1. **Most of the gain is not hedging.** Stripping TLT's average return out and re-running isolates the pure variance-reduction effect: **+0.014 of the +0.059, or 24%**. The other **76% is Treasuries' own return** — largely a forty-year bond bull market that ended in 2022. The defensible framing is that the position was *sized by variance minimisation, not picked for its return*, but do not claim the whole Sharpe gain as hedging alpha.
2. **The return improvement is not statistically significant.** +0.35%/yr with a Newey-West t of **0.54**. The Sharpe gain also comes from lower vol, so this does not sink the hedge, but it is not a strong result on its own.
3. **The drawdown improvement is small** — 3.2%, from −33.2% to −32.2%. This weakens the "drawdown improvement proves it's real hedging" defence.
4. **It helps in only 10 of 20 years.** Close to a coin flip year to year, with the benefit concentrated in crisis years (2011 +0.46, 2014 +0.56, 2019 +0.39).
5. **2022 is the named failure mode** (−0.79). The Fed hiked into a risk-off market; the correlation held at −0.15 but TLT fell 36% anyway. **Negative correlation protects against the book's bad days, not against the hedge instrument having a bad year.**

**Highest-value follow-up:** test **TU1 / FV1** (2y and 5y Treasury futures) instead of TLT. They carry the same negative correlation (−0.27, −0.28) with near-zero own return, so any improvement they deliver is *pure hedging* rather than term premium — and far less exposed to a hiking cycle, which directly addresses the 2022 failure. Note they are generic front-month series and need roll-adjusting first, exactly as `DX1` did.

**Outputs:** `duration_screen.csv`, `duration_regime_corr.csv`, `duration_hedge_stats.csv`, `duration_by_year.csv`, `duration_hedge_series.csv`

---

## The hedging arc, in one paragraph

Individual currencies are hugely dollar-driven, but the *portfolio* is not — a long/short carry sort cancels the dollar between its legs, so there is almost nothing for DXY to hedge, and what little remains is the compensated euro-funding tilt the carry signal deliberately wanted. Two independent instruments (spot and futures) confirm this with the same mechanism. The exposure that *does* threaten the book is the EM crash channel, which DXY structurally cannot see because it contains no EM. Duration reaches that risk directly: a carry unwind and a flight to quality are the same event, so Treasuries rally when the book falls, and the hedge is a long position in a returning asset rather than a short in something that costs to sell.

---

## Data note

`FX_Carry_Bloomberg_DATA_clean.xlsx` is a static-value Bloomberg pull (2007-01 → 2026-06, 16 data tabs) covering the hedge instrument universe: FX spot/forwards/options, dollar indices **including `DX1` futures with bid/ask**, cross-currency basis, OIS and rate vol, credit spreads and sovereign CDS, credit/duration/commodity ETF total returns, equity and equity vol.

Both hedging notebooks include a tab-agnostic block parser (`parse_bbg_tab`) for the workbook's side-by-side layout — reusable for the remaining tabs.

**⚠ Convention warning:** the `FX_Fwd_1M/3M/12M` tabs hold forward **points**, not outright forwards. JPY- and HUF-quoted pairs need a `/100` divisor, everything else `/10000`. The carry book is unaffected (it builds from the repo parquets), but anything constructed directly from those tabs will be silently wrong.

---

## How to run

All notebooks run from **inside `arjun/`** and import the shared engine:

```bash
cd arjun
jupyter lab
```

Suggested order: `fx_analysis` → `robustness_audit` → `em_carry_attribution` → `dxy_hedging` → `dxy_futures_hedging` → `duration_hedge`.

`em_carry_attribution` reads the robustness jackknife for its tie-back chart. The two DXY notebooks and `duration_hedge` are independent of each other.

**Requirements:** pandas, numpy, scipy, statsmodels, matplotlib, **pyarrow ≥ 24** (parquet), **openpyxl** (Bloomberg workbook).

**Reproducibility:** common window 2007-05 → 2026-06; no lookahead (`ffill().shift(1)`); Newey-West HAC inference; every track reported gross **and** net of costs; a reconciliation gate at the top of each notebook asserts rebuilt books match the committed Sharpes (G10 0.119 / ALL 0.466) to within 5e-3.

---

## Implications for Bank of America

1. **The strategy works but is fragile.** 0.466 net Sharpe, front-loaded to 2007–2012 and cyclically boosted by 2021–2026. Treat as tactical, not strategic.

2. **It is a 5-name concentrated bet dressed as a 27-name book.** Size limits and a live monitor on JPY/MXN are mandatory.

3. **Do not hedge with DXY.** Tested twice, spot and futures, net of real roll and spread costs. It hedges the euro-funding leg the carry signal deliberately wants, and is blind to the EM crash risk that actually threatens the book. No hedge ratio improves it.

4. **The book is quietly long the dollar** (β +0.30, t 6.2) through its short euro-funding leg. Nobody put that position on deliberately. Worth knowing even though it is not tradable as a hedge.

5. **A duration overlay is the recommended direction.** Real-time, cost-inclusive: 0.467 → 0.510, clearing both bars. But present it with the decomposition attached — most of the gain is Treasuries' own return, and 2022 shows the failure mode. Front-end Treasuries are the next test and would make the case cleaner.

---

## Files in this folder

**Notebooks**
- `fx_analysis.ipynb` — exploratory work (spot performance, correlations, macro factors)
- `robustness_audit.ipynb` — stress-test the 0.466 across four axes
- `em_carry_attribution.ipynb` — source-of-premium analysis, per-currency P&L decomposition
- `dxy_hedging.ipynb` — DXY spot hedge test (null; explains why)
- `dxy_futures_hedging.ipynb` — DXY futures hedge test with roll adjustment and real costs (null confirmed)
- `duration_hedge.ipynb` — instrument screen and the duration overlay (clears the bar)
- `fx_findings.ipynb` — presentation notebook with spoken scripts

**Code & data**
- `arjun_utils.py` — helper module wrapping the shared `cesare/fx_utils.py` engine
- `FX_Carry_Bloomberg_DATA_clean.xlsx` — static Bloomberg pull of the hedge instrument universe
- `outputs/` — all CSV outputs (`robustness_*`, `attribution_*`, `dxy_*`, `dxyfut_*`, `duration_*`)
- `README.md` — this file
