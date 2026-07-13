# fxcarry.costs

Transaction-cost models applied on top of gross returns.

## Contents

- `CostModel` (Protocol) — `net_return(gross_return, weights) -> DataFrame`.
- `ZeroCost` — passes gross returns through unchanged.
- `BidAskCost(panel)` — substitutes `panel.rx_net_long` where `weights > 0` and `panel.rx_net_short` where `weights < 0`.
