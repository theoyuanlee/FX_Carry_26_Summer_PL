"""FX quote-convention normalization: Bloomberg native quotes -> paper convention.

The papers (LRV, BER) express every rate as **foreign-currency units (FCU)
per USD**, so an *increase* in the spot rate means USD appreciation.
Bloomberg quotes several major currencies "inverted" relative to that (USD
per 1 FCU), e.g. ``EURUSD``, ``GBPUSD``, ``AUDUSD``, ``NZDUSD``.

This module never hard-codes *which* currencies are inverted or what
forward-point scale to use -- see :mod:`fxcarry.constants`. It only
implements the transformations, defaulting to those constants.

Ordering matters: forward points are always quoted as pips to add directly
to the *native* Bloomberg spot quote. Compute the outright forward in the
native convention first (:func:`fwd_outright`), then flip to FCU-per-USD
(:func:`to_fccu_per_usd` / :func:`to_fccu_per_usd_bid_ask`) -- doing it in
the other order would apply the pips to the wrong (inverted) quote.
"""

from __future__ import annotations

import pandas as pd

from . import constants as const


def to_fccu_per_usd(df: pd.DataFrame, inverted: set[str] | None = None) -> pd.DataFrame:
    """Flip currencies quoted USD-per-FCU into FCU-per-USD (``1/x``).

    Use for a single quote level (e.g. mid). For bid/ask pairs use
    :func:`to_fccu_per_usd_bid_ask` instead, since inverting also swaps which
    side is the bid and which is the ask.

    Columns not present in ``inverted`` are passed through unchanged.
    """
    inverted = const.INVERTED if inverted is None else inverted
    out = df.copy()
    flip_cols = [c for c in out.columns if c in inverted]
    if flip_cols:
        out[flip_cols] = 1.0 / out[flip_cols]
    return out


def to_fccu_per_usd_bid_ask(
    bid: pd.DataFrame,
    ask: pd.DataFrame,
    inverted: set[str] | None = None,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Flip a bid/ask pair into FCU-per-USD, correctly swapping bid<->ask for
    inverted currencies (``1/ask`` becomes the new bid, ``1/bid`` becomes the
    new ask, since ``ask >= bid > 0`` implies ``1/ask <= 1/bid``).

    Returns ``(new_bid, new_ask)``.
    """
    inverted = const.INVERTED if inverted is None else inverted
    common = bid.columns.intersection(ask.columns)
    bid, ask = bid[common], ask[common]

    flip_cols = [c for c in common if c in inverted]
    keep_cols = [c for c in common if c not in inverted]

    new_bid = pd.concat([bid[keep_cols], (1.0 / ask[flip_cols])], axis=1)
    new_ask = pd.concat([ask[keep_cols], (1.0 / bid[flip_cols])], axis=1)
    return new_bid.reindex(columns=common), new_ask.reindex(columns=common)


def fwd_outright(
    spot: pd.DataFrame,
    fwd_pts: pd.DataFrame,
    point_scale: dict[str, float] | None = None,
) -> pd.DataFrame:
    """Outright forward rate: ``F = S + forward_points / scale``.

    ``spot`` and ``fwd_pts`` must both be in Bloomberg's *native* quote
    convention (before any inversion) -- see the module docstring.
    """
    scale_map = const.POINT_SCALE if point_scale is None else point_scale
    default_scale = scale_map.get("default", 10000.0)
    common = spot.columns.intersection(fwd_pts.columns)
    scales = pd.Series({ccy: scale_map.get(ccy, default_scale) for ccy in common})
    return spot[common] + fwd_pts[common].div(scales, axis=1)
