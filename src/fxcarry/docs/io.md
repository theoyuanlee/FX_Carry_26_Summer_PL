# fxcarry.io

Load raw Bloomberg parquet pulls into tidy `(date x currency)` panels.

## Contents

- `load_spot(path, freq=..., tickers=None)` — spot quotes as `{"mid","bid","ask"}`, columns relabeled to ISO codes.
- `load_fwd_points(path, freq=..., tickers=None)` — same structure for 1M forward points.
- `load_yield_series(path, freq=..., field=..., periods_per_year=None)` — single-ticker annualized yield converted to a periodic simple rate.
- `coverage_summary(df)` — first/last non-null date and observation count per column.
- `validate_bid_ask(mid, bid, ask)` — flags `bid <= mid <= ask` violations.

## Input format

Handles both the classic (pre-1.0) xbbg wide `(ticker, field)` MultiIndex-column
shape and the long/tidy `ticker, date, field, value` shape returned by
Rust-powered xbbg (>=1.0). No currency universe, ticker, or file name is
hard-coded here — defaults live in `fxcarry.constants` and are passed in.
