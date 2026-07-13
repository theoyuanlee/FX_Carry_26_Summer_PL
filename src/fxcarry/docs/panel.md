# fxcarry.panel

`FXPanel` — the aligned spot/forward panel every signal, portfolio, and backtest
function in this library consumes.

## Notation

- `s_t` = log spot, `f_t` = log 1M forward, both in FCU-per-USD.
- `fwd_discount` = `f_t - s_t` (≈ CIP interest-rate differential `i*_t - i_t`).
- `rx` = `f_t - s_{t+1}`: the log currency (excess) return on being long the
  foreign currency forward. Indexed by the realization date `t+1`, so it starts
  one period later than `fwd_discount` (no look-ahead by construction).

## Contents

- `FXPanel` (dataclass) — `spot`, `fwd`, `log_spot`, `log_fwd`, `fwd_discount`, `rx`, `rx_net_long`, `rx_net_short`, `currencies`.
- `FXPanel.from_raw(data_dir, freq=..., tickers=None, spot_file=..., fwd_file=..., inverted=None, point_scale=None)` — build a panel from raw parquet files in `data_dir`. `data_dir` is caller-supplied — point it at any folder, such as your own personal data folder; nothing in this library assumes a shared location.
- `FXPanel.from_frames(spot, fwd_pts, inverted=None, point_scale=None)` — build a panel from already-loaded `{"mid","bid","ask"}` dicts.
- `FXPanel.currency_return(kind="excess")` — `"excess"` returns `rx`; `"spot"` returns pure spot log-returns with no carry component.

## Signal convention

Every signal (see `fxcarry.signals`) is indexed by the date the information
became known: `signal.loc[t]` is safe to act on starting at `t`. Portfolio/backtest
code lags a signal by one row before pairing it with `rx`; nothing in this module
pre-shifts for that.
