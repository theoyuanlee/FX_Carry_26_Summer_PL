"""Instrument identity: what a currency is called, and which conventions it follows.

A :class:`Currency` knows one currency's market pair, its forward-point scale, and how to
build the tickers its instruments quote under. A :class:`Catalog` is a set of them, plus the
parsing that turns a ticker string back into the structure encoded in it.

Quote direction is read off the pair rather than stored: a pair ending in USD is already
quoted in dollars per foreign unit, and anything else is quoted the other way up.
"""

from __future__ import annotations

import re
from collections.abc import Iterator, Mapping, Sequence
from dataclasses import dataclass

from fxcarry import reference

# "AUDUSD25R1M BGN Curncy" (25-delta risk reversal), "...25B1M..." (butterfly),
# or "EURUSDV1M BGN Curncy" (at the money). The source suffix is optional.
_VOL_RE = re.compile(r"^([A-Z]{6})(?:V|(\d+)([RB]))([0-9]+[WMY])(?: [A-Z]+)? Curncy$")

# "AUD3M Curncy" -> root AUD, tenor 3M. The root is not always the ISO code:
# non-deliverable forwards quote under their own roots.
_FWD_RE = re.compile(r"^([A-Z]{3})([0-9]+[WMY]) Curncy$")

_WING_KINDS = {"rr": "R", "bf": "B"}


@dataclass(frozen=True)
class TickerId:
    """A ticker string decoded into its parts.

    Attributes:
        symbol: The ticker as it was written.
        iso: Currency code of the non-USD leg.
        tenor: Tenor token such as ``"1M"``, or None for instruments without one.
        kind: ``"spot"``, ``"forward"``, ``"rate"``, ``"atm"``, ``"rr"`` or ``"bf"``.
        delta: Wing delta for a risk reversal or butterfly, None otherwise.
        pair: Market pair an option quotes on, None for everything else.
    """

    symbol: str
    iso: str
    tenor: str | None = None
    kind: str | None = None
    delta: int | None = None
    pair: str | None = None


@dataclass(frozen=True)
class Currency:
    """One currency, its market pair, and the conventions that follow from them.

    Attributes:
        iso: Three-letter currency code.
        pair: Market pair, e.g. ``"AUDUSD"`` or ``"USDJPY"``.
        point_scale: Divisor turning quoted forward points into price units.
        spot_ticker: Ticker the spot rate quotes under.
        fwd_root: Ticker root the forward points quote under, which differs from
            ``iso`` for non-deliverable forwards.
    """

    iso: str
    pair: str
    point_scale: float
    spot_ticker: str
    fwd_root: str

    @property
    def quoted_usd_per_fcu(self) -> bool:
        """Whether the market already quotes this pair in dollars per foreign unit."""
        return self.pair.endswith("USD")

    def fwd_ticker(self, tenor: str) -> str:
        """Forward-points ticker at ``tenor``, e.g. ``"AUD3M Curncy"``."""
        return f"{self.fwd_root}{tenor} Curncy"

    def vol_ticker(
        self,
        kind: str,
        tenor: str,
        delta: int | None = None,
        source: str = reference.VOL_SOURCE,
    ) -> str:
        """Option ticker for one piece of the quoted smile.

        Args:
            kind: ``"atm"``, ``"rr"`` or ``"bf"``.
            tenor: Tenor token, e.g. ``"1M"``.
            delta: Wing delta, required for ``"rr"`` and ``"bf"`` and rejected for ``"atm"``.
            source: Quote-source suffix; pass ``""`` to omit it.

        Returns:
            e.g. ``"EURUSD25R1M BGN Curncy"``.

        Raises:
            ValueError: On an unknown kind, or a delta that does not match the kind.
        """
        suffix = f" {source}" if source else ""
        if kind == "atm":
            if delta is not None:
                raise ValueError("An at-the-money quote has no wing delta.")
            return f"{self.pair}V{tenor}{suffix} Curncy"
        if kind in _WING_KINDS:
            if delta is None:
                raise ValueError(f"A {kind} quote needs a wing delta.")
            return f"{self.pair}{delta}{_WING_KINDS[kind]}{tenor}{suffix} Curncy"
        raise ValueError(f"kind must be 'atm', 'rr' or 'bf', got {kind!r}.")

    def outright(self, spot, points):
        """Outright forward from spot and quoted points, both in the native quote.

        Points are a difference from spot in pips rather than a level, so they carry a
        per-currency scale: 25 pips is 0.0025 on a four-decimal pair, 0.25 on a two-decimal
        one, and 25 where the points are quoted in whole units.
        """
        return spot + points / self.point_scale

    def to_usd_per_fcu(self, rate):
        """Rate expressed in dollars per foreign unit, inverting it where the market is not."""
        return rate if self.quoted_usd_per_fcu else 1.0 / rate


class Catalog:
    """A set of currencies, and the ticker parsing that inverts their builders."""

    def __init__(self, currencies: Mapping[str, Currency]):
        self._currencies = dict(currencies)
        self._by_spot = {c.spot_ticker: c.iso for c in self._currencies.values()}
        self._by_fwd_root = {c.fwd_root: c.iso for c in self._currencies.values()}
        self._by_pair = {c.pair: c.iso for c in self._currencies.values()}

    @classmethod
    def from_tickers(
        cls,
        tickers: Mapping[str, tuple[str, str]],
        point_scale: Mapping[str, float] | None = None,
    ) -> "Catalog":
        """Build from a map of ISO code to ``(spot ticker, 1M forward-points ticker)``."""
        scales = reference.POINT_SCALE if point_scale is None else point_scale
        default = scales.get("default", 10000.0)
        return cls(
            {
                iso: Currency(
                    iso=iso,
                    pair=spot.replace(" Curncy", ""),
                    point_scale=scales.get(iso, default),
                    spot_ticker=spot,
                    fwd_root=fwd.split("1M")[0],
                )
                for iso, (spot, fwd) in tickers.items()
            }
        )

    @classmethod
    def default(cls) -> "Catalog":
        """Every currently traded currency in the reference tables."""
        return cls.from_tickers(reference.SPOT_FWD_TICKERS)

    @classmethod
    def with_legacy(cls) -> "Catalog":
        """The default catalog plus the currencies the euro replaced."""
        return cls.from_tickers(
            {**reference.SPOT_FWD_TICKERS, **reference.LEGACY_EURO_TICKERS}
        )

    def __getitem__(self, iso: str) -> Currency:
        return self._currencies[iso]

    def __iter__(self) -> Iterator[Currency]:
        return iter(self._currencies.values())

    def __len__(self) -> int:
        return len(self._currencies)

    def __contains__(self, iso: object) -> bool:
        return iso in self._currencies

    @property
    def isos(self) -> list[str]:
        """Currency codes, in catalog order."""
        return list(self._currencies)

    def subset(self, isos: Sequence[str]) -> "Catalog":
        """A catalog holding only ``isos``, in the order given."""
        return Catalog({iso: self._currencies[iso] for iso in isos})

    def parse(self, ticker: str) -> TickerId | None:
        """Decode a ticker, or return None if it is not one this catalog covers."""
        match = _VOL_RE.match(ticker)
        if match:
            pair, delta, wing = match.group(1), match.group(2), match.group(3)
            iso = self._by_pair.get(pair)
            if iso is not None:
                kind = "atm" if delta is None else ("rr" if wing == "R" else "bf")
                return TickerId(
                    symbol=ticker,
                    iso=iso,
                    tenor=match.group(4),
                    kind=kind,
                    delta=int(delta) if delta is not None else None,
                    pair=pair,
                )

        iso = self._by_spot.get(ticker)
        if iso is not None:
            return TickerId(symbol=ticker, iso=iso, kind="spot", pair=self._currencies[iso].pair)

        match = _FWD_RE.match(ticker)
        if match:
            iso = self._by_fwd_root.get(match.group(1))
            if iso is not None:
                return TickerId(symbol=ticker, iso=iso, tenor=match.group(2), kind="forward")

        # Rate benchmarks are looked up rather than matched: they share no naming
        # pattern. The domestic leg decodes here too, though it has no pair and so
        # never appears in the catalog itself.
        key = reference.RATE_TICKER_TO_KEY.get(ticker)
        if key is not None:
            return TickerId(symbol=ticker, iso=key[0], tenor=key[1], kind="rate")
        return None

    def tickers(
        self,
        kind: str,
        tenors: Sequence[str] | None = None,
        deltas: Sequence[int] | None = None,
        source: str = reference.VOL_SOURCE,
    ) -> list[str]:
        """Every ticker of one kind across the catalog, deduplicated in order.

        Args:
            kind: ``"spot"``, ``"forward"``, ``"rate"``, ``"atm"``, ``"rr"`` or ``"bf"``.
            tenors: Tenors to build; required for everything except spot.
            deltas: Wing deltas; required for ``"rr"`` and ``"bf"``.
            source: Quote-source suffix for option tickers.

        Raises:
            ValueError: On an unknown kind or a missing tenor or delta list.
        """
        if kind == "spot":
            return list(dict.fromkeys(c.spot_ticker for c in self))
        if kind == "rate":
            wanted = reference.RATE_TENORS if tenors is None else tenors
            out = [
                symbol
                for iso in self.isos
                for tenor, symbol in reference.SHORT_RATE_TICKERS.get(iso, {}).items()
                if tenor in wanted
            ]
            return list(dict.fromkeys(out))
        if tenors is None:
            raise ValueError(f"kind={kind!r} needs a tenor list.")
        if kind == "forward":
            out = [c.fwd_ticker(t) for c in self for t in tenors]
        elif kind == "atm":
            out = [c.vol_ticker("atm", t, source=source) for c in self for t in tenors]
        elif kind in _WING_KINDS:
            if deltas is None:
                raise ValueError(f"kind={kind!r} needs a delta list.")
            out = [
                c.vol_ticker(kind, t, d, source=source)
                for c in self
                for t in tenors
                for d in deltas
            ]
        else:
            raise ValueError(f"Unknown kind {kind!r}.")
        return list(dict.fromkeys(out))

    def label_map(
        self,
        kind: str,
        tenor: str | None = None,
        delta: int | None = None,
        source: str = reference.VOL_SOURCE,
    ) -> dict[str, str]:
        """Ticker to currency code, for one kind and tenor.

        This is the only thing a quote loader needs from a catalog: it says which column each
        ticker pivots into.

        Raises:
            ValueError: On an unknown kind, or a missing tenor where one is required.
        """
        if kind == "spot":
            return {c.spot_ticker: c.iso for c in self}
        if tenor is None:
            raise ValueError(f"kind={kind!r} needs a tenor.")
        if kind == "forward":
            return {c.fwd_ticker(tenor): c.iso for c in self}
        if kind == "rate":
            return {
                symbol: iso
                for iso in self.isos
                for t, symbol in reference.SHORT_RATE_TICKERS.get(iso, {}).items()
                if t == tenor
            }
        if kind in ("atm", *_WING_KINDS):
            return {c.vol_ticker(kind, tenor, delta, source=source): c.iso for c in self}
        raise ValueError(f"Unknown kind {kind!r}.")
