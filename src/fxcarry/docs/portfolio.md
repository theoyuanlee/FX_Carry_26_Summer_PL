# fxcarry.portfolio

Signal-agnostic sort/bucket/weight construction and the BER-style equally-weighted
strategy.

## Contents

- `sort_to_portfolios(signal, n_portfolios, ascending=True)` — rank currencies by `signal` each date, assign to `1..n_portfolios`.
- `portfolio_returns(labels, returns, n_portfolios, weighting="equal")` — portfolio-level returns, lagging `labels` by one row. Only `"equal"` weighting is implemented.
- `hml_factor(portfolio_returns)` — highest portfolio minus lowest.
- `dollar_factor(portfolio_returns)` — average return across all portfolios.
- `ew_strategy_return(signal, returns)` — BER-style `+-1/N` equally-weighted strategy return, not sorted into buckets.

## No-look-ahead

Every function lags its signal/labels by one row before pairing with the return
realized over `(t, t+1]`.
