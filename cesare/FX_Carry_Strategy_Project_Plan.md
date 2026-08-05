# FX Carry Strategy — Project Plan & Status

*Author: Cesare Bavaresco · UChicago Summer Project Lab with Bank of America (Corporate Treasury / Global Funding).*
*Data: daily Bloomberg, 2007-01 → 2026-06, G10 + EM currencies vs USD.*
*Last updated: 2026-08-04 (W4 executed: D1 rerun, D2, the Aug 5 deck, and the full `report/`).*
*Status legend: ✅ done · 🔶 partial · ⬜ not started.*

This document replaces the original generic project outline. It is now git-tracked and serves as the
repo's source of truth: each stage records **what exists** (files, functions, verified results),
**gaps** versus the original plan, and **concrete next actions** with named outputs and acceptance
criteria. Every number quoted below is reproducible from a CSV in `cesare/outputs/`.

Since 2026-08-03 it also carries the **BofA desk mandates** from the Jul 8 → Jul 29 meeting minutes
(ledger in §19.1) and the **team-integration track** (§19). Sections 1–18 remain a record of my own
research; §19 is where the six workstreams converge into one book. Where a desk ask belongs to a
teammate, this document tracks *status and interface*, not their method — their folder is their
source of truth.

---

## 1. Project Objective

Develop, evaluate, and improve a quantitative FX Carry trading strategy using historical foreign
exchange, interest rate, and macroeconomic data. The project replicates the classic academic carry
strategy before extending it with modern portfolio construction, risk management, and forecasting
techniques.

Mapped to the proposal's three implementation goals:

1. Collect Bloomberg time series — ✅ done (§5).
2. Build reusable portfolio / return / risk libraries — ✅ done (`cesare/fx_utils.py`, §5.3).
3. Explore strategy behaviour across market environments — ✅ core done (Stages 3–6 all closed);
   Phase 3 (§17) hunted a novel edge and closed **null twice** (D1 skew, D3 basis).
   **Phase 4 (§19) is now the main event for August**: fold the six workstreams into one combined
   engine, evaluated per stress window, with a tail-event forecast baked into the book.

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
   **⚑ Re-verdict DONE (2026-08-03, W1)** → `outputs/p4_reverdict_tail_objective.csv`. Those
   verdicts were all written with Sharpe in the verdict column. Re-read on the desk's tail
   objective — accept if the net Sharpe cost is ≤ 0.02 **and** the rule buys ≥ 1.0pp of MaxDD or
   ≥ 5% relative CVaR₉₉, a rule fixed before computing — **five of twelve rules flip to ACCEPT**:
   per-currency RR (ALL **and** G10), the G10 IV/RR linear ramp, the regime Moderate→0.5/Crisis→0.0
   variant, and Dafu's VIX percentile gate (−0.0007 Sharpe for **+4.82pp** of MaxDD, exactly as
   §19.3 predicted). No re-runs — committed CSVs only. Details and caveats in §19.3.
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

9. **The first thing to clear the bar came from a teammate, not from a new signal.** Arjun's
   **duration hedge** (bonds/yields, after DXY was shown redundant) lifts the combined book from
   net Sharpe **0.467 → 0.510** on an *expanding, real-time* hedge ratio (0.527 in-sample), with
   MaxDD −33.2% → −32.2% and skew −0.648 → −0.597 (`arjun/outputs/duration_hedge_stats.csv`). Two
   solo differentiators (D1, D3) came back null while the team's own results did not — which is the
   single strongest argument for spending August on **integration** (§19) rather than hunting a
   third novel signal.
   **⚑ Re-priced on the base 2026-08-03 (W2) → net 0.4659 → 0.5145** via the new `ExternalLeg`
   hook, with the hedge ratio re-estimated on this base's own book and the hedge paying its own
   transaction costs. Two corrections to the framing above, both verified by execution
   (Appendix C #22–#24): his `book` column **is** `run().net` bit-identical (1.0e-16), so his
   comparison was already on the shared base; the −33.2% figure is a **cumsum** drawdown, not the
   base's wealth-curve convention, and is not comparable to −29.3%; and honest costing moves the
   headline by **0.02bp/yr**, not at all — the "essentially unpriced" reading was a
   misattribution. Details and per-window table in §19.4.

10. **Nine attempts have now failed to beat the simple book.** Four standard (Stages 3–6), three
    novel (D1/D3/D6), two from integration (Vidhi's regime gate, the P4-B tail forecast). Nothing
    anywhere in the project has produced a *statistically significant* net alpha — the largest
    |t| on any rung of the Phase-4 ladder is **1.16**. What the surviving components buy is tail
    and skew, not return. Written up as report chapter `report/09_what_did_not_work.md`.

**Through-line:** the 2007–2026 premium is EM carry, and every *standard* embellishment — hedges,
optimization, momentum, regime timing — fails to beat the simple vol-targeted inverse-vol book net
of costs; Phase 3's two *non-standard* signals (§17) failed too. What has actually moved the book is
a teammate's duration hedge. **Phase 4 (§19) therefore stops searching and starts assembling.**

> **Desk mandate — evaluation frame changed (BofA, 2026-07-29, restated with emphasis).**
> Results must be reported **per specific stress window**; whole-sample statistics are supporting
> evidence only. The rationale is the strategy's known failure mode — returns compound from carry
> accrual and spot appreciation, so one large loss breaks the compounding path, and *minimizing
> large losses is worth more than adding incremental gains*. Sections 7–18 below were written
> whole-sample-first and are left as the historical record; from §19 onward the frozen episode
> table (§19.2) is the primary lens, codified as guardrail §6.8.

Stage dashboard:

| Stage | Status | Where | Key artifacts |
|---|---|---|---|
| 0. Data & infrastructure | ✅ | `src/`, `data/raw/`, `strategy/fx_utils.py` | 13 parquet groups, ticker manifest |
| 1. Baseline carry | ✅ | `cesare/strategy_backtest.ipynb` §1–2, §4 | `strategy_summary_stats.csv`, weights CSVs |
| 2. Return drivers | ✅ | `cesare/data_visualization.ipynb` §5, §7–8; backtest §3, §5 | `regression_lrv.csv`, `regression_macro.csv`, `uip_fama.csv`, `crash_regressions.csv` |
| 3. Dynamic carry | ✅ | `cesare/dynamic_carry.ipynb`; `fx_utils.exposure_scalar` | `stage3_dynamic_comparison.csv` |
| 4. Portfolio construction comparison | ✅ | `cesare/portfolio_construction.ipynb`; `fx_utils.shrunk_cov`, `erc_weights`, `mvo_weights`, `carry_portfolio(weighting=)` | `stage4_weighting_comparison.csv`, `weights_{scheme}_monthly.csv` |
| 5. Momentum overlay | ✅ | `cesare/momentum_overlay.ipynb`; `fx_utils.momentum_panel`, `zscore_xs`, `carry_portfolio(filter_signal=)`; backtest §3 MOM factor | `stage5_momentum_comparison.csv`, `stage5_track_correlation.csv` |
| 6. Regime analysis | ✅ | `cesare/regime_analysis.ipynb`; `fx_utils.regime_classify` | `regime_series.csv`, `stage6_regime_stats.csv`, `stage6_conditional_by_regime.csv` |
| 7. ML extension (optional) | ⬜ | descoped — survives only as the P4-B tail classifier (§19.3) | — |
| Phase 3 — novel edge (§17) | ✅ closed | D1 skew **null** (**rerun 2026-08-04 on model-free BKM — null survives**), D3 basis **null**, D6 term structure **null**; **D2 vol risk premium ✅ the one non-null, heavily qualified (§17.4)**; D4/D5 cut (§17.3) | `skew_carry_comparison.csv`, `basis_carry_comparison.csv`, `tenor_sweep.csv`, `p3_d1_bkm_*.csv` (5), `p3_d2_*.csv` (8), spanning CSVs |
| **Team base strategy (§18)** | ✅ **v1.2.0** | `strategy/` (repo root) | `strategy/{config,core,fx_utils,episodes,overlays}.py`, README, 5 examples, **12 + 11 + 17 + 8 = 48** acceptance tests |
| **P4-A stress-window standard (§19.2)** | ✅ **done 2026-08-03 (W1)** | `strategy/episodes.py`, `cesare/final_evaluation.py` | `p4_episode_table_baseline.csv`, `p4_stress_table_baseline.csv`, `p4_leg_decomposition.csv`, `p4_reverdict_tail_objective.csv`, `final_comparison.csv`, `tenor_sweep.csv` |
| **P4-B tail-event forecast (§19.3)** | ✅ **done 2026-08-03 (W3) — NULL** | `cesare/tail_forecast.py` | `p4_tail_forecast_eval.csv`, `p4_tail_overlay_stats.csv`, `p4_tail_overlay_by_episode.csv`, `p4_tail_feature_importance.csv` |
| **P4-C combined engine (§19.4)** | ✅ **done 2026-08-03 (W2–W3)** | `strategy/overlays.py` + `COMBINED` preset, `cesare/combined_engine.py` | `p4_component_standalone.csv`, `p4_component_by_episode.csv`, `p4_combined_ladder.csv`, `p4_combined_by_episode.csv`, `p4_selection_vs_derisking.csv` |
| **P4-D delivery (§19.5, §14.2/14.3)** | ✅ **done 2026-08-04 (W4)** | `report/` | `final_comparison.csv` ✅ (**232 rows**, 0 duplicate keys); `final_comparison_by_episode.csv` ✅ (**652 rows**, 38 variants, 6 gaps recorded in-file); **all 11 report chapters** ✅ |
| Final evaluation & report | ✅ **done 2026-08-04** | §14.1 metrics ✅; repo hygiene ✅ (cesare/, §14.4); §14.2 **both** tables ✅; §14.3 **all 11 chapters written** ✅; §14.5 collation ⬜ | `final_comparison{,_by_episode}.csv`; `report/01..11_*.md` |

**Base adoption (§18):** Dafu ✅ · Arjun ⬜ · Theo ⬜ · Vidhi ⬜ · Oleg ⬜. Deadline: the
**2026-08-12** BofA meeting.
**⚑ No longer the gate for §19.** As of 2026-08-03 the §15 fallback is the *primary* plan and has
been executed: all four teammate components are **re-priced on the base from their committed
outputs** (§19.4), so P4-C is delivered without waiting on four other people. Porting remains
valuable — a re-price is my reading of their signal, not their specification of it — but it is no
longer on the critical path.

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

### 5.3 Shared library map — `strategy/fx_utils.py`

*(Moved from `cesare/fx_utils.py` to the team-owned `strategy/` package on 2026-07-28, §18.
`cesare/fx_utils.py` remains as a re-export shim, so every notebook and every teammate's
`sys.path.insert(0, "../cesare"); import fx_utils` keeps working unchanged.)*

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
8. **Per-window reporting is mandatory** *(added 2026-08-03 — BofA standing requirement, §19.1)*.
   Every variant reports the frozen episode table (§19.2, `strategy/episodes.py`) next to its
   whole-sample stats. A whole-sample-only result is incomplete, not a result. The point is not
   decoration: a rule that lifts the full-sample Sharpe while making the crisis eras worse is a
   rule this book does not want.
   **Short windows report different metrics.** Below ~120 trading days, report cumulative return,
   MaxDD, worst day and `n_days` — **never an annualized Sharpe**. Annualizing a ratio off 64 days
   of COVID is noise wearing a decimal point. (`summary_stats` already refuses to do it, which is
   why §19.2 opens with the `min_obs` fix — see Appendix C #13.)
   **✅ Mechanised 2026-08-03 (W1):** `strategy/episodes.py::report_windows` returns the short-window
   metrics and forces `sharpe`/`ann_*` to NaN under 120 days, so the guardrail is enforced by the
   code rather than by memory. Codified for teammates as `strategy/README.md` **rule 11**.
9. **Incremental honesty** *(added 2026-08-03)*. Components are tested **one change at a time**
   against the immediately preceding book on the shared base — not against a number from another
   notebook, window or universe — gross **and** net, with the adopt/reject rule written down
   *before* the run (protocol in §19.4). Build order is fixed in advance, and every ladder is
   reported **both** add-one-in and leave-one-out, so the outcome is an assembly, not a search.
10. **Rebalance-grid safety** *(added 2026-08-03, verified — Appendix C #15)*. `rebal` may only take
    **right-labelled** pandas aliases: `D`, `W-MON`…`W-FRI`, `2W`, `ME`, `QE`. Left-labelled aliases
    (`MS`, `SMS`, `SME`, `QS`, `YS`, `WOM-*`) **leak**: `.resample("MS").last()` stamps the
    *January 31st* value onto the label *January 1st*, so the single `shift(1)` in the base removes
    one day of a lookahead that can be thirty. This matters directly for the desk's "test different
    rebalancing dates" ask (§19.1) — the naive way to do it is the wrong way.
11. ~~**Cost-model validity**~~ **✅ FIXED 2026-08-03 in base v1.1.0 (W1)** *(was: added 2026-08-03,
    verified — Appendix C #14)*. `roundtrip_cost` used to charge the roll leg on the **rebalance**
    grid rather than the **forward tenor** grid, so it was exact only at the committed baseline
    (tenor `1M`, rebal `ME`). It now bills the roll on a tenor-derived grid via
    `fx_utils.roll_schedule`, and the fix is **bit-identical at the baseline** — the whole daily
    cost series matches the pre-fix series to `0.0e+00`, so no committed number moves. Off-baseline
    net numbers are now comparable: the 12M drag falls 4.84% → 1.87%/yr and the 1M×QE cell, which
    was *under*charged, rises 0.89% → 1.33%. The old "report gross only" caveat is withdrawn.
    Guard: `tests/test_episodes.py::test_baseline_cost_drag_unchanged`.
12. **A trimming overlay must be reported against a gross-matched de-risking control**
    *(added 2026-08-03, W3 — verified, Appendix C #25)*. An overlay that zeroes or trims positions
    does two things at once: it drops *particular* names (selection) and it leaves the book holding
    *less notional* (de-risking). A shallower drawdown follows mechanically from the second whatever
    the first is worth. The control is cheap and exact —
    `combined_engine.gross_matched_control(overlay)` reproduces the overlay's daily gross to
    **8.9e-16** while spreading the reduction across every name — and it changed the reading of the
    strongest Phase-4 component: of the bad-skew filter's 7.3pp drawdown improvement, **6.8pp is
    de-risking and 0.5pp is selection**, with the selection alpha insignificant (t 0.92). What
    selection *does* buy is skew, −0.63 → −0.31, which de-risking does not deliver at all. Without
    the control the headline would have been the most misleading number in the project.
13. **A component's slot verdict must be re-measured on the stack actually proposed**
    *(added 2026-08-03, W3)*. Leave-one-out run on a stack containing a component that is later
    rejected measures every survivor against a book nobody will build. Re-running the ladder over
    the survivors is applying criterion (iii), not searching for a better answer — provided both
    passes stay in the output, which they do (`p4_combined_ladder.csv`, `ladder` column).

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
Menkhoff et al. (2012b). BER is in `papers/`; Menkhoff (2012b) is not held locally (Appendix C #34).

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

**Status:** not started; **deferred to the "back pocket" (decision 2026-07-10)**, and **descoped for
good on 2026-08-03**: the full five-model version is cut for the August runway (§19.6). What
survives is item 3 below — the purged walk-forward CV scheme is **reused verbatim** by the P4-B
tail-event classifier (§19.3), which is the same machinery pointed at the question the desk actually
asked (forecast the tail, not the return). Read §13 as the spec P4-B inherits.

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

### 14.2 Consolidated comparison table ⬜ *(scope widened 2026-08-03)*

**Two artifacts, not one** — the second is what the desk will actually read (§6.8):

- `outputs/final_comparison.csv` — whole-sample. Every named variant **across all six workstreams**
  (× gross/net) plus both benchmarks, on the common window. Metrics = the original plan's
  final-evaluation list (CAGR, Sharpe, Sortino, Calmar, MaxDD, IR, hit rate, turnover) + the repo's
  extras (skew, VaR/CVaR). Widened from "Cesare's stages" because §19 makes the team's variants
  directly comparable for the first time.
- `outputs/final_comparison_by_episode.csv` — the **variants × episodes** matrix from
  `episodes.compare_windows` (§19.2). Same variant list, one column per frozen window.

✅ **`final_comparison.csv` stood up 2026-08-03 (W1)** — 158 rows, 6 owners, assembled entirely from
committed CSVs. `on_base` flags whether a row was produced through `run()` and therefore reconciles
to the shared baseline; **10 rows are `on_base=False` and are kept and flagged rather than dropped**,
because a teammate's book disagreeing with the base *is* the §18 finding. Produced by
**`cesare/final_evaluation.py`** (importable, re-runnable, testable) and displayed by
`cesare/final_evaluation.ipynb` — a module rather than notebook cells because this is refreshed every
week through W4, so the terminal week is assembly, not authorship.

✅ **Refreshed W3 → 212 rows, 7 owners, 5 not on base** (was 158 / 6 / 10). Arjun's five rows moved
to `on_base=True` after Appendix C #22; the Phase-4 components, both ladders and the P4-B tail
overlay are now in the table, and they are the first rows in it that are directly comparable to each
other *across owners* rather than merely collected together.

✅ **Refreshed W4 (2026-08-04) → 232 rows, 7 owners, 5 not on base, and 0 duplicate keys.** Added the
D1-rerun battery (14 rows, proxy and model-free kept side by side — the comparison *is* the result)
and D2 (6 rows). D2's rows carry `basis="monthly_uncosted"` rather than gross/net **on purpose**:
they are monthly, on the 21-name option universe, and gross of option bid/ask, so dropping a 1.69
Sharpe into the same `net` column as the daily costed books would manufacture exactly the false
comparability this table exists to prevent. Six duplicate rows fixed (Appendix C #31) and the P4-B
AUC note corrected (#32).

✅ **`final_comparison_by_episode.csv` BUILT 2026-08-04 (W4)** — 652 rows, **38 variants** on the
frozen windows, assembled from the Phase-4 per-episode tables plus the D1 rerun and D2 rather than
re-run. Two metric conventions coexist and are labelled so they cannot be silently compared:
`daily_net` (annualised columns already NaN under 120 trading days, per §6.8) and
`monthly_uncosted` (D2 — no annualised ratio at *any* length, no transaction cost at all).
**What is missing is recorded in the file itself as six explicit `basis="missing"` rows**, with the
reason per owner: teammates' *own* ported books do not exist, and the re-price fallback deliberately
does not substitute for them; Dafu publishes whole-sample stats only; Vidhi's track is monthly and
omits the carry accrual; Theo's results are parquet-only; Oleg has no committed output; and Stages
1–6 plus D3 were deliberately not retrofitted because the per-window standard is prospective
(§19.2). A gap stated in the artifact is a gap; a gap omitted from it is a claim.

### 14.3 Final report outline 🔶 (deliverable for BoA; `report/`) *(restructured 2026-08-03)*

✅ **Skeleton and the null-results chapter written W3** — `report/README.md` (chapter table, the six
rules the report follows, headline numbers for cross-checking) and
`report/09_what_did_not_work.md`, which is item 7 below and is now the longest planned chapter:
**nine** failed attempts, each with the pre-registered bar it failed against and the committed CSV
behind it. ✅ **All remaining chapters written 2026-08-04 (W4)**, and the files renumbered so file numbers match chapter numbers — the null chapter moved `07_` → `09_`. Chapter 8 (the volatility risk premium) is new and did not exist in the original §14.3 outline, because D2 was cut when that outline was written.

Lead with the per-window results, per §6.8, and use the desk's four beats (current results / what we
did / what we have / what is next) as the spine:

1. **Executive summary** — current results, in the desk's terms: what the book earns, where it
   loses, what August's integration added.
2. Data & conventions · 3. Methodology & guardrails (incl. the uniform base, §18).
3. **Baseline results per stress window** — the episode table first, the G10-vs-EM finding second.
4. Return drivers & crash risk · 6. Risk-managed carry · 7. Portfolio construction & momentum ·
   8. Regimes as a diagnostic.
5. **The tail-event forecast** (§19.3) — the desk's central ask, and whether it worked.
6. **The combined engine** (§19.4) — the fold-in ladder, what earned its slot and what did not.
7. **What did not work** — an explicit null-results chapter: D1 skew, D3 basis, DXY hedge, momentum,
   mean-variance, regime timing. The desk has been told a null is a valid deliverable; these are
   stated, not buried, and several of them are the most defensible findings in the project.
8. Limitations (option data is mids-only; no market impact/funding curve; daily USD-per-FX only) ·
   10. Conclusions & recommendations framed for a Corporate Treasury / Global Funding audience.

### 14.4 Repo hygiene checklist ✅ (cesare/ pass done 2026-07-13)

Repo-hygiene pass **scoped to `cesare/` only** (this is a multi-person repo — siblings `theo/`,
`dafu/`, plus shared `notebooks/`/`src/`/`data/` at root). The `README.md` and `requirements.txt`
are written to be self-contained for `cesare/` now **and** to collate LATER into ONE repo-wide
pair, with shared-vs-cesare-unique items flagged for easy dedup. Left uncommitted per the
no-git-ops rule (suggested commit: `docs(cesare): add README + requirements.txt, fix stale
fx_utils docstring paths`).

- [x] **`cesare/README.md`** — created: overview + the EM-carry finding (every overlay incl.
      Phase-3 D1 fails to beat the simple book), folder map, notebook→stage→output table (mirrors
      Appendix A), `fx_utils` API summary (panel chain + helper groups), setup/run + the shared
      `../data/raw/` dependency, a scope & collation note (shared vs unique), and the §6
      reproducibility conventions. Links to this plan as source of truth.
- [x] **`cesare/requirements.txt`** — created: only what `cesare/` actually imports (grepped) —
      numpy, pandas, scipy, statsmodels, pyarrow (indirect via `pd.read_parquet`; pip-over-conda
      caveat inline, §5.2), matplotlib, seaborn (cesare-unique — only `data_visualization.ipynb`)
      — plus the notebook runtime (jupyter, ipykernel, nbformat). Loose `>=` pins with dev versions
      in comments, grouped SHARED/UNIQUE. Deliberately **excluded** unused-but-installed libs
      (scikit-learn, plotly, tqdm, openpyxl, fastparquet); scikit-learn/xgboost join only if Stage 7
      starts. `openpyxl` belongs to `src/convert_extra_xlsx.py`, and the optional `requirements-bbg.txt`
      (xbbg/blpapi) covers the `src/` Bloomberg pull — both **outside `cesare/`**, deferred to the
      repo-wide collation.
      **Superseded and deleted 2026-08-05** — see the hygiene pass in §14.6.
- [x] **.gitignore** — no folder-local `cesare/.gitignore` needed: the root `.gitignore` already
      ignores `__pycache__/`, `.ipynb_checkpoints/`, `.DS_Store` repo-wide and nothing under
      `cesare/` is mis-tracked (the `__pycache__` build cache is untracked). Plan-file exclusion was
      already removed (this document is tracked).
- [x] **Stale `fx_utils` docstring fixed** — module docstring `notebooks/`→`cesare/`, and the
      `FWD_SCALE` comment `notebooks/data_visualization.ipynb`→`cesare/data_visualization.ipynb`;
      the `src/convert_extra_xlsx.py` reference is correct and left as-is. `import fx_utils` verified
      clean; no behaviour change.
- [ ] **Deferred (not blocking):** decide the fate of legacy `notebooks/view_data.ipynb`
      (keep-as-scratch or delete) — it lives in the shared `notebooks/` folder, outside this
      cesare/-scoped pass. Repo-wide collation of the per-person READMEs/requirements happens once
      every teammate has done their own folder.

### 14.5 Repo-wide collation ✅ **done 2026-08-04 (W4)**

*(Promoted from the §14.4 deferral 2026-08-03. Executed without waiting for the Aug 12 adoption
gate — the collation describes the repo as it is, and gating it on four other people would have been
the same mistake §15 already routed around once.)*

- [x] **Root `README.md`** — was a 24-byte stub, now the front door: the research question and its
      short answer, the three headline books, the four findings, `test_reconciliation.py` as the
      one-command reproduction, a folder map, the pyarrow caveat, and the four conventions a reader
      needs before trusting any number here.
- [x] **Root `requirements.txt`** — collated from `cesare/requirements.txt` and `oleg/` plus a grep
      of every third-party import in the repo. Adds **scikit-learn** (1.6.1), which the P4-B tail
      classifier imports and no per-folder file listed, and **openpyxl** for
      `src/convert_extra_xlsx.py`. Deliberately excludes installed-but-unimported libraries.
- [x] **`requirements-bbg.txt`** — created, closing the §14.4 deferral. `xbbg` + `blpapi`, with the
      non-PyPI install line for blpapi and an explicit note that it is **not needed** to reproduce
      anything: `data/raw` is git-tracked, so only a *refresh* needs a terminal.
- [x] **`notebooks/view_data.ipynb`** — **decision: keep as scratch, do not delete.** It lives in the
      shared `notebooks/` folder rather than in `cesare/`, so it is not mine to remove, and it costs
      nothing. Recorded so the question stops being reopened.

Per-folder `README.md` files are left in place: they are each owner's description of their own work.
Per-folder `requirements.txt` files are superseded by the root file for environment setup —
`cesare/requirements.txt` was deleted on 2026-08-05 once it was shown to have drifted (§14.6).

### 14.6 `strategy/` + `cesare/` cleanup ✅ **done 2026-08-05**

*A legibility pass on the two folders I own, scoped to them. Nothing was written to a teammate's
folder; the four suites and every acceptance number are unchanged.*

- [x] **Decks grouped** — `cesare/presentations/` now holds all three: `deck_2026_08_05.html`
      (generated), `overview.html` (moved out of `strategy/`, which is a Python package and should
      not hold a slide deck) and `FX_Carry_Update_Presentation.html`, with a README saying which is
      generated and which numbers are dated. `build_deck.py`'s `DECK` constant follows.
- [x] **`cesare/requirements.txt` deleted.** It was not merely redundant with the root file, it was
      **wrong**: its own header records that it was grepped from `fx_utils.py` and the seven stage
      notebooks, so it predates every Phase-3/4 module and omitted **scikit-learn**, which
      `tail_forecast.py` imports. Two files that must be hand-synced is how it broke; the root file
      is now the only environment spec. No teammate file referenced it.
- [x] **`deck_2026_08_05.md` → `notes/deck_2026_08_05_draft.md`.** The Aug-3 markdown draft of a deck
      that is now generated as HTML. Superseded on its face — its "what is next" lists the combined
      engine and the tail forecast as future work, both since shipped, and it quotes 23 tests where
      there are now 48. Kept as raw material, out of the folder's top level.
- [x] **`cesare/README.md` rewritten.** The old one documented 12 of 26 top-level entries — no
      Phase-3/4 module, neither deck, no `notes/`, and "26 committed result CSVs" against an actual
      59. It now maps the whole folder and states the two couplings that make it un-restructurable:
      the `fx_utils.py` shim (eight consumers in `arjun/`, which is read-only to me) and
      `combined_engine.py` (imported by `strategy/config.py`).
- [x] **`cesare/outputs/README.md` created** — an index by producer covering all 59 CSVs, pointing at
      Appendix A for the per-file description rather than restating it, so the two cannot drift.
- [x] **`strategy/README.md` reconciled to the shipped base.** The base's written contract had no
      mention of `test_combined.py`, the 8/8 suite or the `COMBINED` preset, although `config.py`
      ships `PRESETS["COMBINED"]` and this document, the root README and `report/README.md` all
      quote four suites / 48 tests. Fixed in five places, and a `COMBINED` section added.
- [x] **Nothing else moved.** Every `cesare/` module resolves `OUTPUTS` from
      `Path(__file__).resolve().parent` and the nine notebooks `import fx_utils` as a bare top-level
      module with cwd `cesare/`, so subdividing the folder would break both. The legibility problem
      was the README, not the file count.

## 15. Sequencing — the August runway (2026-08-03 → 2026-08-31)

Stages 1–6, the Phase-3 differentiators and the team base (§18) are all closed. What remains is
**Phase 4 (§19)**: integrate, evaluate per window, deliver. Four weekly buckets, each ending
deck-ready for the Tuesday BofA meeting (Aug 5 · 12 · 19 · 26), with a final hand-in ~Aug 31.

| Week | What I do | What I coordinate | Acceptance |
|---|---|---|---|
| **W1** Aug 3–9 → *Aug 5 mtg* | ✅ **DONE 2026-08-03.** Both base fixes shipped as **v1.1.0** (F1 `summary(min_obs=)` + the `__repr__` guard; F2 tenor-indexed roll leg, bit-identical at baseline); `strategy/episodes.py` + 11 tests; baseline window tables; per-leg accrual reconciled to 3.9e-17; Stages 3 & 6 re-verdicted (5 flips); `final_comparison.csv` + `cesare/final_evaluation.py` stood up; `tenor_sweep.csv` regenerated | ⬜ Issue the porting deadline (Aug 12) with the recipe already in `strategy/README.md`; ⬜ hand Theo the skew-collision spec (§19.1) — **both still open, carried into W2** | ✅ all met: net **0.4659**, gross **0.6284**, turnover **0.675470**, drag **0.018146611** unchanged to **0.0e+00**; **12/12 + 11/11** green; all 8 stress windows populated incl. the four under 120 days; per-leg split reconciles at **3.88e-17** |
| **W2–W3** *(run together, 2026-08-03)* | ✅ **DONE.** Base **v1.2.0**: `strategy/overlays.py` (`compose_exposure`, `compose_overlays` with the gross-non-increasing contract, `ExternalLeg`) + `StrategyConfig.external_legs` + `core.run` step 6, all exact no-ops; `test_overlays.py` **17/17**. All four teammate components **re-priced on the base** from committed outputs (`cesare/combined_engine.py`); both ladders + a survivor re-ladder; `COMBINED` preset frozen with `test_combined.py` **8/8**. P4-B built and **rejected as a null** (`cesare/tail_forecast.py`), including the `purged_walkforward` scheme §13 specified but nobody had written. Aug 5 deck material + both W1 carry-over drafts written | Porting deadline note and Theo's skew-collision spec **drafted, not sent** (`cesare/notes/`). Adoption still 1 of 5 — **deliberately no longer blocking**, see the §18 note | ✅ all met: **48/48** tests green; baseline unchanged to 0.0e+00; `run("COMBINED")` reproduces the ladder's final row at 0.0e+00; every component carries its `report_windows` table and `config.describe()` |
| **W4** *(pulled forward to 2026-08-04)* | ✅ **DONE, three weeks early.** All eleven `report/` chapters written and renumbered so file numbers match chapter numbers; D1 rerun and D2 folded in (ch. 8 is new, ch. 9 restated on model-free skewness); `final_comparison.csv` refreshed to **232 rows** with the D1-rerun and D2 variants and the 6 duplicate rows fixed; **`final_comparison_by_episode.csv` built** (652 rows, 38 variants, 6 gaps recorded in-file); `p3_d2_by_episode.csv` built, closing D2's §6.8 breach; the Aug 5 deck generated by `cesare/build_deck.py`; `implied_skew_panel`'s false docstring corrected (Appendix C #28) | Per-member methodology justification still open; ports still the highest-value outstanding item — four components remain *re-priced, not rebuilt* | ✅ all met: 48/48 tests green, baseline unchanged, every number traceable to a committed CSV. **Remaining: §14.5 collation** |

**Critical path:** ~~the **F1 `min_obs` fix** → `episodes.py` (W1) → everything~~ **cleared W1**;
~~teammate porting (W2 gate) → the combined ladder (W3)~~ **removed W2 by executing the re-price
fallback**. **Nothing is now on the critical path except writing.** Three of the four August weeks'
scheduled work is complete, and the remaining risk is prose, not computation.

**Why W2 and W3 collapsed into one block.** The W2 hard gate (adoption ≥ 3 of 4) was never going to
be met — it stood at 1 of 5 with nine days to go — so waiting for it would have burned both weeks
and still left P4-C unbuilt. Executing §15's own fallback instead cost about a day and produced the
same deliverable, with every folded-in component labelled *re-priced, not rebuilt* and its
reconstruction method recorded in the CSV. **The lesson is worth keeping: a gate that depends on
four other people is a risk to be routed around, not a milestone to be waited on.**

**Risk on the F2 cost fix — retired.** ✅ Shipped as v1.1.0. The pre-fix daily cost series was
snapshotted first; after the fix it matches to **0.0e+00** (not merely the drag to 1e-9), 12/12
stayed green, and the "report gross only" fallback was not needed. The design that made exactness
provable: bill the roll on a **calendar-month-count** grid thinned from the observed rebalance days.
Two naive designs were tried and rejected on evidence first — a "first trading day of each month"
grid is wrong because the rebalance effective day is the *second* trading day in 67 of 230 months,
and a day-count test is wrong because Jul 3 → Aug 1 is 29 days and would skip a roll. The baseline
has exactly one rebalance day in every one of its 230 live months, which is what makes the
month-count test an identity there.

**Fallback if teammates slip past the Aug 12 gate:** accept a **daily net return series** in place
of ported code and re-price it at the reporting layer (`add_hedge_leg`-style). Less clean, and the
construction differences the base was built to eliminate come back — but it keeps the combined
engine off the critical path of four other people. Document any variant folded in this way as
*re-priced, not rebuilt*.

## 16. Alignment with the BoA Proposal

The project satisfies the proposal objectives by: constructing historical FX carry portfolios ✅;
evaluating return and risk characteristics ✅; investigating macroeconomic and market drivers ✅;
exploring alternative portfolio construction techniques (Stage 4); testing performance across
market environments (Stages 3, 6); and building reusable Python tools for future research ✅
(`fx_utils`). Beyond replicating the academic literature, it adds the practical layers that matter
on a desk: real transaction costs, external benchmark validation, crash-risk measurement, and
regime-aware exposure management.

---

## 17. Phase 3 — Beyond Vanilla EM Carry: Toward a Novel Edge (Jul 2026) ✅ **CLOSED** — D1 null · D3 null · D6 null · D2/D4/D5 cut (§17.3)

> **Closed 2026-08-03.** Two differentiators were built and both came back null. The remaining
> candidates are cut with reasons in §17.3; the specs stay intact and reversible. Current focus is
> now **Phase 4 (§19)**. The text below is the record of what was tried and why it failed — which is
> itself a report chapter (§14.3 item 8).

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
| D6 | **Term structure of carry** | Harvest the forward-curve slope / roll-down rather than the single 1M point; *which tenor* to hold. | ~~⚠️ needs multi-tenor forwards (only 1M pulled)~~ → **✅ in repo all along** (Appendix C #12) | Medium |

**Recommendation:** lead with **D1** — the most differentiated signal, fully feasible today, and it
re-uses the crash-risk thread the project already owns — optionally paired with **D3** (the
audience-relevant funding angle, also feasible today). **D2** is the high-upside stretch. D4–D6 need
a data add first.

**Process per chosen direction:** (1) deep-read the literature to sharpen the exact signal and its
priors; (2) add a pure `fx_utils` helper + a dedicated notebook under the existing guardrails;
(3) backtest gross+net vs the two bars with NW tests; (4) an explicit adopt/reject verdict and a new
`stageX_*.csv`. The Phase-3 result — positive *or* null — becomes the centrepiece of the §14.3 report.

*(Historical: the recommendation above was executed as D1 then D3. Both null. See §17.3 for the
disposition of the rest.)*

### 17.1 D1 — Crash-Risk-Premium-Adjusted Carry ✅ (Jul 2026) — **null** · *can rerun with better data*

**Status:** done. An option-implied-skew battery, built on the matched 21-name option universe and
falsified against both bars. Result: **null** — a valid deliverable.

**⚑ Completed, but re-runnable with stronger inputs — see [`DATA_SHOPPING_LIST.md`](DATA_SHOPPING_LIST.md) §0, §2.**
Two upgrades would harden (or genuinely retest) the null:
1. ✅ **DONE 2026-08-04 — the null is now bulletproof.** *(was: model-free skewness from the 10Δ wings we already
   have, no purchase.)* `data/raw/` holds full-history **10Δ RR *and* BF** for all 21 option names — the surface
   is a **5-point smile**, *not* the 3-point set `implied_skew_panel`'s docstring asserts (that docstring is
   wrong; Appendix C #28). Built `cesare/bkm_skew.py` — a Breeden–Litzenberger risk-neutral density from the
   five-point smile, then the third central moment of the log return — and re-ran the battery in
   `cesare/d1_bkm_rerun.py`. **The reconstruction is licensed by an exact reconciliation:** the proxy variants
   reproduce the committed D1 numbers to four decimals (carry **0.4962**, iskew **0.1316**, srp **−0.0906**,
   clean **−0.0309**), so the only thing that changes between the two runs is the risk-neutral leg.

   | Variant | 25Δ slope proxy (D1) | **model-free BKM** | α vs carry (t) |
   |---|---|---|---|
   | U21 carry (anchor) | 0.4962 | 0.4962 | — |
   | SRP (Li–Sarno–Zinna) | −0.0906 | **−0.0611** | −3.06%/yr (−1.39) |
   | implied skew, long crash-priced | 0.1316 | **0.0339** | −4.00%/yr (**−2.36**) |
   | clean carry (Jurek) | −0.0309 | −0.0684 | −3.16%/yr (−1.33) |

   **Spanning, with the model-free input the claim is actually about:**
   `CARRY ~ SRP` α **+3.22%/yr, t +2.23**; `SRP ~ CARRY` α −0.18%/yr, t −0.16. **Carry subsumes SRP; SRP earns
   nothing over carry.** The Li–Sarno–Zinna reversal D1 reported on a proxy *survives the correct construction*,
   and sorting on model-free crash-pricing is now *significantly* worse than carry (t −2.36, where the proxy gave
   an insignificant −1.59). D1's null is no longer contingent on an approximation.

   **The methodological finding, which is the durable part.** The proxy and the model-free measure agree on
   **which** currencies are crash-priced — cross-sectional rank correlation **0.886**, and the sign pattern is
   economically right (JPY **+0.45** and CHF **+0.08** are the only positive names: the funding currencies that
   rally in crises; TRY −1.04, MXN −0.83, BRL −0.77, ZAR −0.76 the most crash-priced). But they barely agree on
   **month-to-month changes at all**: median per-currency change correlation **0.0198**. A pooled level
   correlation of 0.98 hides this completely — it is mostly cross-sectional level dispersion. *The 25Δ smile
   slope is a good cross-sectional proxy for risk-neutral skewness and a nearly useless time-series one*, which
   is exactly why a cross-sectional sort was insensitive to the upgrade and why anyone using RR as a
   **timing** signal should not.
   Outputs: `p3_d1_bkm_comparison.csv`, `p3_d1_bkm_spanning.csv`, `p3_d1_bkm_signal_agreement.csv`
   (all three written by `d1_bkm_rerun.py`); `p3_d1_bkm_skew_panel.csv`, `p3_d1_bkm_clipped_mass.csv`
   (the two QA panels — exported by hand from `bkm_skew.bkm_skew_diagnostics("1M", "ME")`, not
   written by any module; see Appendix C #35).
2. **Full-27 universe (purchase).** Adding option surfaces for the 6 currently-optionless EM (CLP/COP/IDR/MYR/PEN/PHP,
   shopping list §2.2) would let D1 run on the full tradable 27 instead of the matched U21.

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
dollar funding, feasible today) and **D2** (FX vol risk premium) — were next up (**D3** is now done
below, §17.2 — also null); the D1 null already earns a place in the §14.3 report as evidence that the
crash-risk thread, though economically real, is not tradable alpha.

### 17.2 D3 — Cross-Currency Basis / Dollar-Funding Carry ✅ (Jul 2026) — **null** · *can rerun with better data*

**Status:** done. A cross-currency-basis battery — a funding-stress **conditioner** *and* a
**cross-sectional signal** — built on the matched 7-name basis universe and falsified against both
bars. Result: **null** — a valid deliverable, and a decisive one: on the only universe where the basis
is measurable here, carry itself is uncompensated.

**⚑ Completed, but the null was largely a data artifact — the two limits that crippled it are both fixable, so this
is the Phase-3 result most likely to *change* with new data. See [`DATA_SHOPPING_LIST.md`](DATA_SHOPPING_LIST.md) §3.**
1. **Window cap is the USD LIBOR leg, not the onshore fixings (correction).** Verified 2026-07-14: the onshore EM
   fixings *and* the NDFs/forwards all run to **2026-06/07** — but synthetic **USD LIBOR `US0001M`/`US0003M` was
   discontinued 2024-09-30**, which is what kills `interest_diff_vs_usd` → `cip_basis`. Swapping in a **USD SOFR-OIS
   leg** (shopping list §3.1) extends the whole D3 window ~2 years *and* modernizes the basis to the DTV-consistent
   OIS convention. (The prose below and plan §5.2 still say "onshore fixings end 2024-09" — that attribution is
   wrong and is corrected here.)
2. **The universe is fixably narrow (purchase).** The 7-name onshore-fixing EM set has **no G10** and an anchor
   carry that is itself negative (a TRY artifact). **Direct G10 cross-currency basis swaps** (`EUBS3`/`JYBS3`/…,
   §3.2) are quoted market instruments that sidestep the onshore-fixing requirement entirely — giving us the G10
   dollar-funding basis the Du–Tepper–Verdelhan literature actually studies. This could turn D3 from "null on a
   weak EM universe" into a real test.

**What exists:**
- Helper in `fx_utils.py`: `basis_stress_index` (aggregate dollar-funding-stress gauge from the
  cross-currency-basis panel; default `zmean` = mean of per-name trailing z-scores, negated, so a
  single wide-basis name like TRY cannot dominate — so defined the index peaks at Lehman-2008 and the
  COVID-2020 dollar squeeze). No-lookahead, citation-dense (Du–Tepper–Verdelhan 2018;
  Avdjiev–Du–Koch–Shin 2019; Brunnermeier–Nagel–Pedersen 2009). Everything else *reuses* the engine:
  `cip_basis = carry_panel − interest_diff_vs_usd` is an identity (verified max err 8e-17), so the
  basis, the onshore-rate carry (= carry − basis), the tilts and the orthogonalized carry are all
  compositions of existing functions.
- Notebook `cesare/basis_carry.ipynb` (setup → signals → tracks → stats → spanning → validation →
  outputs → verdict). Validation: matched-universe assert (U7), no-lookahead truncation recompute for
  `cip_basis`, the conditioner scalar *and* the basis weight panel, and reconciliation of the ALL-27
  inv-vol-net Sharpe to the committed Stage-4 0.4659 over the full window (Δ = 0.00000).
- Matched universe **U7** = tradable-27 ∩ `cip_basis` (onshore-fixing) coverage = CNH HUF ILS INR PLN
  THB TRY (7 EM names; **no G10** — the basis needs onshore fixings, so the G10 dollar-funding basis
  DTV studied is out of reach with this engine). Two structural caveats: the **USD funding leg (synthetic
  USD LIBOR `US0001M`/`US0003M`) was discontinued 2024-09-30** — *not* the onshore fixings, which run to 2026-07
  (correction, see the ⚑ note above; fixable with a SOFR-OIS leg) — so every basis-dependent track is evaluated on
  **2007-05 → 2024-09** (the ALL-27 baseline
  is reconciled to the committed number over the full 2007-05 → 2026-06 window separately); and this
  universe is *entirely* restricted/convertibility-constrained EM.

**Results** (matched 7-name EM universe, tercile inv-vol, vol-targeted 10%, **net** of costs; NW alpha
vs the *matched* vanilla carry; 2007-05 → 2024-09):

| track | net Sharpe | MaxDD | CVaR₉₉ | skew | turnover | cost drag | α vs carry | t |
|---|---|---|---|---|---|---|---|---|
| **U7 vanilla carry** (anchor) | **−0.32** | −0.72 | 3.0% | −0.29 | 0.45 | 1.8% | — | — |
| (a) basis-sorted | −0.13 | −0.54 | 3.0% | −0.11 | 1.14 | 3.4% | −0.9% | −0.3 |
| (b) onshore-rate carry (= carry − basis) | −0.41 | −0.74 | 2.9% | −0.35 | 0.23 | 1.3% | −1.5% | −1.2 |
| (c) carry tilted toward rich basis (tilthi) | −0.17 | −0.67 | 3.3% | −0.73 | 0.95 | 2.8% | +0.9% | +0.5 |
| (c) carry tilted toward dollar-shortage (tiltlo) | −0.69 | −0.83 | 3.0% | −0.61 | 0.77 | 2.3% | −5.7% | **−2.8** |
| (d) clean carry (carry ⟂ basis) | −0.20 | −0.62 | 2.7% | −0.59 | 0.77 | 2.2% | +0.7% | +0.5 |
| conditioner on ALL-27 (basis funding-stress de-risk) | 0.31 | −0.28 | 2.8% | −0.67 | 0.69 | 1.7% | +0.4%¹ | +0.8¹ |
| ALL-27 vanilla carry (2007–24 subsample) | 0.28 | −0.29 | 2.9% | −0.62 | 0.66 | 1.7% | — | — |

¹ conditioner α/t are vs the *un-conditioned* ALL-27 book (its natural comparator); the same book
reconciles to the committed 0.4659 over the full 2007-05 → 2026-06 window (§5 guard, Δ = 0.00000).

**Basis-vs-carry spanning** (U7 unit long/short factor books, gross returns, NW 5 lags):

| regression | α (ann) | t(α) | β | t(β) | R² |
|---|---|---|---|---|---|
| BASIS ~ CARRY | +1.6% | +0.66 | 0.24 | 2.84 | 0.05 |
| CARRY ~ BASIS | −0.8% | −0.34 | 0.20 | 2.67 | 0.05 |
| ONSHORE ~ CARRY | −0.6% | −0.45 | 0.89 | 41.6 | 0.71 |

**Verdict — REJECT (null).** The basis is only measurable where onshore fixings exist, which confines
the tradable universe to 7 restricted EM names — and on that universe the matched vanilla carry book is
itself **negative** (−0.32), miles below both published bars (0.466 / 0.457). Every basis variant is
also negative; only `tiltlo` (chasing the most dollar-short names — Du's "shortage pays") is
*significantly* worse (t −2.8). Cross-sectionally the basis adds nothing that clears the bar, and the
two-way spanning is a non-result on a universe too weak to span or be spanned (both |t| < 0.7); the
onshore-rate carry is a near-clone of the forward carry (β 0.89, R² 0.71), so the basis is a small,
non-priced increment — exactly what the `carry = onshore + basis` identity implies. As a conditioner
the basis-derived funding-stress index does light up at Lehman-2008 and the COVID-2020 dollar squeeze
(it measures what DTV/Avdjiev say it does), but halving ALL-27 exposure in its top quintile lifts the
book only 0.28 → 0.31 with insignificant alpha (t +0.8) and stays far under 0.466 — the same verdict
Stage-6 regime-timing reached with VIX/vol/EMBI. Robustness: the negative anchor is a TRY-lira-crisis
artefact (drop TRY → +0.27, still far below the bars; drop CNH → −0.28), the null holds at the 3M tenor
(carry −0.32, basis-sort +0.07), and the conditioner is null across all four stress methods (0.27–0.33).
The cross-currency basis is economically real — literally the Global-Funding desk's language — but
**not** a tradable carry edge on the only universe where it is observable here. **D3 adds no signal; the
honest null is the deliverable**, reinforcing the through-line that every embellishment, standard *and*
novel, fails to beat the simple book.

**Outputs:** `basis_carry_comparison.csv`, `basis_carry_spanning.csv`, `basis_track_correlation.csv`
(Appendix A).

**Phase-3 status after D3:** D1 and D3 both done (both null). The last open Phase-3 differentiator is
**D2** (FX vol risk premium); D4–D6 need a data add first. Two independent *novel* signals
(option-implied skew, cross-currency basis) now join the four *standard* embellishments in failing to
beat the simple vol-targeted EM-carry book — the §14.3 report's central, well-evidenced result.

**Next up — D2 can start on data already in the repo.** Verified 2026-07-14: `data/raw/` already holds full-history
**ATM implied vol at five tenors (1W/1M/3M/6M/1Y)** for every option name, so the implied-vs-realized VRP term
structure needs no new pull. The data *wants* for D2 (an investable FX vol-carry benchmark for external validation;
OHLC spot for range-based realized vol) plus the free 10Δ/multi-tenor wins and the D1/D3 rerun upgrades are catalogued
in [`DATA_SHOPPING_LIST.md`](DATA_SHOPPING_LIST.md).

---

### 17.3 Why D2 and D4–D6 are cut (decision 2026-08-03)

Recorded so the decision is on paper and reversible — the specs above are untouched.

| # | Direction | Disposition | Reason |
|---|---|---|---|
| **D2** | FX volatility risk premium | **Cut for August; keep for September / back pocket** | Three reasons, in order of weight. (1) *Opportunity cost*: the desk's headline ask is one combined engine (§19), and the only result that has beaten the 0.466 bar so far came from integration, not from a new signal (§4 finding 9). (2) *Evidence quality*: the two `DATA_SHOPPING_LIST.md` items that would make D2 defensible — an **investable FX vol-carry benchmark index** (§1.1) for external validation, and **OHLC spot** (§1.2) for a range-based realized-vol estimator — are unbought, so a D2 run today would rest on close-to-close realized vol with no benchmark to check it against: *weaker* evidence than D1 or D3 had. (3) *Prior*: two differentiators in a row came back null, and D2 shares their failure mode — an option-market premium that carry may already span. **Reversal trigger:** if 1.1 + 1.2 are purchased, D2 is the first thing to restart. |
| **D4** | FX value / multi-factor | Cut | Needs a REER/PPP proxy (BIS effective rates are free but unpulled). Also the least novel of the six — "add a value factor" is the standard next slide, not a differentiated finding. |
| **D5** | Positioning / crowding | Cut | Needs a CFTC IMM pull (free, weekly) — but coverage is G10-ish, and the premium in this sample lives in **EM** (§4 finding 1), so the data does not reach where the money is. |
| **D6** | Term structure of carry | **Not cut — CLOSED as a third null, 2026-08-03.** See below | The §17 table claimed D6 "needs multi-tenor forwards (only 1M pulled)". **That was factually wrong** (Appendix C #12): all 27 names carry 1M/3M/6M/12M forwards, and `fx_utils.TENOR_MONTHS` already supports all four. So D6 ran today, for free. |

**D6 — Term structure of carry ✅ null (2026-08-03).** Running the baseline book at each available
tenor, everything else held at the committed configuration:

| Tenor | Gross Sharpe | Net Sharpe (v1.1.0) | Turnover | Cost drag (v1.1.0) | ~~Net (v1.0.0)~~ | ~~drag (v1.0.0)~~ |
|---|---|---|---|---|---|---|
| **1M** (baseline) | **0.6284** | **0.4659** | 0.675 | 1.81%/yr | 0.4659 | 1.81%/yr |
| 3M | 0.4875 | 0.3501 | 0.526 | 1.55%/yr | ~~0.2891~~ | ~~2.24%/yr~~ |
| 6M | 0.5148 | 0.3697 | 0.450 | 1.64%/yr | ~~0.2376~~ | ~~3.14%/yr~~ |
| 12M | 0.5657 | 0.3995 | 0.426 | 1.87%/yr | ~~0.1346~~ | ~~4.84%/yr~~ |

**Verdict: the 1M point dominates**, on **gross** and on net. Holding longer-dated carry gives up
return without buying anything.

✅ **Caveat resolved 2026-08-03.** The net column was contaminated by guardrail §6.11 — drag *rose*
1.81% → 4.84% while turnover *fell* 0.675 → 0.426, which is backwards and was the signature of the
roll-leg indexing defect (Appendix C #14). **That defect is now fixed** (base v1.1.0), and the table
is re-priced above: drag is roughly flat across tenors (1.55–1.87%/yr) as it should be, and the
longer tenors are worth 0.10–0.27 more net Sharpe than the old model claimed. **The D6 null is
unchanged and is now stronger** — it no longer rests on reading only the gross column. Output:
`outputs/tenor_sweep.csv`, **which did not exist until W1** despite being cited here and in
Appendix A (Appendix C #18).

**What this buys:** roughly three of the four August weeks, redirected into §19. If Phase 4 finishes
early or the combined ladder produces nothing adoptable, D2 is the designated fallback.

> **Three novel signals, three nulls** (D1 skew, D3 basis, D6 term structure) on top of four standard
> embellishments that also failed (Stages 3–6). That accumulated negative evidence is not a
> disappointment to be buried — it is the most defensible thing this project has produced, and it is
> the centrepiece of the §14.3 report.
>
> **⚑ Amended 2026-08-04: D2 is no longer cut, and it is the first thing in this project that is not
> a null.** See §17.4. The through-line above survives but needs one word changed: every attempt to
> improve *the carry sort* has failed; the thing that works is a **different premium** measured on
> the same data.

### 17.4 D2 — FX Volatility Risk Premium ✅ (2026-08-04) — **the first non-null, heavily qualified**

Phase 4 finished early, which §19.6 named as the trigger to restart D2. Built in
`cesare/d2_vrp.py` on the ATM term structure already in `data/raw` (shopping-list §0 free win).

**1. The premium exists, and it is not marginal.** Selling 1M ATM vol and paying realised over the
following month earns a positive mean in **20 of 21 currencies** (CHF is −0.003, i.e. zero), pooled
**+0.67 vol points**, positive in **67.6%** of months, with **13 of 21** individually significant at
NW t > 1.96. Largest in EM — TRY +2.79, THB +1.89, INR +1.42, KRW +1.38, MXN +1.00 — and ~zero in
AUD and CHF. → `p3_d2_premium.csv`

**2. The books** (monthly, vol-targeted 10%, **gross of vol bid/ask** — see 4):

| Book | Ann ret | Ann vol | Sharpe | MaxDD | Skew |
|---|---|---|---|---|---|
| carry (monthly, for comparability) | 5.4% | 11.5% | 0.4708 | −25.2% | −0.49 |
| **short vol** (directional) | 18.4% | 14.4% | **1.2719** | −23.1% | **−2.13** |
| **VRP cross-section** (vega-neutral) | 23.4% | 13.9% | **1.6891** | −23.4% | +1.66 |
| carry + short vol (50/50) | 14.1% | 14.4% | 0.9840 | **−18.0%** | −0.24 |

**3. It is NOT carry in disguise — and the spanning runs the *opposite* way to D1 and D3.**
`short_vol ~ CARRY` α **+3.33%/yr, t 4.58**; `CARRY ~ short_vol` α −0.19%/yr, t −0.30. Correlation
0.40. **The vol premium spans carry; carry does not span it.** Every previous direction died on
exactly this test — this one passes it, with the largest t-statistic anywhere in the project.

**4. Three reasons this is reported as *qualified*, not as a win.**

- **Two-thirds of the cross-sectional Sharpe is a standing tilt, not timing.** Removing the
  per-currency mean with an expanding, lagged average takes `vrp_xs` from **1.689 → 0.547**, and the
  skew flips **+1.66 → −1.84** with the drawdown doubling to **−48.7%**. The standing shorts are
  TRY, MXN, THB, KRW, INR. The positive skew of the raw book is the tell: it is short vol in managed
  and low-realised-vol currencies whose tail *has not occurred inside 2007–2026*. This is the same
  discipline as guardrail §6.12 applied to a different strategy, and it changes the reading.
  → `p3_d2_static_vs_timing.csv`
- **It cannot be costed.** Option data is mids only. Rather than publish a zero-cost Sharpe, the
  module solves for the **breakeven round-trip vol spread**. ⚑ **Corrected 2026-08-04 (Appendix C
  #29): the figures first written here were one grid point too generous** — they quoted the first
  spread at which each book *fails*, not the widest at which it still passes. Read directly off
  `p3_d2_breakeven_cost.csv`'s own `beats_both_bars` column, the **widest spread still clearing both
  bars is 0.25 vol pts for `short_vol` and `carry+short_vol`, and 0.10 for `vrp_xs`** (was written
  as ~0.5 / ~0.5 / ~0.25). This materially strengthens the caveat rather than softening it:
  `d2_vrp.COST_GRID`'s own docstring notes interbank G10 1M ATM trades inside ~0.2 vol pts, so
  **the headline `vrp_xs` book dies *inside* G10 interbank** — and its largest positions are the EM
  standing shorts, where spreads are several times wider. `short_vol` survives a G10-realistic
  spread with little margin.
  → `p3_d2_breakeven_cost.csv`
- **The evidence is weaker than D1's or D3's by construction**, which was §17.3's second reason for
  cutting it and remains true: realised vol is close-to-close (OHLC unbought, §1.2), and there is no
  investable FX vol-carry index to validate against the way carry was validated against DBHVG10U
  (§1.1). **Those two purchases are now the highest-value data asks in the project.**

**Verdict — ADOPT for the report as a qualified positive, do not fold into `COMBINED`.** It clears
both bars with significance and survives the spanning test that killed everything else, so it is a
genuine result and the report's centrepiece alongside the nulls. It does **not** go into the
combined engine, because `COMBINED` is a costed, executable book and this one is not costable on
current data. Folding an uncostable strategy into a costed preset would undo the honesty the rest of
Phase 4 was built on.

**Outputs:** `p3_d2_premium.csv`, `p3_d2_books.csv`, `p3_d2_spanning.csv`, `p3_d2_correlation.csv`,
`p3_d2_static_vs_timing.csv`, `p3_d2_avg_weights.csv`, `p3_d2_breakeven_cost.csv`.

## 18. Team Base Strategy — `strategy/` ✅ (2026-07-28)

**Why.** Team decision: every teammate's extension should be tested on *one* baseline so the
extensions are comparable to each other. Until now they were not. An audit of the repo on
2026-07-28 found five different baseline carry strategies in five folders, differing in
frequency, quoting convention, universe, cost model, data source — and, in one case, in whether
the strategy collects carry at all:

| Person | Their baseline | Divergence from this project's construction |
|---|---|---|
| Vidhi | own 26-name daily book, flat 5bps cost | **Portfolio returns are `log_return(spot)` only — the carry accrual is never added**, so the book sorts on carry and harvests none of it. Static track: Sharpe −0.71, MaxDD −72%. Her regime gate's "improvement" is loss-reduction on a book that should not be losing. Also: full-sample feature screening before the expanding-window fit (leak), and the gate multiplies *returns*, so de-risking is costless. |
| Dafu | `src/fxcarry/` + private `dafu/data/raw/` copies | Monthly, FCU-per-USD, `rx = f_t − s_{t+1}`, 1984-start, ±1/N sign weighting, no costs, no vol target. Internally coherent and correct for the BER replication it was built for — but not comparable to anything else here, and on different data. |
| Arjun | rebuilds this project's book inline, three copies of the same `build_book()` | Correct — reconciles to 0.466 within 5e-3 — but duplicated per notebook. His unmerged `arjun_utils.py` docstring already names itself "the seam where my work can diverge from the team's headline strategy". |
| Theo | own G10/EM panels and processed parquets | Owns the FX-options / skew / vol-filter extension (`theo/06_options_skew_and_vol_filters.ipynb`). |
| Cesare | this project's engine | The validated construction: external benchmarks, real bid/ask costs, no-lookahead guards, reconciled outputs. |

**What was built.** `strategy/` at the repo root — a thin, config-driven wrapper over this
project's engine. It adds no financial maths of its own; it fixes the *order of operations* and
exposes every knob and two extension hooks.

- **`strategy/config.py`** — `StrategyConfig`, a frozen dataclass whose defaults ARE the published
  baseline. Fields cover universe/exclusions/tenor, signal (carry, momentum, or any user panel or
  callable), sort and within-leg weighting (`n_buckets`, `weighting`, `max_leg_share`,
  `min_per_leg`, `vol_window`, `cov_window`, `rebal`), sizing (`vol_target`, `lev_cap`,
  `vol_floor`), costs (`costs`, `cost_multiple`), window, and the hooks below. Presets
  `ALL_BASELINE` / `G10_BASELINE` / `EM_BASELINE`; `.with_()` derives variants.
- **`strategy/core.py`** — `run(config) -> StrategyResult`. Fixed pipeline: panels (cached) →
  signal → `carry_portfolio` → `vol_target_weights` → **overlays** → `portfolio_returns` /
  `roundtrip_cost`. `StrategyResult` carries gross/cost/net, unit and traded weight panels, the
  per-currency `contrib`, the `spot_component`/`carry_component` decomposition, turnover and cost
  drag, plus `summary()`, `monthly()`, `reslice()`, and `returns_from_weights` /
  `cost_from_weights` for post-hoc re-pricing without a rebuild.
- **`strategy/fx_utils.py`** — the engine, moved from `cesare/` unchanged. `cesare/fx_utils.py` is
  now a re-export shim, so all eight cesare notebooks and Arjun's three notebooks keep working
  with zero edits.
- **`strategy/README.md`** — the contract, written for teammates *and their AI agents*: setup,
  what the base enforces for you, full `StrategyConfig`/`StrategyResult` reference tables, the four
  extension patterns, a ten-point rules section for agents, a per-teammate porting guide, and the
  reconciliation targets.
- **`strategy/examples/`** — five runnable scripts (baseline, regime exposure gate, per-currency
  option overlay, robustness sweep, universe/crisis studies).
- **`strategy/tests/test_reconciliation.py`** — 12 acceptance tests, all passing.
- **`strategy/episodes.py`** *(added 2026-08-03, v1.1.0)* — the frozen `ERAS` / `STRESS` windows and
  `report_windows` / `compare_windows` / `leg_decomposition`, built on `reslice()` and
  `summary_stats` with no new statistics. Plus **`strategy/tests/test_episodes.py`**, 11 tests, in
  its own file so the documented "12/12" string stays true.

**v1.1.0 changelog (2026-08-03).** Two defects fixed, both **exact no-ops at the committed
baseline** — the whole daily cost series matches the pre-fix series to `0.0e+00`, so no published
number moves:
1. `StrategyResult.summary(min_obs=)` passthrough + a `__repr__` guard, so windows shorter than 120
   trading days are reportable at all (F1, Appendix C #13/#17).
2. `roundtrip_cost(tenor=)` now bills the roll leg on the **forward-tenor** grid via the new
   `fx_utils.roll_schedule`, not the rebalance grid (F2, Appendix C #14). Retires guardrail §6.11.

**The two hooks (the design decision that matters).** Overlays modify **weights**, not returns,
and are applied *before* the cost model:

- `exposure: pd.Series` — total-risk gate (regimes, macro, ML timing). Sampled on the rebalance
  grid and lagged one period by the base; pre-history is fully invested (the `exposure_scalar`
  convention).
- `weight_overlay: f(weights, ctx) -> weights` — per-currency changes (option hedges, filters,
  manual edits), with `ctx` carrying panels, unit weights and the signal.

Because both move weights, a de-risking rule pays the transaction costs of the trades it triggers
and its turnover is reported. An overlay applied to a return series is free — which flatters every
risk-management rule ever tested, and is precisely the defect found in the surveyed baselines.

**Acceptance criteria — met.** `run()` reproduces the committed headline exactly: ALL gross
**0.6284** / net **0.4659**, G10 **0.1669** / **0.1191** (vs `outputs/strategy_summary_stats.csv`,
|Δ| < 5e-4 including ann_return, ann_vol, MaxDD and skew); turnover 0.675, cost drag 1.81%/yr.
Internal identities hold to **0.00e+00**: `contrib.sum(axis=1) == gross`,
`xret == spot_component + carry_component`, `net == gross − cost`. Both hooks are exact no-ops at
neutral settings (`exposure=1.0`, identity overlay), so an extension measures its own effect.
Post-hoc `cost_from_weights` / `returns_from_weights` match a full rebuild to 0.00e+00. All nine
swept knobs demonstrably move the book.

**External cross-check.** The sweep example independently reproduces Arjun's published audit from
the shared base: jackknife most-damaging names JPY (−0.086) / CNH (−0.076) / MXN (−0.073), ZAR a
drag (+0.099 to drop), the edge dying between 2× and 3× spreads, and the 60d × ME cell sitting on a
plateau rather than a spike. Two independent implementations agreeing is the strongest evidence the
base is right.

**Consequences for the team.** Vidhi's headline result must be re-derived on the base — the sign of
her static book will very likely flip, and her gate will now pay for itself. Arjun's three inline
`build_book()` copies collapse into `run(**override)`. Theo's option work becomes a
`weight_overlay` (with the honest caveat that `data/raw` holds option **mids only**, so a
premium-paying hedge cannot be costed until the bid/ask in `DATA_SHOPPING_LIST.md` §2.2 is bought —
a position-trimming proxy is the defensible version meanwhile). Dafu's `src/fxcarry/` stays as-is
for the BER replication, which **cannot** be reproduced on the team base at all: BER starts in 1984
and the shared `data/raw/` starts in 2007.

**Not done / deliberately out of scope for v1.** Monthly frequency and the FCU-per-USD convention
(so `src/fxcarry/` is not absorbed); an options *pricing* layer; packaging (`pyproject.toml`) and
a repo-wide `requirements.txt` — both belong to the §14.5 repo-wide collation.

### 18.1 Adoption tracker ⬜ — the gate for Phase 4 *(added 2026-08-03)*

The base exists; **adoption does not follow automatically**, and this is now the binding constraint
on §19. Nothing can be folded into a combined engine until the components are built on the same
book. Verified 2026-08-03 by grepping `from strategy import` across the repo:

| Owner | Status | What is still private | Port |
|---|---|---|---|
| Dafu | ✅ **ported** | — (`src/fxcarry/` stays for the 1984 BER replication, which the base cannot express) | `dafu/regime_lab.py` + `regime_switching_carry.ipynb` already `from strategy import fx_utils as fx, run` |
| Arjun | ⬜ | `import fx_utils as fx` plus **three inline `build_book()` copies** across his notebooks | Collapse to `run(**overrides)`; `arjun_utils.py` already delegates to the engine, so this is small |
| Theo | ⬜ | Own carry panels built directly off `data/raw/` parquet | Replace the panel build with `load_panels()`; his option filter becomes `filter_signal` / `weight_overlay` |
| Vidhi | ⬜ | `vidhi/src/*` — **plus two known defects the base fixes**: returns use `log_return(spot)` only (carry never added → Sharpe −0.71, −72% DD) and the feature screen is run on the full sample (leak) | Her overlay already multiplies a return series by a probability scalar — that is exactly the `exposure` hook |
| Oleg | ⬜ | `oleg/ v1/carry_utils.py`, a private mini-copy of the engine; `oleg/v2/utils.py` is 0 bytes | Delete the copy, `from strategy import run` |

Per-teammate porting recipes are already written in `strategy/README.md` §"Porting existing work
onto the base" — no new documentation is needed, only the deadline.

**Gate: the 2026-08-12 BofA meeting.** Definition of done for each row: their headline result
re-derived through `run()`, reported gross **and** net, with the §19.2 episode table attached, and
`python strategy/tests/test_reconciliation.py` printing 12/12. Slippage triggers the
re-price-don't-rebuild fallback in §15.

---

## 19. Phase 4 — Integration & Delivery (Aug 2026) 🔶 ← **current focus**

**Why.** Phase 3 asked whether a differentiated *signal* could beat the simple book. Three times the
answer was no (§17: D1 skew, D3 basis, D6 term structure). Meanwhile the desk asked for something
different and, on the evidence, more promising: **stop evaluating whole-sample, forecast the tail and
bake it in, and fold six workstreams into one engine.** The one result that has beaten the 0.466 bar
so far — Arjun's duration hedge at 0.510 real-time — came from integration, not from a new signal
(§4 finding 9). And at least one already-rejected rule turns out to *win* once the objective is the
one the desk actually stated (§19.3).

**The bar (unchanged and falsifiable).** Any component must beat, net of costs with Newey–West
significance, *both* the simple vol-targeted book (**ALL net Sharpe 0.466**) and the
per-currency-RR-hedged book (**0.457**) — **or** clear the desk's explicit alternative: a material
tail improvement (MaxDD / CVaR₉₉) at ≤ 0.02 Sharpe cost, demonstrated **per episode**, not merely
whole-sample. Anything else is reported as a null. Guardrails §6 apply throughout, now including
§6.8 (per-window) and §6.9 (incremental honesty).

**Four work items.** P4-A stress-window standard → P4-B tail forecast → P4-C combined engine →
P4-D delivery. **P4-A is the critical path** — nothing can be judged before it exists — and inside
P4-A the first move is a one-kwarg bug fix, because today the per-window table comes back *empty*
for every window shorter than 120 days, including all three the desk named (§19.2).

### 19.1 Desk mandate ledger — BofA & internal meetings, Jul 8 → Jul 29 2026

Every action item from the running minutes, with an owner and a status, so nothing is silently
dropped and nothing is paid for twice. This table is also the source for the "what we did / what is
next" beats of any BofA deck (Jul 17 ask).

*Status: ✅ done · 🔶 partial · ⬜ open · ✂️ cut (with reason) · ⚠️ needs a decision.*

**Evaluation & risk framing**

| Ask (date) | Owner | Status | Evidence / verdict |
|---|---|---|---|
| Max-drawdown & stress tests as a core lens, not an afterthought (Jul 8) | Team | ✅ | Stage 6 (§12), `stage6_conditional_by_regime.csv`; MaxDD/CVaR₉₉ in every stats table since |
| Isolate specific drawdowns; diagnose each rather than lament the whole sample (Jul 15) | Team | ✅ **done 2026-08-03** | `strategy/episodes.py` freezes 9 `ERAS` + 8 `STRESS` windows; `outputs/p4_episode_table_baseline.csv` + `p4_stress_table_baseline.csv`. The one-off `overview.html` snapshot is superseded |
| **Report per stress window, not whole-sample — standing requirement** (Jul 29) | Team | ✅ **mechanised 2026-08-03** | Guardrail §6.8 + `report_windows`, which *enforces* the short-window metric rule in code; made mandatory for teammates as `strategy/README.md` **rule 11** |
| Extrapolate stress-period lessons into full-sample improvements (Jul 15) | Team | ✅ **answered 2026-08-03 — negatively** | The tail forecast operationalised it (§19.3) and it does not work. The stress-period lesson that *does* generalise is not a timing signal: it is that the losses are spot events on the long leg, never carry events (`p4_leg_decomposition.csv`) |
| **Forecast tail events and bake the signal into the strategy** (Jul 29) | Team | ✅ **done 2026-08-03 (W3) — NULL** | Built and falsified: mean OOS AUC **0.4685** across 13 purged folds, fails all three pre-registered bars. Sixteen features on ~228 monthly observations lose to one VIX threshold. `p4_tail_forecast_eval.csv`, §19.3. Not iterated — that was fixed in advance |
| Single-currency + options deep dive through one large drawdown (Jul 15) | Team | 🔶 | `crash_regressions.csv` covers crash betas cross-sectionally; the per-currency narrative is not written. Cheap once P4-A exists (`result.contrib` resliced to one episode) → §14.3 report chapter |
| December year-end liquidity / USD demand compressing JPY implied yield (Jul 8) | Team | ⬜ low | Not a strategy change — a month-of-year diagnostic on the carry panel. Park as a report sidebar; the data is already in `data/raw` |
| Explain end-to-end where the risk and the gains come from (Jul 15) | All | ✅ | §4 findings 1–9 + the reconciled per-leg decomposition below |
| Decompose the rate differential **month-by-month / quarter-by-quarter, split short leg vs long leg** (Jul 15) | Team | ✅ **done 2026-08-03** | `outputs/p4_leg_decomposition.csv` (ME/QE/YE + annualized), reconciling to `gross` at **3.88e-17**. Carry accrues **+14.31%/yr on the long leg**, spot gives back **−10.43%/yr on the same leg**, and **carry on the long leg is positive in all 20 years including all 7 losing years** — every losing year is a spot event on the long leg, never a carry event |

**Data quality & construction**

| Ask (date) | Owner | Status | Evidence / verdict |
|---|---|---|---|
| Verify implied yields against cross-currency basis; choose rates- vs forward-based construction (Jul 8) | Team | ✅ | §5.4 CIP validation + `implied_carry_validation.csv`. Verdict recorded in Appendix C #1: **forward-implied carry** ln(S/F), so basis and convertibility distortions are already embedded in the quoted price — the desk's own preferred answer |
| Forward as unbiased predictor of spot; is the spot–forward premium **stable** (Jul 15) | Team | 🔶 | `outputs/uip_fama.csv` already holds the Fama regression: pooled **b = 0.733, t = 4.48, n = 6,713** — i.e. the forward is a *biased* predictor and the bias is the carry premium (that is the whole trade). Per-name, only IDR (−1.63, t −2.45) and TRY (0.84, t 2.48) are significant. **No new work: reframe as a stability statement** in §14.3 (rolling b by episode is a one-liner once P4-A exists) |
| Uniform base setup so every variant is compared like-for-like — *blocking* (Jul 22) | Team | ✅ | `strategy/` v1.0.0, §18. Delivered 2026-07-28 |
| Migrate every workstream onto the base and re-run (Jul 29) | All | 🔶 **1 of 5 ported — but all 4 re-priced** | §18.1. Adoption is still 1 of 5 and the Aug 12 deadline note is **drafted, not sent** (`cesare/notes/porting_deadline_aug12.md`). The fallback ran instead: every component is now measured on the base (§19.4), labelled *re-priced, not rebuilt*. **Verified along the way: Arjun's book IS the base, bit-identical** — Appendix C #22 |
| Re-run the regime / adaptive overlay on the universal baseline (Jul 29) | Vidhi | ✅ **done for her 2026-08-03 (W3) — and the expectation was wrong** | Her *gate* recovered from committed outputs and re-priced on the base: net **0.0964** vs baseline 0.4659, the most destructive component tested. Her static book's sign does flip positive (it is just the base), but **the gate does not survive contact with a book that actually earns carry**. Its correlation with VIX is ≈0 at every lead/lag, and it fails under both lag conventions. §19.4 |

**Trade mechanics**

| Ask (date) | Owner | Status | Evidence / verdict |
|---|---|---|---|
| Test alternative forward **tenors** (Jul 22, Jul 29) | Cesare | ✅ **done 2026-08-03 — null** | Ran it: 1M dominates on gross **and** net (0.6284/0.4659 vs 12M's 0.5657/0.1346). Full table and the cost-model caveat in §17.3. The plan's claim that this needed a data pull was wrong (Appendix C #12) |
| Test alternative **rebalancing frequencies / dates** (Jul 22, Jul 29) | **Arjun** | 🔶 **one blocker cleared 2026-08-03** | `arjun/outputs/robustness_window_rebal_heatmap.csv` already sweeps vol_window {20,40,60,90,120} × rebal {W,2W,ME,QE}: best cell **0.5007** at (40, ME), month-end sits on a **plateau**, weekly roughly halves the Sharpe on costs. Missing: daily rebalance. **Blocker 1 (§6.11 roll-leg cost) is FIXED in base v1.1.0** — the frequency axis is now reportable **net**, and note his committed QE numbers move (that cell was *under*charged: drag 0.89% → 1.33%/yr, net 0.368 → 0.330), so the heatmap needs re-running on v1.1.0. **Blocker 2 (§6.10 leaking rebalance-*date* aliases) still stands.** Delegated, with both caveats handed over |
| Auto-funding crosses, e.g. JPY/TRY funded in the paying leg (Jul 22) | Team | ✂️ **answered, not implementable** | Worth saying out loud rather than dropping: a JPY/TRY cross is mechanically ≈ long TRY/USD + short JPY/USD, **which the book already holds** — the sort routinely pairs TRY on the long leg with JPY on the short. The only genuine differences are (a) saving one USD leg's bid/ask and (b) the cross's own basis. Neither is priceable here: `data/raw` has spot/forward bid/ask **vs USD only**, no cross-pair quotes. Record as a data request, not a backtest |

**Options, skew & hedging**

| Ask (date) | Owner | Status | Evidence / verdict |
|---|---|---|---|
| Hedging overlays (options / derivatives) to cut tail risk while preserving carry (Jul 8) | Team | ✅ | Stage 3 (§9): no timing rule has significant alpha (all \|t\| < 1.7); **per-currency RR conditioning** adopted as the preferred tail hedge (net 0.457, skew −0.65→−0.60, CVaR₉₉ 2.9→2.7%) |
| Why did the option overlay lose more than plain carry in 2009 (Jul 22) | Dafu | ⬜ | Answer is likely structural — selling options leaves the book short vol, so the option leg and the carry leg lose together in a crash. P4-A gives him the episode table to show it |
| Buy options as insurance vs sell; run the inverse of the existing trades (Jul 22) | Dafu | ⬜ ⚠️ | **Flag to the desk:** `data/raw` option data is usable as **mids only**, so a premium-paying hedge cannot be honestly costed. A position-trimming proxy is the defensible version until `DATA_SHOPPING_LIST.md` §2.2 (option bid/ask) is bought. Do not report an insurance overlay's Sharpe as if the premium were free |
| **Bad-skew exclusion / sizing filter** (Jul 29) | Theo | 🔶 **spec drafted; collision now quantified** | Overlaps completed work: Stage 3 per-currency RR conditioning (net **0.457**, adopted) and Phase-3 **D1** (skew as a cross-sectional signal = **null**; spanning shows carry subsumes SRP — CARRY~SRP α **+3.77%/yr, t +2.19**, while SRP~CARRY α −0.48%/yr, t −0.38). **Spec his test as marginal over per-currency RR, not versus raw baseline** — otherwise the team brings the desk two contradictory skew answers in the same meeting. Spec drafted W3 (`cesare/notes/theo_skew_collision_spec.md`), not yet sent. **⚑ The collision is total, and now verified: his committed `bad_skew25_1m` is BIT-IDENTICAL to `fx_utils.vol_surface_panel("RR","1M")` — max diff 0.0 across all 21 shared currencies (Appendix C #23).** His rule differs from the adopted one only in conditioning axis (cross-sectional vs per-currency trailing) and action (exclude vs halve). Re-priced in §19.4, where it earns a slot — with the caveat that most of its tail gain is de-risking (§6.12) |
| Quantify how carry-signal predictive power degrades as bad skew rises (Jul 29) | Theo | ⬜ | Genuinely additive and *not* covered by D1 — D1 tested skew as a signal, not as a moderator of carry's predictive power. Keep |
| DXY hedge — regressions + written negative result (Jul 29) | Arjun | ✅ | Dollar exposure nets out within the book; both spot-DXY and DXY-futures hedges are documented nulls |
| Duration hedge (bonds / yields) instead of DXY (Jul 29) | Arjun | ✅ **the one positive result** | 0.467 → **0.510** expanding/real-time (0.527 in-sample), MaxDD −33.2%→−32.2%, skew −0.648→−0.597. Folds in at §19.4 — note it needs an interface the base does not yet have |
| Compare regime-switching vs the insurance-style option overlay on the common baseline (Jul 22) | Team | 🔶 | `dafu/outputs/headline.csv` does this on the base; best real-time variant is still the **VIX rule (incumbent)**, baseline 0.46592. Rolls into the P4-C ladder |

**Macro & regimes**

| Ask (date) | Owner | Status | Evidence / verdict |
|---|---|---|---|
| Oil shock (Feb–May 2026) and semiconductor shock (Apr 2026 →) as live regime tests (Jul 22) | Cesare | ✅ **answered 2026-08-03, frozen and committed** | Oil **+10.07% net, MaxDD −1.78%** (85d); semis **+11.68% net, MaxDD −1.78%** (65d) — in `outputs/p4_stress_table_baseline.csv`, reproducible from `strategy.episodes.STRESS`. **Neither 2026 shock was FX-carry stress** — they hit equities and supply chains, not this book. Previously invisible inside `overview.html`'s "Recent 2023-26" bucket, *and* unreportable at all until the F1 fix. The per-name attribution is a W3 half-day. **Caveat:** the *import/export exposure* framing needs trade-balance data that is not pulled — the return study runs now, the causal framing is Oleg's track |
| EM central-bank inflation-fighting cycles and their timeframes vs carry (Jul 22) | Oleg | ⬜ | Tracked, not mine. EM policy rates are in `data/raw/em_interest_rates` |
| Election events / surprise volatility on spot (Jul 22) | Oleg | ⬜ | Tracked. Needs an election calendar — not in repo |
| Trade balances and other macro proxies (Jul 22) | Oleg | ⬜ | Tracked. Not in repo; also the input the oil-shock framing above wants |
| NFP / CPI / growth as currency-ranking proxies (Jul 29) | Oleg | ⬜ | Tracked. Partial coverage in `data/raw/macro_market_proxies` (CPI YoY for US/DE/UK/JP/CA/AU) |
| Zoom into historical stress episodes (e.g. 2008) as macro event studies (Jul 29) | Oleg | ⬜ | Should consume the same frozen windows (§19.2) so his episodes and mine are the same episodes |

**Team & process**

| Ask (date) | Owner | Status | Note |
|---|---|---|---|
| Fold all workstream takeaways into one combined engine (Jul 22, ongoing) | Team | ✅ **done 2026-08-03 (W2–W3)** | `run("COMBINED")` — baseline + Arjun's duration leg + Theo's bad-skew exclusion: net **0.4891**, MaxDD **−19.07%**, CVaR₉₉ **0.0200**. All four components **re-priced from committed outputs**, not waiting on ports. Both ladders + survivor re-ladder in `p4_combined_ladder.csv`. §19.4 |
| Group slide deck; results-ready, four beats, visible collaboration (Jul 15, Jul 17) | Team | ✅ recurring | Precedent exists: `cesare/presentations/FX_Carry_Update_Presentation.html`, `cesare/presentations/overview.html`. This ledger + §19.5 supply the content each week |
| Per-member methodology justification — the "why", not the output (Jul 17) | All | ⬜ | Collected in W4 as §14.3 report input |
| **Capture Arjun's idea from Jul 22** | **Cesare** | ⬜ **overdue — carried a third time** | Still unrecorded. Ask at the Aug 5 meeting and write it into this ledger. Flagged here as the one action item this document has failed to close three cycles running |
| Distinct strategy ownership, no overlap (Jul 10) | All | ⚠️ | One live breach: the Theo/Cesare skew collision above. Resolve W1 |

### 19.2 P4-A — The stress-window standard ✅ **done 2026-08-03 (W1)**

**What exists and why it isn't enough.** Two episode sets are already in the repo and they disagree:
`dafu/regime_lab.py` `EPISODES` (9 contiguous windows) and the six windows hard-coded in
`cesare/presentations/overview.html` / `strategy/examples/05_subset_and_crisis.py`. Neither is canonical, neither
contains the 2026 shocks the desk named, and neither is required of anyone.

> **Blocker found and verified 2026-08-03 — ✅ FIXED the same day (Appendix C #13).**
> `StrategyResult.summary()` returned an **empty (0, 0) DataFrame** for any window shorter than 120
> trading days: `fx_utils.summary_stats(..., min_obs=120)` silently `continue`s and `summary()` had
> no passthrough. Confirmed by execution — oil 2026 (85 days), semis 2026 (65 days), the COVID
> crash (64 days) **and the 2013 taper tantrum (109 days)** all returned nothing. **Four** of the
> eight `STRESS` windows, not the three originally recorded here: the taper tantrum is the
> second-worst window in the sample, and the window this document uses to argue that aggregation
> hides losses was itself hidden by the defect.
> Fixed by adding `min_obs=120` as a passthrough kwarg on `StrategyResult.summary()`; the default is
> unchanged, so the 12 acceptance tests could not break. **A second surface of the same defect was
> found in the process** and is fixed too: `StrategyResult.__repr__` indexed `s.iloc[0]`/`s.iloc[1]`
> unconditionally, so merely *echoing* a resliced short window in a notebook raised `IndexError`
> rather than returning an empty frame (Appendix C #17). Regression tests:
> `test_episodes.py::test_short_windows_are_populated` and `::test_short_window_repr`.

**Build `strategy/episodes.py`** — small, additive, importing only `pandas` and the existing
`fx_utils.summary_stats`. Beyond the one kwarg above it touches nothing `core.py` does.

Two frozen dicts, and the distinction between them is the point:

- **`ERAS`** — a *contiguous partition* of 2007-05 → 2026-06. Copy **verbatim** from
  `dafu/regime_lab.py:36` (pre-crisis 2007-08 · GFC 2008-09 · recovery 2009-11 · euro crisis 2011-12 ·
  taper+EM 2013-16 · calm 2017-19 · covid 2020 · tightening 2021-23 · recent 2024-26) — verbatim so
  Dafu's committed `episodes_sharpe.csv` stays valid and his port is a one-line import change.
  Because it partitions the sample, **per-era shares of P&L sum to 100%** — that is what makes "this
  era produced X% of the book's return" an honest statement rather than a cherry-pick, and it is the
  answer to "you picked your windows".
- **`STRESS`** — *tight, tail-focused event windows*, allowed to overlap and to sit inside eras.
  Its job is the different question: **did the book preserve capital.** All figures below were run
  on `run()` today and are the acceptance targets for the implementation:

| Key | Window | n | Cum net | MaxDD | Why |
|---|---|---|---|---|---|
| `gfc_2008` | 2008-09-01 → 2009-06-30 | 217 | −5.9% | −17.8% | Lehman |
| `euro_2011` | 2011-07-01 → 2012-12-31 | **392** | −5.1% | −19.0% | EZ sovereign |
| `taper_2013` | 2013-05-01 → 2013-09-30 | 109 | **−12.9%** | **−19.1%** | see below |
| `china_em_2015` | 2015-06-01 → 2016-02-29 | 196 | −5.2% | −9.9% | CNY devaluation |
| `covid_2020` | 2020-02-01 → 2020-04-30 | 64 | **−19.6%** | **−24.0%** | worst window in the sample |
| `rates_2022` | 2022-01-01 → 2022-10-31 | 216 | **+25.5%** | −6.6% | **control** — carry's *best* crisis |
| `oil_2026` | 2026-02-01 → 2026-05-31 | 85 | **+10.1%** | −1.8% | desk-nominated, Jul 22 |
| `semis_2026` | 2026-04-01 → 2026-06-30 | 65 | **+11.7%** | −1.8% | desk-nominated, Jul 22 |

✅ **Reproduced exactly by the implementation** (`test_episodes.py::test_stress_table_matches_the_plan`
asserts all eight to 1e-3) → `outputs/p4_stress_table_baseline.csv`, gross **and** net.
One correction: `euro_2011` is **392** trading days, not 399 — the original figure was a
transcription error and is fixed above.

Two findings fall straight out of the table, before any new modelling:

- **The 2026 shocks were not FX-carry stress.** Both windows are *strongly positive* with a −1.8%
  drawdown. That is a direct, honest answer to a direct desk ask (Jul 22) and it costs half a day —
  the oil and semiconductor shocks hit equities and supply chains, not the carry book.
- **The taper tantrum is the second-worst window in the sample and is invisible in both existing
  episode lists** — buried inside dafu's "taper + EM 2013-16" bucket, which shows a *positive* 0.29,
  and absent from `overview.html` entirely. This is precisely the aggregation failure the desk was
  complaining about on Jul 29, found in our own tooling.

Both dicts are **frozen**: adding a window later is allowed, silently changing one is not, because
every cross-workstream comparison depends on them being the same windows for everybody. A test
asserts the exact keys and dates — that lock is what stops anyone re-picking a window after seeing a
result.

Helpers — both built on existing code (`StrategyResult.reslice()`, `strategy/core.py:260`, and
`fx_utils.summary_stats`); no new statistics are implemented:

**The per-leg accrual (Jul 15 ask) lands here too**, because it is the same machinery.
✅ **Done and reconciled 2026-08-03** → `outputs/p4_leg_decomposition.csv` (ME + QE + YE + a
full-sample annualized row). Annualized contribution over the full sample, **reconciling to `gross`
at 3.88e-17**:

| leg | annualized contribution |
|---|---|
| carry, long leg | **+14.31%** |
| carry, short leg | +2.47% |
| spot, long leg | **−10.43%** |
| spot, short leg | +0.67% |
| **total = gross** | **+7.03%** |

So carry accrual is roughly **2.4× the realized P&L, and spot gives back over half of it —
essentially all of that on the long leg.** By year: **carry on the long leg is positive in all 20
years, including all 7 losing years** — i.e. *every losing year is a spot event on the long leg,
never a carry event.* Verified on the reconciled split, not the provisional one. That is the
cleanest one-line answer to the desk's "where does the risk sit and where do the gains come from"
(Jul 15), and it reframes the whole book: the trade is not "earn carry", it is "earn carry and
survive spot".

⚑ *(Historical — the provisional figures, now superseded.)* The first pass came from a quick
weight × component reconstruction summing to 7.32% against the book's 7.03%. The reconciled numbers
above differ from it by up to 0.23pp (`spot_long` −10.43% vs the guessed −10.2%). **The cause of the
gap is worth recording, because it is a trap anyone repeating this work will hit:** a currency can
have a spot return on a day its carry is missing, and on such a day `xret` is NaN so
`portfolio_returns` drops the name from `gross` entirely — while an unmasked spot leg keeps counting
it. The components must be masked to where `xret` itself is present. Un-masked, the daily residual
reaches 8e-3. The qualitative conclusion survived; the numbers moved.

```python
report_windows(result, windows=ERAS, which="net", min_obs=20) -> pd.DataFrame
    # one row per window: window, start, end, n_days, cum_return, ann_return,
    # ann_vol, sharpe, max_drawdown, worst_day, hit_rate, cost_drag
    # sharpe and ann_* are NaN when n_days < 120, per guardrail §6.8 -- so that
    # nobody quotes an annualized Sharpe off 64 days of COVID.
    # Internals: result.reslice(a, z) + fx_utils.summary_stats. No new statistics.

compare_windows(results: dict[str, StrategyResult], windows=ERAS,
                metric="max_drawdown") -> pd.DataFrame
    # windows x variants for one metric -- the table that goes straight in the deck

leg_decomposition(result, freq="ME") -> pd.DataFrame
    # long-leg vs short-leg carry and spot contribution per period
    # -- the Jul 15 ask; `result.contrib` split by weight sign, resampled
```

**Making it mandatory, cheaply.** Append **rule 11** to the existing ten-point *"Rules for AI agents
working in this repo"* list (`strategy/README.md:225`): *every result table carries a `window`
column; report `report_windows(res)` before any whole-sample number.* Teammates' agents already read
that file, which makes it the cheapest enforcement surface in the repo. Nothing else in the contract
changes.

**Tests** ✅ — `strategy/tests/test_episodes.py`, **11/11 green**. A *separate file* deliberately:
`test_reconciliation.py` collects `test_*` from its own `globals()`, so adding cases there would
turn the documented "12/12 passed" into "13/13" and invalidate the string quoted in the README, in
agent rule 3 and in `overview.html`. The suite covers `test_windows_are_frozen` (exact keys and
dates, duplicated in the test file so it can detect an edit to the module), `ERAS` tiling with no
gap or overlap, `ERAS` P&L shares summing to 1.0, resliced stats reconciling with a direct
`summary_stats`, the §19.2 `STRESS` table reproducing to 1e-3, the per-leg split at < 1e-12, the
**F1** and **F1b** regressions, and the **F2** no-op guard (baseline drag to 1e-9 *and* roll mask ==
rebalance mask at 1M × ME).

**Do not retrofit the closed stages.** The standard applies **prospectively**. Stages 1–6 and D1/D3
get a per-window row for the baseline and their preferred variant only, computed in one pass over
the already-committed `cesare/outputs/strategy_returns_daily.csv` — about an hour, not a re-run of
the back catalogue. Re-running six closed stages × seven variants × fourteen windows would consume
the runway and produce nothing new.

**Outputs:** ✅ `outputs/p4_episode_table_baseline.csv` (18 rows), `outputs/p4_stress_table_baseline.csv`
(16 rows), `outputs/p4_leg_decomposition.csv` (328 rows) — all built by `cesare/final_evaluation.py`,
displayed by `cesare/final_evaluation.ipynb`, every row stamped with `config.describe()` plus the
evaluation window (`describe()` omits `start`/`end`, so the window is added explicitly).

**Acceptance — all met (2026-08-03):** **12/12 + 11/11** green; baseline gross **0.6284** / net
**0.4659**, G10 **0.1669** / **0.1191**, turnover **0.675470**, cost drag **0.018146611** (unchanged
to 0.0e+00); `report_windows(run())` returns fully populated rows for every sub-120-day window;
the numbers reproduce the `STRESS` table above; the per-leg split reconciles at **3.88e-17**.

### 19.3 P4-B — Tail-event forecast signal ⬜ *(the desk's central ask)*

**Target the loss, not the return.** The desk was explicit: minimizing large losses is worth more
than adding incremental gains, because one crash breaks the compounding path. So the forecast target
is a **tail indicator**, not next month's return.

> **First, a reframing — and it may be the single most valuable line in this update.**
> Under a Sharpe objective this project has already rejected tail protection four times. Under the
> desk's *stated* objective it has not. Take the VIX percentile gate, on the base, from
> `dafu/outputs/headline.csv`:
>
> | | Net Sharpe | MaxDD | Calmar |
> |---|---|---|---|
> | baseline | 0.46592 | −29.32% | 0.1601 |
> | VIX percentile gate | 0.46527 | **−24.50%** | **0.1815** |
>
> It costs **0.00065 of Sharpe** and buys **4.8 points of maximum drawdown** and **+0.021 of Calmar**.
> Stage 3 wrote that up as "reject" because the verdict column was Sharpe. On the objective the desk
> actually stated on Jul 29, it is an **accept** — and it is available today, with no new modelling.
> *(Careful: Stage 3's own VIX threshold rule scored 0.441 on the combined book — that is a
> different rule from this percentile gate. Do not merge the two numbers.)*
>
> ✅ **DONE 2026-08-03 (W1)** → `outputs/p4_reverdict_tail_objective.csv`, 13 rules, no re-runs.
> **Decision rule, fixed before computing** (it is §19's own second bar, not a new one): accept iff
> the net Sharpe cost is ≤ **0.02** *and* the rule buys ≥ **1.0pp** of MaxDD **or** ≥ **5%** relative
> CVaR₉₉. Both the old Sharpe verdict and the new tail verdict are carried side by side.
>
> | Book | Rule | ΔSharpe | ΔMaxDD | ΔCVaR₉₉ | Tail verdict |
> |---|---|---|---|---|---|
> | ALL | **VIX percentile gate** (Dafu) | −0.0007 | **+4.82pp** | n/p | **ACCEPT** ⟵ flip |
> | ALL | **Per-currency RR** | −0.0092 | +1.70pp | −6.9% | **ACCEPT** ⟵ flip |
> | ALL | **Regime Mod→0.5 / Crisis→0.0** | **+0.0171** | +3.75pp | −9.5% | **ACCEPT** ⟵ flip |
> | G10 | **Per-currency RR** | −0.0030 | +4.54pp | −7.3% | **ACCEPT** ⟵ flip |
> | G10 | **IV/RR linear ramp** | −0.0106 | +2.03pp | −9.5% | **ACCEPT** ⟵ flip |
> | ALL | VIX *threshold* (Stage 3) | −0.0247 | +4.39pp | −7.3% | REJECT — **misses the 0.02 budget by 0.005** |
> | ALL | IV/RR binary, book-level | −0.0970 | −2.02pp | −4.9% | REJECT (unchanged) |
> | ALL | Regime Crisis→0.5 / →0.0 | +0.004 / 0.000 | −0.86 / −1.72pp | −3.7 / −3.8% | REJECT — no tail gain |
>
> **Five of twelve tail rules flip to accept.** Three caveats travel with the table and are recorded
> in the CSV's own `note` column, not just here:
> 1. **`reg_mod` is the strongest cell on *both* objectives, and §12's caveat still stands** — it
>    de-risks the *highest-Sharpe* regime (Moderate, Sharpe 0.94), its NW alpha is insignificant
>    (t = 0.59), and it was a beyond-spec sensitivity. A re-verdict is a re-reading, not a promotion.
> 2. **Stage 3's VIX threshold is a near-miss, and is reported as one** rather than rounded either
>    way: it buys 4.39pp of MaxDD but costs 0.0247 Sharpe against a 0.02 budget.
> 3. **"Vol targeting vs static" is excluded from the flip count** as a category error. It is the
>    sizing standard, not an exposure-timing rule: it levers a 7.6%-vol book to the 10% target, so
>    its 11pp deeper MaxDD is the target working. The row is kept in the CSV and labelled
>    `tail_rule=False` — dropping a row because the mechanical rule gives an awkward answer is the
>    failure mode this document exists to prevent.
>
> P4-B now has to beat a genuinely competitive incumbent rather than a strawman.

- **Formulation.** Binary: P(next-month book return in the worst decile of the training sample).
  ~230 monthly observations. Stated up front, per §13 and `strategy/README.md` rule 8: **a null is a
  valid deliverable** — "does forecasting the tail add value?" has *no* as a legitimate answer, and
  given Stages 3 and 6 that is the honest prior.
- **Features** — all sampled month-end at *t*, trailing windows only, predicting *t+1* (§6.1). VIX
  level and 1M change; MOVE; JPMVXY G7/EM level and change; cross-sectional mean 25Δ risk-reversal
  (what the option market is charging for crash protection); EMBI level and change; DXY 3M trend;
  ΔUST2Y; 2s10s; BFCIUS; trailing 60d realized book vol; cross-sectional carry dispersion; trailing
  book return. All present in `data/raw/{global_risk, macro_market_proxies, em_risk, g10_fx_options,
  em_fx_options}` — no purchase needed.
- **Estimation.** Expanding-window logistic under the **§13 purged walk-forward** spec —
  `min_train=60, test_size=12, embargo=1`, standardized on train folds only, never shuffled k-fold.
  Regularized (L2) given the feature count against ~230 observations.
- **Use.** Map P(tail) → the `exposure` Series on `StrategyConfig`. No new plumbing: the hook already
  exists and is an exact no-op at 1.0, so the overlay measures only its own effect.
- **Three bars, pre-registered** (choosing them after seeing results is the failure mode this whole
  document is built to avoid):
  1. the baseline **0.466** and the per-currency-RR book **0.457** (§17 bar, unchanged);
  2. the **dumb incumbent** — the VIX percentile gate above (net 0.46527, MaxDD −24.50%,
     Calmar 0.1815), still the best real-time variant in `dafu/outputs/headline.csv`. A learned
     forecast on twelve features that cannot beat a single VIX threshold has not earned its
     complexity, and should be reported as not having earned it;
  3. the desk's alternative route to adoption: a material MaxDD / CVaR₉₉ improvement at
     ≤ 0.02 Sharpe cost — **provided it shows up in the crisis eras of the §19.2 table**, not only
     whole-sample.
- **Where:** `cesare/tail_forecast.py`. **Outputs:** `p4_tail_forecast_eval.csv` (OOS AUC and
  sign hit rate per fold), `p4_tail_feature_importance.csv`, `p4_tail_overlay_stats.csv`,
  `p4_tail_overlay_by_episode.csv`.
- **Acceptance:** every number strictly out-of-sample under the purged scheme; gross and net; the
  episode table attached; an explicit adopt/reject verdict against all three bars.

#### ✅ DONE 2026-08-03 (W3) — **REJECT, null.** The forecast loses to one VIX threshold.

`purged_walkforward(min_train=60, test_size=12, embargo=1)` was **built here** — §13 specified it
and cited it, but it did not exist anywhere in the repo (the same pattern as Appendix C #18, and now
#26). Everything that could leak is fitted inside the fold: the worst-decile threshold comes from
the *training* returns, the scaler's moments from training rows only, and the embargo drops the
adjacent observation whose outcome period overlaps the test block.

**Mean out-of-sample AUC across 13 purged folds: 0.4685** — worse than a coin flip.

| Bar (pre-registered) | Result |
|---|---|
| beat 0.4659 / 0.4559 net Sharpe | **NO** — 0.4179 |
| beat the VIX gate on Sharpe **and** MaxDD | **NO** — ΔSharpe −0.0473, ΔMaxDD −4.23pp |
| tail route: ≤0.02 Sharpe cost, ≥1pp MaxDD | **NO** — ΔSharpe −0.0480, ΔMaxDD +0.58pp |

Reported honestly, the *test* has two limits that do not change the verdict but do bound what was
learned. **7 of 13 folds contain no tail month at all** in their test block, so AUC is undefined
there — with ~23 tail months in the whole sample, this question may simply not be answerable at
monthly frequency on nineteen years of data. And the fitted coefficients are not stable enough to
read as an economic ranking, which is why the importance table ships with a `sign_stability` column
and an explicit caveat in its own `caveat` field rather than in prose.

**The model was not iterated.** That was fixed in advance and it was honoured: one L2 strength, one
mapping pre-registered (the same half-risk-at-p80 action as the incumbent, so the comparison is
signal-vs-signal), and the continuous mapping reported beside it as the spread, not as a second
attempt. It scores 0.2974 — worse still.

*Correction to this section's own spec: it says "twelve features"; its bulleted list enumerates
**sixteen** once levels and changes are counted separately. The list was implemented as written.*

### 19.4 P4-C — The combined engine ⬜

**The interface problem, stated before it bites.** `StrategyConfig` carries exactly **one**
`exposure: pd.Series | None` and **one** `weight_overlay: Callable | None`. Four teammates each want
one. Discovering this in week 3 would cost the deliverable.

There is a second, subtler problem: **an overlay that re-normalizes gross exposure silently undoes
the gate that ran before it.** Composition needs a stated contract, not just a chaining helper.

**Fix — a new `strategy/overlays.py` plus one config field** (both no-ops by default, so the 12
reconciliation tests cannot break):

```python
compose_exposure(*series, floor=0.0, cap=None) -> pd.Series
    # product of gates on the union index, fillna(1.0), clipped. Gates are
    # multiplicative de-risking factors, so the product is the "any gate says
    # de-risk" rule -- and it is associative, so component order cannot matter.

compose_overlays(*fns) -> Callable
    # left-to-right chain. Each step receives the SAME ctx (which carries
    # weights_unit, not the running weights) -- deliberate: an overlay should key
    # off the base book, not off what the previous overlay did. Plus a runtime
    # assertion that every step is gross-non-increasing. That assertion is the
    # contract: overlays may scale positions down, never re-normalize back up.
```

The existing `OverlayContext` signature (`strategy/core.py:124`) already supports this.

**The one component that fits neither hook — verified, not assumed.** Arjun's duration hedge adds a
**new instrument** (bond / rate exposure), not a reweighting of an FX pair. Passing it through
`weight_overlay` fails twice: `portfolio_returns` (`strategy/fx_utils.py:812`) **silently intersects
columns** and drops the hedge, so it never earns its return; and `roundtrip_cost`
(`strategy/fx_utils.py:877`) **raises** `ValueError: No half-spread series for [...]`, so it can
never pay its cost. No amount of overlay cleverness fixes this — it is an additional asset.

```python
@dataclass(frozen=True)
class ExternalLeg:
    returns:  pd.Series           # daily return of one unit of the hedge instrument
    weight:   pd.Series | float   # signed units held, on the rebalance grid
    cost_bps: float = 0.0         # round-trip cost per unit of turnover
```

consumed by **one new field**, `StrategyConfig.external_legs: tuple[ExternalLeg, ...] = ()`, in
`core.run` step 6 (~12 lines): add `Σ w·r` to `gross` and `Σ|Δw|·cost_bps/1e4` to `cost`. Default
`()` is an exact no-op.

This matters beyond tidiness. It forces the hedge to **pay its own transaction costs**, which the
current notebook does not: `duration_hedge_stats.csv` reports expanding gross **0.5095478** vs net
**0.5095096** — a difference of **3.8e-5**. A beta-sized TLT position rebalanced monthly cannot cost
that little, so **re-pricing the duration hedge honestly on the base is itself a result**, and it may
move the headline 0.510. The hedge ratio must also be the **expanding / real-time** estimate (0.510),
never the in-sample fit (0.527).

**Fold-in ledger.**

| Component | Owner | Attachment | Standalone evidence today | Decision |
|---|---|---|---|---|
| Duration hedge | Arjun | `ExternalLeg` | 0.467 → **0.510** real-time, but essentially **unpriced** (see above) | strongest candidate |
| Bad-skew filter | Theo | `filter_signal` / `weight_overlay` | contested — must beat per-ccy RR **0.457**, not the raw baseline (§19.1) | pending his re-spec |
| Regime / VIX gate | Vidhi, Dafu | `exposure` | VIX gate 0.465, composite regime 0.470 — both inside noise (§12: max \|t\| 0.59) | likely tail-only |
| Option insurance | Dafu | `weight_overlay` proxy | **blocked** — option data is mids only, premium not costable | proxy only, caveated |
| Tail forecast | Cesare | `exposure` | §19.3, tbd | tbd |

**Fixed composition order** (declared in advance, so the outcome is an assembly rather than a search
over 2⁵ combinations): `external_legs` first — additive, does not touch FX weights; then `exposure`
= `compose_exposure(vidhi_gate, dafu_vix_gate)` — book-level risk-off, a scalar that commutes with
everything; then `weight_overlay` = `compose_overlays(theo_skew_filter, dafu_option_trim)` —
per-name, and last because these compete for the same positions and must act on an already-sized
book so the trim is measured on real notional.

**Incremental-value protocol — two ladders, both reported:**

> **Add-one-in:** baseline → **+** duration leg → **+** exposure gate → **+** weight overlay
> **Leave-one-out:** the full book, minus each component in turn

Reporting only the first is the standard way to flatter whoever goes first — add-one-in is
order-dependent by construction. **Leave-one-out is the real test:** a component that does not hurt
when removed has not earned its slot. **If the two ladders disagree about a component, that component
is not robust, and the plan is to say so rather than pick the flattering ladder.**

At each rung report: whole-sample gross **and** net; the §19.2 window table; NW alpha **versus the
immediately preceding rung** (not versus the baseline — that is how a component gets credit for
someone else's work), via `fx_utils.nw_regression`; and the turnover / cost delta, with the
per-window MaxDD delta **printed beside** the alpha, because §19's second bar is the one most likely
to decide this.

**Slot criterion — falsifiable, and fixed now.** A component earns its slot if, net of costs, it
(i) improves MaxDD **or** CVaR₉₉ in **≥ 4 of the 6 pre-2026 stress windows**, **and** (ii) costs less
than 0.05 whole-sample net Sharpe, **and** (iii) survives leave-one-out. On today's evidence the
duration leg is the only candidate that plausibly clears all three.

**Pre-registered prior: the combination is expected to be worth less than the sum of its parts.**
Stages 3–6 and D1/D3/D6 are seven nulls on this bar; the honest prior is that overlays which each
barely clear noise do not stack. Committing to that here means a negative combined result is the
deliverable it should be, and cannot be spun afterwards.

**Outputs:** `outputs/p4_combined_ladder.csv` (one row per rung), `outputs/p4_combined_by_episode.csv`.
The surviving stack is frozen as a named **`COMBINED`** preset in `strategy/config.py`, alongside
`ALL_BASELINE` / `G10_BASELINE` / `EM_BASELINE`, with its own reconciliation test.

**Acceptance:** `run("COMBINED")` reproduces the ladder's final row exactly; the full test suite is
green; every adopted component has a written verdict and every rejected one has a written reason.

#### ✅ DONE 2026-08-03 (W2–W3). Built solo, on re-priced components.

**Base v1.2.0** shipped `strategy/overlays.py` (`compose_exposure`, `compose_overlays` with the
runtime gross-non-increasing assertion, `ExternalLeg`) plus `StrategyConfig.external_legs` consumed
in `core.run` step 6. All three are **exact no-ops at neutral settings (0.0e+00)**, so the 12 + 11
existing tests could not break, and `test_overlays.py` adds 17 more. The external leg appends its
P&L as a column of `contrib`, so `contrib.sum(axis=1) == gross` stays true *with* a bond leg
attached rather than quietly becoming false.

**Every component was re-priced, not rebuilt** (§15 fallback, executed as the primary plan), with
the reconstruction recorded in the CSV:

| Component | Owner | Attachment | Reconstruction | Standalone net |
|---|---|---|---|---|
| Duration hedge | Arjun | `ExternalLeg` | TLT return from his committed series; hedge ratio re-estimated on **this** base with his estimator; `cost_bps` **backed out** of his own gross-vs-net (0.678bp, reproduces his net to 1.1e-15) | **0.5145** |
| VIX percentile gate | Dafu | `exposure` | exact — one `fx.exposure_scalar` call on shared `data/raw`, no file needed; reproduces his headline to 5dp | 0.4653 |
| Macro/regime gate | Vidhi | `exposure` | recovered as `probability_scaled / static` from her committed monthly tracks (173 months, values in [0,1]) | **0.0964** |
| Bad-skew exclusion | Theo | `weight_overlay` | his committed `bad_skew25_1m` panel + his cross-sectional p80 rule | 0.4360 |

**Results — the ladders.** Both reported, plus a survivor re-ladder (guardrail §6.13):

| Rung (`final` ladder) | Net Sharpe | MaxDD | CVaR₉₉ | α vs prev (t) | Windows | Slot |
|---|---|---|---|---|---|---|
| baseline | 0.4659 | −29.32% | 0.0292 | — | — | — |
| **+ duration hedge** | 0.5145 | −28.42% | 0.0282 | +0.74%/yr (1.16) | 4/6 | ✅ |
| + VIX percentile gate | 0.5127 | −24.12% | 0.0275 | +0.08%/yr (0.18) | 3/6 | ❌ |
| **+ bad-skew exclusion** | **0.5323** | **−19.07%** | **0.0189** | +1.40%/yr (1.10) | 6/6 | ✅ |

**`COMBINED` = baseline + duration leg + bad-skew exclusion** → net **0.4891**, MaxDD **−19.07%**
(+10.25pp), CVaR₉₉ **0.0200** (−31%), turnover 0.5902, drag 1.27%/yr. `run("COMBINED")` reproduces
that row at **0.0e+00**; `test_combined.py` 8/8.

**Four things this result must be reported with, and they matter more than the headline.**

1. **No alpha anywhere is significant.** The largest |t| on any rung is **1.16**. The book buys
   drawdown and skew, not return. The pre-registered prior — the combination is worth less than the
   sum of its parts — is **half right**: the parts do stack on the tail, and not at all on alpha.
2. **Most of the tail gain is de-risking, not selection** (guardrail §6.12). Against a control
   holding the exclusion's *exact* daily gross spread across all names, 6.8pp of the 7.3pp drawdown
   improvement is simply holding less; selection's alpha is +1.25%/yr, **t 0.92**. What selection
   genuinely buys is skew, −0.63 → −0.31. The combined book also runs at **8.8% vol, not 10%** — so
   its MaxDD is partly a lower risk level, and the comparison is stated that way.
3. **The two ladders disagree about the VIX gate** — add-one-in says 3 of 6 windows (fail),
   leave-one-out says removing it costs 0.043 Sharpe (pass). Per the pre-registered protocol it is
   marked **not robust** and excluded on the strict reading of criterion (i). That decision costs
   0.043 of net Sharpe, and taking the cost rather than re-reading the rule is what pre-registration
   is for. Both numbers are in the CSV.
4. **Vidhi's gate is the single most destructive component tested** (0.4659 → 0.0964; removing it
   from the stack is worth +0.33). The diagnostic matters more than the number: its correlation with
   VIX is ≈0 at every lead and lag, and it fails under **both** possible lag conventions, so the
   verdict does not rest on a judgement call about a convention her outputs do not record.

**Outputs:** `p4_component_standalone.csv`, `p4_component_by_episode.csv`, `p4_combined_ladder.csv`,
`p4_combined_by_episode.csv`, `p4_selection_vs_derisking.csv`. Built by
`cesare/combined_engine.py`.

### 19.5 P4-D — Delivery ⬜

Three artifacts, and nothing else counts as done (per §14.2, §14.3):

1. **Combined engine** — the `COMBINED` preset in `strategy/config.py`, tests green.
2. **Final comparison tables** — `outputs/final_comparison.csv` (whole-sample) and
   `outputs/final_comparison_by_episode.csv` (variants × episodes), covering every named variant from
   all six workstreams plus both benchmarks.
3. **Final written report** — `report/`, structured per the revised §14.3, including the
   null-results chapter.

A final slide deck is *not* a committed deliverable this cycle; the weekly deck continues to be
assembled from this ledger and the tables, reusing the `overview.html` precedent if wanted.

### 19.6 Cut list — what August will not do, and why

Saying this explicitly is what keeps the four-week schedule honest.

| Cut | Reason | Where it lives |
|---|---|---|
| ~~**D2 (FX vol risk premium)**~~ D4, D5 | **D2 is NO LONGER CUT — the reversal trigger fired.** §17.3 named "if Phase 4 finishes early" as the condition to restart it; Phase 4 finished early on 2026-08-03 and D2 ran on 2026-08-04, returning **the project's only non-null** (§17.4, report ch. 8). Its three stated weaknesses all survived the run and are reported as qualifications, so the cut was correctly reasoned and correctly reversed. D4/D5 remain cut on the original reasons | §17.4; `p3_d2_*.csv` (8 files); report ch. 8 |
| ~~D6 term structure~~ | **Not cut — closed as a null on 2026-08-03** (§17.3) | §17.3 |
| **Stage 7 ML** (five-model version) | Oversized for ~230 monthly observations; its CV scheme is what mattered and P4-B inherits it | §13 |
| **Rebalance frequency / date grid** | Arjun has ~80% of it; duplicating it is exactly the overlap the team agreed to avoid on Jul 10. (The *tenor* axis is done — §17.3) | Delegated (§19.1), with the two blockers handed over |
| **1W tenor** | Not wired into `TENOR_MONTHS`, and the 3M–12M result already establishes the direction — shorter is better, so a 1W test would only confirm the gradient | §17.3 |
| **Retrofitting per-window stats to closed stages** | Weeks of re-runs for nothing new; the standard is prospective (§19.2) | One pass over `strategy_returns_daily.csv` instead |
| **Repo packaging** (`pyproject.toml`, CI) | No desk value inside four weeks; the thing that matters — `strategy/tests` green — is already scheduled every week | §14.5 keeps only the README/requirements collation |
| **Auto-funding crosses** | Answered analytically — the book already holds the cross; the cost/basis difference is unpriceable without cross-pair quotes | §19.1, recorded as a data request |
| **Macro adds** — EM CB cycles, elections, trade balances, NFP/CPI/growth | Oleg's workstream; my job is to make sure he uses the same frozen windows | §19.1, tracked |
| **Option insurance / 2009 diagnosis** | Dafu's workstream; blocked on option bid/ask for honest costing — flag to the desk rather than report a free-premium Sharpe | §19.1, tracked |
| **December / year-end liquidity study** | Diagnostic, not a strategy change | §19.1, report sidebar |

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
| `basis_carry_comparison.csv` | basis_carry §3 (D3) | cross-currency-basis battery (basis/onshore/tilthi/tiltlo/clean, matched U7) + ALL-27 carry & basis-funding-stress conditioner × gross/net: full metrics, IR, turnover, cost drag, NW alpha vs matched carry (basis window 2007-05→2024-09) |
| `basis_carry_spanning.csv` | basis_carry §4 (D3) | basis-vs-carry spanning both ways + onshore≈carry (α/β/t/R²): neither spans the other on the weak U7 universe |
| `basis_track_correlation.csv` | basis_carry §6 (D3) | correlation matrix of the net daily D3 tracks |

**Planned — Phase 4** (§19; all in `cesare/outputs/` unless noted):

| CSV | Produced by | Contents |
|---|---|---|
| ✅ `tenor_sweep.csv` | `final_evaluation.tenor_sweep`, §17.3 | D6 term-structure null — 1M/3M/6M/12M × gross/net, turnover, cost drag. **Net re-priced on base v1.1.0** |
| ✅ `p4_episode_table_baseline.csv` | `episodes.report_windows`, §19.2 | baseline on the 9 frozen `ERAS` × gross/net, incl. share of P&L (sums to 1.0) |
| ✅ `p4_stress_table_baseline.csv` | `episodes.report_windows`, §19.2 | baseline on the 8 frozen `STRESS` windows × gross/net, incl. both 2026 shocks |
| ✅ `p4_leg_decomposition.csv` | `episodes.leg_decomposition`, §19.2 | carry/spot × long-leg/short-leg, monthly + quarterly + annual + annualized full sample; reconciles to `gross` at **3.88e-17** |
| ✅ `p4_reverdict_tail_objective.csv` | `final_evaluation.reverdict`, §19.3 | Stages 3 & 6 re-read on the tail objective: old Sharpe verdict vs new tail verdict, ΔSharpe / ΔMaxDD / ΔCVaR₉₉, the decision thresholds, and a per-rule caveat column |
| ✅ `p4_tail_forecast_eval.csv` | `tail_forecast.py`, §19.3 | OOS AUC / hit rate per purged fold, with `n_tail_in_test` (7 of 13 folds have none) |
| ✅ `p4_tail_feature_importance.csv` | `tail_forecast.py`, §19.3 | standardised L2 coefficients across folds + `sign_stability` and an inline caveat column |
| ✅ `p4_tail_overlay_stats.csv` · ✅ `p4_tail_overlay_by_episode.csv` | §19.3 | the tail overlay (binary **and** continuous mappings) vs all three bars, whole-sample and per window |
| ✅ `p4_component_standalone.csv` · ✅ `p4_component_by_episode.csv` | `combined_engine.standalone`, §19.4 | each teammate component re-priced on the base, one change at a time, each against its own stated bar, with the `reconstruction` method recorded per row |
| ✅ `p4_combined_ladder.csv` · ✅ `p4_combined_by_episode.csv` | `combined_engine.ladder`, §19.4 | `add` / `loo` / `final` / `final_loo` ladders, NW alpha vs previous rung, per-window win counts, slot verdict and `ladders_agree` |
| ✅ `p4_selection_vs_derisking.csv` | `combined_engine.selection_vs_derisking`, §6.12 | the gross-matched control: how much of a trimming overlay's tail gain is selection vs simply holding less |
| ✅ `p3_d1_bkm_comparison.csv` · ✅ `p3_d1_bkm_spanning.csv` · ✅ `p3_d1_bkm_signal_agreement.csv` (`d1_bkm_rerun.py`) · ✅ `p3_d1_bkm_skew_panel.csv` · ✅ `p3_d1_bkm_clipped_mass.csv` (**hand-exported** from `bkm_skew.bkm_skew_diagnostics("1M","ME")` — no module writes these two, Appendix C #35) | `bkm_skew.py` + `d1_bkm_rerun.py`, §17.1 | the D1 rerun on model-free Breeden–Litzenberger/BKM skewness from the 5-point smile: battery vs the 25Δ proxy, two-way spanning, proxy-vs-model-free agreement (levels 0.886, changes 0.0198), the monthly skew panel and the integration-clipping diagnostic |
| ✅ `p3_d2_premium.csv` · ✅ `p3_d2_books.csv` · ✅ `p3_d2_spanning.csv` · ✅ `p3_d2_correlation.csv` · ✅ `p3_d2_static_vs_timing.csv` · ✅ `p3_d2_avg_weights.csv` · ✅ `p3_d2_breakeven_cost.csv` · ✅ `p3_d2_by_episode.csv` | `d2_vrp.py`, §17.4 | the FX volatility risk premium: per-currency premium and NW t, the four books, two-way spanning vs carry, the standing-tilt-vs-timing split, average weights, the breakeven vol spread grid, and **the per-window table (added 2026-08-04 — it was cited but never written, Appendix C #30)** |
| ✅ `final_comparison.csv` · ✅ `final_comparison_by_episode.csv` | `final_evaluation.final_comparison{,_by_episode}`, §14.2 | every named variant across all workstreams, whole-sample (**232 rows, 7 owners, 5 not on base, 0 duplicate keys**) and per window (**652 rows, 38 variants, 6 gaps recorded as explicit rows**). Two metric conventions coexist and must not be compared across: `daily_net` and `monthly_uncosted` (D2) |
| ✅ `presentations/deck_2026_08_05.html` | `cesare/build_deck.py` | the Aug 5 BofA progress deck — one self-contained HTML file, 7 matplotlib figures inlined as SVG, every number read from a committed CSV and asserted against `run()` before the page is written. **Not in `outputs/`** — it lives with the other two decks in `cesare/presentations/` (repo hygiene, 2026-08-05) |

**Deferred:** `stage7_ml_forecast_eval.csv`, `stage7_ml_strategy_stats.csv` (§13 — descoped, §19.6).

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
- Jurek (2014), *Crash-Neutral Currency Carry Trades* — not held locally (Appendix C #34). Crash-hedging
  removes ≤35% of the carry return; fully crash-neutralizing + dollar-neutral + including 2008 → ~zero.
- Farhi & Gabaix (2016), *Rare Disasters and Exchange Rates* — not held locally (Appendix C #34).
- Farhi, Fraiberger, Gabaix, Rancière, Verdelhan, *Crash Risk in Currency Markets* — SSRN 1397668.
  Disaster risk ≈ one-third of the G10 carry premium; RR ∝ the currency risk premium.
- Broll (2016), *The Skewness Risk Premium in Currency Markets* — SSRN 2775663.
- Li, Sarno & Zinna (2023), *Skewness Risk Premium* — SSRN 4580189. SRP = physical − risk-neutral
  (model-free) skewness; claims SRP subsumes carry. **Single-source spanning claim; falsified on our
  2007–2026 21-name panel (§17.1) — carry subsumes SRP.**
- Della Corte et al., *Volatility Risk Premia and Exchange Rate Predictability* — SSRN 2892114 (Phase-3
  direction D2, parked).

**Phase 3 / D3 — cross-currency basis / dollar funding** (post-2008 CIP fails; the basis is the
dollar-funding premium, positively correlated with the rate level in the cross-section — so a basis
sort points the *same* way as carry, making the spanning test decisive; tested here as both a
funding-stress conditioner and a cross-sectional signal — **null** on the 7-name onshore-fixing EM
universe, see §17.2):
- Du, Tepper & Verdelhan (2018), *Deviations from Covered Interest Rate Parity* — Journal of Finance;
  NBER WP 23170. Large, persistent post-2008 CIP deviations from intermediary/balance-sheet costs; the
  basis is positively correlated with nominal rates in the cross-section (high-rate ⇒ higher basis), and
  the CIP-arb allocation (borrow high-rate / lend low-rate, hedged) is the *opposite* of the carry trade.
- Avdjiev, Du, Koch & Shin (2019), *The Dollar, Bank Leverage, and Deviations from Covered Interest
  Parity* — AER: Insights; BIS WP 592. The dollar / bank-leverage / CIP-basis "triangle": a stronger
  broad dollar co-moves with a wider (more negative) basis — the aggregate basis as a funding-stress gauge.
- Cenedese, Della Corte & Wang (2021), *Currency Mispricing and Dealer Balance Sheets* — Journal of
  Finance; SSRN 3335265. The basis is priced by dealer balance-sheet constraints (leverage-ratio shock ≈
  +20bps synthetic-dollar premium).
- Borio, McCauley, McGuire & Sushko (2016), *Covered Interest Parity Lost: Understanding the
  Cross-Currency Basis* — BIS Quarterly Review. Hedging demand + tighter bank balance sheets sustain the
  basis; the reference framing of the post-crisis basis.
- Brunnermeier, Nagel & Pedersen (2008/2009), *Carry Trades and Currency Crashes* (above) — the
  funding-liquidity channel that motivates a basis-stress *conditioner*.

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

*Corrections 12–16 added 2026-08-03; all four code findings were verified by execution, not inferred.*

12. **§17's D6 row was factually wrong.** It stated that term structure "needs multi-tenor forwards
    (only 1M pulled)". All 27 names carry **1M / 3M / 6M / 12M** forwards in `data/raw/`, and
    `fx_utils.TENOR_MONTHS` already supports all four. The direction was therefore free to run and
    is now closed as a third null (§17.3). Lesson: a "needs data" claim in this document is a
    testable claim, and this one was never tested.
13. **`summary_stats(min_obs=120)` silently voids short windows.** `StrategyResult.summary()` has no
    passthrough, so any window under 120 trading days returns an **empty (0, 0) frame** rather than
    an error — verified on oil 2026 (85d), semis 2026 (65d) and COVID (64d). Every window the desk
    personally named was unreportable. Fixed by a `min_obs` kwarg (§19.2) plus guardrail §6.8 on
    which metrics a short window may quote. **A silent empty is worse than a raise**, and this one
    sat undiscovered because nothing had asked for a short window before.
14. **The roll-leg cost model is indexed to the rebalance grid, not the forward tenor.**
    `roundtrip_cost` charges `Σ min(|w_old|, |w_new|) · hs_points` on *every* rebalance date, which
    is correct only when the rebalance frequency matches the tenor — i.e. only at the committed
    baseline (1M, ME). The signature of the defect: at 12M the cost drag **rises** to 4.84%/yr while
    turnover **falls** to 0.426. Codified as guardrail §6.11. **✅ Fixed 2026-08-03 in base v1.1.0**
    (`fx_utils.roll_schedule` + `roundtrip_cost(tenor=)`), bit-identical at the baseline —
    see §6.11, §17.3 and Appendix C #20 for the design and why the two obvious designs failed.
15. **`.resample(alias).last()` leaks with left-labelled aliases.** Verified on a monotone series:
    `MS` stamps the January-31 value onto the label January-1 (23.0 vs the true 1.0); `SMS` and
    `SME` likewise. Right-labelled aliases (`ME`, `QE`, `W-FRI`) are safe. The base's single
    `shift(1)` removes one day of what can be a thirty-day lookahead. Codified as guardrail §6.10 —
    which matters because the desk's "test different rebalancing **dates**" ask is exactly the
    request that tempts you into `MS` / `SMS` / `WOM-3FRI`.
16. **The evaluation frame itself was wrong for the audience.** The whole document optimizes and
    verdicts on Sharpe; the desk's stated objective (Jul 29) is capital preservation through the
    tail. At least one existing "reject" flips under the correct objective — the VIX percentile gate
    costs 0.0007 Sharpe for 4.8 points of MaxDD (§19.3). Guardrails §6.8 and the §19 bar now carry
    the tail objective explicitly, and Stages 3 and 6 are re-verdicted in W1. This is the most
    consequential correction in the list: it does not change a number anywhere, it changes which
    number decides. **✅ Executed 2026-08-03: five of twelve tail rules flip to accept** (§19.3).

*Corrections 17–21 added 2026-08-03 during W1 execution; all verified by execution.*

17. **`min_obs` had a second failure surface that #13 missed.** `StrategyResult.__repr__`
    unconditionally indexes `s.iloc[0]`/`s.iloc[1]` of the summary frame, so echoing a resliced
    short window in a notebook raised **`IndexError`** rather than returning the empty frame #13
    describes. Anyone following the README's own episode-study example into a crisis window hit a
    crash. Fixed alongside F1; `__repr__` now degrades to a window-and-day-count line.
18. **A cited output did not exist.** §17.3 and Appendix A both named `outputs/tenor_sweep.csv` as
    D6's artifact. It was never written — so the D6 null, one of the three Phase-3 nulls this
    document calls its most defensible result, had **no committed CSV behind it**, contradicting
    the document's opening promise that every number is reproducible from one. Regenerated in W1,
    now including corrected net figures. *Lesson, and it is the same one as #12: a claim in this
    document that an artifact exists is a testable claim.*
19. **The per-leg decomposition needs an `xret`-presence mask, and the plan's ~0.3pp gap was that.**
    A currency can have a spot return on a day its carry is missing; `xret` is then NaN and
    `portfolio_returns` drops the name from `gross` entirely, while an unmasked spot leg keeps
    counting it. Unmasked, the daily residual reaches **8e-3** — which is exactly the shape of the
    7.32%-vs-7.03% gap §19.2 flagged as provisional. Masking the components to `xret.notna()` takes
    the reconciliation to **3.88e-17**. The qualitative conclusion survived; `spot_long` moved from
    the guessed −10.2% to −10.43%.
20. **The rebalance effective day is not the first trading day of the month.** Verified: it is the
    *second* trading day in **67 of 230 months**, because the ME resample label is a calendar
    month-end that can fall on a weekend before the single `shift(1)` is applied. This killed the
    obvious design for the F2 fix (a calendar-driven roll grid), and a day-count rule fails too
    (Jul 3 → Aug 1 is 29 days). What works, and is provably exact, is a **calendar-month-count**
    test thinned from the observed rebalance days — the baseline has exactly one rebalance day in
    every one of its 230 live months. Recording this because the same trap sits under the desk's
    "test different rebalancing **dates**" ask, next to §6.10.
21. **`euro_2011` is 392 trading days, not 399** (§19.2 table) — a transcription error, corrected.
    The other seven `STRESS` windows reproduce exactly and are now asserted in
    `test_episodes.py::test_stress_table_matches_the_plan`.

*Corrections 22–27 added 2026-08-03 during W2–W3 execution; all verified by execution.*

22. **"Arjun's baseline is not the shared base" was wrong, and the diagnosis matters more than the
    correction.** `arjun/outputs/duration_hedge_series.csv["book"]` **is** `run().net`,
    bit-identical: max |Δ| = **1.0e-16**, correlation 1.0, across all 4,994 shared days. Both
    apparent discrepancies decompose exactly:
    * **0.4673 vs 0.4659** — he drops **7 US market holidays** in the TLT inner join (2011-09-04 …
      2011-10-23). On his index the base scores **0.467288**, his committed figure to six digits.
    * **−33.2% vs −29.3%** — a **drawdown-convention** difference, not a different book. He uses
      `cumsum` (arithmetic); the base uses the wealth curve. His convention applied to the base's own
      net series gives **−0.3322331117648022**, matching his committed number to every digit.
    Consequence: his +0.043 delta was **already measured on the shared base**, and the row was
    wrongly flagged `on_base=False` in `final_comparison.csv` (now corrected). What genuinely does
    not transfer is the MaxDD, which is in different units. *Lesson: "their numbers differ from ours"
    is a hypothesis with at least three explanations — different book, different sample, different
    convention — and only the first is worth a week of anyone's time.*
23. **Theo's "bad skew" and the base's risk reversal are the same number.** His committed
    `bad_skew25_1m` is **bit-identical** to `fx_utils.vol_surface_panel("RR", "1M")` resampled to
    month-end: max absolute difference **0.0** across all 21 shared currencies. The §19.1 skew
    collision is therefore not an overlap of related ideas, it is the same signal conditioned on a
    different axis (his cross-sectional p80 vs the adopted per-currency trailing p80) with a
    different action (exclude vs halve). Recorded because it converts a vague coordination warning
    into a checkable fact, and because it sharpens the spec handed to him.
24. **The duration hedge was never "essentially unpriced" — the 3.8e-5 gap was slow beta drift.**
    His cost model charges `half_spread × |Δh|`, and an expanding-window beta moves very little
    (Σ|Δh| = **0.94** over eighteen years, ≈0.05/yr), so a near-zero charge is arithmetically correct
    for what he bills. Priced honestly through `ExternalLeg` the leg costs **0.02bp/yr**
    (0.41bp total), and the rebalance-drift charge nobody bills — holding the position at β× equity
    as TLT moves — adds **0.074bp/yr**. **The headline does not move.** The plan's "may move the
    headline 0.510" is answered: no. *Lesson: a suspiciously small number deserves the same
    diagnosis as a suspiciously large one, and "unpriced" and "barely trades" look identical in the
    output.*
25. **A trimming overlay's drawdown improvement is mostly de-risking unless proven otherwise.**
    Against a control reproducing the bad-skew filter's *exact* daily gross (matched to 8.9e-16)
    spread uniformly across names: of a 7.3pp MaxDD improvement, **6.8pp is holding less and 0.5pp
    is selection**, and selection's NW alpha is +1.25%/yr with **t 0.92**. The exception, and the
    real result: **skew −0.63 → −0.31**, which de-risking does not deliver at all. Codified as
    guardrail §6.12. Without this control the project's strongest-looking Phase-4 number would have
    been its most misleading.
26. **`purged_walkforward` was cited but never written.** §13 specifies it, §19.3 inherits it "verbatim",
    and it existed nowhere in the repo — the third instance of this document asserting an artifact
    that did not exist (see #12, #18). Built in `cesare/tail_forecast.py`. *The rule this keeps
    earning: a claim in this document that something exists is a testable claim.*
27. **`.mask()` on a weight panel silently extends the evaluation window.** An overlay written as
    `weights.mask(bad, 0.0)` converts a **pre-inception NaN** weight into a real 0.0;
    `portfolio_returns` (`min_count=1`) then emits a return on a day the book does not exist, and
    the window starts **2007-02-01 instead of 2007-05-01** — breaking guardrail §6.7 and making the
    variant non-comparable to the baseline it is being measured against. Caught by comparing
    `result.window` rather than by the numbers looking wrong, which they did not. Fix:
    `.mask(bad, 0.0).where(weights.notna())`. Guard:
    `test_combined.py::test_combined_shares_the_baseline_window`.
28. **`implied_skew_panel`'s docstring asserts a data limitation that does not exist.** It states that a
    "full Bakshi-Kapadia-Madan model-free skewness would need the whole strike chain, which the
    3-point (ATM/RR/BF) surface here does not provide." Verified 2026-08-04: the surface is
    **5-point** — 10Δ RR *and* BF are present for all 24 option tickers with ~5,080 observations
    each, identical coverage to the 25Δ pair. **This is the fourth instance of the same failure
    mode** (#12 D6 "needs data", #18 `tenor_sweep.csv` "exists", #26 `purged_walkforward` "exists"),
    and the most consequential: it meant D1 — one of three headline nulls — tested a
    *single-source spanning claim about model-free skewness* using a smile-slope proxy, and the
    docstring is why nobody questioned it. The rerun (§17.1) confirms the null, so no published
    conclusion moves; the lesson is that the claim was never checked, not that it was harmful.
    **✅ FIXED 2026-08-04.** The docstring now states that the surface is 5-point, that BKM skewness
    IS reachable from it (`cesare/bkm_skew.py` does exactly that), records that the earlier assertion
    was false, and directs the reader to the proxy for cross-sectional work and to `bkm_skew` for
    anything keying off *changes*. All 48 tests green after the edit; no behaviour change.

*Corrections 29–33 added 2026-08-04 during W4 execution; all verified by execution.*

29. **§17.4's D2 breakeven figures were one grid point too generous — and it was our own number,
    one day old.** The section reported that `short_vol` "clears the bars up to ~0.5 vol points,
    `carry+short_vol` to ~0.5, and `vrp_xs` only to ~0.25". Those are the first grid points at which
    each book **fails**. Read off `p3_d2_breakeven_cost.csv`'s own `beats_both_bars` column, the
    widest spread still *clearing* both bars is **0.25 / 0.25 / 0.10**. The error is not cosmetic:
    `d2_vrp.COST_GRID`'s docstring notes interbank G10 1M ATM trades inside ~0.2 vol points, so the
    corrected figure moves the headline `vrp_xs` book from "tight for EM" to **"dies inside G10
    interbank"** — and the EM names are precisely its standing shorts. *The lesson is narrower than
    the usual one and worth keeping: when a result is a threshold read off a coarse grid, say which
    side of the grid point you are quoting.*
30. **`d2_vrp.py`'s own module docstring listed an output it never wrote.** It named
    `p3_d2_by_episode.csv`; `grep to_csv` shows the module writes seven files and no episode table.
    **This is the fifth instance of the same failure mode** (#12 D6 "needs data", #18
    `tenor_sweep.csv` "exists", #26 `purged_walkforward` "exists", #28 the `implied_skew_panel`
    docstring), and the first one written by this project *after* the pattern had been named four
    times. The consequence was not bookkeeping: **D2 had no per-window table at all**, so the one
    non-null result in the project was in breach of guardrail §6.8 and `strategy/README.md` rule 11
    — the desk's only standing requirement. Fixed by adding `d2_vrp.by_episode()`; the table
    reconciles to the full monthly series over `ERAS` at machine precision for all four books.
31. **`final_comparison.csv` contained 6 exact duplicate rows.** The Phase-4 ladder file holds four
    ladders (`add`/`loo`/`final`/`final_loo`) keyed only by `step`, and several rungs are shared
    between them — `add`'s baseline *is* `final`'s baseline. Labelling rows by `step` alone therefore
    emitted the baseline twice per basis and double-counted it in any `groupby`. Fixed by making the
    ladder name part of the variant label (`[final] + Duration hedge …`) rather than by dropping
    rows: the four ladders are different measurements and collapsing them would delete the
    leave-one-out result. Now 0 duplicate keys.
32. **The P4-B null was described with more evidence than it has.** `final_comparison.csv`'s note
    read "mean OOS AUC 0.4685 across 13 purged folds". **7 of those 13 folds contain no tail month
    at all**, so AUC is undefined in them and 0.4685 is the mean of the **6** that are defined —
    a fact §19.3 states correctly two paragraphs later. The verdict does not change; the strength of
    the evidence behind it does, and the note now says so. *A null is a result, which means it can be
    overstated exactly like a positive one.*
33. **The two spanning CSVs disagree on units, and both are read correctly today only by accident of
    who wrote the prose.** `p3_d1_bkm_spanning.csv` stores `alpha_ann` as a decimal
    (0.032172 = 3.22%/yr); `p3_d2_spanning.csv` stores it as a percent (3.334531 = 3.33%/yr). No
    published number is wrong, but any chart or table combining the two would be off by 100×. Left
    as-is rather than silently renormalised — changing a committed CSV's units to fix a
    documentation problem is how a reconciliation breaks — and recorded here plus in report ch. 8 so
    the next reader is warned.

*Corrections 34–35 added 2026-08-05 during the §14.6 cleanup; both verified by execution.*

34. **Three references are cited as being in `papers/` and are not.** `papers/` holds exactly two
    PDFs — Lustig–Roussanov–Verdelhan (2011) and Burnside–Eichenbaum–Rebelo (2011). Appendix B cited
    `papers/jurek_currency.pdf` and `papers/rare_disasters_and_exchange_rates` as local files, and
    §11 said Menkhoff et al. (2012b) is "in `papers/`". None of the three is there, and the two
    filenames never existed under any spelling. The citations are kept — the papers are real and the
    arguments drawn from them stand — but the false locality claim is removed. **Same class as #12,
    #18, #26 and #30: a "we have this" claim in this document that nobody checked.** Six of the
    eight references in Appendix B are not held locally; `papers/` is not a bibliography.
35. **Two committed outputs are produced by nothing.** Appendix A and §17.1 both credit
    `p3_d1_bkm_skew_panel.csv` and `p3_d1_bkm_clipped_mass.csv` to "`bkm_skew.py` +
    `d1_bkm_rerun.py`". Neither module writes them: `bkm_skew.py` contains no `to_csv` at all, and
    `d1_bkm_rerun.py` writes exactly three files. They were exported by hand from
    `bkm_skew.bkm_skew_diagnostics("1M", "ME")` and committed. **The numbers are sound** — verified
    2026-08-05 by recomputing both from the current code: identical shape (234 × 24), identical NaN
    pattern, `max|diff|` **4.4e-16** and **1.0e-16**, i.e. one unit in the last place. What was wrong
    is the registry's producer claim, and the practical cost is that
    `python cesare/d1_bkm_rerun.py` does *not* reproduce the full D1 artifact set. Fixed by stating
    the true provenance in both places rather than by adding the two writes: at 1 ULP they would
    rewrite a committed deliverable on every run, and churning a frozen artifact to fix a
    documentation error is the trade #33 already declined. *"Produced by" is a testable claim too,
    not just "exists".*
