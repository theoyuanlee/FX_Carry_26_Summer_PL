"""Aligned spot/forward FX panel -- the central data structure that every
signal, portfolio, and backtest function in this library consumes.

Notation:
  - ``s_t`` = log spot, ``f_t`` = log 1M forward, both in FCU-per-USD.
  - ``fwd_discount`` = ``f_t - s_t`` (~ CIP interest-rate differential ``i*_t - i_t``).
  - ``rx`` = ``f_t - s_{t+1}``: the log **currency (excess) return** on being
    long the foreign currency forward. This is *the* "Currency Return" used
    throughout the FX carry-trade literature (LRV, BER). It is indexed by
    the realization date ``t+1`` (row ``t+1`` uses ``f_t`` and ``s_{t+1}``),
    so it necessarily starts one period later than ``fwd_discount`` (no
    look-ahead by construction).

Signal convention (see :mod:`fxcarry.signals`): every signal is indexed by
the date the information became known, i.e. ``signal.loc[t]`` is safe to act
on starting at ``t``. Portfolio/backtest code (:mod:`fxcarry.portfolio`,
:mod:`fxcarry.backtest`) is responsible for lagging a signal by one row
before pairing it with ``rx`` -- nothing here pre-shifts for that.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import numpy as np
import pandas as pd

from . import constants as const
from . import io as fxio
from .conventions import fwd_outright, to_fccu_per_usd, to_fccu_per_usd_bid_ask


@dataclass
class FXPanel:
    spot: pd.DataFrame  # level (mid), date x ccy, FCU per USD
    fwd: pd.DataFrame  # level (mid), date x ccy, FCU per USD
    log_spot: pd.DataFrame  # s_t
    log_fwd: pd.DataFrame  # f_t
    fwd_discount: pd.DataFrame  # f_t - s_t
    rx: pd.DataFrame  # f_t - s_{t+1}  (gross currency excess return)
    rx_net_long: pd.DataFrame  # net of bid-ask, long FCU forward
    rx_net_short: pd.DataFrame  # net of bid-ask, short FCU forward
    currencies: list[str] = field(default_factory=list)

    @classmethod
    def from_raw(
        cls,
        data_dir: str | Path,
        freq: str = const.DEFAULT_FREQ,
        tickers: dict[str, tuple[str, str]] | None = None,
        spot_file: str = const.SPOT_FILE,
        fwd_file: str = const.FWD_FILE,
        inverted: set[str] | None = None,
        point_scale: dict[str, float] | None = None,
    ) -> "FXPanel":
        """Build a panel straight from the raw Bloomberg parquet pulls in
        ``data_dir`` (as written by ``notebooks/00_bloomberg_pull.ipynb``)."""
        data_dir = Path(data_dir)
        spot = fxio.load_spot(data_dir / spot_file, freq=freq, tickers=tickers)
        fwd_pts = fxio.load_fwd_points(data_dir / fwd_file, freq=freq, tickers=tickers)
        return cls.from_frames(spot, fwd_pts, inverted=inverted, point_scale=point_scale)

    @classmethod
    def from_frames(
        cls,
        spot: dict[str, pd.DataFrame],
        fwd_pts: dict[str, pd.DataFrame],
        inverted: set[str] | None = None,
        point_scale: dict[str, float] | None = None,
    ) -> "FXPanel":
        """Build a panel from already-loaded ``{"mid", "bid", "ask"}`` dicts
        (as returned by :func:`fxcarry.io.load_spot` / ``load_fwd_points``),
        still in Bloomberg's *native* quote convention.
        """
        common = spot["mid"].columns.intersection(fwd_pts["mid"].columns)
        spot = {side: df[common] for side, df in spot.items()}
        fwd_pts = {side: df[common] for side, df in fwd_pts.items()}

        # 1. Outright forward in native convention, for every quoted side.
        fwd_native = {
            side: fwd_outright(spot[side], fwd_pts[side], point_scale=point_scale)
            for side in ("mid", "bid", "ask")
        }

        # 2. Flip to FCU-per-USD. Bid/ask must be flipped together so
        #    inverted currencies swap sides correctly.
        spot_mid = to_fccu_per_usd(spot["mid"], inverted=inverted)
        fwd_mid = to_fccu_per_usd(fwd_native["mid"], inverted=inverted)
        spot_bid, spot_ask = to_fccu_per_usd_bid_ask(spot["bid"], spot["ask"], inverted=inverted)
        fwd_bid, fwd_ask = to_fccu_per_usd_bid_ask(fwd_native["bid"], fwd_native["ask"], inverted=inverted)

        log_spot = np.log(spot_mid)
        log_fwd = np.log(fwd_mid)
        fwd_discount = log_fwd - log_spot

        rx = log_fwd.shift(1) - log_spot
        rx_net_long = np.log(fwd_bid).shift(1) - np.log(spot_ask)
        rx_net_short = np.log(spot_bid) - np.log(fwd_ask).shift(1)

        return cls(
            spot=spot_mid,
            fwd=fwd_mid,
            log_spot=log_spot,
            log_fwd=log_fwd,
            fwd_discount=fwd_discount,
            rx=rx,
            rx_net_long=rx_net_long,
            rx_net_short=rx_net_short,
            currencies=list(common),
        )

    def currency_return(self, kind: str = "excess") -> pd.DataFrame:
        """The "Currency Return" series (date x currency).

        - ``kind="excess"`` (default): forward-implied excess return ``rx``
          (``f_t - s_{t+1}``) -- the standard FX carry-trade currency return,
          combining both the spot move and the interest-rate carry.
        - ``kind="spot"``: pure spot appreciation/depreciation, ``s_{t+1} - s_t``,
          with no interest/forward-carry component.
        """
        if kind == "excess":
            return self.rx
        if kind == "spot":
            return self.log_spot.diff()
        raise ValueError(f"Unknown kind={kind!r}; expected 'excess' or 'spot'.")
