"""Option pricing, positions, and the hedges built out of them.

Three layers, each unaware of the one above it.

:class:`PricingModel` turns a forward, a strike, a volatility and a tenor into a value, and
inverts a quoted delta into the strike it refers to. :class:`Instrument` says what is owned:
a forward, a vanilla option, or any signed combination of them. :class:`Overlay` says which
instruments to put on, stated in deltas, since deltas are what the market quotes and a strike
only exists once a smile and a model are supplied.

Nothing above the first layer names a pricing formula, so replacing the model changes the
numbers and nothing else.

Prices come out in the same units as the forward and the strike, both of which are exchange
rates. A premium is therefore directly comparable to a forward payoff and needs no separate
notional bookkeeping. Instruments are vectorized: pass Series for the forward, strike or
volatility and a whole panel prices in one call.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field, replace

import numpy as np
import pandas as pd
from scipy.stats import norm

from fxcarry.vol import Smile

_OMEGA = {"call": 1.0, "put": -1.0}


def _template(*args: object) -> object:
    """The first pandas argument to borrow labels from, preferring a frame over a series."""
    frame = next((a for a in args if isinstance(a, pd.DataFrame)), None)
    if frame is not None:
        return frame
    return next((a for a in args if isinstance(a, pd.Series)), None)


def _like(result: np.ndarray, template: object) -> object:
    """Rewrap a numpy result onto a pandas template, or hand back a plain value."""
    if isinstance(template, pd.DataFrame):
        return pd.DataFrame(result, index=template.index, columns=template.columns)
    if isinstance(template, pd.Series):
        return pd.Series(result, index=template.index, name=template.name)
    if np.ndim(result) == 0:
        return float(result)
    return result


def _omega(kind: str) -> float:
    """+1 for a call, -1 for a put.

    Raises:
        ValueError: On anything else.
    """
    try:
        return _OMEGA[kind]
    except KeyError:
        raise ValueError(f"kind must be 'call' or 'put', got {kind!r}.") from None


class PricingModel(ABC):
    """Values a European option and translates between its strike and its delta."""

    @abstractmethod
    def value(self, kind: str, forward, strike, vol, tenor: float, discount=1.0):
        """Present value of one option."""

    @abstractmethod
    def delta(self, kind: str, forward, strike, vol, tenor: float, base_rate=0.0):
        """Signed delta of one option, in the convention the model quotes."""

    @abstractmethod
    def strike_from_delta(
        self, delta: float, kind: str, forward, vol, tenor: float, base_rate=0.0
    ):
        """Strike a quoted delta magnitude refers to."""

    @abstractmethod
    def atm_strike(self, forward, vol, tenor: float):
        """Strike the market calls at the money."""


class Black76(PricingModel):
    """The Black model written on a forward price rather than on spot.

    A call is ``discount * (F N(d1) - K N(d2))`` with
    ``d1 = (log(F/K) + sigma^2 tau / 2) / (sigma sqrt(tau))`` and ``d2 = d1 - sigma sqrt(tau)``.

    Writing the option on the forward is what keeps interest rates out of it. An option on one
    currency against another has two rates in it, and the outright forward already prices
    their difference, so only a single discount factor survives.

    Deltas are the plain spot delta, ``omega exp(-r_base tau) N(omega d1)``. Premium-adjusted
    deltas, which some pairs quote instead, have no closed-form inverse and are not
    implemented.
    """

    def value(self, kind: str, forward, strike, vol, tenor: float, discount=1.0):
        """Present value, in the units of ``forward`` and ``strike``.

        Collapses to discounted intrinsic value as volatility times root tenor goes to zero. A
        missing volatility stays missing rather than becoming intrinsic, so a gap in a
        volatility history cannot read as a free option.
        """
        omega = _omega(kind)
        f = np.asarray(forward, dtype=float)
        k = np.asarray(strike, dtype=float)
        disc = np.asarray(discount, dtype=float)
        vs = np.asarray(vol, dtype=float) * np.sqrt(float(tenor))

        with np.errstate(divide="ignore", invalid="ignore"):
            d1 = (np.log(f / k) + 0.5 * vs**2) / vs
            d2 = d1 - vs
        priced = omega * disc * (f * norm.cdf(omega * d1) - k * norm.cdf(omega * d2))
        intrinsic = disc * np.maximum(omega * (f - k), 0.0)

        price = np.where(vs > 0, priced, intrinsic)
        price = np.where(np.isnan(vs), np.nan, price)
        return _like(price, _template(forward, strike, vol, discount))

    def delta(self, kind: str, forward, strike, vol, tenor: float, base_rate=0.0):
        """Signed spot delta: positive for a call, negative for a put."""
        omega = _omega(kind)
        f = np.asarray(forward, dtype=float)
        k = np.asarray(strike, dtype=float)
        rb = np.asarray(base_rate, dtype=float)
        vs = np.asarray(vol, dtype=float) * np.sqrt(float(tenor))
        with np.errstate(divide="ignore", invalid="ignore"):
            d1 = (np.log(f / k) + 0.5 * vs**2) / vs
        out = omega * np.exp(-rb * float(tenor)) * norm.cdf(omega * d1)
        return _like(out, _template(forward, strike, vol, base_rate))

    def strike_from_delta(
        self, delta: float, kind: str, forward, vol, tenor: float, base_rate=0.0
    ):
        """Strike the quoted delta magnitude refers to.

        A delta is a coordinate, not a moneyness: turning it into a strike takes the model, so
        the strike moves when the volatility fed in moves.

        Args:
            delta: Quoted magnitude, e.g. ``0.25`` for a 25-delta wing.
            kind: ``"call"`` or ``"put"``.
            forward: Outright forward rate.
            vol: Decimal volatility at that wing.
            tenor: Years to expiry.
            base_rate: Continuously compounded rate of the pair's base currency, which enters
                because a spot delta carries an ``exp(-r_base tau)`` factor.
        """
        omega = _omega(kind)
        f = np.asarray(forward, dtype=float)
        rb = np.asarray(base_rate, dtype=float)
        vs = np.asarray(vol, dtype=float) * np.sqrt(float(tenor))
        d1 = omega * norm.ppf(float(delta) * np.exp(rb * float(tenor)))
        return _like(f * np.exp(-vs * d1 + 0.5 * vs**2), _template(forward, vol, base_rate))

    def atm_strike(self, forward, vol, tenor: float):
        """The strike at which a straddle has zero net delta, ``F exp(sigma^2 tau / 2)``."""
        f = np.asarray(forward, dtype=float)
        sig = np.asarray(vol, dtype=float)
        return _like(f * np.exp(0.5 * sig**2 * float(tenor)), _template(forward, vol))


@dataclass(frozen=True)
class MarketState:
    """Everything an instrument needs in order to be valued.

    Attributes:
        forward: Outright forward rate for the instrument's expiry.
        tenor: Years to expiry.
        discount: Domestic discount factor over the tenor.
        base_rate: Continuously compounded rate of the pair's base currency.
        smile: Quoted smile, needed only to resolve a delta into a strike.
        model: Pricing model; a plain Black76 unless another is supplied.
    """

    forward: object
    tenor: float
    discount: object = 1.0
    base_rate: object = 0.0
    smile: Smile | None = None
    model: PricingModel = field(default_factory=Black76)

    def require_smile(self) -> Smile:
        """The smile, or an error naming what is missing.

        Raises:
            ValueError: If this state carries no smile.
        """
        if self.smile is None:
            raise ValueError("This market state carries no smile, so a delta has no strike.")
        return self.smile


class Instrument(ABC):
    """Something that costs a price today and pays a payoff at expiry.

    Signed quantities and sums of instruments are instruments too, so a spread, a ladder and a
    naked sale are all the same type with different contents.
    """

    @abstractmethod
    def price(self, market: MarketState):
        """Value at inception, positive when the position is paid for."""

    @abstractmethod
    def payoff(self, terminal):
        """Value at expiry, given the rate the contract settles against."""

    def worst_case(self, grid):
        """Least payoff over a grid of terminal rates.

        Generic rather than per-structure: evaluate the payoff and take the minimum. A bounded
        structure reports its bound, an unbounded one reports the worst point on the grid, so
        the grid has to be wide enough to be worth believing.
        """
        return float(np.min([np.min(np.asarray(self.payoff(x), dtype=float)) for x in grid]))

    def __mul__(self, quantity: float) -> "Combination":
        return Combination(((float(quantity), self),))

    __rmul__ = __mul__

    def __neg__(self) -> "Combination":
        return self * -1.0

    def __add__(self, other: "Instrument") -> "Combination":
        return Combination(_legs_of(self) + _legs_of(other))

    def __sub__(self, other: "Instrument") -> "Combination":
        return self + (-other)


def _legs_of(instrument: Instrument) -> tuple[tuple[float, Instrument], ...]:
    """A instrument's legs, flattened, so sums stay one level deep."""
    if isinstance(instrument, Combination):
        return instrument.legs
    return ((1.0, instrument),)


@dataclass(frozen=True)
class Forward(Instrument):
    """A forward contract struck at ``strike``.

    Attributes:
        strike: Rate the contract was struck at.
    """

    strike: object

    def price(self, market: MarketState):
        """Zero. Entering a forward costs nothing."""
        return 0.0

    def payoff(self, terminal):
        """Settlement rate less the struck rate."""
        return terminal - self.strike


@dataclass(frozen=True)
class Vanilla(Instrument):
    """A European call or put.

    Attributes:
        kind: ``"call"`` or ``"put"``.
        strike: Strike, in the same units as the forward.
        vol: Decimal volatility to price it at.
    """

    kind: str
    strike: object
    vol: object

    @classmethod
    def from_delta(cls, delta: int, kind: str, market: MarketState) -> "Vanilla":
        """The option a quoted delta refers to, given a market carrying a smile.

        The volatility comes off the smile at that wing, and the strike follows from it, so an
        error in the smile moves the strike as well as the premium.

        Args:
            delta: Quoted wing delta as the market says it, so ``25`` for a 25-delta option.
                Only the pricing model works in fractions.
            kind: ``"call"`` or ``"put"``.
            market: Supplies the smile, the forward and the model.

        Raises:
            ValueError: If the market carries no smile.
        """
        vol = market.require_smile().vol(delta, kind)
        strike = market.model.strike_from_delta(
            delta / 100.0, kind, market.forward, vol, market.tenor, base_rate=market.base_rate
        )
        return cls(kind=kind, strike=strike, vol=vol)

    def price(self, market: MarketState):
        """Present value through the market's own pricing model."""
        return market.model.value(
            self.kind, market.forward, self.strike, self.vol, market.tenor,
            discount=market.discount,
        )

    def payoff(self, terminal):
        """Intrinsic value at expiry."""
        return np.maximum(_omega(self.kind) * (terminal - self.strike), 0.0)


@dataclass(frozen=True)
class Combination(Instrument):
    """Signed quantities of other instruments, priced and settled leg by leg.

    Attributes:
        legs: Pairs of quantity and instrument. A negative quantity is a sale.
    """

    legs: tuple[tuple[float, Instrument], ...] = ()

    def price(self, market: MarketState):
        """Net cost, negative when the structure is a credit."""
        if not self.legs:
            return 0.0
        return sum(qty * leg.price(market) for qty, leg in self.legs)

    def payoff(self, terminal):
        """Net settlement value."""
        if not self.legs:
            return 0.0 * terminal if hasattr(terminal, "shape") else 0.0
        return sum(qty * leg.payoff(terminal) for qty, leg in self.legs)


class Overlay(ABC):
    """A rule for what to put on top of a position, stated in deltas.

    Deltas are what the market quotes; strikes only exist once a smile and a model are
    supplied, which is what :meth:`build` does.
    """

    @abstractmethod
    def build(self, market: MarketState) -> Combination:
        """The position this rule implies in the given market."""

    def on(self, kind: str) -> "Overlay":
        """The same rule written against the other side of the smile.

        Which side protection sits on depends on the position being protected, not on the rule,
        so a caller holding both directions asks for each side in turn.
        """
        return replace(self, kind=kind)


class NoOverlay(Overlay):
    """Nothing on top."""

    def build(self, market: MarketState) -> Combination:
        """An empty combination, worth nothing at any rate."""
        return Combination()

    def on(self, kind: str) -> "NoOverlay":
        """Still nothing, whichever side is asked for."""
        return self


@dataclass(frozen=True)
class SingleWing(Overlay):
    """One option at one delta.

    Attributes:
        delta: Quoted wing delta, e.g. 25.
        kind: ``"call"`` or ``"put"``.
        quantity: Signed size; negative sells the option.
    """

    delta: int
    kind: str
    quantity: float = -1.0

    def build(self, market: MarketState) -> Combination:
        """One leg at the quoted delta."""
        return Combination(((self.quantity, Vanilla.from_delta(self.delta, self.kind, market)),))


@dataclass(frozen=True)
class VerticalSpread(Overlay):
    """Two options of the same kind at different deltas.

    Reversing ``sell_delta`` and ``buy_delta`` reverses the trade, turning a credit spread into
    a debit one. Quantities other than one apiece give a ratio spread.

    Attributes:
        sell_delta: Delta of the leg taken with the first quantity.
        buy_delta: Delta of the leg taken with the second.
        kind: ``"call"`` or ``"put"``; the side of the smile the structure sits on.
        quantities: Signed sizes of the two legs, in that order.
    """

    sell_delta: int
    buy_delta: int
    kind: str
    quantities: tuple[float, float] = (-1.0, 1.0)

    def build(self, market: MarketState) -> Combination:
        """Both legs, priced off the same smile."""
        sold, bought = self.quantities
        return Combination((
            (sold, Vanilla.from_delta(self.sell_delta, self.kind, market)),
            (bought, Vanilla.from_delta(self.buy_delta, self.kind, market)),
        ))
