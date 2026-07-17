# `arjun/` — FX Carry Strategy: Exploratory Research & Robustness Analysis

**Arjun** · UChicago Summer Project Lab with Bank of America (Corporate Treasury / Global Funding).

---

## Overview

This folder contains two weeks of work on the FX carry strategy:

**Week 1 (fx_analysis.ipynb):** Exploratory diagnostics on G10+EM currency performance, drawdowns, correlations, and macro factor exposures. Built the diagnostic foundation for understanding which currencies move together and why.

**Week 2 (robustness_audit.ipynb + em_carry_attribution.ipynb):** Stress-testing and attribution of the team's headline result. The strategy works (0.466 net Sharpe vs 0.119 G10-only), but *how much can we trust it?* These two notebooks answer that question by interrogating time stability, currency concentration, parameter sensitivity, and implementation robustness.

---

## The headline finding

The team's combined G10+EM carry book earns a **net Sharpe of 0.466** (gross 0.628) — a clean result. But when stress-tested:

- **Time stability:** The premium is NOT durable. All gains (0.75 Sharpe) were made in 2007–2012 (crisis/recovery). The next 8 years (2013–2020) were underwater. Only 2021–2026 recovered. ⚠️
- **Currency concentration:** The strategy is a **5-name bet** (JPY, MXN, CNH, EUR, SEK carry 80%+ of the premium), not a diversified 27-name book. Removing JPY alone cuts Sharpe by 7.5 percentage points. ⚠️
- **Parameter sensitivity:** The 60-day vol window × month-end rebalance is an isolated peak, not a plateau. Step to 40d or 2W and Sharpe drops 10–15%. Overfit risk. ⚠️
- **Attribution:** IDR is the largest earner (1.3%/yr) but high-volatility; JPY matters most for risk-adjusted returns (low-vol, steady). The premium is predominantly carry accrual (interest pickup), not spot appreciation. ✓

**Bottom line:** The 0.466 is real but *fragile and front-loaded to two specific windows (2007–2012, 2021–2026)*. For a Treasury desk, this shifts from "allocate" to "allocate with a live monitor on JPY/MXN, dollar strength, and EM volatility."

---

## Notebook 1: `robustness_audit.ipynb`

**Question:** How robust is the 0.466 Sharpe under stress?

**What it tests:**

| Axis | Test | Key Finding |
|---|---|---|
| **Time stability** | Rolling 3-year Sharpe, expanding-window Sharpe, per-year returns, subsample splits | Premium front-loaded to 2007–2012; flat-to-negative 2013–2020; recovering 2021–2026 |
| **Currency concentration** | Drop-one-currency jackknife (rebuild 27× with each name removed) | Top 5 names (JPY −0.075, MXN −0.06, CNH −0.05, EUR −0.05, SEK −0.04) carry 80%+ of premium; rest are noise or drags |
| **Parameter sensitivity** | Sweep vol window, vol target, rebalance freq, bucket count, leg cap, weighting; 2-D heatmap | Vol window & rebalance freq are sensitive (60d × ME is isolated peak); vol target & weighting are robust |
| **Implementation robustness** | Cost multiples (2–5×), execution lag (1–5 days), worst-drawdown anatomy | Edge survives 2–3× cost inflation; max DD ~30% with multi-year recovery periods |

**Outputs (CSVs):**
- `robustness_jackknife.csv` — currency-by-currency impact on Sharpe
- `robustness_param_sweeps.csv` — one-knob sweep results
- `robustness_window_rebal_heatmap.csv` — 2-D parameter grid
- `robustness_cost_stress.csv`, `robustness_lag_stress.csv` — implementation stress
- `robustness_concentration.csv` — cumulative impact of dropping top carriers
- `robustness_scorecard.csv` — executive summary

**Verdict:** **FRAGILE**. The 0.466 is decaying over time (front-loaded to 2007–2012, flat 2013–2020, recovering 2021–2026), concentrated in 5 names (80%+ of premium), and a knife-edge in parameters (60d × ME is an isolated peak, not a plateau). Biggest risk: *time decay* — the strategy made its money in a specific historical window; recent recovery (2021–2026) is cyclical, not structural.

---

## Notebook 2: `em_carry_attribution.ipynb`

**Question:** Where does the EM premium actually come from? Which currencies? Carry vs spot?

**Part A — EM vs G10 establishment:**
- Rebuild G10-only, EM-only, and combined books side by side
- Show cumulative curves: G10 is negative; EM drives all the gains
- Cross-check against investable DB indices (DBHVG10U G10 vs FXCTEM8 EM)
- **Finding:** EM-only net Sharpe ~0.47 vs G10-only ~0.12 → the premium is EM ✓

**Part B — per-currency attribution:**
- Decompose the combined book using exact P&L contribution: `w[ccy] × xret[ccy]` sums to book return
- For each currency, measure: contribution to return, share of P&L, share of variance, carry-accrual vs spot split
- Rank by contribution; tie back to jackknife (high P&L *and* high removal-impact = concentration risk)
- Year-by-year heatmap: does the source rotate, or is it the same names every year?

**Key findings:**

| Currency | Annualized Contribution | P&L Share | Risk Share | Carry vs Spot | Jackknife Delta |
|---|---|---|---|---|---|
| **IDR** | +1.25% | 18% | 12% | ~70% carry, 30% spot | −0.01 (low risk-adjusted impact) |
| **JPY** | +1.0% | 14% | 18% | ~100% spot (no carry!) | −0.075 (critical) |
| **MXN** | +0.8% | 11% | 10% | mixed carry/spot | −0.06 (critical) |
| **BRL** | +0.7% | 10% | 14% | ~60% carry, 40% spot | −0.04 (important) |
| **ZAR** | +0.4% | 6% | 8% | carry-heavy | +0.10 (drag!) |

**Outputs (CSVs):**
- `em_vs_g10_stats.csv` — G10, EM-only, and combined book headline stats
- `attribution_by_currency.csv` — per-currency contribution, carry/spot split, weight, position frequency
- `attribution_by_group.csv` — EM vs G10 share of P&L and variance
- `attribution_by_year.csv` — annual contribution per currency (is the source rotating?)

**Verdict:** The premium is **concentrated in 5 names** (IDR, JPY, MXN, BRL, COP supply ~65% of P&L). The strategy is *not* a classical carry trade (high interest pickup earns steady return) — it's a **macro FX bet** where most money comes from currency appreciation (spot), not interest accrual. JPY is the most critical (lowest-vol earner), while IDR makes the most but is high-vol. ZAR and TRY are active drags despite positive carry. The source doesn't rotate much year-to-year; same 5 names dominate every year.

---

## Key Results Summary

### Robustness Audit

| Metric | Finding | Implication |
|---|---|---|
| **Rolling 3-yr Sharpe** | Underwater 2010–2020, spikes 2021–2026 | Premium is cyclical, not structural |
| **Expanding Sharpe** | Rose to 0.75 in 2012, collapsed to 0.25 by 2018, recovering | All gains front-loaded; recent 5 years can't offset 8-year drought |
| **Most-carrying currency** | JPY (−0.075 delta) | Removing it cuts Sharpe by 7.5pp; critical concentration risk |
| **Parameter plateau** | Vol window 60d × rebal ME is isolated peak | Not robust; stepping to 40d or 2W drops Sharpe 10–15% |
| **Cost stress** | Survives up to 2–3× spread widening | High EM liquidity risk; crisis widening kills the edge |
| **Max drawdown** | ~30% (2008, 2020) | Multi-year recovery periods; tail risk is real |

### EM Attribution

| Finding | What it means |
|---|---|
| **IDR is #1 earner** (+1.25%/yr) but JPY is most important (jackknife −0.075) | High-return, high-vol vs low-return, low-vol; Sharpe depends on the latter |
| **65% of P&L from 5 names** | Concentrated bet dressed as diversified strategy |
| **70% of premium is carry accrual** (orange bars) | Classical carry story (interest pickup), but with spot volatility |
| **JPY made money on spot alone** (100% purple bar) | Safe-haven appreciation, not interest pickup; separate macro bet |
| **ZAR and TRY are drags** (positive delta in jackknife) | Holding them for diversification hurts risk-adjusted returns |

---

## How to run

Both notebooks run from **inside `arjun/`** and import the shared engine and data:

```bash
cd arjun
jupyter lab
# run robustness_audit.ipynb top-to-bottom (generates outputs/ CSVs)
# run em_carry_attribution.ipynb (reads robustness jackknife for tie-back chart)
```

**Requirements:** pandas, numpy, scipy, statsmodels, matplotlib, and **pyarrow ≥ 24** (for parquet).

**Reproducibility:** Common window 2007-05 → 2026-06; no lookahead; every track gross **and** net of costs; reconciliation gate asserts rebuilt books match committed Sharpes to within 5e-3.

---

## Implications for Bank of America

1. **The strategy works, but it's fragile.** The 0.466 Sharpe is real but front-loaded to 2007–2012 and cyclically boosted by 2021–2026 EM strength. If the dollar strengthens, the edge disappears.

2. **It's a 5-name concentrated bet, not diversified.** JPY, MXN, CNH, EUR, SEK carry 80%+ of the premium. Size limits on these names and a live monitor on JPY revaluation are mandatory.

3. **The premium is not structural.** It's a combo of carry accrual (IDR, BRL) + safe-haven appreciation (JPY) + recent EM rallies (2021–2026). None of these are permanent.

4. **Parameters matter.** The 60d vol window × monthly rebalance are specific choices that optimize on historical data. Any change materially hurts the edge.

5. **Implementation costs will kill it.** In a crisis (when spreads widen to 2–3×), the edge vanishes. EM liquidity is thin.

**Recommendation:** Treat as **tactical, not strategic.** Monitor JPY strength, MXN volatility, dollar weakness, and EM carry curves. If any reverse, unwind quickly. The 0.466 is not a "set and forget" allocation.

---

## Files in this folder

- `robustness_audit.ipynb` — stress-test the 0.466 headline number (4 axes: time, concentration, parameters, implementation)
- `em_carry_attribution.ipynb` — source-of-premium analysis (EM vs G10 establishment + per-currency P&L decomposition)
- `fx_analysis.ipynb` — week-1 exploratory work (spot performance, correlations, macro factors)
- `outputs/` — CSV outputs from both notebooks (robustness CSVs + attribution CSVs)
- `README.md` — this file
