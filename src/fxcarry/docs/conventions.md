# fxcarry.conventions

FX quote-convention normalization: Bloomberg-native quotes -> paper convention
(foreign-currency units per USD).

## Contents

- `to_fccu_per_usd(df, inverted=None)` — flip a single quote level (e.g. mid) for currencies in `inverted`.
- `to_fccu_per_usd_bid_ask(bid, ask, inverted=None)` — flip a bid/ask pair, swapping bid/ask sides for inverted currencies.
- `fwd_outright(spot, fwd_pts, point_scale=None)` — outright forward rate, `F = S + points / scale`.

## Ordering

Compute the outright forward in the native Bloomberg convention first
(`fwd_outright`), then flip to FCU-per-USD (`to_fccu_per_usd*`). Doing it in the
other order applies the forward points to the wrong (inverted) quote.
