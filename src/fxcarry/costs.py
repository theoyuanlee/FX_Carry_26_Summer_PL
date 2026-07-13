"""Transaction-cost models.

A :class:`CostModel` maps a (date x currency) grid of gross per-unit returns
and the weights applied to it into a (date x currency) grid of net-of-cost
per-unit returns. Callers (e.g. :func:`fxcarry.backtest.run_backtest`) then
weight-sum the result themselves -- cost models only decide *which* return
(gross, long-leg, or short-leg) applies to each cell.
"""

from __future__ import annotations

from typing import Protocol

import pandas as pd

from .panel import FXPanel


class CostModel(Protocol):
    def net_return(
        self, gross_return: pd.DataFrame, weights: pd.DataFrame
    ) -> pd.DataFrame:
        """Return net-of-cost per-unit returns, same shape as `gross_return`."""
        ...


class ZeroCost:
    """No transaction costs (for gross return comparison)."""

    def net_return(self, gross_return: pd.DataFrame, weights: pd.DataFrame) -> pd.DataFrame:
        return gross_return


class BidAskCost:
    """Use the panel's bid-ask legs to compute net-of-cost returns.

    Where `weights` is positive (long the currency), substitutes
    ``panel.rx_net_long``; where negative (short), substitutes
    ``panel.rx_net_short``; flat (zero-weight) cells pass through
    `gross_return` unchanged (harmless, since they get multiplied by a zero
    weight downstream anyway).
    """

    def __init__(self, panel: FXPanel):
        self.panel = panel

    def net_return(self, gross_return: pd.DataFrame, weights: pd.DataFrame) -> pd.DataFrame:
        long_leg = self.panel.rx_net_long.reindex_like(gross_return)
        short_leg = self.panel.rx_net_short.reindex_like(gross_return)

        out = gross_return.where(weights <= 0, long_leg)
        out = out.where(weights >= 0, short_leg)
        return out
