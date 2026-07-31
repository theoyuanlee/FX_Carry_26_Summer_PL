"""Two-sided market data, and the one pipeline that reads it.

Pulls arrive long: one row per ``(ticker, date, field)`` observation. Turning that into
something usable is always the same three steps, so :class:`QuoteSource` holds them once.

    read the long frame  ->  map each ticker to a column label  ->  pivot by field

Only the map varies between instruments, and it comes from a
:class:`~fxcarry.catalog.Catalog`. Nothing here inspects a ticker string.

Files carrying all three quoted sides come back as :class:`Quotes`. Single-field data has no
sides, so it comes back as a frame or a series.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Callable, Iterator, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path

import pandas as pd
import pyarrow.parquet as pq

from fxcarry import reference

_LONG_COLUMNS = ("ticker", "date", "field", "value")


class DataNotPulled(FileNotFoundError):
    """A tracked parquet is not on disk, almost always because nobody has pulled it yet.

    Worth its own type rather than a bare ``FileNotFoundError`` because the fix is specific
    and unguessable: the file is not missing, it is unmaterialised, and the pointer next to
    it says so.
    """


def _dvc_root(path: Path) -> Path | None:
    """Nearest ancestor holding a ``.dvc`` directory, which is where a pull has to be run."""
    resolved = path if path.is_absolute() else Path.cwd() / path
    for parent in resolved.resolve().parents:
        if (parent / ".dvc").is_dir():
            return parent
    return None


def _data_not_pulled(path: Path) -> DataNotPulled:
    """The error to raise when a parquet is absent, with the fix spelled out.

    Whoever hits this is usually running someone else's notebook on a fresh clone, so the
    message has to carry the whole recipe: which directory to stand in, what to type, where
    the bytes come from, and what to do when the tool is not installed either.
    """
    root = _dvc_root(path)
    pointer = path.with_name(path.name + ".dvc")
    lines = [f"No data file at {path}."]

    if pointer.is_file():
        lines.append(
            f"Its DVC pointer ({pointer.name}) is there, so the file is tracked and simply "
            "has not been pulled yet."
        )
    else:
        lines.append(
            "fxcarry keeps its pulls under DVC rather than in git, so a fresh clone has the "
            "pointer files and none of the parquet."
        )

    where = root if root is not None else "the folder containing .dvc"
    lines += [
        "",
        "To fetch it:",
        f"    cd {where}",
        "    dvc pull",
        "",
        f"The default remote is the public dataset {reference.DATA_REMOTE_URL},",
        "so this needs no account and no credentials.",
        "",
        f"If dvc is not installed:  {reference.DVC_INSTALL_HINT}",
        f"Other ways to install it: {reference.DVC_INSTALL_URL}",
    ]

    if root is None:
        lines += [
            "",
            "Note: no .dvc directory was found above this path, so either you are outside the "
            "project or the path itself is wrong.",
        ]
    return DataNotPulled("\n".join(lines))


def _resample_alias(freq: str) -> str:
    """Public frequency code mapped to an offset alias this pandas build accepts."""
    alias = reference.RESAMPLE_ALIAS.get(freq, freq)
    try:
        pd.tseries.frequencies.to_offset(alias)
    except ValueError:
        return freq
    return alias


def _clean_axes(frame: pd.DataFrame) -> pd.DataFrame:
    """Drop the axis names a pivot leaves behind, which otherwise title every plot."""
    frame.index.name = None
    frame.columns.name = None
    return frame


def _validate_long(frame: pd.DataFrame) -> pd.DataFrame:
    """Check a frame is long and return it with a real datetime ``date`` column.

    Raises:
        ValueError: If any of the four long columns is missing.
    """
    missing = [c for c in _LONG_COLUMNS if c not in frame.columns]
    if missing:
        raise ValueError(
            f"Expected a long frame with columns {list(_LONG_COLUMNS)}; "
            f"{missing} are absent and the columns present are {list(frame.columns)[:8]}."
        )
    out = frame.loc[:, list(_LONG_COLUMNS)].copy()
    out["date"] = pd.to_datetime(out["date"])
    return out


@dataclass(frozen=True)
class Quotes:
    """The three quoted sides of one panel, sharing an index and a column set.

    The sides are pivoted out of a single frame, so they cannot come out misaligned. That is
    what makes :meth:`apply` safe: mid only ever meets mid, bid only ever meets bid.

    Attributes:
        mid: Date by label frame of mid quotes.
        bid: Date by label frame of bids.
        ask: Date by label frame of asks.
    """

    mid: pd.DataFrame
    bid: pd.DataFrame
    ask: pd.DataFrame

    def __iter__(self) -> Iterator[pd.DataFrame]:
        """Yield the sides in mid, bid, ask order."""
        yield from (self.mid, self.bid, self.ask)

    @property
    def columns(self) -> pd.Index:
        """Column labels, read off mid."""
        return self.mid.columns

    @property
    def index(self) -> pd.Index:
        """Date index, read off mid."""
        return self.mid.index

    def select(self, columns: Sequence[str] | pd.Index) -> "Quotes":
        """Narrow every side to ``columns``, in the order given."""
        cols = list(columns)
        return Quotes(*(df.loc[:, cols] for df in self))

    def apply(self, fn: Callable[..., pd.DataFrame], *others: "Quotes") -> "Quotes":
        """Combine sides positionally through ``fn``.

        ``fn`` is called once per side, with that side taken from this object and from each of
        ``others``. Pairing sides rather than whole objects is what stops a spread being
        crossed by accident.
        """
        return Quotes(*(fn(*sides) for sides in zip(self, *others)))

    def invert(self, columns: Sequence[str] | None = None) -> "Quotes":
        """Reciprocate the named columns, swapping bid and ask on exactly those.

        Inverting turns the larger number into the smaller one, so the old ask becomes the new
        bid. Skipping the swap crosses the spread and pays a negative transaction cost.

        Args:
            columns: Labels to invert; None inverts every column.
        """
        cols = list(self.columns if columns is None else columns)

        def flip(frame: pd.DataFrame, source: pd.DataFrame) -> pd.DataFrame:
            out = frame.copy()
            out[cols] = 1.0 / source[cols]
            return out

        return Quotes(
            mid=flip(self.mid, self.mid),
            bid=flip(self.bid, self.ask),
            ask=flip(self.ask, self.bid),
        )

    def spread(self) -> pd.DataFrame:
        """Ask minus bid."""
        return self.ask - self.bid

    def half_spread(self, relative: bool = True) -> pd.DataFrame:
        """Half the quoted spread, as a fraction of mid unless ``relative`` is False."""
        half = self.spread() / 2.0
        return half / self.mid if relative else half

    def crossed(self) -> pd.DataFrame:
        """True where ``bid <= mid <= ask`` is violated. NaN cells read as fine."""
        return (self.bid > self.mid) | (self.mid > self.ask)

    def coverage(self) -> pd.DataFrame:
        """Per-column first and last valid date and observation count, read off mid."""
        rows = {}
        for col in self.mid.columns:
            series = self.mid[col].dropna()
            rows[col] = {
                "first_valid": series.index.min() if not series.empty else pd.NaT,
                "last_valid": series.index.max() if not series.empty else pd.NaT,
                "n_obs": int(series.shape[0]),
            }
        return pd.DataFrame(rows).T


class QuoteSource(ABC):
    """Somewhere long-format market data can be read from.

    Subclasses supply :meth:`long_frame`. Everything else is shared, because the difference
    between loading spot, forwards, rates and option surfaces is which tickers map to which
    column, not how the reshaping works.
    """

    @abstractmethod
    def long_frame(self) -> pd.DataFrame:
        """The validated long frame, with columns ticker, date, field and value."""

    def tickers(self) -> pd.Index:
        """Distinct tickers present."""
        return pd.Index(self.long_frame()["ticker"].unique())

    def _labelled(self, label_of: Mapping[str, str]) -> pd.DataFrame:
        frame = self.long_frame()
        out = frame[frame["ticker"].isin(label_of)].copy()
        out["label"] = out["ticker"].map(dict(label_of))
        return out

    def quotes(self, label_of: Mapping[str, str], freq: str | None = None) -> Quotes:
        """Mid, bid and ask panels for the tickers in ``label_of``.

        Pivoting once on a ``(field, label)`` column index and slicing afterwards keeps the
        three sides on one index and one column set.

        Raises:
            ValueError: If no ticker matched, or any of the three fields is absent.
        """
        labelled = self._labelled(label_of)
        if labelled.empty:
            raise ValueError("No rows matched the requested tickers; nothing to pivot.")
        wide = labelled.pivot_table(
            index="date", columns=["field", "label"], values="value", aggfunc="last"
        ).sort_index()
        if freq:
            wide = wide.resample(_resample_alias(freq)).last()

        present = set(wide.columns.get_level_values(0))
        missing = [f for f in reference.FIELDS if f not in present]
        if missing:
            raise ValueError(
                f"Cannot build two-sided quotes: {missing} absent, found {sorted(present)}. "
                "Single-field data has no sides; read it with panel() or series()."
            )
        labels = sorted(set(wide.columns.get_level_values(1)))
        sides = {
            reference.FIELD_TO_KEY[f]: _clean_axes(wide[f].reindex(columns=labels))
            for f in reference.FIELDS
        }
        return Quotes(**sides)

    def panel(
        self,
        label_of: Mapping[str, str],
        field: str = reference.PX_LAST,
        freq: str | None = None,
    ) -> pd.DataFrame:
        """One field as a date by label frame."""
        labelled = self._labelled(label_of)
        return self._pivot(labelled[labelled["field"] == field], freq)

    def series(
        self,
        ticker: str,
        field: str = reference.PX_LAST,
        freq: str | None = None,
    ) -> pd.Series:
        """One ticker's single field as a date-indexed series.

        Raises:
            ValueError: If the ticker and field pair has no rows.
        """
        frame = self.long_frame()
        rows = frame[(frame["ticker"] == ticker) & (frame["field"] == field)]
        if rows.empty:
            raise ValueError(f"No {field} rows for ticker {ticker!r}.")
        wide = self._pivot(rows.assign(label=ticker), freq)
        return wide.iloc[:, 0]

    @staticmethod
    def _pivot(labelled: pd.DataFrame, freq: str | None) -> pd.DataFrame:
        wide = labelled.pivot_table(
            index="date", columns="label", values="value", aggfunc="last"
        ).sort_index().sort_index(axis=1)
        if freq:
            wide = wide.resample(_resample_alias(freq)).last()
        return _clean_axes(wide)


class ParquetSource(QuoteSource):
    """Long parquets on disk, concatenated.

    Where two files carry the same ``(ticker, date, field)``, the later path wins, so a
    refreshed pull can be listed after the one it supersedes without editing either.
    """

    def __init__(self, *paths: str | Path):
        if not paths:
            raise ValueError("ParquetSource needs at least one path.")
        self._paths = [Path(p) for p in paths]
        self._frame: pd.DataFrame | None = None

    def long_frame(self) -> pd.DataFrame:
        """Read, concatenate and de-duplicate the parquets. Cached after the first call."""
        if self._frame is None:
            frames = []
            for path in self._paths:
                if not path.exists():
                    raise _data_not_pulled(path)
                # Arrow hands date32 back as Python date objects, which is ruinous on a
                # sixteen-million-row pull; date_as_object=False lands datetime64 directly.
                raw = pq.read_table(path).to_pandas(date_as_object=False)
                frames.append(_validate_long(raw))
            combined = pd.concat(frames, ignore_index=True)
            self._frame = combined.drop_duplicates(
                ["ticker", "date", "field"], keep="last"
            ).reset_index(drop=True)
        return self._frame


class FrameSource(QuoteSource):
    """A long frame already in memory."""

    def __init__(self, frame: pd.DataFrame):
        self._frame = _validate_long(frame)

    def long_frame(self) -> pd.DataFrame:
        """The frame this source was built from."""
        return self._frame
