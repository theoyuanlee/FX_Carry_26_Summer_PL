# Macro and Option Information in Systematic FX Carry

Can option-implied and macro state variables improve FX carry by answering two different questions: what to hold, and when to be smaller?

## Overview

FX carry buys currencies trading at a forward discount and sells currencies trading at a forward premium. In this project, the baseline is a monthly 1M forward carry book formed from normalized spot and forward quotes, then extended from G10 into EM and finally conditioned on option-implied and macro risk information.

The central result is not a claim that a production trading edge has been validated. The strongest evidence is methodological and economic: option surfaces are more useful when selection and exposure control are separated, and macro variables are more informative about return magnitude and downside states than about the sign of next-month returns.

The final research layer evaluates a 20-currency G10+EM option/macro universe from January 2007 through June 2026 with chronological discovery, validation, and frozen evaluation samples. Earlier notebooks also analyze a broader 26-currency G10+EM carry universe without requiring option coverage.

## Research Questions

1. Does vanilla monthly FX carry survive realistic implementation assumptions?
2. What does EM add to G10 carry, and how much of the result is concentration in persistent high-carry currencies?
3. Do option-implied volatility, depreciation skew, and butterfly information help with currency selection or with exposure control?
4. Does macro information add incremental value after option-conditioned carry, or does it mostly repackage a defensive sizing rule?

## Key Findings

- **G10 carry is weak in this sample.** In the broader Notebook 04 carry comparison, the 9-currency G10 book has a gross Sharpe of 0.21 over 233 monthly returns from 2007-01-31 to 2026-05-31. At a 25 bp monthly roll-cost stress it becomes materially negative.
- **Adding EM changes the strategy economically.** EM ex-CNH has a gross Sharpe of 0.71, and the pooled G10+EM ex-CNH book has a gross Sharpe of 0.73 over the same 233-month sample. The improvement comes with meaningful EM concentration and sensitivity to roll-cost assumptions.
- **The final 20-currency option/macro baseline is a stronger but risky book.** In Notebook 08, pooled baseline carry earns 5.24% annualized at 9.07% volatility, gross Sharpe 0.58, and maximum drawdown -19.0% over 234 months.
- **Option information is not one mechanism.** Fixed-gross selection rules such as Core A+B keep average gross near 2.00 and raise full-sample Sharpe to 0.69. Variable-gross risk control such as Core A+C reaches Sharpe 0.70 with average gross only 1.14, so the drawdown improvement is partly lower exposure, not pure selection skill.
- **Macro evidence is broadest for risk, not mean returns.** Of 25 point-in-time macro features, Notebook 08 flags 3 with supported mean-return evidence, 4 with magnitude evidence, and 8 with tail-risk evidence. The macro overlays therefore scale exposure rather than change directional views.
- **The strict statistical screen is deliberately conservative.** Of 270 active non-reference strategies in Notebook 08's evaluated pool, 36 have raw HAC p-values below 0.05 on mean active return, but none has Benjamini-Hochberg q below 0.10. The Tier 1 robust shortlist is empty.

Selected full-sample gross results from the final Notebook 08 option/macro comparison:

| Strategy | Main mechanism | Ann. return | Vol. | Sharpe | Max DD | Avg. gross |
| --- | --- | ---: | ---: | ---: | ---: | ---: |
| Baseline carry | Pooled carry rank | 5.24% | 9.07% | 0.58 | -19.00% | 2.00 |
| G10-aware ATM conditioning | Fixed-gross selection | 5.70% | 8.93% | 0.64 | -20.81% | 2.00 |
| Butterfly-conditioned carry | Fixed-gross selection | 5.26% | 7.99% | 0.66 | -16.89% | 2.00 |
| Core A+B | Fixed-gross selection | 5.35% | 7.77% | 0.69 | -17.51% | 2.00 |
| Core A+C | Selection plus exposure control | 3.10% | 4.43% | 0.70 | -11.57% | 1.14 |
| OIL 50% gross-scaling overlay | Macro exposure control | 5.23% | 8.03% | 0.65 | -19.00% | 1.80 |

These are gross full-sample results. They should be read together with the cost, common-sample, evaluation-window, and multiple-testing audits in the later notebooks.

## Research Architecture

`FX data -> G10 carry -> turnover and roll costs -> EM extension -> concentration and robustness -> option regressions -> option-conditioned strategies -> macro risk overlays -> comprehensive strategy universe`

The conceptual split is:

- **What to hold?** Cross-sectional selection changes the ranking or composition of the long and short baskets while keeping gross exposure approximately fixed.
- **When to be smaller?** Exposure control scales the whole book, reducing gross exposure in riskier states without claiming better currency selection.

## Data and Universe

Theo's notebooks expect local market-data inputs outside this project directory and write generated research artifacts under `data/processed/` inside `theo/`. The public research materials are organized around the notebooks, formulas, strategy definitions, validation checks, and derived analytical outputs; licensed source-market data are not presented as public data assets.

The required input types are:

- G10 and EM spot and 1M forward data
- G10 and EM 1M FX option-surface data
- global risk and macro-market indicators
- interest-rate and risk-free-rate inputs
- ticker manifests and coverage diagnostics for mapping the local input schema

The G10 carry baseline uses AUD, CAD, CHF, EUR, GBP, JPY, NOK, NZD, and SEK. The broader EM carry extension begins with MXN, ZAR, BRL, KRW, IDR, MYR, PHP, CLP, COP, PEN, SGD, CNH, INR, THB, PLN, HUF, TRY, and ILS. The widest combined carry sample excludes CNH to preserve the 2007 start and ranks G10 and EM jointly rather than imposing fixed regional sleeves.

The final option-regression and option/macro strategy panel is narrower: 20 currencies, 234 formation months, and 4,680 currency-months from 2007-01-31 to 2026-06-30. It contains 9 G10 currencies and 11 EM currencies: BRL, HUF, ILS, INR, KRW, MXN, PLN, SGD, THB, TRY, and ZAR. IDR, MYR, PHP, CLP, COP, and PEN are outside the current option-signal panel; CNH is present in a 21-currency full panel but excluded from the primary option sample as a research choice and tested separately.

Signal panels include the final formation month even when the next-month realized return is not available. Return regressions and strategy evaluations use rows with realized one-month-ahead returns.

## Strategy Construction

### Carry Signal

Raw FX quotes are normalized to a consistent USD-per-unit-of-foreign-currency convention before carry is computed. This matters because some spot pairs are quoted as USD per foreign currency and others as local currency per USD, and because many 1M forward inputs are stored as forward points rather than outright forwards.

The canonical downstream log carry signal is:

$$
c_{i,t}=\log\left(\frac{S_{i,t}}{F^{1M}_{i,t}}\right)
$$

where \(S_{i,t}\) is normalized spot and \(F^{1M}_{i,t}\) is the normalized one-month forward outright. Positive carry means the foreign currency is at a forward discount and is a candidate long in the carry book.

### Realized Forward Return

The realized one-month forward excess return is:

$$
r_{i,t+1}=\log\left(\frac{S_{i,t+1}}{F^{1M}_{i,t}}\right)
$$

The notebooks explicitly audit the identity:

$$
r_{i,t+1}=c_{i,t}+\log\left(\frac{S_{i,t+1}}{S_{i,t}}\right)
$$

This separates the known carry component at formation from the spot move realized during the holding period.

### Portfolio Construction

Portfolios are formed monthly. Each month, available currencies are ranked by carry, the high-carry basket is held long, and the low-carry basket is held short. Weights are equal within each leg, net exposure is approximately zero, and the baseline gross exposure is 2.00.

For the G10-only baseline, the notebooks use the top 3 and bottom 3 of 9 currencies. In the broader G10+EM stage, the leg size is dynamic: at least 3 currencies per side when the universe has 6 or more currencies, approximately the top and bottom 20%, and no more than half the universe. For the combined universe, G10 and EM are ranked in one pooled cross-section.

### Transaction Costs

The notebooks distinguish two cost concepts:

- **Basket rebalancing turnover:** cost is applied to changes in portfolio weights. In the G10 baseline, average monthly rebalancing turnover is 0.246 and the median is 0 because carry rankings are persistent.
- **Forward-roll notional:** cost is applied to the gross notional of forwards that must be rolled every month. A 2.00-gross long-short book has monthly gross roll notional near 2.00 even when basket membership does not change.

Cost scenarios are fixed-basis-point assumptions because the processed G10 panel does not preserve bid/ask spread columns. Earlier G10 work uses 1, 2, and 5 bp rebalancing-cost cases and 1, 2, 5, and 10 bp roll-cost cases; the EM extension also stresses 25 and 50 bp monthly roll costs.

## Option-Implied Risk Signals

The option layer uses one-month option information and standardizes option variables cross-sectionally within asset class each month. Carry itself remains raw.

### ATM Volatility

`atm_vol_1m` measures the one-month at-the-money implied volatility level. It is especially useful as a risk variable: in the option regressions, ATM volatility is strongly associated with absolute returns, squared returns, and severe-loss probabilities. The G10 carry-by-ATM interaction is the clearest mean-return interaction result.

### Depreciation Skew

`depreciation_skew_25d_1m` is defined so positive values mean depreciation protection on the foreign currency is more expensive:

$$
D_{i,t}=IV(\text{foreign-currency put})-IV(\text{foreign-currency call})
$$

This converts raw risk-reversal conventions into a common economic sign. The README uses "depreciation skew" rather than legacy informal labels.

### Butterfly

`bf25_1m` captures 25-delta smile curvature. Economically, high butterfly means both wings are expensive, so the market is pricing fatter tails. Butterfly appears more informative for risk and for some carry interactions than as a simple unconditional return predictor.

### Selection vs Exposure Control

Selection strategies alter the ranking score before the long-short baskets are chosen. Exposure-control strategies multiply weights after selection, so they can lower drawdowns by carrying less gross risk. Notebook 08's gross-matched and exposure-aware comparisons are designed to avoid treating lower exposure as if it were pure selection skill.

## Macro Risk Conditioning

Notebook 08 adds 25 formation-time macro features from 11 market series: VIX, JPMVXYEM, MOVE, DXY, SPX, MXEF, broad commodities, oil, the US 2-year yield, the US 10-year yield, and the 2s10s curve.

Features include levels, one-month changes, three-month momentum, one-month log returns, equity drawdowns, and lower-tail return labels. The month-\(t\) feature observation is measured at formation time, while the normalization mean, standard deviation, and rolling event thresholds are estimated strictly from lagged history using a trailing 60-month window with at least 24 observations. A risk-sign multiplier makes all features direction-normalized: high VIX is risky, low oil or EM equity returns are risky, and so on.

The macro regressions separate predictive formation-time regressions from contemporaneous holding-period regressions. They also separate mean returns, magnitude outcomes, and tail outcomes. Since the predictive evidence is broader for downside and magnitude than for mean returns, macro strategies are implemented primarily as exposure overlays: a rolling 80th/20th percentile risk event halves the parent strategy's weights instead of changing the currency ranking.

## Research Progression / Notebook Guide

| Notebook | Role in the Research |
| --- | --- |
| `01_build_core_carry_panel.ipynb` | Normalizes G10 spot and 1M forward quotes and builds the initial monthly carry panel. |
| `02_g10_carry_baseline.ipynb` | Constructs the vanilla equal-weight G10 long-short carry benchmark. |
| `03_transaction_costs_and_turnover.ipynb` | Separates rebalancing turnover from recurring forward-roll costs for the G10 benchmark. |
| `04_em_carry_extension.ipynb` | Builds the EM carry panel and compares G10, EM, EM including CNH, and pooled G10+EM carry. |
| `05_em_carry_robustness_and_attribution.ipynb` | Tests EM concentration, currency exclusions, weight caps, volatility targeting, and attribution. |
| `06_options_filter_regression.ipynb` | Provides the rigorous option-signal panel and regression ladder for carry, ATM volatility, depreciation skew, and butterfly. |
| `06_options_skew_and_vol_filters.ipynb` | Explores option-filtered carry variants and long-leg-specific option risk filters. |
| `07_option_conditioned_carry_strategy.ipynb` | Converts option regression evidence into implementable fixed-gross selection and variable-gross scaling strategies. |
| `08_comprehensive_carry_strategy_optimization.ipynb` | Integrates option architectures with macro features, sample splits, no-look-ahead audits, cost tests, and multiple-testing controls. |
| `09_comprehensive_strategy_universe_and_interactive_explorer.ipynb` | Expands beyond Notebook 08's 271-strategy canonical pool into 371 canonical records by adding historical, robustness, and exploratory configurations from the option-strategy lineage, then deduplicates configurations, builds leaderboards, and provides an interactive explorer. |
| `data_preview.ipynb` | Supporting utility for inspecting raw data coverage, ticker groups, and recommended clean samples. |

## Validation and Robustness

The project uses several guardrails:

- Chronological sample splits: discovery 2007-01-31 to 2018-08-31, validation 2018-09-30 to 2022-07-31, and frozen evaluation 2022-08-31 to 2026-06-30.
- Point-in-time feature construction with lagged historical normalization and rolling event thresholds.
- No-look-ahead audits across macro signals, option signals, weights, and strategy return timing; the final Notebook 09 summary reports zero future-horizon violations.
- Common-sample comparisons, independent price/return reconstruction, and reconciliation of Notebook 07 streams inside Notebook 08.
- HAC/Newey-West inference for time-series strategy tests, and panel inference checks for option regressions, including clustered standard errors where valid.
- Transaction-cost sensitivity, crisis-period analysis, leave-one-currency-out tests, weight caps, volatility-targeting checks, strategy deduplication, and primary/robustness/exploratory labels.
- Multiple-testing correction over Notebook 08's 270 active non-reference strategies. Notebook 09 is a broader catalog and explorer: it retains the Notebook 08 evaluation pool while expanding the historical configuration universe to 371 canonical strategy records. The final statistical conclusion is intentionally restrained: no active strategy survives the Benjamini-Hochberg threshold used in Notebook 08.

## Repository Structure

```text
repo/
└── theo/
    ├── 01_build_core_carry_panel.ipynb
    ├── 02_g10_carry_baseline.ipynb
    ├── 03_transaction_costs_and_turnover.ipynb
    ├── 04_em_carry_extension.ipynb
    ├── 05_em_carry_robustness_and_attribution.ipynb
    ├── 06_options_filter_regression.ipynb
    ├── 06_options_skew_and_vol_filters.ipynb
    ├── 07_option_conditioned_carry_strategy.ipynb
    ├── 08_comprehensive_carry_strategy_optimization.ipynb
    ├── 09_comprehensive_strategy_universe_and_interactive_explorer.ipynb
    ├── data/
    │   └── processed/               # generated panels, strategy returns, audits, and figures
    ├── data_preview.ipynb
    └── slides/
        ├── options_signals.pdf
        ├── macro_option_signals_presentation.pdf
        └── macro_option_signals_document.pdf
```

## Reproduction

From the repository root:

```bash
pip install -r requirements.txt
jupyter notebook theo/
```

Run the notebooks in numeric order. The later notebooks assume earlier processed artifacts exist under `theo/data/processed/`, especially the carry panels, option-signal panel, strategy weights, strategy returns, and audit files.

The research code and methodology are reproducible from the repository: notebooks, formulas, strategy definitions, transformations, validation procedures, and derived analytical outputs are documented in the project files. Rebuilding the source panels from scratch requires access to licensed market data, or equivalent inputs mapped into the expected local schema used by the notebooks.

The main runtime dependencies are `numpy`, `pandas`, `pyarrow`, `matplotlib`, `statsmodels`, `nbformat`, `jupyter`, and `ipykernel`. The root `requirements.txt` documents the project environment. Any source-data refresh requires access to the licensed market-data provider and the corresponding data-access environment.

## Limitations

- The project relies on licensed market data that are not redistributed as part of the public research materials; full source-level reproduction therefore requires equivalent data access.
- The option-covered primary universe is narrower than the broader carry universe and excludes some EM currencies used in the carry-only extension.
- EM forward liquidity, market impact, capacity, and bid/ask costs are simplified through fixed-basis-point scenarios rather than full executable quote histories.
- The frozen evaluation window is only 47 months, too short to resolve small Sharpe differences.
- Many later strategy variants are exploratory or robustness configurations, not independent out-of-sample hypotheses.
- Variable-gross strategies improve drawdown partly by carrying less risk; those gains are not equivalent to fixed-gross selection alpha.
- The project identifies associations between macro/option variables and carry outcomes, not causal relationships.

## Data Availability

Raw licensed market data are not redistributed. The repository provides the research code, methodology, strategy definitions, validation procedures, and derived analytical outputs required to understand and audit the study. Rebuilding the source panels from scratch requires access to equivalent licensed market data conforming to the expected input schema. Do not treat the saved strategy universe as a menu of validated trading rules; it is a research audit trail showing which mechanisms were tested, which comparisons were fair, and where evidence did not survive stricter validation.
