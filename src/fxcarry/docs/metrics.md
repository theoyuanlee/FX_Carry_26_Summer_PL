# fxcarry.metrics

Performance and risk metrics for return series.

## Contents

- `sharpe_ratio(returns, annualize=...)` — annualized Sharpe ratio.
- `max_drawdown(cumulative)` — maximum peak-to-trough drawdown.
- `skewness(returns)`, `kurtosis(returns, excess=True)` — sample skew/kurtosis.
- `turnover(weights)` — average absolute change in weights per rebalance.
- `newey_west_se(returns, lags=None)` — HAC standard error of the mean.
- `summary_table(returns, annualize=..., nw_lags=None)` — one-row-per-column table of mean, std, Sharpe, skew, kurtosis, and NW standard error.
