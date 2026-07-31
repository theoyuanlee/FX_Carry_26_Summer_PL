"""The quoted volatility smile, and volatility at a delta.

Nobody quotes a volatility per strike. The market quotes three numbers per tenor and per
delta: an at-the-money level, a risk reversal (the call volatility less the put) and a
butterfly (the average of the two wings, less at-the-money). :class:`Smile` undoes that
packaging and does nothing else. It refuses a delta it was not given rather than
interpolating, because filling in a smile between quotes is a modelling decision.

Volatilities cross this boundary as decimals. Quotes arrive in vol points and are divided by
100 as a surface is sliced, so nothing downstream has to remember which it is holding.

Quoted risk reversals and butterflies reference the pair's base currency. Where the base is
the dollar, the quoted call side is a foreign-currency put, so :meth:`VolSurface.smile`
orients the wings before handing them over and every caller can read "call" as a call on the
foreign currency.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass

import numpy as np
import pandas as pd

from fxcarry import reference
from fxcarry.catalog import Catalog
from fxcarry.quotes import QuoteSource

_SIDE_SIGN = {"call": 0.5, "put": -0.5}


@dataclass(frozen=True)
class Smile:
    """One tenor's quoted smile, as three pieces.

    Values may be scalars or aligned pandas objects, so one instance can carry a single
    observation or a whole history.

    Attributes:
        atm: At-the-money volatility, decimal.
        risk_reversal: Wing delta to call-minus-put volatility, decimal.
        butterfly: Wing delta to average-wing-minus-at-the-money volatility, decimal.
    """

    atm: object
    risk_reversal: Mapping[int, object]
    butterfly: Mapping[int, object]

    @property
    def deltas(self) -> tuple[int, ...]:
        """Wing deltas quoted on both sides of the smile, ascending."""
        return tuple(sorted(set(self.risk_reversal) & set(self.butterfly)))

    def vol(self, delta: int | None = None, side: str = "call"):
        """Volatility at one wing delta, or at the money when ``delta`` is None.

        A call is at-the-money plus the butterfly plus half the risk reversal; a put subtracts
        that half instead. The risk reversal carries the asymmetry, the butterfly the
        curvature.

        Raises:
            KeyError: If ``delta`` was not quoted.
            ValueError: If ``side`` is neither call nor put.
        """
        if side not in _SIDE_SIGN:
            raise ValueError(f"side must be 'call' or 'put', got {side!r}.")
        if delta is None:
            return self.atm
        if delta not in self.risk_reversal or delta not in self.butterfly:
            raise KeyError(
                f"No {delta}-delta quote on this smile; quoted deltas are {self.deltas}."
            )
        return self.atm + self.butterfly[delta] + _SIDE_SIGN[side] * self.risk_reversal[delta]

    def reindex_like(self, template: pd.DataFrame) -> "Smile":
        """The same smile on another frame's index and columns.

        Quotes the template asks for but the smile does not carry become NaN, which prices to
        NaN rather than to something cheap. Volatility coverage is almost never as wide as
        spot coverage, so this is the usual case rather than an edge one.
        """
        return Smile(
            atm=self.atm.reindex(index=template.index, columns=template.columns),
            risk_reversal={
                d: v.reindex(index=template.index, columns=template.columns)
                for d, v in self.risk_reversal.items()
            },
            butterfly={
                d: v.reindex(index=template.index, columns=template.columns)
                for d, v in self.butterfly.items()
            },
        )


class VolSurface:
    """Quoted option volatilities across currencies, tenors and wing deltas.

    Held long, because the surface is indexed by date, currency, kind, delta and tenor at once
    and no two-dimensional frame holds that without choosing a slice. The methods take the
    usual slices.
    """

    _COLUMNS = ("date", "iso", "kind", "delta", "tenor", "field", "value")

    def __init__(self, frame: pd.DataFrame, catalog: Catalog):
        missing = [c for c in self._COLUMNS if c not in frame.columns]
        if missing:
            raise ValueError(
                f"A surface frame needs columns {list(self._COLUMNS)}; {missing} absent."
            )
        self._frame = frame.loc[:, list(self._COLUMNS)]
        self._catalog = catalog

    @classmethod
    def from_source(
        cls,
        source: QuoteSource,
        catalog: Catalog,
        tenors: Sequence[str] | None = None,
        deltas: Sequence[int] | None = None,
    ) -> "VolSurface":
        """Decode every option ticker a source carries into one long surface.

        Args:
            source: Where the quotes are read from.
            catalog: Decodes the tickers and supplies each pair's quote direction.
            tenors: Tenors to keep; None keeps all.
            deltas: Wing deltas to keep; None keeps all.
        """
        raw = source.long_frame()
        decoded = {t: catalog.parse(t) for t in raw["ticker"].unique()}
        decoded = {
            t: tk for t, tk in decoded.items() if tk is not None and tk.kind in ("atm", "rr", "bf")
        }
        frame = raw[raw["ticker"].isin(decoded)].copy()
        for attr in ("iso", "kind", "delta", "tenor"):
            frame[attr] = frame["ticker"].map({t: getattr(tk, attr) for t, tk in decoded.items()})
        frame["field"] = frame["field"].map(reference.FIELD_TO_KEY)
        # At-the-money rows carry no delta. Zero stands in for it so the column groups
        # cleanly; nothing reads the value except the slicing below.
        frame["delta"] = frame["delta"].fillna(0).astype(int)
        if tenors is not None:
            frame = frame[frame["tenor"].isin(list(tenors))]
        if deltas is not None:
            frame = frame[frame["delta"].isin([0, *deltas])]
        return cls(frame.dropna(subset=["field"]), catalog)

    @property
    def frame(self) -> pd.DataFrame:
        """The decoded long surface."""
        return self._frame

    def _wide(self, iso: str, tenor: str, field: str, freq: str | None) -> pd.DataFrame:
        f = self._frame
        rows = f[(f["iso"] == iso) & (f["tenor"] == tenor) & (f["field"] == field)]
        if rows.empty:
            raise KeyError(f"No {field} {tenor} surface for {iso}.")
        key = rows["kind"] + rows["delta"].astype(str).where(rows["kind"] != "atm", "")
        wide = rows.assign(key=key).pivot_table(
            index="date", columns="key", values="value", aggfunc="last"
        ).sort_index()
        if freq:
            wide = wide.resample(reference.RESAMPLE_ALIAS.get(freq, freq)).last()
        wide.index.name = None
        wide.columns.name = None
        return wide / 100.0

    def smile(
        self,
        iso: str,
        tenor: str,
        field: str = "mid",
        freq: str | None = None,
    ) -> Smile:
        """One currency's smile at one tenor, oriented to the foreign currency.

        Raises:
            KeyError: If that currency, tenor and field carries no quotes.
        """
        wide = self._wide(iso, tenor, field, freq)
        # Swapping the call and put sides is exactly negating the risk reversal, since a call
        # adds half of it and a put subtracts half. The butterfly is symmetric and stands.
        sign = 1.0 if self._catalog[iso].quoted_usd_per_fcu else -1.0
        deltas = sorted(
            int(c[2:]) for c in wide.columns if c.startswith("rr") and f"bf{c[2:]}" in wide.columns
        )
        return Smile(
            atm=wide["atm"],
            risk_reversal={d: sign * wide[f"rr{d}"] for d in deltas},
            butterfly={d: wide[f"bf{d}"] for d in deltas},
        )

    def panel_smile(
        self,
        tenor: str,
        field: str = "mid",
        freq: str | None = None,
        currencies: Sequence[str] | None = None,
    ) -> Smile:
        """One smile spanning many currencies, each piece a date by currency frame.

        The same object as :meth:`smile` and oriented the same way, but wide enough to price a
        whole cross-section in one call. A currency that does not quote a given wing shows NaN
        in that column rather than dropping out of the panel.

        Args:
            tenor: Tenor token, e.g. ``"1M"``.
            field: Quoted side to read.
            freq: Frequency to snap to, or None to leave as quoted.
            currencies: Currencies to include; None takes every one that quotes at this tenor.

        Raises:
            KeyError: If no currency quotes at that tenor and field.
        """
        f = self._frame
        available = f[(f["tenor"] == tenor) & (f["field"] == field)]["iso"].unique()
        isos = [c for c in (currencies if currencies is not None else sorted(available))
                if c in set(available)]
        if not isos:
            raise KeyError(f"No {field} {tenor} surface for any requested currency.")

        smiles = {iso: self.smile(iso, tenor, field, freq) for iso in isos}
        deltas = sorted({d for s in smiles.values() for d in s.deltas})

        def wide(getter) -> pd.DataFrame:
            columns = {}
            for iso, smile in smiles.items():
                piece = getter(smile)
                # A currency that does not quote this wing contributes an empty column rather
                # than dropping out, so every piece of the panel keeps the same shape.
                columns[iso] = pd.Series(np.nan, index=smile.atm.index) if piece is None else piece
            return pd.concat(columns, axis=1).reindex(columns=isos)

        return Smile(
            atm=wide(lambda s: s.atm),
            risk_reversal={d: wide(lambda s, d=d: s.risk_reversal.get(d)) for d in deltas},
            butterfly={d: wide(lambda s, d=d: s.butterfly.get(d)) for d in deltas},
        )

    def atm_panel(
        self,
        tenor: str,
        field: str = "mid",
        freq: str | None = None,
    ) -> pd.DataFrame:
        """At-the-money volatility at one tenor, one column per currency.

        Raises:
            KeyError: If nothing quotes at that tenor and field.
        """
        f = self._frame
        rows = f[
            (f["kind"] == "atm") & (f["tenor"] == tenor) & (f["field"] == field)
        ]
        if rows.empty:
            raise KeyError(f"No {field} at-the-money quotes at {tenor}.")
        wide = rows.pivot_table(
            index="date", columns="iso", values="value", aggfunc="last"
        ).sort_index().sort_index(axis=1)
        if freq:
            wide = wide.resample(reference.RESAMPLE_ALIAS.get(freq, freq)).last()
        wide.index.name = None
        wide.columns.name = None
        return wide / 100.0

    def term_structure(self, iso: str, date, field: str = "mid") -> pd.Series:
        """At-the-money volatility across tenors for one currency on one date.

        Tenors come back in the reference grid's order, which is short to long.

        Raises:
            KeyError: If that currency has no at-the-money quotes on that date.
        """
        f = self._frame
        rows = f[
            (f["iso"] == iso)
            & (f["kind"] == "atm")
            & (f["field"] == field)
            & (f["date"] == pd.Timestamp(date))
        ]
        if rows.empty:
            raise KeyError(f"No {field} at-the-money quotes for {iso} on {date}.")
        out = rows.set_index("tenor")["value"] / 100.0
        order = [t for t in reference.VOL_TENORS if t in out.index]
        return out.reindex(order + [t for t in out.index if t not in order])
