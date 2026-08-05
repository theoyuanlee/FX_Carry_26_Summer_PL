# `cesare/` — research track and Phase-4 integration

**Start here:** [`FX_Carry_Strategy_Project_Plan.md`](FX_Carry_Strategy_Project_Plan.md) is the
repo's **source of truth** — methodology, every stage verdict, the guardrails, and the Appendix A
output registry. This README is the scannable front door to the folder; the plan is the document
that decides anything.

This folder holds two things: the **research track** (Stages 0–6 and the Phase-3 differentiators,
one notebook per idea) and the **Phase-4 integration track** (seven modules that fold six
workstreams into one engine and produce the report's tables). All committed results are in
[`outputs/`](outputs/) — 59 CSVs, indexed in [`outputs/README.md`](outputs/README.md).

The headline finding: **the 2007–2026 currency premium is EM carry, not G10** — a vol-targeted,
inverse-vol long/short carry book in EM+G10 earns ~7.0%/yr gross (Sharpe **0.63** gross / **0.47**
net) versus ~1.9%/yr for a G10-only book (Sharpe 0.17). **Every overlay tried — dynamic hedges,
portfolio optimization, a momentum double-sort, regime timing, the D1 crash-skew signal, the D3
basis signal, the D6 term structure, and the P4-B learned tail forecast — fails to beat that simple
book net of costs.** The one qualified positive is the D2 volatility risk premium. Integration cuts
maximum drawdown by a third and adds no significant return.

> **The engine moved.** `fx_utils.py` now lives in the team-owned [`../strategy/`](../strategy/)
> package (plan §18), which also provides `run(config)` — the one base strategy every teammate's
> extension builds on. **`cesare/fx_utils.py` is a re-export shim and must stay**: eight of Arjun's
> notebooks and `arjun/arjun_utils.py` do `sys.path.insert(0, "../cesare"); import fx_utils`, and
> deleting it silently breaks them. New work should start from
> [`../strategy/README.md`](../strategy/README.md).

## Folder map

```
cesare/
├── FX_Carry_Strategy_Project_Plan.md   # SOURCE OF TRUTH — methodology, verdicts, Appendix A
├── DATA_SHOPPING_LIST.md               # what data would unlock what, and what it costs
├── README.md                           # this file
├── fx_utils.py                         # re-export shim -> ../strategy/fx_utils.py (load-bearing)
│
│   # --- research track: one notebook per idea, Stages 0-6 + D1 + D3 ---
├── data_visualization.ipynb            # Stage 2  return drivers (+ Stage-0 validation)
├── strategy_backtest.ipynb             # Stage 1  baseline carry (+ attribution / crash)
├── dynamic_carry.ipynb                 # Stage 3  dynamic carry & risk management
├── portfolio_construction.ipynb        # Stage 4  weighting-scheme comparison
├── momentum_overlay.ipynb              # Stage 5  momentum overlay
├── regime_analysis.ipynb               # Stage 6  market-regime analysis
├── skew_carry.ipynb                    # Phase 3 / D1  crash-risk-premium (skew) carry
├── basis_carry.ipynb                   # Phase 3 / D3  cross-currency-basis carry
│
│   # --- Phase-3 / Phase-4 modules: rebuilt weekly, so modules not notebook cells ---
├── bkm_skew.py                         # model-free risk-neutral skewness from the 5-point smile
├── d1_bkm_rerun.py                     # D1 battery re-run on true BKM skewness
├── d2_vrp.py                           # D2 the FX volatility risk premium
├── tail_forecast.py                    # P4-B tail-event forecast (the desk's central ask)
├── combined_engine.py                  # P4-C the combined engine  (load-bearing, see below)
├── final_evaluation.py                 # P4-A reporting tables + final_comparison
├── final_evaluation.ipynb              # thin display layer over final_evaluation.py
├── build_deck.py                       # generates the Aug 5 deck from committed CSVs
│
├── outputs/                            # 59 committed result CSVs (deliverables — do not delete)
├── presentations/                      # the three HTML decks
└── notes/                              # unsent drafts and superseded material
```

**Two couplings you must know about before moving anything here:**

1. **`fx_utils.py` is a shim for teammates**, not dead code. See the note above.
2. **`combined_engine.py` is imported by the shared base.** `strategy/config.py:252` does
   `from cesare.combined_engine import combined_components` and
   `strategy/tests/test_combined.py:117` imports `ADOPTED`. Renaming or moving it breaks
   `run("COMBINED")` and the 8/8 suite. `cesare/` works as an implicit namespace package — there is
   no `__init__.py` and there does not need to be. The reasoning is in the `combined_preset`
   docstring in [`../strategy/config.py`](../strategy/config.py); read it first.

Every module here also resolves its paths from `Path(__file__).resolve().parent`, and the notebooks
`import fx_utils` as a bare top-level module. **Both assume the file sits directly in `cesare/`**,
which is why this folder is flat rather than subdivided.

## Research track — notebook → stage → verdict → outputs

Summary of Appendix A; see the plan for the full mapping and the reasoning behind each verdict.

| Notebook | Stage | Verdict | Key output(s) |
|---|---|---|---|
| `data_visualization.ipynb` | St2 — return drivers (+ St0 validation) | ✅ done | `summary_stats_carry_excess.csv`, `uip_fama.csv`, `cip_basis_summary.csv`, `regression_{lrv,macro}.csv` |
| `strategy_backtest.ipynb` | St1 — baseline carry (+ attribution/crash) | ✅ done | `strategy_returns_daily.csv`, `strategy_summary_stats.csv`, `strategy_costs_by_ccy.csv`, `weights_{g10,combined}_monthly.csv` |
| `dynamic_carry.ipynb` | St3 — dynamic carry / risk mgmt | ✅ done; timing rules null (per-ccy RR preferred as tail hedge) | `stage3_dynamic_comparison.csv` |
| `portfolio_construction.ipynb` | St4 — portfolio construction | ✅ done; **NO** — optimization doesn't beat inverse-vol | `stage4_weighting_comparison.csv`, `weights_{scheme}_monthly.csv` |
| `momentum_overlay.ipynb` | St5 — momentum overlay | ✅ done; **NO** — kept only as a regression factor | `stage5_momentum_comparison.csv`, `stage5_track_correlation.csv` |
| `regime_analysis.ipynb` | St6 — regime analysis | ✅ done; **reject as allocation, adopt as diagnostic** | `regime_series.csv`, `stage6_regime_stats.csv`, `stage6_conditional_by_regime.csv` |
| `skew_carry.ipynb` | D1 — skew carry | ✅ done; **REJECT (null)** — carry subsumes SRP | `skew_carry_comparison.csv`, `srp_carry_spanning.csv`, `skew_track_correlation.csv` |
| `basis_carry.ipynb` | D3 — cross-currency basis | ✅ done; **REJECT (null)** — neither spans the other on the weak U7 universe | `basis_carry_comparison.csv`, `basis_carry_spanning.csv`, `basis_track_correlation.csv` |

Stages 3–6 were **re-verdicted on the desk's tail objective** in Phase 4 (plan §19.3); five of
twelve rules flip to accept. See `p4_reverdict_tail_objective.csv`.

## Phase-3 / Phase-4 modules

Modules rather than notebook cells because these are rebuilt every week through hand-in: a refresh
should be one function call, not a re-execute-all. All are run from the **repo root** and write to
`outputs/`.

| Module | What it does | Run |
|---|---|---|
| `bkm_skew.py` | Model-free risk-neutral skewness (Breeden–Litzenberger) from the 5-point smile. D1 originally used a 25Δ slope *proxy*; the 10Δ wings were in `data/raw` all along | library only |
| `d1_bkm_rerun.py` | Re-runs the D1 battery on true model-free skewness. The null survives | `python cesare/d1_bkm_rerun.py` |
| `d2_vrp.py` | D2 — the FX volatility risk premium, **the one qualified positive**. Solves for the breakeven bid/ask because `data/raw` has option mids only | `python cesare/d2_vrp.py` |
| `tail_forecast.py` | P4-B — forecasts tail events against a single VIX percentile threshold. **Loses; reported as the null it is** | `python cesare/tail_forecast.py` |
| `combined_engine.py` | P4-C — every teammate component *re-priced, not rebuilt*, then an add-one-in **and** leave-one-out ladder. Two of four components earn a slot | `python cesare/combined_engine.py` |
| `final_evaluation.py` | P4-A — the baseline window tables, per-leg decomposition, tenor sweep, tail re-verdict, and `final_comparison{,_by_episode}.csv` | `python cesare/final_evaluation.py` |
| `final_evaluation.ipynb` | Thin display layer over the above: base reconciliation, the flipped verdicts, the per-leg reading, narrated | run with cwd `cesare/` |
| `build_deck.py` | Builds `presentations/deck_2026_08_05.html` — every number read from a committed CSV and asserted against `run()` before the page is written | `python cesare/build_deck.py` |

## `fx_utils.py` — API at a glance

A single-file, pure-function library. The core is one processing chain; the rest are helper groups.
It lives in `../strategy/fx_utils.py`; this folder only re-exports it.

**Panel chain** (raw parquet → tradable excess-return panel):

```
load_wide → spots_usd_per_fx → carry_panel → excess_returns → xret
```

`load_wide` reads a wide parquet group; `spots_usd_per_fx` re-expresses spot as USD-per-FX;
`carry_panel` builds annualized forward-implied carry `ln(S/F)`; `excess_returns` combines spot
log-returns with lagged carry accrual; `xret` is the daily excess-return frame nearly every
downstream function consumes.

**Helper groups:**

- **Performance stats** — `summary_stats`, `max_drawdown`, `turnover`
- **Factors & regressions** — `dollar_factor`, `carry_hml_factor`, `nw_regression` (Newey–West
  HAC), `regression_table`, `zscore_xs`, `xs_residual`
- **Signals** — `momentum_panel`, `realized_skew_panel`, `implied_skew_panel`
- **Portfolio construction** — `carry_portfolio`, `vol_target_weights`, and the weighting schemes
  `shrunk_cov`, `erc_weights`, `mvo_weights`
- **Costs & returns** — `forward_halfspreads`, `roundtrip_cost` (tenor-aware since v1.1.0),
  `portfolio_returns`, `roll_schedule`
- **Rates / CIP** — `load_rates_panel`, `interest_diff_vs_usd`, `cip_basis`
- **Risk / regime** — `exposure_scalar`, `regime_classify`
- **IO / benchmarks** — `load_benchmarks`, `benchmark_returns`, `load_em_risk`, `vol_surface_panel`

## Setup & run

1. **Python 3.13** (developed on 3.13.5).
2. Install from the **repo-root** requirements file — it is authoritative for the whole repo
   (plan §14.5), and it covers everything this folder imports including `scikit-learn`
   (`tail_forecast.py`) and `seaborn` (`data_visualization.ipynb`):
   ```bash
   pip install -r requirements.txt        # from the repo root
   ```
   > **⚠ pyarrow must be the pip build (≥ 24).** Conda's 19.x cannot read this repo's parquet files
   > and fails in a way that looks like data corruption. Re-fix after any broad conda update with
   > `/opt/anaconda3/bin/pip install -U pyarrow`. See plan §5.2.
3. **Modules** run from the repo root (`python cesare/d2_vrp.py`). **Notebooks** run with the
   working directory set to `cesare/` (`cd cesare && jupyter lab`) — `fx_utils` is a bare top-level
   module, so importing it relies on the cwd. Run each notebook top to bottom.

**Data (SHARED, repo-root):** `fx_utils` computes `RAW_DIR = <repo_root>/data/raw`, so everything
here reads the shared `../data/raw/*.parquet` (13 groups, each stored wide + long). Those snapshots
are git-tracked, so **nothing here needs a Bloomberg terminal** — a terminal is only required to
*refresh* the data via `../src/`. Results are written to `cesare/outputs/`.

## Conventions

Baked into every stage. The full set is plan §6; these are the five you will trip over:

- **Common evaluation window** 2007-05 → 2026-06 (5,001 trading days).
- **Sizing** 10% annualized vol target, 60-day window, 4× leverage cap.
- **No lookahead** — signals sampled at month-end, weights `ffill().shift(1)`; trailing windows only.
- **Gross AND net**, always, via `forward_halfspreads` + `roundtrip_cost`. A result quoted without
  its cost drag is not a result.
- **Per window before whole-sample** — `strategy.episodes.report_windows` on the frozen `ERAS` /
  `STRESS` sets before any whole-sample number is quoted. Below ~120 trading days the code
  suppresses annualised ratios.

Every number quoted in the plan is reproducible from a CSV in [`outputs/`](outputs/).
