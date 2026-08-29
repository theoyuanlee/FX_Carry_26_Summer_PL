"""Spot and forward levels at one tenor, and the returns they imply.

Everything here is in dollars per foreign currency unit, so a rise in a rate means the foreign
currency gained and every column of the panel points the same way. One cross-sectional formula
is only valid if they do.

Two return conventions are exposed because two are needed. :attr:`SpotForward.excess_return`
is the log return on being long the foreign currency forward, which is what a sorted book
sums. :attr:`SpotForward.forward_return` is the same trade in simple terms, which is what adds
to an option payoff written on the same notional.

Returns are indexed by the date they settle. Row ``t+1`` pairs the forward struck at ``t``
with the spot that settled it, so nothing on a row is unknown when that row is dated.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from fxcarry.catalog import Catalog
from fxcarry.quotes import Quotes


@dataclass(frozen=True)
class SpotForward:
    """Aligned spot and outright forward quotes, and what follows from them.

    Attributes:
        spot: Two-sided spot, dollars per foreign unit.
        forward: Two-sided outright forward at ``tenor``, dollars per foreign unit.
        tenor: Contract length in years, e.g. ``1/12`` for one month.
    """

    spot: Quotes
    forward: Quotes
    tenor: float

    @classmethod
    def from_quotes(
        cls,
        spot_native: Quotes,
        points_native: Quotes,
        catalog: Catalog,
        tenor: float,
    ) -> "SpotForward":
        """Build from quotes as the market publishes them.

        Args:
            spot_native: Spot in the market's own quote direction.
            points_native: Forward points at ``tenor``, same direction, in pips.
            catalog: Supplies the point scale and the quote direction per currency.
            tenor: Contract length in years.

        Returns:
            A panel on the currencies present in both inputs and in the catalog.

        Order matters. Points are quoted against the native rate, so the outright is built
        before anything is inverted. The other order applies pips to a reciprocal and is
        silently wrong by roughly the square of the rate.
        """
        common = [
            c for c in spot_native.columns if c in points_native.columns and c in catalog
        ]
        spot_n = spot_native.select(common)
        points_n = points_native.select(common)

        def outright(s: pd.DataFrame, p: pd.DataFrame) -> pd.DataFrame:
            return pd.DataFrame(
                {c: catalog[c].outright(s[c], p[c]) for c in common}, index=s.index
            )

        forward_n = spot_n.apply(outright, points_n)
        inverted = [c for c in common if not catalog[c].quoted_usd_per_fcu]
        return cls(
            spot=spot_n.invert(inverted),
            forward=forward_n.invert(inverted),
            tenor=tenor,
        )

    @property
    def currencies(self) -> list[str]:
        """Currency codes carried by the panel."""
        return list(self.spot.columns)

    @property
    def log_discount(self) -> pd.DataFrame:
        """Log forward minus log spot. Positive means the foreign currency is dear forward."""
        return np.log(self.forward.mid) - np.log(self.spot.mid)

    @property
    def carry(self) -> pd.DataFrame:
        """Annualized yield pickup from holding the foreign currency.

        This is minus the log discount, and the sign is the whole point. A currency that is
        dear forward is one the forward market makes you pay to hold, which under covered
        parity means it yields less than the dollar. So a forward above spot is negative carry.

        Equivalently: if spot were a random walk this is the expected excess return per unit of
        time on :attr:`excess_return`, which is what makes it the natural thing to sort on.
        """
        return -self.log_discount / self.tenor

    @property
    def excess_return(self) -> pd.DataFrame:
        """Log return on being long the foreign currency forward, indexed at settlement."""
        return np.log(self.spot.mid) - np.log(self.forward.mid).shift(1)

    @property
    def forward_return(self) -> pd.DataFrame:
        """The same trade in simple terms: settlement spot over the struck forward, minus one."""
        return self.spot.mid / self.forward.mid.shift(1) - 1.0

    @property
    def spot_return(self) -> pd.DataFrame:
        """Log spot appreciation, with no interest component."""
        return np.log(self.spot.mid).diff()

    def net_excess_return(self, side: str) -> pd.DataFrame:
        """Excess return after crossing the quoted spread on both legs.

        Args:
            side: ``"long"`` to buy the foreign currency forward and sell it back spot,
                ``"short"`` for the mirror.

        Raises:
            ValueError: If ``side`` is neither.
        """
        if side == "long":
            return np.log(self.spot.bid) - np.log(self.forward.ask).shift(1)
        if side == "short":
            return np.log(self.forward.bid).shift(1) - np.log(self.spot.ask)
        raise ValueError(f"side must be 'long' or 'short', got {side!r}.")

    def implied_foreign_rate(self, domestic: pd.Series | pd.DataFrame | float):
        """Foreign rate the forward implies under covered parity.

        Holding dollars and going through the foreign currency with the forward sold today are
        the same trade, so the forward has to price the differential exactly. Rearranged, the
        foreign rate is the domestic one less the annualized log discount.

        Args:
            domestic: Continuously compounded domestic rate, as a series or a scalar.
        """
        if isinstance(domestic, pd.Series):
            return self.carry.add(domestic, axis=0)
        return self.carry + domestic

    def basis(
        self,
        r_foreign: pd.DataFrame,
        r_domestic: pd.Series | pd.DataFrame | float,
    ) -> pd.DataFrame:
        """Deviation from covered parity: the forward-implied differential less the actual one.

        Zero when parity holds. A non-zero value means the forward market and the deposit
        market disagree about what it costs to hold one currency against the other.

        Args:
            r_foreign: Annualized foreign rates, one column per currency.
            r_domestic: Annualized domestic rate, as a series or a scalar.

        Returns:
            Annualized basis on this panel's columns; currencies with no rate are NaN.
        """
        actual = (
            r_foreign.sub(r_domestic, axis=0)
            if isinstance(r_domestic, pd.Series)
            else r_foreign - r_domestic
        )
        return self.carry.sub(actual).reindex(columns=self.spot.columns)
