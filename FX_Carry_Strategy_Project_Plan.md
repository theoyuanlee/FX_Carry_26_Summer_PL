# FX Carry Strategy — Project Plan & Status

*Author: Cesare Bavaresco · UChicago Summer Project Lab with Bank of America (Corporate Treasury / Global Funding).*
*Data: daily Bloomberg, 2007-01 → 2026-06, G10 + EM currencies vs USD.*
*Last updated: 2026-07-10.*
*Status legend: ✅ done · 🔶 partial · ⬜ not started.*

This document replaces the original generic project outline. It is now git-tracked and serves as the
repo's source of truth: each stage records **what exists** (files, functions, verified results),
**gaps** versus the original plan, and **concrete next actions** with named outputs and acceptance
criteria. Every number quoted below is reproducible from a CSV in `cesare/outputs/`.

---

## 1. Project Objective

Develop, evaluate, and improve a quantitative FX Carry trading strategy using historical foreign
exchange, interest rate, and macroeconomic data. The project replicates the classic academic carry
strategy before extending it with modern portfolio construction, risk management, and forecasting
techniques.

Mapped to the proposal's three implementation goals:

1. Collect Bloomberg time series — ✅ done (§5).
2. Build reusable portfolio / return / risk libraries — ✅ done (`cesare/fx_utils.py`, §5.3).
3. Explore strategy behaviour across market environments — ✅ core done (Stages 3–6 all closed).
   **Phase 3 (§17) now pursues a genuinely novel edge beyond vanilla EM carry** — the main event
   for Jul–Aug.

## 2. Research Question

**Can a traditional FX Carry strategy be improved by dynamically adjusting portfolio exposure using
macroeconomic conditions, volatility, and momentum?**

## 3. Motivation & Economic Rationale

Traditional FX carry borrows in low-interest-rate currencies and invests in high-interest-rate
currencies. It has historically earned attractive returns but is exposed to severe crash risk in
periods of financial stress. Rather than simply reproducing the literature, this project asks:

- Why does carry earn excess returns?
- When does carry perform well?
- When does carry fail?
- Can dynamic portfolio management improve risk-adjusted performance?

Two of these questions already have in-repo evidence:

- **Why carry exists — the forward-premium puzzle is confirmed in-sample.** The pooled Fama
  regression of next-month spot changes on the forward premium gives **b = 0.73**
  (Newey–West t = 4.5, n = 6,713 currency-months) versus the UIP prediction of b = 1: high-carry
  currencies do not depreciate enough to offset their rate advantage
  (`cesare/data_visualization.ipynb` §8, `outputs/uip_fama.csv`).
- **Carry is compensated crash risk.** Both portfolio tracks load negatively on changes in FX
  implied vol and the EMBI spread, with t-stats ≈ −4 to −6 (`outputs/crash_regressions.csv`).
  This is the failure mode Stages 3 and 6 manage.

## 4. Current State — Executive Summary

Headline backtest results (from `outputs/strategy_summary_stats.csv`; common sample
2007-05-01 → 2026-06-30, ~5,000 trading days; all tracks vol-targeted to 10% annualized):

| Track | Ann. return | Ann. vol | Sharpe | Max DD | IR vs benchmark |
|---|---|---|---|---|---|
| G10 gross | 1.9% | 11.5% | 0.17 | −36.5% | 0.27 |
| G10 net | 1.4% | 11.5% | 0.12 | −38.2% | 0.21 |
| G10 hedged (gross) | 1.2% | 10.2% | 0.12 | −36.2% | 0.21 |
| Combined gross | 7.0% | 11.2% | 0.63 | −26.8% | 0.50 |
| Combined net | 5.2% | 11.2% | 0.47 | −29.3% | 0.34 |
| Combined hedged (gross) | 5.6% | 10.5% | 0.53 | −29.1% | 0.38 |
| DBHVG10U (DB G10 carry index) | −0.7% | 9.0% | −0.08 | −39.1% | — |
| FXCTEM8 (DB EM carry index) | 1.5% | 8.9% | 0.16 | −32.1% | — |

Key findings so far:

1. **The 2007–2026 carry premium lives in EM, not G10.** The combined track earns 7.0%/yr gross
   (Sharpe 0.63) versus 1.9%/yr for G10-only (Sharpe 0.17) — mirroring the benchmarks, where the DB
   G10 harvest index was *negative* over the sample.
2. **Construction is validated externally.** Daily correlation 0.55 with DBHVG10U and 0.39 with
   FXCTEM8 — same trade — and both tracks beat their benchmark (IR 0.27 / 0.50): the sizing adds
   value over the index construction.
3. **Costs matter but don't kill the trade.** Actual bid/ask drag is 0.55%/yr (G10) and 1.8%/yr
   (combined); net Sharpe 0.12 / 0.47. Rolling positions via FX swap (points spread, not outright)
   is what keeps EM viable.
4. **The strategy is levered HML, not a new signal.** Against DOL + HML_FX the combined track is
   ≈1.4× HML (R² 0.69) with ~2%/yr alpha (t ≈ 1.6, not significant) — the value added is risk
   management, as expected for a carry sort.
5. **Crash hedging is tail insurance, not a Sharpe improver — and the implementation decides
   whether it is worth having.** Stage 3 (net of costs, `stage3_dynamic_comparison.csv`): no
   exposure-timing rule has significant alpha on its baseline (all |t| < 1.7); the book-level
   binary IV/RR hedge is *rejected* for the combined book net of costs (Sharpe 0.47 → 0.37 with
   a worse MaxDD), while per-currency RR conditioning delivers the tail improvement
   (skew −0.65 → −0.60, CVaR₉₉ 2.9% → 2.7%) at ~zero Sharpe cost. Details in §9.
6. **Optimization does not beat the simple book (Stage 4).** Across equal / inverse-vol / ERC /
   mean-variance within-leg weighting, all re-vol-targeted (`stage4_weighting_comparison.csv`),
   inverse-vol wins net of costs (0.47); ERC ties, equal and MVO trail, and no scheme has
   significant net alpha. Mean-variance is the *worst* net track — it churns on noisy carry.
7. **Momentum does not beat the hedges (Stage 5).** Momentum-filter and carry/momentum blends give
   up 0.1–0.5 Sharpe *and* worsen the drawdown; standalone momentum diversifies but loses money
   net. Retained only as a near-orthogonal regression factor.
8. **Regimes are a diagnostic, not a winning allocation (Stage 6).** The carry premium is a
   calm-market phenomenon — vol-targeted carry earns Sharpe 0.57 (Low) / 0.94 (Moderate) but 0.00
   in Crisis at ~1.5× the vol — yet regime-timed de-risking does not beat per-currency RR with
   significance (max |t| 0.59). Adopt the regime series as a lens, not a rule.

**Through-line:** the 2007–2026 premium is EM carry, and every *standard* embellishment — hedges,
optimization, momentum, regime timing — fails to beat the simple vol-targeted inverse-vol book net
of costs. **Phase 3 (§17) asks whether a less standard, data-differentiated signal can.**

Stage dashboard:

| Stage | Status | Where | Key artifacts |
|---|---|---|---|
| 0. Data & infrastructure | ✅ | `src/`, `data/raw/`, `cesare/fx_utils.py` | 13 parquet groups, ticker manifest |
| 1. Baseline carry | ✅ | `cesare/strategy_backtest.ipynb` §1–2, §4 | `strategy_summary_stats.csv`, weights CSVs |
| 2. Return drivers | ✅ | `cesare/data_visualization.ipynb` §5, §7–8; backtest §3, §5 | `regression_lrv.csv`, `regression_macro.csv`, `uip_fama.csv`, `crash_regressions.csv` |
| 3. Dynamic carry | ✅ | `cesare/dynamic_carry.ipynb`; `fx_utils.exposure_scalar` | `stage3_dynamic_comparison.csv` |
| 4. Portfolio construction comparison | ✅ | `cesare/portfolio_construction.ipynb`; `fx_utils.shrunk_cov`, `erc_weights`, `mvo_weights`, `carry_portfolio(weighting=)` | `stage4_weighting_comparison.csv`, `weights_{scheme}_monthly.csv` |
| 5. Momentum overlay | ✅ | `cesare/momentum_overlay.ipynb`; `fx_utils.momentum_panel`, `zscore_xs`, `carry_portfolio(filter_signal=)`; backtest §3 MOM factor | `stage5_momentum_comparison.csv`, `stage5_track_correlation.csv` |
| 6. Regime analysis | ✅ | `cesare/regime_analysis.ipynb`; `fx_utils.regime_classify` | `regime_series.csv`, `stage6_regime_stats.csv`, `stage6_conditional_by_regime.csv` |
| 7. ML extension (optional) | ⬜ | — | — |
| Final evaluation & report | 🔶 | §14.1 metrics ✅ done; report not started | regenerated stats CSVs |

## 5. Data & Infrastructure — Stage 0 ✅

*(Absent from the original plan, which listed "collect data from Bloomberg" as future work. It is
done and documented here because every later stage depends on these conventions.)*

### 5.1 Universe & quoting conventions

- **Universe constants** (`fx_utils.G10`, `fx_utils.EM`): 11 G10 + 19 EM tickers vs USD.
- **Strategy universe rules (locked):** drop pegged **HKD, DKK** (degenerate vol); drop **CNY**
  (no forwards — **CNH** is the tradable RMB leg). Result: **9 G10** names
  (AUD CAD CHF EUR GBP JPY NOK NZD SEK) and **27 combined** names.
- **Quoting:** EUR/GBP/AUD/NZD are quoted USD-per-FX, the rest FX-per-USD;
  `fx_utils.spots_usd_per_fx` normalizes everything to USD-per-FX (up = FX appreciation).
- **Forwards:** per-currency point scales in `fx_utils.FWD_SCALE` (validated empirically —
  `outputs/implied_carry_validation.csv`); NDF roots for BRL/CLP/COP/IDR/INR/KRW/PEN in
  `fx_utils.FWD_ROOT`.
- **TRY post-2018 extremes** are contained structurally (inverse-vol legs + 40% max single-name
  leg share), not by winsorizing the signal — a deliberate choice, keep it.
- Always load parquets via `fx_utils.load_wide` (raw values are object dtype).

### 5.2 Data inventory & refresh

13 parquet groups in `data/raw/` (each stored wide + long), daily 2007-01 → 2026-06/07:

- **Automated pull** (`src/bloomberg_data.py`, xbbg/blpapi, terminal required to refresh):
  G10/EM spot + forwards (**with BID/ASK** — the cost model uses them), G10/EM option surfaces
  (ATM / 25Δ RR / BF), G10/EM interest rates, global risk (SPX, MXEF, BCOM, DXY, VIX, UST curve…),
  macro market proxies.
- **Hand-pulled supplement** (`data/raw/FX_extra_data.xlsx` → parquet via
  `src/convert_extra_xlsx.py`): USD risk-free (USGG3M), carry benchmark indices
  (DBHVG10U, FXCTEM8, DBHVBUSI), DKK/HKD rate gaps, EM onshore fixings, EMBI Global spread.
- **Provenance:** `ticker_manifest.csv`, coverage and failure CSVs in `data/raw/`.
- **Known gaps:** no option surfaces for CLP/COP/IDR/MYR/PEN/PHP; CNY forwards unavailable;
  NIBOR12M/STIB12M/CLSWA missing.
- Parquet snapshots are git-tracked, so the repo is fully reproducible without a terminal.
- **Environment note:** pyarrow must be the pip build (≥24) — conda's 19.x cannot read these files;
  refix with `/opt/anaconda3/bin/pip install -U pyarrow` after any broad conda update.

### 5.3 Shared library map — `cesare/fx_utils.py`

| Group | Functions |
|---|---|
| Loading | `load_wide`, `load_rates_panel`, `load_benchmarks`, `benchmark_returns`, `load_em_risk` |
| Panel construction | `spots_usd_per_fx`, `carry_panel`, `excess_returns`, `spot_log_returns` |
| Performance stats | `summary_stats`, `max_drawdown`, `turnover` |
| Factors & regressions | `dollar_factor`, `carry_hml_factor`, `nw_regression`, `regression_table` |
| CIP / rates | `onshore_rate`, `interest_diff_vs_usd`, `cip_basis` |
| Portfolio construction | `carry_portfolio`, `vol_target_weights`, `exposure_scalar`, `portfolio_returns` |
| Transaction costs | `forward_halfspreads`, `roundtrip_cost` |
| Options | `vol_surface_panel` |

New helpers proposed by Stages 3–7 below are added to this module, in this style (pure functions on
wide panels, no-lookahead by construction, docstrings that record parameter rationale).

### 5.4 Validation performed (why the pipeline can be trusted)

- **FWD_SCALE check:** median 12M forward-implied carry per currency vs known rate differentials
  (`outputs/implied_carry_validation.csv`).
- **CIP basis:** forward-implied carry ≈ onshore rate differential for deliverable currencies;
  persistent basis only where expected (NDFs, proxy fixings) (`outputs/cip_basis_summary.csv`).
- **Benchmark correlation:** 0.55 / 0.39 daily vs DBHVG10U / FXCTEM8 — the backtest trades the
  same premium as the investable indices.
- **UIP/Fama regressions:** pooled b = 0.73 — the economic license for the strategy
  (`outputs/uip_fama.csv`).

## 6. Methodological Guardrails (global — every stage references these)

1. **No lookahead.** Signals sampled at month-end; weights `ffill().shift(1)` → effective the next
   trading day (the `carry_hml_factor` / `carry_portfolio` / `vol_target_weights` convention).
   Any new conditioning variable (VIX, IV, regimes, ML forecasts) must be sampled the same way,
   using trailing windows only.
2. **Inference.** Newey–West HAC standard errors everywhere (5 lags daily, 3 lags monthly), via
   `fx_utils.nw_regression`.
3. **Costs.** Every strategy variant is reported **gross AND net** using `forward_halfspreads` +
   `roundtrip_cost` (new notional pays the outright half-spread; maintained notional rolls via FX
   swap at the points half-spread).
4. **Benchmarks.** Every stats table reports IR vs DBHVG10U (G10 tracks) and FXCTEM8 (combined).
5. **Universe.** Peg/CNY exclusions and the 40% leg cap are fixed unless a stage explicitly
   studies them.
6. **Sizing standard.** 10% annualized vol target, 60-day window, 4× leverage cap, scaled by the
   unit book's own trailing realized vol (rationale in the `vol_target_weights` docstring).
7. **Common evaluation window** for all comparisons: 2007-05 → 2026-06.

---

## 7. Stage 1 — Baseline Carry Strategy ✅

**Status:** done; exceeds the original spec. Two metric-library gaps deferred to §14.1.

**What exists**

- **Signal:** annualized **forward-implied carry** `fx_utils.carry_panel` — ln(S/F) in USD-per-FX
  terms (= CIP-implied rate differential). *Not* interest-rate ranking (see Appendix C #1).
- **Returns:** `fx_utils.excess_returns` — daily spot log return + lagged carry accrual /252, the
  standard academic construction.
- **Portfolios** (`cesare/strategy_backtest.ipynb` §1–2): G10 tercile sort (9 names) and combined
  quintile sort (27 names) via `carry_portfolio` — inverse-60d-vol legs, 40% max leg share,
  dollar-neutral gross 1 per side, monthly rebalance effective next day — then
  `vol_target_weights` to 10% annualized.
- **Costs** (backtest §4): actual bid/ask half-spreads, roll-via-swap treatment;
  per-currency detail in `outputs/strategy_costs_by_ccy.csv`.
- **Results:** §4 headline table. Panel-level stats in `outputs/summary_stats_carry_excess.csv`
  and `summary_stats_spot.csv` (carry vs spot P&L split).
- **Outputs:** `strategy_summary_stats.csv`, `strategy_returns_daily.csv`,
  `weights_g10_monthly.csv`, `weights_combined_monthly.csv`, `strategy_costs_by_ccy.csv`.

**Gaps vs original plan**

- Original promised Sortino, Calmar, and portfolio-level turnover among Stage-1 metrics;
  `summary_stats` lacks Sortino/Calmar and turnover only appears per-currency in the costs CSV
  → §14.1 work item.

**Next actions:** none beyond §14.1 — stage closed.

## 8. Stage 2 — Understanding Return Drivers ✅

**Status:** done for the daily, market-based scope; low-frequency macro releases deliberately
descoped (see Gaps).

**What exists**

- **LRV two-factor regressions** per currency (DOL + HML_FX, Newey–West)
  — `data_visualization.ipynb` §5.1 → `outputs/regression_lrv.csv`.
- **Market-factor regressions** per currency: SPX, MXEF, BCOM, DXY, ΔVIX, ΔFXvol, ΔUST2Y, Δ2s10s
  — §5.2 → `outputs/regression_macro.csv`; correlation snapshot §5.3.
- **Track-level attribution** (backtest §3): combined track ≈ 1.4× HML_FX (R² 0.69), alpha ~2%/yr
  (t ≈ 1.6, ns).
- **Crash-risk regressions** (backtest §5): ΔIV, crash-positive Δ25ΔRR, ΔEMBI, controlling for
  DOL/HML → `outputs/crash_regressions.csv`. Documented caveat: the G10 ΔRR coefficient flips
  positive in the multivariate table because ΔIV (corr 0.38 with ΔRR) absorbs the crash variation
  — collinearity, not a hedge property.
- **UIP/Fama** (§8) as the "why carry exists" evidence.

**Gaps vs original plan**

- Original listed MOVE, TED spread, FCI, inflation, GDP, PMI, payrolls, IP, unemployment. Not
  downloaded; monthly releases have vintage/revision problems at daily frequency. **Descoped to
  optional** — the daily market-based proxy set was a deliberate choice.
- Original listed **cross-sectional carry dispersion** and a **momentum factor** as regressors —
  neither built yet; dispersion feeds Stage 6, momentum arrives with Stage 5.

**Next actions** (~half day)

1. Add a carry-dispersion series (cross-sectional std of `carry_panel` at month-end) as a timing
   variable for Stage 6.
2. Add a momentum-factor row to the backtest §3 regressions once Stage 5 exists. ✅ done — backtest
   §3 now regresses each track on DOL + HML_FX + MOM (combined loads +0.16 on MOM, t 6.1; see §11).

## 9. Stage 3 — Dynamic Carry & Risk Management ✅

**Status:** done. The static vs vol-targeted vs risk-managed comparison exists, every variant
gross AND net, with NW tests and an explicit verdict per rule
(`cesare/dynamic_carry.ipynb` → `outputs/stage3_dynamic_comparison.csv`).

**What exists**

- **`fx_utils.exposure_scalar(indicator, lookback=756, q=0.80, low_mult=0.5, rebal="ME",
  method="binary")`** — trailing-percentile de-risking multiplier for any conditioning series
  (VIX, IV, RR, EMBI); binary threshold plus the `method="linear"` ramp refinement; daily,
  `ffill().shift(1)`, NaN-free (missing signal → fully invested). Replaces the ad-hoc backtest
  §5 `hedge_scalar` — 0.97 monthly decision agreement, hedged-track correlation 0.99 (the
  windowing changed from 36 month-end points to a 756-day daily rank).
- **`cesare/dynamic_carry.ipynb`**: variants {static unit-gross, vol-targeted, VIX-threshold,
  IV/RR-threshold, IV/RR linear, per-currency RR} × {gross, net} × {G10, combined}, common
  window. Hedges scale **weights**, not returns, so `roundtrip_cost` prices the reduced
  notional and the toggle trades — this is what makes the net-of-cost hedged tracks possible.
- **In-notebook validation:** no-lookahead truncation test; weights-level ≡ return-level
  machinery check (<1e-12); ≤2 trade-days/month cost-alignment assertion; cost drags reproduce
  the §4 headline values (0.6%/1.8%/yr).
- §14.1 (metrics + `turnover`) was completed first as this stage's prerequisite.

**Results** (net of costs, common window; alpha/t vs the same-cost-basis baseline):

| Rule | G10 | Combined | Verdict |
|---|---|---|---|
| Vol targeting (vs static) | t = −0.29 | t = +0.51 | adopt as sizing standard — no alpha claim |
| VIX threshold | t = −1.15; CVaR₉₉ 3.2→2.7% | t = −0.27; MaxDD −29→−25% | tail-insurance-only |
| IV/RR binary (old §5 rule) | t = −0.56; MaxDD −38→−31% | **t = −1.69; Sharpe 0.47→0.37, MaxDD −29→−31%** | G10 tail-insurance-only; **combined reject** |
| IV/RR linear | t = −0.24, mild tail gain | t = −0.41, no tail gain | dominated — reject |
| Per-currency RR (longs only) | t = 0.01; MaxDD −38→−34% | t = −0.04; skew −0.65→−0.60, CVaR₉₉ 2.9→2.7% | tail-insurance-only — **preferred** |

Headline: **no exposure-timing rule adds significant net alpha** (all |t| < 1.7) — consistent
with carry compensating priced crash risk: de-risking on elevated risk indicators sells premium
roughly one-for-one. Refinement still matters: the original book-level binary hedge *fails net
of costs* on the combined book, while per-currency RR conditioning buys the tail improvement
for ~1 Sharpe point. Caveat: the per-currency rule breaks dollar-neutrality by design (mean net
FX exposure −0.10, ≈−1.1 in 2008 stress) — the long-USD tilt in crises *is* the hedge, reported
as an exposure. **Stage-6 bar: a regime rule must beat per-currency RR (combined net Sharpe
0.457, MaxDD −28%) and the VIX threshold (0.441, −25%) — not the old binary hedge.**

## 10. Stage 4 — Portfolio Construction Comparison ✅

**Status:** done. Four within-leg weighting schemes compared on the combined ALL quintile book,
every variant re-vol-targeted to 10%, gross AND net, with turnover, cost drag and NW alpha vs the
inverse-vol baseline, plus a falsifiable verdict (`cesare/portfolio_construction.ipynb` →
`outputs/stage4_weighting_comparison.csv` + `outputs/weights_{scheme}_monthly.csv`). Reference:
Ledoit–Wolf (2004), in Appendix B.

**Design.** Hold everything fixed except within-leg weighting (combined quintile sort, monthly,
same cost model); re-vol-target every variant to 10% so the Sharpe comparison is scale-free — the
differentiators become net-of-cost efficiency and tail shape. Schemes: **equal**, **inverse vol**
(current), **equal risk contribution (ERC)**, **mean-variance (MVO) with μ = forward-implied
carry** (with μ = carry, the original plan's "mean-variance" and "maximum Sharpe" collapse into one
scheme — Appendix C #8).

**What exists**

- **Refactor, not duplication:** `carry_portfolio` gained `weighting: str = "inv_vol"`
  (`"equal" | "inv_vol" | "erc" | "mvo"`) and `cov_window: int = 250`; the dispatch is one branch on
  the within-leg weight line, so the sort / filter / normalise / 40%-cap / no-lookahead scaffolding
  stays single-sourced. Default `inv_vol` is **bit-identical** to earlier stages (asserted in-notebook
  against the committed `weights_combined_monthly.csv`).
- **Three pure helpers in `fx_utils`:**
  - `shrunk_cov(xret, window=250)` — Ledoit–Wolf shrinkage toward a scaled-identity target
    (`cov1Para`), computed on the leg's own names over the trailing 250d up to the rebalance date
    (a small, well-conditioned block); not annualised (both consumers are scale-invariant in Σ).
  - `erc_weights(cov, max_iter=1000, tol=1e-8)` — equal risk contribution via cyclical coordinate
    descent; reduces exactly to inverse-vol on a diagonal cov. Cap applied outside, as for inv_vol.
  - `mvo_weights(mu, cov, gross=1.0, max_share=0.40)` — long-only max-Sharpe (SLSQP) under leg-gross
    and single-name-cap constraints, μ = `sign·carry` (no return forecasting); min-variance fallback
    on degenerate μ, so the caller never sees NaNs.
- **`cesare/portfolio_construction.ipynb`:** four schemes × {gross, net}, vol-targeted 10%/60d,
  common window 2007-05→2026-06, IR vs FXCTEM8, NW alpha vs the same-basis inverse-vol baseline.
  In-notebook guards: helper unit tests (ERC=inv_vol on diagonal, ERC equal-RC, MVO cap/gross/tilt,
  shrunk_cov PD & better-conditioned), an ERC no-lookahead truncation test, the inv_vol bit-identity
  check, and an exact reconciliation that vol-targeted inv_vol = Stage-3 `voltgt` (ALL 0.466 net
  Sharpe, Δ = 0.000).

**Results** (combined ALL book, common window, net of costs)

| Scheme | Gross Sharpe | Net Sharpe | Turnover | MaxDD | Skew | α vs inv_vol (t) |
|---|---|---|---|---|---|---|
| Inverse vol (current) | 0.63 | **0.47** | 0.68 | −0.29 | −0.65 | — (baseline) |
| ERC | 0.59 | 0.44 | 0.63 | −0.32 | −0.56 | −0.2%/yr (−0.5) |
| Equal weight | 0.46 | 0.34 | 0.47 | −0.32 | −0.52 | −1.2%/yr (−1.8) |
| Mean-variance (μ=carry) | 0.46 | 0.32 | 0.70 | −0.52 | −1.15 | −1.1%/yr (−0.8) |

**Verdict — NO.** Optimization does not beat inverse-vol net of costs. **Inverse-vol is the best
net-of-cost scheme.** ERC is a near-tie (it shares inverse-vol's diagonal limit and only re-weights
for correlation) but its edge doesn't survive costs. Equal-weight gives up Sharpe by ignoring the
vol structure. **MVO is the worst net track:** μ = noisy monthly carry makes it churn (highest
turnover), concentrate into the cap, and inherit a fatter left tail (worst MaxDD −0.52, worst skew
−1.15) — optimizing on estimation error. Every scheme's NW alpha vs inverse-vol is ≤ 0 and
insignificant (|t| < 2), so there is no net outperformance to capture. This confirms the §10 prior
on its pessimistic side and vindicates the baseline's inverse-vol choice.

- **Outputs:** `outputs/stage4_weighting_comparison.csv` (9 rows: 4 schemes × gross/net + benchmark)
  and `outputs/weights_{equal,inv_vol,erc,mvo}_monthly.csv` (unit books, gross 2, comparable).

## 11. Stage 5 — Momentum Overlay ✅

**Status:** done. Signal helpers, the three combination methods, the momentum factor row in the
backtest §3 regressions, and a falsifiable verdict all exist
(`cesare/momentum_overlay.ipynb` → `outputs/stage5_momentum_comparison.csv` +
`outputs/stage5_track_correlation.csv`). Reference: Burnside–Eichenbaum–Rebelo (2011) and
Menkhoff et al. (2012b), in `papers/`.

**What exists**

- **`fx_utils.momentum_panel(xret, lookback=63, skip=0)`** — trailing cumulative **excess**
  return (rolling sum of `xret`, `min_periods=lookback//2`), a daily panel consumed exactly like
  `carry_panel` (month-end sample + `shift(1)` inside `carry_portfolio`; no lookahead by
  construction). Grid **21 / 63 / 252 d**; `skip=0` default.
- **`fx_utils.zscore_xs(panel)`** — per-date cross-sectional z-score, for the blend.
- **`filter_signal=` kwarg on `carry_portfolio`** (chosen over a separate wrapper — backward
  compatible, zero logic duplication): after bucketing, keeps long names with `filter_signal ≥ 0`
  and short names with `≤ 0`, re-normalising each leg over survivors (cap still binds); an empty
  leg is left flat. Stage-3 behaviour unchanged (default `None`).
- **`cesare/momentum_overlay.ipynb`**: {pure carry, (a) pure momentum, (b) double-sort filter,
  (c) 50/50 z-blend} × {21/63/252 where applicable} × {G10 tercile, ALL quintile} × {gross, net},
  all vol-targeted (10%/60d), common window 2007-05→2026-06, IR vs DBHVG10U/FXCTEM8, NW alpha vs
  the same-basis pure-carry baseline. In-notebook guards: `momentum_panel` no-lookahead truncation
  test; **exact** reconciliation that vol-targeted pure carry = Stage-3 `voltgt`
  (G10 0.119, ALL 0.466 net Sharpe, Δ = 0.000).
- **Backtest §3** now regresses each track on DOL + HML_FX + **MOM** (momentum HML from
  `carry_hml_factor(xret, momentum_panel(xret,63))`); the shared DOL+HML `factors` used by §5 are
  left untouched.

**Results** (net of costs, common window):

| Family | ALL net Sharpe (best L) | ALL MaxDD | vs pure carry (0.466 / −29%) |
|---|---|---|---|
| pure carry (baseline) | 0.466 | −29% | — |
| (a) pure momentum | −0.02 to −0.33 | −52 to −73% | net loser; low carry corr (−0.07..+0.14), flips skew +, trims CVaR₉₉ |
| (b) double-sort filter | 0.37 (63d) | −51% (63d) | **dominated** — less Sharpe *and* worse tail |
| (c) 50/50 blend | 0.16 (252d) | −49% | dominated — worse Sharpe and MaxDD |

Track regressions: combined track loads +0.16 on MOM (t 6.1, significant) with HML loading and
alpha unchanged; G10 +0.07 (t 1.7, marginal) — carry and momentum are near-orthogonal.

- **Outputs:** `outputs/stage5_momentum_comparison.csv` (42 rows: pure carry vs momentum vs filter
  vs blend, per lookback, gross+net + benchmarks) and `outputs/stage5_track_correlation.csv`.
- **Verdict — NO.** Momentum does **not** reduce MaxDD/CVaR₉₉ at less Sharpe cost than the Stage-3
  hedges — the filter and blend give up 0.1–0.5 Sharpe *and worsen* the drawdown (filtering thins
  each leg and vol-targeting then levers the concentrated book). Standalone momentum diversifies
  (near-zero carry correlation, positive skew, lower CVaR₉₉) but is a net money loser, so it is not
  investable on its own here. The one apparent win (G10 blend @ 252d) is single-cell — only 252d,
  only G10, gone in the combined book — classic lookback-mining, **not adopted**. Per-currency RR
  (0.466 → 0.457, MaxDD −28%, skew −0.60) remains the preferred near-free tail hedge; momentum is
  carried forward only as a regression **factor**, not an allocation.

## 12. Stage 6 — Market Regime Analysis ✅

**Status:** done. A transparent percentile-composite regime classifier, the conditional-by-regime
performance table, and a head-to-head of regime-aware allocation vs the Stage-3 hedges all exist,
gross AND net, with NW tests and an explicit verdict (`cesare/regime_analysis.ipynb` →
`outputs/regime_series.csv` + `stage6_regime_stats.csv` + `stage6_conditional_by_regime.csv`).
Reference: extends the Stage-2 crash-risk finding; Ledoit–Wolf N/A here.

**Design.** Generalise Stage 3's single-indicator thresholds into a multi-indicator regime, then ask
(a) descriptively where carry earns, and (b) whether regime-aware de-risking beats the best Stage-3
hedges net of costs.

**What exists**

- **`fx_utils.regime_classify(indicators, lookback=756, breaks=(0.70, 0.90))`** — ranks each
  indicator into its trailing-3y percentile (min_periods = lookback//2), averages the ranks, and
  cuts the composite into **Low / Moderate / Crisis** at asymmetric breaks (crisis is a tail state —
  equal terciles would mislabel a third of history). Trailing windows only → no lookahead as a
  descriptive label; lagged (ME-sampled + shift 1) when it drives allocation, mirroring
  `exposure_scalar`. Returns per-indicator ranks + composite + regime.
- **Classification variables** (daily, in `data/raw/`): VIX (`global_risk`), aggregate FX ATM IV
  (cross-sectional mean of `vol_surface_panel("ATM","1M")` over the 21 option-covered ALL names),
  EMBI spread (`load_em_risk`). The composite flags **77% Low / 18% Moderate / 6% Crisis**; Crisis
  days isolate exactly the known episodes — 2008 GFC, 2015–16 China/EM, 2020 COVID, 2022 risk-off.
- **`cesare/regime_analysis.ipynb`:** regime diagnostics + no-lookahead truncation test;
  conditional performance of the vol-targeted book by lagged regime (with n_days); regime-aware
  allocation variants {reg_half: Crisis→0.5, reg_off: Crisis→0.0, reg_mod: Moderate→0.5/Crisis→0.0
  (beyond-spec sensitivity)} vs static / voltgt / VIX / per-ccy RR, gross+net, common window, NW
  alpha vs the vol-targeted baseline. In-notebook guards: weights-level ≡ return-level machinery
  check (<1e-12), ≤2 trade-days/month cost alignment, and exact reconciliation that voltgt/vix/rrccy
  net Sharpe match `stage3_dynamic_comparison.csv`.

**Results** — conditional performance (ALL vol-targeted book, net-of-nothing gross, by lagged regime)

| Regime | n_days | Ann. return | Ann. vol | Sharpe | Skew | Share of total P&L |
|---|---|---|---|---|---|---|
| Low | 3,603 | 6.0% | 0.107 | 0.57 | −0.71 | 62% |
| Moderate | 822 | 10.6% | 0.113 | **0.94** | −0.27 | 25% |
| Crisis | 277 | −0.0% | 0.159 | −0.00 | −0.98 | 0% |

Regime-aware allocation vs the bars (ALL net Sharpe): reg_half **0.470**, reg_off 0.466,
reg_mod 0.483 · voltgt 0.466 · **per-ccy RR 0.457** · **VIX 0.441**. All regime variants' NW alpha
vs voltgt is insignificant (max |t| = 0.59).

**Verdict — REJECT as a replacement, ADOPT as a diagnostic.** Descriptively the regime lens is the
payoff: the carry premium is a calm-market phenomenon (Sharpe ~0.6 Low, ~0.9 Moderate) that earns
**nothing in Crisis at ~1.5× the vol** — the ~6% of days carrying the crash risk. But as an
allocation rule no regime variant beats the Stage-3 per-currency RR hedge with significance
(max |t| 0.59); crisis-only de-risking lands within a whisker of the baseline, and reg_mod's higher
point estimate comes from de-risking the *highest-Sharpe* regime (a vol-scaling artifact + mild
spec-search). Per-currency RR remains the preferred near-free tail hedge; the regime series is kept
as an interpretive tool and a Stage-7 feature source. Consistent with the project: crash-conditioning
buys tail insurance, not Sharpe.

- **Outputs:** `outputs/regime_series.csv` (daily ranks + composite + regime), `stage6_regime_stats.csv`
  (7 variants × gross/net + benchmark), `stage6_conditional_by_regime.csv`.

## 13. Stage 7 — Machine Learning Extension (Optional) ⬜

**Status:** not started; **deferred to the "back pocket" (decision 2026-07-10)** — Phase-3
novel-edge work (§17) comes first, and ML returns only if a new signal set makes it worthwhile.
The original plan named five models but no target, feature lags, or CV scheme — for ~230 monthly
observations that silence is a lookahead trap (Appendix C #8). Specs:

1. **Target — timing formulation first:** next-month combined-track (or HML_FX) return, monthly,
   ~230 obs. Cross-sectional per-currency forecasting is a stretch goal only. State up front:
   **a null result is a valid deliverable** ("does complexity add value?" — no is an answer).
2. **Features** (all known at month-end t, predicting t+1): carry level and cross-sectional
   dispersion; trailing 1/3/12M momentum (Stage 5); VIX / FX IV level and 1M change; 25Δ RR;
   EMBI level and change; DXY 3M trend; ΔUST2Y; 2s10s; trailing 60d realized book vol; trailing
   track return. No macro releases (not downloaded; vintage issues).
3. **Cross-validation — purged walk-forward:**
   `purged_walkforward(index, min_train=60, test_size=12, embargo=1)` — expanding window,
   12-month test blocks, 1-month embargo (per López de Prado). Never shuffled k-fold.
4. **Models (descoped):** Ridge/LASSO/ElasticNet as the primary family (interpretable, right-sized
   for 230 obs) + **one** tree ensemble (RF *or* XGBoost) as robustness. Standardize on train
   folds only.
5. **Use:** map forecast → exposure (sign or sigmoid), run through the same cost machinery;
   benchmark against vol-targeted static **and** the Stage-6 regime rule — the simple competitors
   ML must beat to justify itself.

- **Dependencies:** Stage 5 (momentum features), Stage 6 (regime features); adds scikit-learn
  (+xgboost) to requirements.
- **Outputs:** `outputs/stage7_ml_forecast_eval.csv` (OOS R², sign hit rate per model/fold),
  `outputs/stage7_ml_strategy_stats.csv`.
- **Acceptance criteria:** every result strictly out-of-sample under the purged scheme;
  net-of-cost comparison vs both simple competitors; feature-importance table with a stated
  stability caveat.

## 14. Final Evaluation, Report & Repo Hygiene 🔶

### 14.1 Metric library completion ✅ (done with Stage 3)

- `fx_utils.summary_stats` extended in place (backward-compatible — columns appended before
  `info_ratio`, old values verified unchanged against git): `cagr` (geometric, compounding daily
  values as simple returns, the `max_drawdown` wealth-curve convention), `sortino` (annualized
  mean over the lower partial moment of order 2 vs 0), `calmar` (CAGR / |MaxDD|).
- New `turnover(weights, rebal="ME")` — average one-sided turnover per rebalance period,
  Σ|Δw|/2 over live periods; inception trade excluded (convention in the docstring).
- `strategy_summary_stats.csv`, `summary_stats_carry_excess.csv`, `summary_stats_spot.csv`
  regenerated (both notebooks re-executed).

### 14.2 Consolidated comparison table

`outputs/final_comparison.csv` — every named variant from Stages 1/3/4/5/6/7 (× gross/net) plus
both benchmarks, on the common window; metrics = the original plan's final-evaluation list (CAGR,
Sharpe, Sortino, Calmar, MaxDD, IR, hit rate, turnover) + the repo's extras (skew, VaR/CVaR).
Produced by a final section of `strategy_backtest.ipynb` or a dedicated
`cesare/final_evaluation.ipynb`.

### 14.3 Final report outline (deliverable for BoA; `report/` or `docs/`)

1. Introduction & motivation (the UIP puzzle) · 2. Data & conventions · 3. Methodology &
guardrails · 4. Baseline results, incl. the G10-vs-EM finding · 5. Return drivers & crash risk ·
6. Dynamic / risk-managed carry · 7. Momentum · 8. Portfolio construction · 9. Regimes ·
(10. ML, if done) · 11. Conclusions & recommendations framed for a Corporate Treasury / Global
Funding audience.

### 14.4 Repo hygiene checklist

- [ ] **README.md** (currently a one-line stub): project summary, headline table, repo map, setup
      (terminal only needed for data refresh — parquet snapshots are tracked), how to run the
      notebooks, link to this plan.
- [ ] **requirements.txt**: pandas, numpy, pyarrow (pip build — see §5.2 note), statsmodels,
      matplotlib, openpyxl, jupyter; scikit-learn/xgboost when Stage 7 starts. Separate optional
      `requirements-bbg.txt` for xbbg/blpapi (Bloomberg's package index).
- [x] **.gitignore**: plan-file exclusion removed (this document is now tracked).
- [ ] Fix stale `fx_utils` module docstring ("notebooks in `notebooks/`" — they live in
      `cesare/`); decide fate of legacy `notebooks/view_data.ipynb` (keep-as-scratch or delete).

## 15. Sequencing, Dependencies & Effort

| # | Work item | Depends on | Effort | Why here |
|---|---|---|---|---|
| 1 | §14.1 metrics + regenerate CSVs ✅ | — | 0.5 d | Every later comparison consumes these |
| 2 | §14.4 hygiene (README, requirements) | — | 0.5 d | Cheap; makes the repo presentable now |
| 3 | Stage 3 completion ✅ | 1 | 1 d | Mostly assembles existing pieces; closes the first 🔶 |
| 4 | Stage 5 momentum ✅ | 1 | 1.5 d | Feeds Stage 6 conditional stats and Stage 7 features |
| 5 | Stage 4 weighting comparison ✅ | 1 | 1.5–2 d | Independent — parallelizable with #4 |
| 6 | Stage 6 regimes ✅ | 3, 4 | 1.5 d | Generalizes the Stage-3 threshold rule |
| 7 | **Phase 3 — novel edge (§17)** ← next | 4, 5, 6 | 4–6 wk | The main event: a differentiated signal that beats the simple book |
| 8 | Stage 7 ML (optional) | 7 | 2–3 d | Back pocket; only if Phase-3 signals warrant it |
| 9 | §14.4 hygiene + §14.2 final table + §14.3 report | all above | 2–3 d | Terminal deliverable; folds in the Phase-3 result |

Key dependency edges: metrics → everything; momentum → regime stats → ML features; the Stage-3
verdict shapes the Stage-6 design (the regime rule must beat the binary hedge). **Phase 3 (§17) is
now the critical path — Stage 7 ML and the final report both wait on its outcome.**

## 16. Alignment with the BoA Proposal

The project satisfies the proposal objectives by: constructing historical FX carry portfolios ✅;
evaluating return and risk characteristics ✅; investigating macroeconomic and market drivers ✅;
exploring alternative portfolio construction techniques (Stage 4); testing performance across
market environments (Stages 3, 6); and building reusable Python tools for future research ✅
(`fx_utils`). Beyond replicating the academic literature, it adds the practical layers that matter
on a desk: real transaction costs, external benchmark validation, crash-risk measurement, and
regime-aware exposure management.

---

## 17. Phase 3 — Beyond Vanilla EM Carry: Toward a Novel Edge (Jul–Aug 2026) 🔶 ← current focus (D1 ✅ null)

**Why.** Stages 1–6 produced a clean but unsurprising result: the 2007–2026 carry premium is an EM
phenomenon, and every *standard* embellishment — crash hedges (St3), portfolio optimization (St4),
momentum (St5), regime timing (St6) — fails to beat the simple vol-targeted inverse-vol book net of
costs. "Be long EM carry, size by inverse vol" is defensible but not differentiated. With ~7 weeks
of runway (10 Jul → end Aug) the goal is a genuinely **novel, defensible signal** that exploits the
repo's less-common data — full FX **option surfaces** (ATM / 25Δ RR / BF), **EMBI**, onshore rates →
**cross-currency basis** — and speaks to the BoA Corporate-Treasury / Global-Funding audience.

**The bar (unchanged, falsifiable).** Any new signal must beat *both* the simple vol-targeted book
(ALL net Sharpe 0.466) *and* the per-currency-RR-hedged book (0.457), net of costs, with Newey–West
significance — or be reported honestly as another null result. Same guardrails (§6): no lookahead,
gross AND net, IR vs benchmark, common window.

**Candidate directions** (feasibility = data already in `data/raw/`):

| # | Direction | Thesis (why it's *not* just "long EM") | Data in repo? | Novelty / audience fit |
|---|---|---|---|---|
| D1 | **Crash-risk-premium-adjusted carry** | The 25Δ risk-reversal prices how expensively each currency's crash is already insured; two currencies with equal carry but different RR are *not* the same trade. Signal = carry orthogonalized to the priced crash-risk premium ("clean" carry), and RR-richness as a standalone cross-sectional signal. | ✅ full RR/ATM/BF surfaces (already crash-sign-normalised) | High — turns the Stage-2 crash finding into alpha; uses data most books lack |
| D2 | **FX volatility risk premium (VRP)** | Implied − realized vol is a systematically harvested premium *distinct* from directional carry; sell rich vol, combine with carry as a second, diversifying return source. | ✅ ATM IV + realized from spot (option-return proxy is the crux) | High — a different premium entirely |
| D3 | **Cross-currency basis / dollar funding** | Post-2008 CIP fails; the basis measures the *dollar funding premium* (Du–Tepper–Verdelhan). Use it as a funding-stress conditioner *and* a signal — dollar-shortage currencies behave differently. | ✅ `cip_basis` already built from onshore rates + forwards | High — modern; **literally** the Global-Funding desk's language |
| D4 | **FX value + multi-factor** | Add a value factor (real-exchange-rate mean reversion / PPP) to carry+momentum+dollar and time the combination; carry alone is one leg of a fuller factor model. | ⚠️ needs a REER/PPP proxy (constructible from long-horizon real spot) | Medium — more "complete" than novel |
| D5 | **Positioning / crowding** | Crowded carry unwinds violently; fade extreme CFTC IMM speculative positioning / de-risk when carry is crowded (the parked thread). | ⚠️ needs a CFTC pull (public, weekly; G10-ish only) | Medium — underused data; thin EM coverage |
| D6 | **Term structure of carry** | Harvest the forward-curve slope / roll-down rather than the single 1M point; *which tenor* to hold. | ⚠️ needs multi-tenor forwards (only 1M pulled) | Medium |

**Recommendation:** lead with **D1** — the most differentiated signal, fully feasible today, and it
re-uses the crash-risk thread the project already owns — optionally paired with **D3** (the
audience-relevant funding angle, also feasible today). **D2** is the high-upside stretch. D4–D6 need
a data add first.

**Process per chosen direction:** (1) deep-read the literature to sharpen the exact signal and its
priors; (2) add a pure `fx_utils` helper + a dedicated notebook under the existing guardrails;
(3) backtest gross+net vs the two bars with NW tests; (4) an explicit adopt/reject verdict and a new
`stageX_*.csv`. The Phase-3 result — positive *or* null — becomes the centrepiece of the §14.3 report.

**Immediate next action:** pick the direction(s) (D1 recommended), then deep-research + spec the
first signal. Repo hygiene (§14.4) can run in parallel; the final report (§14.2/14.3) waits to fold
in the Phase-3 finding.

### 17.1 D1 — Crash-Risk-Premium-Adjusted Carry ✅ (Jul 2026) — **null**

**Status:** done. An option-implied-skew battery, built on the matched 21-name option universe and
falsified against both bars. Result: **null** — a valid deliverable.

**What exists:**
- Helpers in `fx_utils.py`: `implied_skew_panel` (RR/ATM smile skew; crash-positive = the *negative*
  of risk-neutral skewness), `realized_skew_panel` (trailing physical skew of `xret`), `xs_residual`
  (per-date cross-sectional clean-carry residual). All no-lookahead (contemporaneous or trailing;
  sampled month-end + shift-1 downstream), citation-dense house style.
- Notebook `cesare/skew_carry.ipynb` (setup → signals → tracks → stats → spanning → validation →
  outputs → verdict). Validation: matched-universe assert (U21 = 9 G10 + 12 EM option-covered names),
  no-lookahead truncation recompute for `realized_skew_panel` and the SRP weight panel, and
  reconciliation of the ALL-27 inv-vol-net Sharpe to the committed Stage-4 0.4659 (Δ < 1e-3).
- Matched universe **U21** = tradable-27 ∩ RR coverage = AUD CAD CHF EUR GBP JPY NOK NZD SEK · BRL
  CNH HUF ILS INR KRW MXN PLN SGD THB TRY ZAR (drops the six optionless EM CLP/COP/IDR/MYR/PEN/PHP;
  CNH from 2011).

**Results** (matched 21-name universe, quintile inv-vol, vol-targeted 10%, **net** of costs; NW alpha
vs the *matched* vanilla carry):

| track | net Sharpe | MaxDD | CVaR₉₉ | skew | turnover | cost drag | α vs carry | t |
|---|---|---|---|---|---|---|---|---|
| **U21 vanilla carry** (anchor) | **0.496** | −0.26 | 3.0% | −0.73 | 0.47 | 1.4% | — | — |
| (a) implied skew, long high RR | 0.13 | −0.51 | 3.5% | −1.07 | 1.05 | 2.3% | −2.8% | −1.6 |
| (b) carry tilted toward crash (blendhi) | 0.15 | −0.47 | 3.3% | −0.91 | 0.73 | 1.6% | −3.3% | **−2.8** |
| (b) carry tilted away (blendlo) | −0.21 | −0.56 | 2.7% | −0.05 | 1.45 | 3.2% | −3.2% | −1.2 |
| (c) clean carry (Jurek) | −0.03 | −0.42 | 2.9% | −0.48 | 1.17 | 2.7% | −2.9% | −1.2 |
| (d) SRP (Li–Sarno–Zinna) | −0.09 | −0.49 | 2.7% | −0.48 | 1.28 | 2.7% | −3.3% | −1.5 |
| ALL-27 vanilla carry (reconciliation) | 0.466 | −0.29 | 2.9% | −0.65 | 0.68 | 1.8% | +0.0% | 0.1 |

**SRP-vs-carry spanning** (U21 unit long/short factor books, gross returns, NW 5 lags):

| regression | α (ann) | t(α) | β | t(β) | R² |
|---|---|---|---|---|---|
| SRP ~ CARRY | −0.5% | −0.38 | 0.29 | 10.2 | 0.16 |
| CARRY ~ SRP | +3.8% | **+2.19** | 0.57 | 13.2 | 0.16 |

**Verdict — REJECT (null).** No option-implied-skew variant beats the matched vanilla carry (0.496),
let alone the published bars (0.466 / 0.457); every net alpha vs carry is negative (blendhi
significantly so, t −2.8). The contested RR direction settles weakly for Farhi–Gabaix (long high RR
is positive but a fraction of carry, no alpha); the Brunnermeier "avoid expensive insurance" tilt is
the worst book. Clean carry collapses under dollar-neutrality, exactly as Jurek warns. The flagship
**SRP fails in both directions, and the Li–Sarno–Zinna spanning claim reverses on this sample: SRP
earns zero alpha over carry (t −0.4) while carry keeps a significant alpha over SRP (t +2.2) — here
carry subsumes SRP, not the other way.** Robustness: a 126d-skew SRP is likewise negative (−0.03), so
this is not a window artefact. The option surface's explicit crash-risk pricing is real (Stage 2) but
not a tradable edge over the simple book — this *sharpens* rather than overturns the project
through-line. **D1 adds no signal; the honest null is the deliverable.**

**Outputs:** `skew_carry_comparison.csv`, `srp_carry_spanning.csv`, `skew_track_correlation.csv`
(Appendix A).

**Phase-3 status after D1:** D1 done (null). Next differentiators — **D3** (cross-currency basis /
dollar funding, feasible today) and **D2** (FX vol risk premium) — remain open; the D1 null already
earns a place in the §14.3 report as evidence that the crash-risk thread, though economically real,
is not tradable alpha.

---

## Appendix A — Output artifact registry

**Existing** (all in `cesare/outputs/`):

| CSV | Produced by | Contents |
|---|---|---|
| `implied_carry_validation.csv` | data_visualization §2 | FWD_SCALE sanity check per currency |
| `summary_stats_carry_excess.csv` | data_visualization §4.1 | per-currency carry excess-return stats |
| `summary_stats_spot.csv` | data_visualization §4.2 | per-currency spot-return stats |
| `regression_lrv.csv` | data_visualization §5.1 | DOL + HML_FX loadings per currency |
| `regression_macro.csv` | data_visualization §5.2 | market-factor loadings per currency |
| `cip_basis_summary.csv` | data_visualization §7 | CIP basis by currency/tenor |
| `uip_fama.csv` | data_visualization §8 | Fama regressions per currency + pooled |
| `strategy_returns_daily.csv` | backtest §6 | daily returns: 6 tracks + 2 benchmarks |
| `strategy_summary_stats.csv` | backtest §6 | headline stats table |
| `strategy_costs_by_ccy.csv` | backtest §4 | half-spreads + turnover per currency |
| `crash_regressions.csv` | backtest §5 | ΔIV/ΔRR/ΔEMBI loadings per track |
| `weights_g10_monthly.csv` | backtest §6 | month-end weights, G10 track |
| `weights_combined_monthly.csv` | backtest §6 | month-end weights, combined track |
| `stage3_dynamic_comparison.csv` | dynamic_carry §6 | all Stage-3 variants × gross/net: full metrics, IR, turnover, cost drag, NW alpha vs baseline |
| `stage4_weighting_comparison.csv` | portfolio_construction §3/5 | 4 within-leg schemes (equal/inv_vol/erc/mvo) × gross/net on the ALL book: full metrics, IR, turnover, cost drag, NW alpha vs inv_vol |
| `weights_{scheme}_monthly.csv` (equal/inv_vol/erc/mvo) | portfolio_construction §5 | month-end **unit-book** weights per scheme (gross 2, pre-vol-target, so schemes are directly comparable) |
| `stage5_momentum_comparison.csv` | momentum_overlay §5 | pure carry vs momentum vs filter vs blend, per lookback (21/63/252) × G10/ALL × gross/net: full metrics, IR, turnover, cost drag, NW alpha vs carry |
| `stage5_track_correlation.csv` | momentum_overlay §4 | correlation matrix of the net daily tracks (carry↔momentum diversification) |
| `regime_series.csv` | regime_analysis §5 | daily per-indicator percentile ranks + composite + Low/Moderate/Crisis label |
| `stage6_regime_stats.csv` | regime_analysis §5 | 7 allocation variants (static/voltgt/vix/rrccy/reg_half/reg_off/reg_mod) × gross/net: full metrics, IR, turnover, cost drag, NW alpha vs voltgt |
| `stage6_conditional_by_regime.csv` | regime_analysis §5 | vol-targeted book's return/vol/Sharpe/skew/P&L-share by regime, with n_days |
| `skew_carry_comparison.csv` | skew_carry §3 (D1) | option-implied-skew battery (iskew/blendhi/blendlo/clean/srp + srp126, matched U21) + ALL-27 carry reconciliation × gross/net: full metrics, IR, turnover, cost drag, NW alpha vs matched carry |
| `srp_carry_spanning.csv` | skew_carry §4 (D1) | SRP-vs-carry spanning both ways (α/β/t/R²): carry subsumes SRP, not vice versa |
| `skew_track_correlation.csv` | skew_carry §6 (D1) | correlation matrix of the net daily D1 tracks |

**Planned:** `stage7_ml_forecast_eval.csv` +
`stage7_ml_strategy_stats.csv` (§13) · `final_comparison.csv` (§14.2).

## Appendix B — References

- Lustig, Roussanov, Verdelhan (2011), *Common Risk Factors in Currency Markets* — in `papers/`.
- Burnside, Eichenbaum, Rebelo (2011), *Carry Trade and Momentum in Currency Markets* — in `papers/`.
- Menkhoff, Sarno, Schmeling, Schrimpf (2012a), *Carry Trades and Global Foreign Exchange Volatility*.
- Menkhoff, Sarno, Schmeling, Schrimpf (2012b), *Currency Momentum Strategies*.
- Brunnermeier, Nagel, Pedersen (2008), *Carry Trades and Currency Crashes*.
- Fama (1984), *Forward and Spot Exchange Rates*.
- Ledoit & Wolf (2004), covariance shrinkage.
- López de Prado (2018), *Advances in Financial Machine Learning* (purged walk-forward CV).

**Phase 3 / D1 — crash-risk-premium-adjusted carry** (crash risk explains only *part* of carry; tilt,
don't neutralize; RR direction is contested; the SRP-subsumes-carry claim is the key hypothesis — and
it did **not** replicate here, see §17.1):
- Jurek (2014), *Crash-Neutral Currency Carry Trades* — `papers/jurek_currency.pdf`. Crash-hedging
  removes ≤35% of the carry return; fully crash-neutralizing + dollar-neutral + including 2008 → ~zero.
- Farhi & Gabaix (2016), *Rare Disasters and Exchange Rates* — `papers/rare_disasters_and_exchange_rates`.
- Farhi, Fraiberger, Gabaix, Rancière, Verdelhan, *Crash Risk in Currency Markets* — SSRN 1397668.
  Disaster risk ≈ one-third of the G10 carry premium; RR ∝ the currency risk premium.
- Broll (2016), *The Skewness Risk Premium in Currency Markets* — SSRN 2775663.
- Li, Sarno & Zinna (2023), *Skewness Risk Premium* — SSRN 4580189. SRP = physical − risk-neutral
  (model-free) skewness; claims SRP subsumes carry. **Single-source spanning claim; falsified on our
  2007–2026 21-name panel (§17.1) — carry subsumes SRP.**
- Della Corte et al., *Volatility Risk Premia and Exchange Rate Predictability* — SSRN 2892114 (Phase-3
  direction D2, parked).

## Appendix C — Corrections vs the original plan

1. **Signal definition.** Original: "rank currencies by interest rates." The repo (correctly) uses
   **forward-implied carry** ln(S/F) — tradable, includes the NDF/convertibility basis, no
   onshore-fixing availability problems; validated against onshore differentials via the CIP
   check. Codified as the project's signal definition.
2. **"Collect data from Bloomberg" as future work.** Done — converted to the §5 inventory and
   refresh procedure.
3. **Stage-1 metric list vs library.** Sortino/Calmar/turnover promised but absent from
   `summary_stats` → explicit §14.1 work item instead of a silent mismatch.
4. **Stage-2 macro releases** (GDP, PMI, payrolls, inflation, MOVE, TED, FCI): not downloaded;
   release-frequency/vintage problems at daily horizon → explicitly descoped to optional, with
   the daily market-proxy set documented as the deliberate choice.
5. **Transaction costs were absent from the original plan.** The implemented bid/ask +
   roll-via-swap model changes conclusions (EM viability) → promoted to a global guardrail:
   every result gross AND net.
6. **Universe/convention hygiene was absent** (pegs, CNY/CNH, NDF roots, FWD_SCALE, TRY) — where
   real-world errors live → promoted to first-class §5.1.
7. **External benchmarks were absent.** The repo validates against investable DB indices
   (corr 0.55/0.39, IR 0.27/0.50) → codified as mandatory reporting.
8. **Stage 7 was underspecified and oversized.** Five models with no CV scheme is a lookahead trap
   at ~230 monthly obs → descoped to the ElasticNet family + one ensemble, purged walk-forward CV
   specified, null-result-is-a-result framing. Relatedly, with μ = carry, the original Stage-4
   "mean-variance" and "maximum Sharpe" items collapse into one scheme.
9. **Regime terciles.** Crisis is a tail state → asymmetric breaks (70th/90th trailing
   percentile) instead of equal thirds.
10. **No acceptance criteria or output registry anywhere.** Every stage now ends with named CSVs
    and falsifiable acceptance criteria; Appendix A maps all artifacts.
11. **Narrative correction.** The original implicitly assumes carry works in the majors; over
    2007–2026 the premium is EM (combined 7.0%/yr Sharpe 0.63 vs G10 1.9%/yr 0.17; DBHVG10U
    negative over the sample). The executive summary leads with this finding.


push