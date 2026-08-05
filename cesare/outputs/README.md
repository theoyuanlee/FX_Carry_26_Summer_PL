# `cesare/outputs/` — committed results

**59 CSVs. Every number quoted anywhere in this project — the plan, the eleven report chapters, the
decks — traces to one of them.** They are deliverables, not build artifacts: they are git-tracked
on purpose and should not be deleted or regenerated casually.

This file is an **index by producer**, so you can go from a file to the thing that made it. For what
is *in* each file, see **Appendix A of
[`../FX_Carry_Strategy_Project_Plan.md`](../FX_Carry_Strategy_Project_Plan.md)**, which is the
registry of record and carries a description per artifact. Nothing is described twice here, so the
two cannot drift apart.

## Research track — the stage notebooks

Run with the working directory set to `cesare/`.

| Producer | Stage | Files |
|---|---|---|
| `data_visualization.ipynb` | St0 / St2 | `implied_carry_validation` · `summary_stats_carry_excess` · `summary_stats_spot` · `regression_lrv` · `regression_macro` · `cip_basis_summary` · `uip_fama` |
| `strategy_backtest.ipynb` | St1 | `strategy_returns_daily` · `strategy_summary_stats` · `strategy_costs_by_ccy` · `crash_regressions` · `weights_g10_monthly` · `weights_combined_monthly` |
| `dynamic_carry.ipynb` | St3 | `stage3_dynamic_comparison` |
| `portfolio_construction.ipynb` | St4 | `stage4_weighting_comparison` · `weights_{equal,inv_vol,erc,mvo}_monthly` *(four files — cited by pattern, not by name)* |
| `momentum_overlay.ipynb` | St5 | `stage5_momentum_comparison` · `stage5_track_correlation` |
| `regime_analysis.ipynb` | St6 | `regime_series` · `stage6_regime_stats` · `stage6_conditional_by_regime` |
| `skew_carry.ipynb` | D1 | `skew_carry_comparison` · `srp_carry_spanning` · `skew_track_correlation` |
| `basis_carry.ipynb` | D3 | `basis_carry_comparison` · `basis_carry_spanning` · `basis_track_correlation` |

## Phase-3 / Phase-4 modules

Run from the repo root.

| Producer | Section | Files |
|---|---|---|
| `d1_bkm_rerun.py` (uses `bkm_skew.py`) | §17.1 | `p3_d1_bkm_comparison` · `p3_d1_bkm_spanning` · `p3_d1_bkm_signal_agreement` |
| **hand-exported** from `bkm_skew.bkm_skew_diagnostics("1M","ME")` | §17.1 | `p3_d1_bkm_skew_panel` · `p3_d1_bkm_clipped_mass` — QA panels; **no module writes these**, so `python cesare/d1_bkm_rerun.py` does not reproduce them (Appendix C #35). Recomputing from current code matches to 4.4e-16 |
| `d2_vrp.py` | §17.4 | `p3_d2_premium` · `p3_d2_books` · `p3_d2_spanning` · `p3_d2_correlation` · `p3_d2_static_vs_timing` · `p3_d2_avg_weights` · `p3_d2_breakeven_cost` · `p3_d2_by_episode` |
| `final_evaluation.py` | §19.2 · §17.3 · §19.3 · §14.2 | `p4_episode_table_baseline` · `p4_stress_table_baseline` · `p4_leg_decomposition` · `tenor_sweep` · `p4_reverdict_tail_objective` · `final_comparison` · `final_comparison_by_episode` |
| `tail_forecast.py` | §19.3 | `p4_tail_forecast_eval` · `p4_tail_feature_importance` · `p4_tail_overlay_stats` · `p4_tail_overlay_by_episode` |
| `combined_engine.py` | §19.4 · §6.12 | `p4_component_standalone` · `p4_component_by_episode` · `p4_combined_ladder` · `p4_combined_by_episode` · `p4_selection_vs_derisking` |

## Reading them

- **Two metric conventions coexist** in `final_comparison.csv` and must never be compared across:
  `daily_net` (everything else) and `monthly_uncosted` (D2). The convention is a column.
- **Rows that do not reconcile to the shared base are kept and flagged** `on_base=False`, never
  dropped — a teammate's book disagreeing with the base is the plan §18 finding, not noise.
- **Components folded into the combined engine are labelled *re-priced, not rebuilt***, with the
  reconstruction method recorded per row.
- The four `weights_{scheme}_monthly.csv` files are **unit-book** weights (gross 2, pre-vol-target),
  so the schemes are directly comparable. A literal filename grep will report them as unreferenced;
  they are cited by pattern in Appendix A and `report/06_risk_managed_carry.md`.
