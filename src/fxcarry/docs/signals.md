# fxcarry.signals

Turn a panel + config into a `(date x currency)` grid of scores.

## Contents

- `Signal` (Protocol) — `(panel, **kwargs) -> DataFrame`; higher score = more long.
- `carry_signal(panel)` — forward discount `f_t - s_t`.
- `momentum_signal(panel, lookback=1)` — trailing sum of currency returns; `lookback=1` (BER default) is just `panel.rx`.

## Convention

A signal's row `t` must be computable from information known as of `t` (no
look-ahead). Downstream portfolio/backtest code lags signals by one row before
pairing them with returns — signal functions should not pre-shift.
