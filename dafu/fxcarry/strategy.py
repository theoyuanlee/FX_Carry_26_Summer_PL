"""Turning a view into weights, and weights into returns.

A :class:`Signal` scores the cross-section, a :class:`Weighting` turns those scores into
positions, an :class:`~fxcarry.options.Overlay` optionally puts options on top, and a
:class:`CostModel` charges for the trading. :class:`Book` is where they meet.

Scores are indexed by the date the information became known. Book performs the single shift
that pairs a position chosen at one date with the return realized over the period that
follows. Nothing else in the library shifts anything, so the absence of look-ahead is a
property of one line rather than of a convention everyone has to remember.

Returns are simple rather than logarithmic, because a portfolio return is the weighted sum of
its holdings' simple returns and because an option payoff adds to a forward payoff written on
the same notional.
"""

from __future__ import annotations

from abc import ABC, abstractmethod

import numpy as np
import pandas as pd

from fxcarry.curves import SpotForward
from fxcarry.options import Black76, MarketState, NoOverlay, Overlay, PricingModel
from fxcarry.vol import Smile


class Signal(ABC):
    """Scores the cross-section, higher meaning more worth being long."""

    @abstractmethod
    def scores(self, curves: SpotForward) -> pd.DataFrame:
        """Scores indexed by the date they became knowable."""


class Carry(Signal):
    """The annualized forward discount: what the forward market pays to hold the currency."""

    def scores(self, curves: SpotForward) -> pd.DataFrame:
        """The panel's carry, which is known as soon as the two rates are quoted."""
        return curves.carry


class Momentum(Signal):
    """Trailing realized return over a lookback window.

    Attributes:
        lookback: Number of periods to accumulate. One is the previous period's return.
    """

    def __init__(self, lookback: int = 1):
        if lookback < 1:
            raise ValueError(f"lookback must be at least 1, got {lookback}.")
        self.lookback = lookback

    def scores(self, curves: SpotForward) -> pd.DataFrame:
        """Summed past returns. Already indexed at realization, so no further shift."""
        realized = curves.excess_return
        return realized if self.lookback == 1 else realized.rolling(self.lookback).sum()


class Weighting(ABC):
    """Turns a row of scores into a row of positions.

    Every implementation normalizes within the row, so a period with fewer scored currencies
    still holds the same gross exposure.
    """

    @abstractmethod
    def weights(self, scores: pd.DataFrame) -> pd.DataFrame:
        """Positions, one column per currency, on the scores' own index."""

    @staticmethod
    def _empty(scores: pd.DataFrame) -> pd.DataFrame:
        return pd.DataFrame(0.0, index=scores.index, columns=scores.columns)


class TopBottom(Weighting):
    """Long the highest ``k`` scores, short the lowest, a dollar on each side.

    Attributes:
        k: Number of currencies per side.
    """

    def __init__(self, k: int = 5):
        if k < 1:
            raise ValueError(f"k must be at least 1, got {k}.")
        self.k = k

    def weights(self, scores: pd.DataFrame) -> pd.DataFrame:
        """A dollar spread across the top ``k`` and minus a dollar across the bottom ``k``."""
        rank_high = scores.rank(axis=1, ascending=False, method="first")
        rank_low = scores.rank(axis=1, ascending=True, method="first")
        out = self._empty(scores)
        out = out.mask(rank_high <= self.k, 1.0 / self.k)
        return out.mask(rank_low <= self.k, -1.0 / self.k)


class Bucket(Weighting):
    """One slice of an ``n``-way sort, equally weighted and held long.

    Attributes:
        n: Number of buckets the cross-section is cut into.
        index: Which bucket to hold, counting from 1 at the lowest score.
    """

    def __init__(self, n: int, index: int):
        if not 1 <= index <= n:
            raise ValueError(f"index must lie in 1..{n}, got {index}.")
        self.n = n
        self.index = index

    def weights(self, scores: pd.DataFrame) -> pd.DataFrame:
        """Equal weight on the currencies falling in this bucket, nothing elsewhere."""
        ranks = scores.rank(axis=1, ascending=True, method="first")
        valid = scores.notna().sum(axis=1).replace(0, np.nan)
        labels = np.ceil(ranks.div(valid, axis=0) * self.n).clip(1, self.n)
        member = labels.eq(self.index)
        size = member.sum(axis=1).replace(0, np.nan)
        return member.div(size, axis=0).fillna(0.0)


class SignEqualWeight(Weighting):
    """Every scored currency held at equal size, in the direction of its score."""

    def weights(self, scores: pd.DataFrame) -> pd.DataFrame:
        """Sign of the score over the number of scored currencies."""
        valid = scores.notna().sum(axis=1).replace(0, np.nan)
        return np.sign(scores).div(valid, axis=0).fillna(0.0)


class SpreadWeighted(Weighting):
    """Positions proportional to the size of the score, in its direction."""

    def weights(self, scores: pd.DataFrame) -> pd.DataFrame:
        """Score over the sum of absolute scores, so the gross position is a dollar."""
        total = scores.abs().sum(axis=1).replace(0, np.nan)
        return scores.div(total, axis=0).fillna(0.0)


class EqualLong(Weighting):
    """Every scored currency held long at equal size, whatever the score says."""

    def weights(self, scores: pd.DataFrame) -> pd.DataFrame:
        """One over the number of scored currencies, on each of them."""
        valid = scores.notna().sum(axis=1).replace(0, np.nan)
        return scores.notna().div(valid, axis=0).fillna(0.0)


class CostModel(ABC):
    """Charges for running a book, given the positions actually held."""

    @abstractmethod
    def cost(self, holdings: pd.DataFrame) -> pd.Series:
        """Cost charged in each period, as a positive number to subtract."""


class ZeroCost(CostModel):
    """Trading is free, for reading a gross return."""

    def cost(self, holdings: pd.DataFrame) -> pd.Series:
        """Zero on every row."""
        return pd.Series(0.0, index=holdings.index)


class BidAskCost(CostModel):
    """Charges the quoted spread on both legs of each position.

    The charge per unit held is the gap between the return at mid and the return actually
    available on the side being traded, which is what the panel's own quotes already say.
    """

    def __init__(self, curves: SpotForward):
        self.curves = curves

    def cost(self, holdings: pd.DataFrame) -> pd.Series:
        """Weighted round-trip spread across the held legs."""
        gross = self.curves.excess_return
        long_gap = (gross - self.curves.net_excess_return("long")).reindex_like(holdings)
        short_gap = (-gross - self.curves.net_excess_return("short")).reindex_like(holdings)
        per_leg = long_gap.where(holdings >= 0, short_gap)
        return (holdings.abs() * per_leg).sum(axis=1, min_count=1)


class HalfSpreadCost(CostModel):
    """Charges a roll on maintained notional and a crossing on the change in position.

    Attributes:
        roll: Relative half-spread paid to keep a position on for another period.
        outright: Relative half-spread paid to open or close one.
    """

    def __init__(self, roll: pd.DataFrame, outright: pd.DataFrame):
        self.roll = roll
        self.outright = outright

    def cost(self, holdings: pd.DataFrame) -> pd.Series:
        """Maintained notional times the roll, plus traded notional times the crossing."""
        traded = holdings.diff().abs()
        traded.iloc[0] = holdings.iloc[0].abs()
        charge = holdings.abs() * self.roll.reindex_like(holdings)
        charge = charge + traded * self.outright.reindex_like(holdings)
        return charge.sum(axis=1, min_count=1)


class Book:
    """A signal, a weighting, an optional overlay and a cost model, run over a panel.

    Attributes:
        curves: The spot and forward panel the book trades.
        signal: Scores the cross-section.
        weighting: Turns scores into positions.
        overlay: Options put on top of each leg, on that leg's crash side.
        costs: What the trading is charged.
        smile: Quoted smile panels, required whenever there is an overlay.
        domestic_rate: Continuously compounded funding rate, used to compound an option
            premium from inception to settlement.
        model: Pricing model for the overlay.
    """

    def __init__(
        self,
        curves: SpotForward,
        signal: Signal,
        weighting: Weighting,
        overlay: Overlay | None = None,
        costs: CostModel | None = None,
        smile: Smile | None = None,
        domestic_rate: pd.Series | float = 0.0,
        model: PricingModel | None = None,
    ):
        self.curves = curves
        self.signal = signal
        self.weighting = weighting
        self.overlay = NoOverlay() if overlay is None else overlay
        self.costs = ZeroCost() if costs is None else costs
        self.smile = smile
        self.domestic_rate = domestic_rate
        self.model = Black76() if model is None else model
        if not isinstance(self.overlay, NoOverlay) and smile is None:
            raise ValueError(
                "An overlay needs a smile: without one a delta does not resolve to a strike."
            )

    def weights(self) -> pd.DataFrame:
        """Positions the signal calls for, on the date the signal was knowable."""
        return self.weighting.weights(self.signal.scores(self.curves))

    def holdings(self) -> pd.DataFrame:
        """Positions actually in force over the period ending on each row.

        This is the library's only shift. A position chosen on one row is held over the next,
        so it can only ever earn a return that had not happened when it was chosen.
        """
        return self.weights().shift(1).fillna(0.0)

    def _funding(self) -> pd.DataFrame:
        """The funding rate widened to the panel's shape.

        A rate quoted once per date has to be spread across the cross-section before it can
        meet a date-by-currency forward, since the pricing layer works element by element.
        """
        template = self.curves.forward.mid
        rate = self.domestic_rate
        if isinstance(rate, pd.Series):
            return template.mul(0.0).add(rate.reindex(template.index), axis=0)
        return template.mul(0.0) + rate

    def _market(self) -> MarketState:
        """Market state as of the date each position is put on.

        The smile is put on the panel's own index and columns first. Volatility coverage is
        narrower than spot coverage in practice, and a leg with no quote prices to NaN and drops
        out rather than being treated as unhedged.
        """
        rate = self._funding()
        return MarketState(
            forward=self.curves.forward.mid,
            tenor=self.curves.tenor,
            discount=np.exp(-rate * self.curves.tenor),
            # In this direction the quote's base currency is the foreign one, so the delta
            # convention discounts at the rate the forward itself implies.
            base_rate=self.curves.implied_foreign_rate(self.domestic_rate),
            smile=self.smile.reindex_like(self.curves.forward.mid),
            model=self.model,
        )

    def overlay_kinds(self) -> pd.DataFrame:
        """Which side of the smile each leg's protection sits on, or NaN where flat.

        A leg held long loses when the currency falls, so it is protected with puts. A leg held
        short loses when it rises, so it takes calls.
        """
        direction = np.sign(self.weights())
        return direction.replace({1.0: "put", -1.0: "call", 0.0: np.nan})

    def _overlay_returns(self) -> pd.DataFrame:
        """Overlay profit per unit of capital, on the date each position is put on."""
        market = self._market()
        forward = self.curves.forward.mid
        settle = self.curves.spot.mid.shift(-1)
        growth = np.exp(self._funding() * self.curves.tenor)

        direction = np.sign(self.weights())
        out = pd.DataFrame(0.0, index=forward.index, columns=forward.columns)
        for sign, kind in ((1.0, "put"), (-1.0, "call")):
            position = self.overlay.on(kind).build(market)
            # One unit of capital buys 1/F of face at the forward, so an overlay priced per
            # unit of the underlying is divided by the same forward. The premium changes hands
            # at inception and therefore compounds; the forward costs nothing and does not.
            pnl = (position.payoff(settle) - position.price(market) * growth) / forward
            out = out.mask(direction == sign, pnl)
        return out

    def leg_returns(self) -> pd.DataFrame:
        """Return on each leg per unit of capital, direction and overlay included.

        Indexed by settlement, so row ``t`` reports what the position put on at ``t-1`` earned.
        """
        direction = np.sign(self.weights())
        legs = direction * (self.curves.spot.mid.shift(-1) / self.curves.forward.mid - 1.0)
        if not isinstance(self.overlay, NoOverlay):
            legs = legs + self._overlay_returns()
        return legs.shift(1)

    def returns(self, net: bool = True) -> pd.Series:
        """Book return per period, net of costs unless asked otherwise."""
        holdings = self.holdings()
        gross = (holdings.abs() * self.leg_returns()).sum(axis=1, min_count=1)
        return gross - self.costs.cost(holdings) if net else gross

    def nav(self) -> pd.Series:
        """Compounded net return, starting from one."""
        return (1.0 + self.returns().fillna(0.0)).cumprod()

    def turnover(self) -> pd.Series:
        """Mean absolute change in position across the cross-section, per period."""
        return self.holdings().diff().abs().mean(axis=1)

    def buckets(self, n: int) -> pd.DataFrame:
        """Returns of the ``n`` sorted buckets, side by side, lowest score first."""
        return pd.DataFrame(
            {
                i: Book(
                    self.curves,
                    self.signal,
                    Bucket(n, i),
                    overlay=self.overlay,
                    costs=self.costs,
                    smile=self.smile,
                    domestic_rate=self.domestic_rate,
                    model=self.model,
                ).returns()
                for i in range(1, n + 1)
            }
        )
