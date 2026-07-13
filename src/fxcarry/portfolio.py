"""Generic, signal-agnostic sort-based portfolio construction.

This module knows nothing about "carry" or "momentum" -- it only knows how
to rank, bucket, weight, and combine currencies given a signal and a return
grid. The one thing every function here is responsible for is the
no-look-ahead lag: signals are "known as of t" (see :mod:`fxcarry.signals`),
so they are shifted one row forward before being paired with the return
realized over ``(t, t+1]`` (``panel.rx`` at row ``t+1``).
"""

from __future__ import annotations

import numpy as np
import pandas as pd


def sort_to_portfolios(
    signal: pd.DataFrame,
    n_portfolios: int,
    ascending: bool = True,
) -> pd.DataFrame:
    """Each date, rank currencies by `signal` and assign to portfolios
    ``1..n_portfolios`` (1 = lowest signal if ``ascending=True``).

    Returns a frame of the same shape as `signal` with integer portfolio
    labels (float dtype to allow NaN where the signal itself is missing).
    """

    def _bucket_row(row: pd.Series) -> pd.Series:
        valid = row.dropna()
        if valid.empty:
            return pd.Series(np.nan, index=row.index)
        ranks = valid.rank(method="first", ascending=ascending)
        buckets = np.ceil(ranks / len(valid) * n_portfolios).clip(1, n_portfolios)
        return buckets.reindex(row.index)

    return signal.apply(_bucket_row, axis=1)


def portfolio_returns(
    labels: pd.DataFrame,
    returns: pd.DataFrame,
    n_portfolios: int,
    weighting: str = "equal",
) -> pd.DataFrame:
    """Portfolio-level returns (date x portfolio), lagging `labels` by one
    row so a bucket formed at ``t`` earns the return realized at ``t+1``.

    ``weighting``: ``"equal"`` (both papers). ``"inv_vol"`` is a documented
    future extension point, not yet implemented.
    """
    if weighting != "equal":
        raise NotImplementedError(
            f"weighting={weighting!r} is not implemented yet; only 'equal' is supported."
        )

    aligned_labels = labels.shift(1)
    out: dict[int, pd.Series] = {}
    for p in range(1, n_portfolios + 1):
        mask = aligned_labels.eq(p)
        bucket_size = mask.sum(axis=1).replace(0, np.nan)
        w = mask.div(bucket_size, axis=0).fillna(0.0)
        out[p] = (w * returns).sum(axis=1)
    return pd.DataFrame(out)


def hml_factor(portfolio_returns: pd.DataFrame) -> pd.Series:
    """High-minus-low: return of the last portfolio minus the first
    (columns sorted ascending, so this is P_max - P_min)."""
    cols = sorted(portfolio_returns.columns)
    return portfolio_returns[cols[-1]] - portfolio_returns[cols[0]]


def dollar_factor(portfolio_returns: pd.DataFrame) -> pd.Series:
    """DOL: average return across all portfolios."""
    return portfolio_returns.mean(axis=1)


def ew_strategy_return(
    signal: pd.DataFrame,
    returns: pd.DataFrame,
) -> pd.Series:
    """Equally-weighted strategy return: each currency with a valid signal
    gets a ``+-1/N`` weight based on ``sign(signal)`` (``N`` = number of
    currencies with a valid signal that date). This is the BER-style
    carry/momentum portfolio (not sorted into buckets).

    Lags `signal` by one row for the same no-look-ahead reason as
    :func:`portfolio_returns`.
    """
    direction = np.sign(signal)
    n_valid = signal.notna().sum(axis=1).replace(0, np.nan)
    weights = direction.div(n_valid, axis=0)
    aligned_weights = weights.shift(1)
    return (aligned_weights * returns).sum(axis=1)
