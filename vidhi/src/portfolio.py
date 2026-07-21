from __future__ import annotations

import math

import numpy as np
import pandas as pd

from .features import annualized_vol

TRADING_DAYS = 252


def cross_sectional_carry_weights(
    carry: pd.DataFrame,
    returns: pd.DataFrame,
    long_fraction: float = 0.30,
    short_fraction: float = 0.30,
    vol_window: int = 60,
) -> pd.DataFrame:
    """Create dollar-neutral inverse-volatility weights from carry rankings."""
    vol = annualized_vol(returns, vol_window).replace(0, np.nan)
    inverse_vol = 1.0 / vol

    weights = pd.DataFrame(0.0, index=carry.index, columns=carry.columns)

    for date in carry.index:
        score = carry.loc[date].dropna()
        if len(score) < 4:
            continue

        number_long = max(1, int(math.ceil(len(score) * long_fraction)))
        number_short = max(1, int(math.ceil(len(score) * short_fraction)))

        long_names = score.nlargest(number_long).index
        short_names = score.nsmallest(number_short).index

        long_iv = inverse_vol.loc[date, long_names].replace([np.inf, -np.inf], np.nan).dropna()
        short_iv = inverse_vol.loc[date, short_names].replace([np.inf, -np.inf], np.nan).dropna()

        if not long_iv.empty:
            weights.loc[date, long_iv.index] = 0.5 * long_iv / long_iv.sum()
        if not short_iv.empty:
            weights.loc[date, short_iv.index] = -0.5 * short_iv / short_iv.sum()

    return weights


def portfolio_returns(
    returns: pd.DataFrame,
    weights: pd.DataFrame,
    transaction_cost_bps: float = 0.0,
) -> tuple[pd.Series, pd.Series, pd.Series]:
    """Calculate gross return, net return, and one-way turnover."""
    aligned_weights = weights.reindex(returns.index).ffill().fillna(0.0)
    gross = (aligned_weights.shift(1) * returns).sum(axis=1)
    turnover = aligned_weights.diff().abs().sum(axis=1).fillna(0.0)
    costs = turnover * transaction_cost_bps / 10_000.0
    net = gross - costs

    return (
        gross.rename("gross_return"),
        net.rename("net_return"),
        turnover.rename("turnover"),
    )


def volatility_target_scalar(
    returns: pd.Series,
    target: float = 0.10,
    window: int = 60,
    leverage_cap: float = 4.0,
) -> pd.Series:
    """Lagged exposure scalar targeting annualized portfolio volatility."""
    realized = annualized_vol(returns, window)
    scalar = (target / realized).clip(lower=0.0, upper=leverage_cap)
    return scalar.shift(1).fillna(0.0)
