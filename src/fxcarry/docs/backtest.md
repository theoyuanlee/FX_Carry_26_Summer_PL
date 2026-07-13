# fxcarry.backtest

Signal -> sort -> weight -> returns -> NAV loop.

## Contents

- `BacktestResult` (dataclass) — `gross_returns`, `net_returns`, `weights`, `nav`, `turnover`.
- `run_backtest(signal, panel, n_portfolios=6, cost_model=None)` — sorts `signal` into `n_portfolios` buckets, equal-weights within each, applies `cost_model`, and reports the long-top/short-bottom (HML) spread as the headline NAV/turnover series.
