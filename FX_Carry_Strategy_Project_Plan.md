# FX Carry Strategy — Project Plan & Status

*Author: Cesare Bavaresco · UChicago Summer Project Lab with Bank of America (Corporate Treasury / Global Funding).*
*Data: daily Bloomberg, 2007-01 → 2026-06, G10 + EM currencies vs USD.*
*Last updated: 2026-07-07.*
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
3. Explore strategy behaviour across market environments — 🔶 in progress (Stages 3–6).

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
5. **The simple crash hedge is tail insurance, not a Sharpe improver.** Halving exposure above the
   trailing 80th percentile of implied vol / risk reversals cuts G10 CVaR₉₉ from 3.2% to 2.8% and
   improves skew (−0.95 → −0.67), but costs Sharpe (combined 0.63 → 0.53). Refinement is Stage 3/6
   work.

Stage dashboard:

| Stage | Status | Where | Key artifacts |
|---|---|---|---|
| 0. Data & infrastructure | ✅ | `src/`, `data/raw/`, `cesare/fx_utils.py` | 13 parquet groups, ticker manifest |
| 1. Baseline carry | ✅ | `cesare/strategy_backtest.ipynb` §1–2, §4 | `strategy_summary_stats.csv`, weights CSVs |
| 2. Return drivers | ✅ | `cesare/data_visualization.ipynb` §5, §7–8; backtest §3, §5 | `regression_lrv.csv`, `regression_macro.csv`, `uip_fama.csv`, `crash_regressions.csv` |
| 3. Dynamic carry | 🔶 | backtest §5 (hedge only) | `crash_regressions.csv` |
| 4. Portfolio construction comparison | ⬜ | — | — |
| 5. Momentum overlay | ⬜ | — | — |
| 6. Regime analysis | ⬜ | — | — |
| 7. ML extension (optional) | ⬜ | — | — |
| Final evaluation & report | 🔶 | metrics partial in `fx_utils.summary_stats` | — |

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
| Performance stats | `summary_stats`, `max_drawdown` |
| Factors & regressions | `dollar_factor`, `carry_hml_factor`, `nw_regression`, `regression_table` |
| CIP / rates | `onshore_rate`, `interest_diff_vs_usd`, `cip_basis` |
| Portfolio construction | `carry_portfolio`, `vol_target_weights`, `portfolio_returns` |
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
2. Add a momentum-factor row to the backtest §3 regressions once Stage 5 exists.

## 9. Stage 3 — Dynamic Carry & Risk Management 🔶

**Status:** partial. Vol targeting and one threshold hedge exist; the stage's core deliverable —
an explicit static vs vol-targeted vs risk-managed comparison — does not.

**What exists**

- `vol_target_weights` (10% target, 60d window, monthly, 4× cap, 1% vol floor, next-day
  effective).
- **Threshold hedge** (backtest §5): halve next month's exposure when month-end aggregate 1M ATM
  IV *or* 25Δ RR exceeds its trailing 36-month 80th percentile. Result: tail insurance
  (G10 CVaR₉₉ 3.2% → 2.8%, skew −0.95 → −0.67) but Sharpe cost (combined 0.63 → 0.53).

**Gaps vs original plan**

- No **Static / Vol-Targeted / Risk-Managed comparison table** — the stage's stated output.
- No **VIX-conditioned rule** tested (the original's headline example); VIX is in `global_risk`.
- Hedged tracks are **gross only** — no net-of-cost hedged variant.
- The static (un-vol-targeted, unit-gross) track is never reported as a named row.
- Hedge logic lives ad-hoc in the notebook, not in `fx_utils`.

**Next actions**

1. Promote the hedge logic into `fx_utils`:
   `exposure_scalar(indicator, lookback=756, q=0.80, low_mult=0.5, rebal="ME", method="binary")`
   — trailing-quantile threshold sampled at rebalance dates, `ffill().shift(1)`; generalizes to
   any conditioning series (VIX, IV, RR, EMBI). Add `method="linear"` (scale continuously in the
   trailing percentile) as the flagged refinement.
2. New backtest section (or `cesare/dynamic_carry.ipynb`): comparison rows =
   {static unit-gross, vol-targeted, VIX-threshold, IV/RR-threshold} × {gross, net}.
3. Test **per-currency RR conditioning** (scale individual weights, not the whole book).
4. Build the **net-of-cost hedged track** (§4 × §5 combination flagged in the notebook takeaways).

- **Outputs:** `outputs/stage3_dynamic_comparison.csv` (all variants, full metrics + benchmark IR).
- **Acceptance criteria:** all four variants gross+net on the common window; NW t-stat on the
  dynamic-minus-static difference (or alpha of dynamic on static); an explicit written verdict per
  rule — adopt / tail-insurance-only / reject.

## 10. Stage 4 — Portfolio Construction Comparison ⬜

**Status:** not started — only inverse-vol-within-legs (+40% cap) exists, inside `carry_portfolio`.

**Design**

Hold everything fixed except within-leg weighting (combined quintile sort, monthly, same cost
model), and re-vol-target every variant to 10% so the Sharpe comparison is scale-free — the
differentiators become net-of-cost efficiency and tail shape.

Schemes: **equal weight**, **inverse vol** (current), **equal risk contribution**,
**mean-variance with μ = current forward-implied carry**. Note: with μ = carry, the original
plan's "mean-variance" and "maximum Sharpe" collapse into one scheme (Appendix C #8).

**Next actions**

1. Refactor, don't duplicate: add `weighting: str = "inv_vol"` to `carry_portfolio`
   (`"equal" | "inv_vol" | "erc" | "mvo"`), keeping the sort/no-lookahead scaffolding
   single-sourced.
2. New pure helpers in `fx_utils`:
   - `erc_weights(cov, max_iter=1000, tol=1e-8)` — equal risk contribution per leg (cyclical
     coordinate descent).
   - `shrunk_cov(xret, window=250)` — Ledoit–Wolf shrinkage (27 assets on a 60-obs window is
     near-singular; 250d + shrinkage is the standard fix).
   - `mvo_weights(mu, cov, gross=1.0, max_share=0.40)` — max-Sharpe under leg-gross and cap
     constraints, μ = observable carry (no return forecasting).
3. New notebook `cesare/portfolio_construction.ipynb`; report per-scheme **turnover** explicitly
   (MVO will churn — net results are the decision criterion).

- **Outputs:** `outputs/stage4_weighting_comparison.csv`; `outputs/weights_{scheme}_monthly.csv`.
- **Acceptance criteria:** four schemes × gross/net on the common window, with turnover; a written
  conclusion on whether optimization beats inverse-vol **net of costs** (honest prior: modestly at
  best).

## 11. Stage 5 — Momentum Overlay ⬜

**Status:** not started; the reference paper (Burnside–Eichenbaum–Rebelo, *Carry Trade and
Momentum in Currency Markets*) is in `papers/`.

**Next actions**

1. Signal helper: `momentum_panel(xret, lookback=63, skip=0)` — trailing cumulative **excess**
   return (not spot-only: the carry accrual is part of what a trend follower realizes). Lookback
   grid **21 / 63 / 252 days** (1/3/12M) per Burnside et al. (2011) and Menkhoff et al. (2012b);
   `skip=0` default — the FX momentum literature does not use the equity 12-2 skip (parameter kept
   for robustness checks).
2. Three combination methods, all reusing `carry_portfolio` (it accepts any signal panel):
   - **(a) Standalone momentum sort** — establishes the diversification premise; measure the
     carry–momentum track correlation (literature: low/negative).
   - **(b) Double-sort filter** (the original plan's rule): long = high carry ∩ momentum ≥ 0;
     short = low carry ∩ momentum ≤ 0. Thin wrapper `filtered_carry_portfolio(carry_ann, mom,
     xret, **kwargs)` (or a `filter_signal=` kwarg) since it changes bucket membership.
   - **(c) Blend:** `zscore_xs(panel)`; combined signal = 0.5·z(carry) + 0.5·z(momentum), fed
     straight into `carry_portfolio`.
3. Add the momentum factor to the Stage-2 track regressions (§8 cross-reference).

- **Outputs:** `outputs/stage5_momentum_comparison.csv` (pure carry vs pure momentum vs filter vs
  blend, per lookback, gross+net); correlation matrix of tracks.
- **Acceptance criteria:** the plan's own test, made falsifiable — does the momentum filter reduce
  MaxDD / CVaR₉₉ at **less** Sharpe cost than the Stage-3 hedge did (0.63 → 0.53)? Report
  gross+net; state which lookback wins and whether the result is robust across the grid (guard
  against lookback-mining).

## 12. Stage 6 — Market Regime Analysis ⬜

**Status:** not started. The Stage-3 single-threshold hedge is the only regime-like logic; this
stage generalizes and, if successful, supersedes it.

**Next actions**

1. **Classification variables** (all daily, already in `data/raw/`): VIX (`global_risk`),
   aggregate FX ATM IV (cross-sectional mean of `vol_surface_panel("ATM","1M")`), EMBI spread
   (`load_em_risk`); optional: DXY trend, carry dispersion (Stage-2 add-on).
2. **Primary method — transparent percentile composite:**
   `regime_classify(indicators, lookback=756, breaks=(0.70, 0.90))` — composite = mean of
   trailing-3y percentile ranks; regimes **Low / Moderate / Crisis** at asymmetric breaks.
   Rationale: crisis is a tail state — equal terciles would label a third of history "crisis"
   (Appendix C #9). Trailing windows only, sampled at rebalance, shifted per §6.
3. **Stretch (optional, clearly marked):** 2–3 state Gaussian HMM on (DOL realized vol,
   carry-factor return), expanding-window fit only.
4. **Analyses:** (a) conditional performance of every existing track by regime, with observation
   counts (expected: carry earned in Low, crashes in Crisis — verify); (b) regime-aware
   allocation — exposure multipliers {Low: 1.0, Moderate: 1.0, Crisis: 0.5 or 0.0} — compared
   head-to-head vs the Stage-3 binary hedge and vs static, gross+net.

- **Outputs:** `outputs/regime_series.csv`, `outputs/stage6_regime_stats.csv`, regime-shaded
  cumulative-return plot.
- **Acceptance criteria:** regime series reproducible from the stated rules alone; conditional
  table includes n_days per regime; net comparison (regime-aware vs Stage-3 hedge vs static) with
  an explicit adopt/reject verdict — the regime rule must beat the binary hedge to justify itself.

## 13. Stage 7 — Machine Learning Extension (Optional) ⬜

**Status:** not started. The original plan named five models but no target, feature lags, or CV
scheme — for ~230 monthly observations that silence is a lookahead trap (Appendix C #8). Specs:

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

### 14.1 Metric library completion (do first — everything downstream consumes it)

- Extend `fx_utils.summary_stats` in place (backward-compatible new columns): `cagr` (geometric),
  `sortino` (annualized, downside deviation vs 0), `calmar` (CAGR / |MaxDD|).
- New `turnover(weights, rebal="ME")` — average monthly one-sided turnover Σ|Δw|/2; state the
  convention explicitly.
- Regenerate `strategy_summary_stats.csv` and the other stats CSVs afterwards.

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
| 1 | §14.1 metrics + regenerate CSVs | — | 0.5 d | Every later comparison consumes these |
| 2 | §14.4 hygiene (README, requirements) | — | 0.5 d | Cheap; makes the repo presentable now |
| 3 | Stage 3 completion | 1 | 1 d | Mostly assembles existing pieces; closes the first 🔶 |
| 4 | Stage 5 momentum | 1 | 1.5 d | Feeds Stage 6 conditional stats and Stage 7 features |
| 5 | Stage 4 weighting comparison | 1 | 1.5–2 d | Independent — parallelizable with #4 |
| 6 | Stage 6 regimes | 3, 4 | 1.5 d | Generalizes the Stage-3 threshold rule |
| 7 | Stage 7 ML (optional) | 4, 5, 6 | 2–3 d | Last; explicitly droppable |
| 8 | §14.2 final table + §14.3 report | all above | 1.5–2 d | Terminal deliverable |

Key dependency edges: metrics → everything; momentum → regime stats → ML features; the Stage-3
verdict shapes the Stage-6 design (the regime rule must beat the binary hedge); Stage 4 is the
only fully parallel branch.

## 16. Alignment with the BoA Proposal

The project satisfies the proposal objectives by: constructing historical FX carry portfolios ✅;
evaluating return and risk characteristics ✅; investigating macroeconomic and market drivers ✅;
exploring alternative portfolio construction techniques (Stage 4); testing performance across
market environments (Stages 3, 6); and building reusable Python tools for future research ✅
(`fx_utils`). Beyond replicating the academic literature, it adds the practical layers that matter
on a desk: real transaction costs, external benchmark validation, crash-risk measurement, and
regime-aware exposure management.

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

**Planned:** `stage3_dynamic_comparison.csv` (§9) · `stage4_weighting_comparison.csv` +
`weights_{scheme}_monthly.csv` (§10) · `stage5_momentum_comparison.csv` (§11) ·
`regime_series.csv` + `stage6_regime_stats.csv` (§12) · `stage7_ml_forecast_eval.csv` +
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