"""Signal-agnostic backtest loop: signal -> sort -> weight -> returns -> NAV."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from . import metrics
from .costs import CostModel, ZeroCost
from .panel import FXPanel
from .portfolio import sort_to_portfolios


@dataclass
class BacktestResult:
    gross_returns: pd.DataFrame  # date x portfolio (all n_portfolios buckets, equal-weight, gross)
    net_returns: pd.DataFrame  # date x portfolio, net of `cost_model`
    weights: pd.DataFrame  # date x currency; long-top/short-bottom (HML) weights actually applied
    nav: pd.Series  # cumulative NAV of the net long-top/short-bottom (HML) spread
    turnover: pd.Series  # fxcarry.metrics.turnover applied to `weights`


def run_backtest(
    signal: pd.DataFrame,
    panel: FXPanel,
    n_portfolios: int = 6,
    cost_model: CostModel | None = None,
) -> BacktestResult:
    """Sort `signal` into `n_portfolios` buckets, equal-weight within each,
    apply `cost_model`, and report the long-top/short-bottom (HML) spread as
    the headline NAV/turnover series.

    Signals are "known as of" their own row date (see :mod:`fxcarry.signals`);
    this lags the sort by one row before pairing with `panel.rx` so a bucket
    formed at ``t`` only earns the return realized over ``(t, t+1]``.
    """
    cost_model = ZeroCost() if cost_model is None else cost_model

    labels = sort_to_portfolios(signal, n_portfolios)
    aligned_labels = labels.shift(1)
    gross_by_ccy = panel.rx

    gross_cols: dict[int, pd.Series] = {}
    net_cols: dict[int, pd.Series] = {}
    bucket_weights: dict[int, pd.DataFrame] = {}
    for p in range(1, n_portfolios + 1):
        mask = aligned_labels.eq(p)
        bucket_size = mask.sum(axis=1).replace(0, np.nan)
        w = mask.div(bucket_size, axis=0).fillna(0.0)
        net_unit = cost_model.net_return(gross_by_ccy, w)
        gross_cols[p] = (w * gross_by_ccy).sum(axis=1)
        net_cols[p] = (w * net_unit).sum(axis=1)
        bucket_weights[p] = w

    gross_returns = pd.DataFrame(gross_cols)
    net_returns = pd.DataFrame(net_cols)

    hml_weights = bucket_weights[n_portfolios] - bucket_weights[1]
    hml_net = net_returns[n_portfolios] - net_returns[1]
    nav = (1.0 + hml_net.fillna(0.0)).cumprod()
    turnover = metrics.turnover(hml_weights)

    return BacktestResult(
        gross_returns=gross_returns,
        net_returns=net_returns,
        weights=hml_weights,
        nav=nav,
        turnover=turnover,
    )
