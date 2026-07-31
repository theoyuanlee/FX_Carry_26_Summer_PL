"""What each pull contains, and whether the file on disk still agrees.

A pull is a parquet file with a name that means something to whoever ran it and nothing to
anyone else. :data:`REGISTRY` writes that meaning down: which instrument family a file holds,
which quote sides it carries, roughly how many tickers to expect. Consumers then ask for a
*kind* rather than a path, and several files answering to the same kind merge into one source.

The validation exists because of how the failure looks otherwise. Feed a spot pull where a
volatility surface belongs and nothing raises: the catalog maps no tickers, the panel comes
back empty, and the error surfaces later as an unrelated shape mismatch inside a regression.
:func:`inspect` reads the parquet footer and one column instead, so a wrong file is caught in
milliseconds and named plainly, even for the sixteen-million-row surface.

Nothing here is required. :class:`~fxcarry.quotes.ParquetSource` still takes bare paths, and
this module is a layer above it for callers who would rather be told what went wrong.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import pyarrow.parquet as pq

from fxcarry import reference
from fxcarry.quotes import ParquetSource, _data_not_pulled

#: Column layout every pull shares: one row per observation, no pivoting done yet.
LONG_COLUMNS: tuple[str, ...] = ("ticker", "date", "field", "value")


@dataclass(frozen=True)
class DataSpec:
    """One pull: what it holds, and what a healthy copy of it looks like.

    Attributes:
        name: File stem, without the ``.parquet``.
        kind: Instrument family. Files sharing a kind are interchangeable inputs and can be
            loaded together.
        fields: Quote sides the pull is expected to carry.
        min_tickers: Fewest distinct tickers a healthy copy has. A floor rather than a count,
            because a refreshed pull may widen and should not start failing for it.
        note: What the file is for, in a sentence.
    """

    name: str
    kind: str
    fields: tuple[str, ...]
    min_tickers: int
    note: str

    @property
    def two_sided(self) -> bool:
        """Whether the pull carries bid and ask, and so can price a cost."""
        return reference.PX_BID in self.fields and reference.PX_ASK in self.fields


_BOTH = (reference.PX_LAST, reference.PX_BID, reference.PX_ASK)
_MID = (reference.PX_LAST,)


def _spec(name, kind, fields, min_tickers, note) -> tuple[str, DataSpec]:
    return name, DataSpec(name, kind, fields, min_tickers, note)


#: Every pull this library knows how to read. Adding a file here is what makes it loadable by
#: kind; the table is deliberately literal, in the spirit of :mod:`fxcarry.reference`.
REGISTRY: dict[str, DataSpec] = dict(
    [
        _spec("spot_daily", "spot", _BOTH, 30,
              "Spot for the core currency universe, the longest history available."),
        _spec("spot_fwd_broad_daily", "spot", _BOTH, 12,
              "Spot and outright forwards for the broad dollar basket."),
        _spec("spot_fwd_em_daily", "spot", _BOTH, 12,
              "Spot and outright forwards for the emerging universe."),
        _spec("fwd_points_1m_daily", "forward_points", _BOTH, 30,
              "One-month forward points, the tenor the carry signal is built on."),
        _spec("fwd_points_grid_daily", "forward_points", _BOTH, 60,
              "Forward points across the tenor grid, for term-structure work."),
        _spec("fwd_points_multi_daily", "forward_points", _BOTH, 200,
              "Forward points at every tenor and currency pulled, the widest of the three."),
        _spec("fx_vol_daily", "vol_surface", _BOTH, 500,
              "Option volatility surface: at-the-money, risk reversals and butterflies."),
        _spec("fx_vol_grid_daily", "vol_surface", _BOTH, 400,
              "Volatility surface across the full tenor and delta grid."),
        _spec("fx_vol_broad_daily", "vol_surface", _BOTH, 50,
              "Volatility surface for the broad dollar basket."),
        _spec("fx_vol_em_daily", "vol_surface", _BOTH, 30,
              "Volatility surface for the emerging universe."),
        _spec("fx_short_rate_daily", "short_rate", _MID, 30,
              "Short-dated deposit rates, the parity check on forward-implied carry."),
        _spec("fx_dollar_index_daily", "dollar_index", _BOTH, 1,
              "Trade-weighted dollar indices."),
        _spec("tbill_daily", "riskfree", _MID, 1,
              "US Treasury bill yield, the domestic funding leg."),
    ]
)

#: The kinds, for callers that want to ask what is available.
KINDS: tuple[str, ...] = tuple(dict.fromkeys(spec.kind for spec in REGISTRY.values()))


class UnknownPull(KeyError):
    """A file that no :class:`DataSpec` describes, so nothing can be checked about it."""


class InvalidPull(ValueError):
    """A file that exists and is readable but does not hold what its name claims."""


@dataclass(frozen=True)
class Inspection:
    """What a file turned out to contain, next to what it was supposed to.

    Attributes:
        path: The file inspected.
        spec: What it was checked against, or None when the name is unregistered.
        rows: Row count, from the parquet footer.
        columns: Columns present.
        fields: Quote sides actually present.
        tickers: Distinct tickers, or None when not read deeply.
        problems: Everything wrong with it. Empty means usable.
    """

    path: Path
    spec: DataSpec | None
    rows: int
    columns: tuple[str, ...]
    fields: tuple[str, ...]
    tickers: int | None = None
    problems: tuple[str, ...] = field(default_factory=tuple)

    @property
    def ok(self) -> bool:
        """Whether the file can be loaded without surprises."""
        return not self.problems

    def raise_if_invalid(self) -> "Inspection":
        """Return self, or raise :class:`InvalidPull` listing every problem found."""
        if self.problems:
            listed = "\n".join(f"  - {p}" for p in self.problems)
            raise InvalidPull(f"{self.path} is not a usable {self.spec.kind if self.spec else 'pull'}:\n{listed}")
        return self

    def describe(self) -> str:
        """One line, for a log or a notebook."""
        kind = self.spec.kind if self.spec else "unregistered"
        seen = f"{self.tickers} tickers" if self.tickers is not None else "tickers unread"
        state = "ok" if self.ok else f"{len(self.problems)} problem(s)"
        return f"{self.path.name}: {kind}, {self.rows:,} rows, {seen}, {state}"


def spec_for(path: str | Path) -> DataSpec | None:
    """The specification a file's name claims, or None if the name is not registered."""
    return REGISTRY.get(Path(path).name.removesuffix(".parquet"))


def paths_for(kind: str, root: str | Path = "data/raw", present_only: bool = True) -> list[Path]:
    """Every registered file of one kind, in registry order.

    Order matters downstream: :class:`~fxcarry.quotes.ParquetSource` lets a later file win on
    a clash, so the widest or freshest pull should come last. The registry lists them that way.

    Args:
        kind: One of :data:`KINDS`.
        root: Directory the pulls live in.
        present_only: Skip files that have not been pulled, rather than failing on them.
    """
    if kind not in KINDS:
        raise UnknownPull(f"{kind!r} is not a known kind; expected one of {KINDS}.")
    found = [Path(root) / f"{name}.parquet"
             for name, spec in REGISTRY.items() if spec.kind == kind]
    return [p for p in found if p.exists()] if present_only else found


def inspect(path: str | Path, deep: bool = True) -> Inspection:
    """Check a file against its specification without loading it.

    Reads the parquet footer for the schema and row count, then one column for the fields and,
    when ``deep``, one more for the tickers. Even the largest surface here settles in well
    under a second, which is the point: the check has to be cheap enough that nobody skips it.

    Args:
        path: The parquet to look at.
        deep: Also count distinct tickers, which needs a column read.

    Raises:
        DataNotPulled: If the file is absent, with instructions for fetching it.
    """
    path = Path(path)
    if not path.exists():
        raise _data_not_pulled(path)

    spec = spec_for(path)
    problems: list[str] = []
    parquet = pq.ParquetFile(path)
    columns = tuple(parquet.schema_arrow.names)
    rows = parquet.metadata.num_rows

    missing = [c for c in LONG_COLUMNS if c not in columns]
    if missing:
        # Without these there is nothing to inspect further, so stop here rather than
        # producing a cascade of downstream complaints about the same cause.
        problems.append(f"missing column(s) {missing}; a pull is long-format {LONG_COLUMNS}")
        return Inspection(path, spec, rows, columns, (), None, tuple(problems))

    fields = tuple(sorted(pq.read_table(path, columns=["field"])["field"].to_pandas().unique()))
    tickers = None
    if deep:
        tickers = int(pq.read_table(path, columns=["ticker"])["ticker"].to_pandas().nunique())

    if spec is None:
        problems.append(
            f"no registry entry named {path.stem!r}; known pulls are {sorted(REGISTRY)}"
        )
    else:
        absent = [f for f in spec.fields if f not in fields]
        if absent:
            problems.append(f"expected field(s) {absent} for a {spec.kind} pull, found {list(fields)}")
        if tickers is not None and tickers < spec.min_tickers:
            problems.append(
                f"only {tickers} tickers, expected at least {spec.min_tickers} for "
                f"{spec.name}; the file may be truncated or the wrong pull"
            )
    if rows == 0:
        problems.append("no rows")

    return Inspection(path, spec, rows, columns, fields, tickers, tuple(problems))


def source(
    *paths: str | Path,
    kind: str | None = None,
    root: str | Path = "data/raw",
    deep: bool = True,
) -> ParquetSource:
    """A validated :class:`~fxcarry.quotes.ParquetSource` over one or more pulls.

    Either name the paths, or ask for a ``kind`` and let the registry find them. Every file is
    inspected first, so a wrong or truncated pull is reported by name here rather than as an
    empty panel three steps later.

    Loading several files of one kind is the normal case rather than an edge: the pulls overlap
    in both period and universe, and ``ParquetSource`` resolves a clash in favour of the file
    listed last. So a long, narrow history and a short, wide one combine into the union of
    both without either being special-cased.

    Args:
        paths: Explicit files. Mutually exclusive with ``kind``.
        kind: Load every present pull of this kind instead.
        root: Where the pulls live, when ``kind`` is used.
        deep: Count tickers as well as checking the schema.

    Raises:
        InvalidPull: If any file fails its specification.
        DataNotPulled: If a file is absent.
    """
    if bool(paths) == (kind is not None):
        raise ValueError("Pass either explicit paths or a kind, not both and not neither.")
    chosen = [Path(p) for p in paths] if paths else paths_for(kind, root)
    if not chosen:
        raise _data_not_pulled(Path(root) / f"<any {kind} pull>")
    for path in chosen:
        inspect(path, deep=deep).raise_if_invalid()
    return ParquetSource(*chosen)


def survey(root: str | Path = "data/raw", deep: bool = True) -> list[Inspection]:
    """Inspect every registered pull that is present, for a one-glance health check."""
    root = Path(root)
    return [
        inspect(root / f"{name}.parquet", deep=deep)
        for name in REGISTRY
        if (root / f"{name}.parquet").exists()
    ]
