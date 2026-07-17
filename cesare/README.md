# `cesare/` — FX Carry Strategy Research

This folder is my slice of the FX Carry project. It holds the project's engine
(`fx_utils.py`), seven stage notebooks that each test one idea end-to-end, and the
committed result CSVs in `outputs/`. The headline finding: **the 2007–2026 currency
premium is EM carry, not G10** — a simple vol-targeted, inverse-vol long/short carry book
in EM+G10 earns ~7.0%/yr gross (Sharpe **0.63** gross / **0.47** net) versus ~1.9%/yr for
a G10-only book (Sharpe 0.17). **Every overlay we tried — dynamic hedges, portfolio
optimization, a momentum double-sort, regime timing, and the Phase-3 D1 option-implied
crash-skew signal — fails to beat that simple book net of costs.** The full write-up,
methodology, and per-stage verdicts live in
[`FX_Carry_Strategy_Project_Plan.md`](FX_Carry_Strategy_Project_Plan.md), which is the
**source of truth**; this README is a scannable front door to the folder.

## Folder structure

```
cesare/
├── fx_utils.py                     # the engine: pure-function library (data → panels → stats → portfolios)
├── FX_Carry_Strategy_Project_Plan.md   # source of truth (methodology, results, verdicts)
├── README.md                       # this file
├── requirements.txt                # only what cesare/ imports + the Jupyter runtime
├── data_visualization.ipynb        # Stage 2  (+ Stage-0 validation)
├── strategy_backtest.ipynb         # Stage 1  baseline carry (+ attribution / crash)
├── dynamic_carry.ipynb             # Stage 3  dynamic carry & risk management
├── portfolio_construction.ipynb    # Stage 4  weighting-scheme comparison
├── momentum_overlay.ipynb          # Stage 5  momentum overlay
├── regime_analysis.ipynb           # Stage 6  market-regime analysis
├── skew_carry.ipynb                # Phase 3 / D1  crash-risk-premium (skew) carry
└── outputs/                        # 26 committed result CSVs (deliverables — do not delete)
```

There is **no folder-local `.gitignore`** here on purpose: the repo-root `.gitignore`
already ignores `__pycache__/`, `.ipynb_checkpoints/`, and `.DS_Store` repo-wide, and
nothing under `cesare/` is mis-tracked (the `__pycache__/` build cache is untracked and
ignored). `outputs/*.csv` are intentionally committed artifacts.

## Notebooks → stage → key outputs

Summary of the artifact registry (Appendix A of the plan — see it for the full mapping and
the reasoning behind each verdict).

| Notebook | Stage | Verdict | Key output(s) in `outputs/` |
|---|---|---|---|
| `data_visualization.ipynb` | St2 — return drivers (+ St0 validation) | ✅ done | `summary_stats_carry_excess.csv`, `uip_fama.csv`, `cip_basis_summary.csv`, `regression_lrv.csv`, `regression_macro.csv` |
| `strategy_backtest.ipynb` | St1 — baseline carry (+ attribution/crash) | ✅ done | `strategy_returns_daily.csv`, `strategy_summary_stats.csv`, `strategy_costs_by_ccy.csv`, `weights_{g10,combined}_monthly.csv` |
| `dynamic_carry.ipynb` | St3 — dynamic carry / risk mgmt | ✅ done; timing rules null (per-ccy RR preferred as tail hedge) | `stage3_dynamic_comparison.csv` |
| `portfolio_construction.ipynb` | St4 — portfolio construction | ✅ done; **NO** — optimization doesn't beat inverse-vol | `stage4_weighting_comparison.csv`, `weights_{equal,inv_vol,erc,mvo}_monthly.csv` |
| `momentum_overlay.ipynb` | St5 — momentum overlay | ✅ done; **NO** — kept only as a regression factor | `stage5_momentum_comparison.csv`, `stage5_track_correlation.csv` |
| `regime_analysis.ipynb` | St6 — regime analysis | ✅ done; **reject as allocation, adopt as diagnostic** | `regime_series.csv`, `stage6_regime_stats.csv`, `stage6_conditional_by_regime.csv` |
| `skew_carry.ipynb` | Phase-3 D1 — skew carry | ✅ done; **REJECT (null)** — carry subsumes SRP | `skew_carry_comparison.csv`, `srp_carry_spanning.csv`, `skew_track_correlation.csv` |

## `fx_utils.py` — API at a glance

A single-file, pure-function library (no package, ~900 lines). You don't need to read it
all — the core is one processing chain, and the rest are helper groups called by the
notebooks.

**Panel chain** (raw parquet → tradable excess-return panel):

```
load_wide → spots_usd_per_fx → carry_panel → excess_returns → xret
```

`load_wide` reads a wide parquet group; `spots_usd_per_fx` re-expresses spot as USD-per-FX;
`carry_panel` builds annualized forward-implied carry `ln(S/F)`; `excess_returns` combines
spot log-returns with lagged carry accrual; `xret` is the resulting daily excess-return
DataFrame that nearly every downstream function consumes.

**Helper groups:**

- **Performance stats** — `summary_stats`, `max_drawdown`, `turnover`
- **Factors & regressions** — `dollar_factor`, `carry_hml_factor`, `nw_regression`
  (Newey–West HAC), `regression_table`, `zscore_xs`, `xs_residual`
- **Signals** — `momentum_panel`, `realized_skew_panel`, `implied_skew_panel`
- **Portfolio construction** — `carry_portfolio` (bucket-sort long/short with pluggable
  within-leg weighting), `vol_target_weights`, and the weighting schemes `shrunk_cov`,
  `erc_weights`, `mvo_weights`
- **Costs & returns** — `forward_halfspreads`, `roundtrip_cost`, `portfolio_returns`
- **Rates / CIP** — `load_rates_panel`, `interest_diff_vs_usd`, `cip_basis`
- **Risk / regime** — `exposure_scalar`, `regime_classify`
- **IO / benchmarks** — `load_benchmarks`, `benchmark_returns`, `load_em_risk`,
  `vol_surface_panel`

## Setup & run

1. **Python 3.13** (developed on 3.13.5).
2. Install deps: `pip install -r requirements.txt`.
   - **pyarrow caveat:** pyarrow must be **pip-installed over conda** in this env — conda's
     19.x build cannot read these parquet files (working build is 24.x). See
     `requirements.txt` and plan §5.2.
3. Launch the notebooks with the working directory set to `cesare/` (e.g. `cd cesare &&
   jupyter lab`). `fx_utils` is a bare top-level module — importing it relies on the cwd
   being `cesare/`. Run each notebook top-to-bottom.

**Data dependency (SHARED, repo-root):** `fx_utils` computes

```python
RAW_DIR = Path(__file__).resolve().parent.parent / "data" / "raw"   # = <repo_root>/data/raw
```

so all `cesare/` code reads the shared, repo-root **`../data/raw/*.parquet`** (13 parquet
groups, each stored wide + long). Those parquet snapshots are git-tracked, so the notebooks
are **reproducible without a Bloomberg terminal** (a terminal is only needed to *refresh*
the data via `src/`). Results are written to **`cesare/outputs/`**.

## Scope & collation note

This README covers **`cesare/` only**. This is a multi-person repo (siblings `theo/`,
`dafu/`, plus shared `notebooks/`, `src/`, `data/` at root); once each teammate has done
the same hygiene pass in their own folder, these will be merged into **one repo-wide
`README.md`** and **one `requirements.txt`**. To make that merge easy:

- **Shared** (expect overlap with teammates — dedup on collation): the `../data/raw/`
  parquet dependency; the carry benchmark indices (DBHVG10U, FXCTEM8, DBHVBUSI); the common
  Python stack (numpy, pandas, statsmodels, scipy, matplotlib, pyarrow); the root
  `.gitignore`.
- **Cesare-unique** (should not collide): `fx_utils.py` (the engine), the 7 stage
  notebooks, `cesare/outputs/*.csv`, and `seaborn` (imported only by
  `data_visualization.ipynb`).

## Reproducibility conventions

Baked into every stage (see plan §6 for the full guardrails):

- **Common evaluation window:** 2007-05 → 2026-06 (~5,000 trading days).
- **Sizing:** 10% annualized vol target, 60-day window, 4× leverage cap.
- **No lookahead:** signals sampled at month-end, weights `ffill().shift(1)` → effective the
  next trading day; trailing windows only.
- **Inference:** Newey–West HAC standard errors (5 lags daily / 3 lags monthly) via
  `nw_regression`.
- **Costs:** every variant reported **gross and net**, using `forward_halfspreads` +
  `roundtrip_cost`.
- **Universe:** peg/CNY exclusions and a 40% max single-name leg share are fixed unless a
  stage studies them.

Every number quoted in the plan is reproducible from a CSV in `outputs/`.
