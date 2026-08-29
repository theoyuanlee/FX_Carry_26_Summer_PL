# Adaptive FX Carry: When Carry Works

> ### How this work landed
> **Macro/regime probability gate → REJECTED.** Measured on the common book it was the most
> destructive component tested: standalone net Sharpe **0.0964** against the baseline's 0.4659, a
> drag of **−0.3695**, and removing it from the combined stack was worth 0.332. Evidence:
> `final/evidence/p4_component_standalone.csv` and `p4_combined_ladder.csv`.
>
> That verdict is about this specific gate on this specific book, and it is consistent with the
> project's central finding rather than an outlier from it — **every** exposure-timing rule tested
> here came back null, because carry compensates a priced risk and de-risking on risk indicators
> sells the premium roughly one-for-one. Nine attempts failed the same way.
> Full detail in [`../final/VERDICTS.md`](../final/VERDICTS.md).
>
> One output of this workstream **is** vendored into the hand-off package:
> `outputs/adaptive_strategy_returns_monthly.csv`, in [`../final/inputs/`](../final/inputs/).

Test for an independent regime-aware FX carry research built on shared G10 and EM datasets.

The objective is to research how can the losses be contained under a carry strategy, rather than focusing on increasing the profits.

## Research question

> Can observable market, macroeconomic, rates, and FX conditions identify when a
> conventional carry portfolio should be scaled up, scaled down, or avoided?

The project first builds a transparent static carry benchmark. It then tests
whether an expanding-window regime model improves the benchmark out of sample,
after transaction costs.

## Repository structure

```text
repo_root/
├── data/
│   └── raw/
│       ├── em_fx_spot_forward_wide.parquet
│       ├── g10_fx_spot_forward_wide.parquet
│       ├── em_interest_rates_wide.parquet
│       ├── g10_interest_rates_wide.parquet
│       ├── em_onshore_rates_wide.parquet
│       ├── g10_rates_gaps_wide.parquet
│       ├── em_risk_wide.parquet
│       ├── global_risk_wide.parquet
│       ├── macro_market_proxies_wide.parquet
│       ├── usd_riskfree_wide.parquet
│       └── ...
└── vidhi/
    ├── README.md
    ├── requirements.txt
    ├── notebooks/
    │   ├── 01_data_audit.ipynb
    │   ├── 02_baseline_carry.ipynb
    │   ├── 03_regime_model.ipynb
    │   └── 04_adaptive_backtest.ipynb
    ├── src/
    │   ├── __init__.py
    │   ├── data_loader.py
    │   ├── features.py
    │   ├── portfolio.py
    │   ├── models.py
    │   └── evaluation.py
    ├── tests/
    │   └── test_core.py
    └── outputs/
```

## Strategy design

### Static carry benchmark

1. Load G10 and EM spot and one-month forward prices.
2. Convert every currency to a common quotation convention.
3. Calculate annualized forward-implied carry.
4. Rank currencies cross-sectionally at month-end.
5. Long high-carry currencies and short low-carry currencies.
6. Use inverse-volatility weights inside each leg.
7. Apply a portfolio volatility target.
8. Deduct turnover-based transaction costs.

### Adaptive overlay

Candidate state variables include:

- global and EM risk proxies;
- macro and market proxies;
- offshore and onshore interest rates;
- onshore/offshore rate gaps;
- changes in volatility and broad USD conditions;
- carry dispersion;
- trailing carry momentum, volatility, and drawdown.

The first model is an interpretable expanding-window logistic regression that
estimates the probability that next month's carry return will be positive.

The strategy comparison is:

```text
Static carry
vs
Binary regime filter
vs
Probability-scaled carry
vs
Simple volatility-timing benchmark
```

## Notebook workflow

### `01_data_audit.ipynb`

Inspects every raw file and saves:

- `outputs/data_inventory.csv`
- `outputs/column_inventory.csv`

This notebook automatically detects spot and one-month forward fields, matches them
by currency, determines quotation direction, and writes
`outputs/fx_field_diagnostics.csv` for review.

### `02_baseline_carry.ipynb`

Builds the static G10+EM carry benchmark and saves:

- carry scores;
- portfolio weights;
- gross and net returns;
- benchmark performance statistics.

The notebook uses the automatic field-discovery report from Notebook 01. Ambiguous
currencies are excluded rather than silently guessed, and all accepted pairs are
converted to a common USD-per-foreign-currency quotation.

### `03_regime_model.ipynb`

Combines macro, risk, rates, and strategy-state variables and generates
strictly expanding-window probability forecasts.

### `04_adaptive_backtest.ipynb`

Compares static and adaptive strategies, evaluates performance by predicted
market condition, and produces the final tables and cumulative-return plots.

## Required evaluation

Report all strategies gross and net of costs:

- annualized return and volatility;
- Sharpe and Sortino ratios;
- maximum drawdown and Calmar ratio;
- hit rate and turnover;
- rolling and subperiod performance;
- performance under risk-on, neutral, and risk-off conditions;
- model coefficient stability;
- threshold, cost, and volatility-window sensitivity.

A higher full-sample Sharpe is not sufficient. The adaptive model should only be
considered successful if its improvement survives in an untouched test period
and under reasonable implementation assumptions.
