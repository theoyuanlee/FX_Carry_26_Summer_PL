"""Signals: panel + config -> DataFrame[date x currency] of scores.

Convention: a signal's row ``t`` must be computable from information known
*as of* date ``t`` (no look-ahead). Downstream portfolio/backtest code lags
signals by one row before pairing them with returns, so signal authors
should NOT pre-shift for that -- just return whatever is knowable at ``t``.
"""

from __future__ import annotations

from typing import Protocol

import pandas as pd

from .panel import FXPanel


class Signal(Protocol):
    def __call__(self, panel: FXPanel, **kwargs) -> pd.DataFrame:
        """Return per-date, per-currency scores. Higher = more long."""
        ...


def carry_signal(panel: FXPanel) -> pd.DataFrame:
    """Carry signal = forward discount (``f_t - s_t``), known as of ``t``.
    High discount -> go long."""
    return panel.fwd_discount


def momentum_signal(panel: FXPanel, lookback: int = 1) -> pd.DataFrame:
    """Momentum signal = sum of the trailing `lookback` currency returns,
    ending at (and known as of) date ``t``.

    BER (2011) use ``lookback=1``, i.e. the previous month's currency return
    -- since ``panel.rx`` is itself indexed by its *realization* date, the
    ``lookback=1`` case is simply ``panel.rx`` with no extra shift needed.
    """
    if lookback < 1:
        raise ValueError(f"lookback must be >= 1, got {lookback}")
    if lookback == 1:
        return panel.rx
    return panel.rx.rolling(lookback).sum()
