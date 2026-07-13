"""Load raw Bloomberg parquet pulls into tidy (date x currency) panels.

Responsibilities:
  - Read the raw parquet files produced by ``notebooks/00_bloomberg_pull.ipynb``.
  - Normalize whatever tabular shape ``xbbg`` produced into a wide
    ``(ticker, field)`` MultiIndex-column frame, indexed by date. Two shapes
    are supported: the classic (pre-1.0) xbbg wide shape, and the long/tidy
    ``ticker, date, field, value`` shape returned by default by the
    Rust-powered xbbg (>=1.0).
  - Relabel ticker columns to canonical ISO currency codes.
  - Snap daily data to the requested frequency (default: end-of-month).

Nothing here hard-codes a currency universe, ticker, or file name -- all of
those defaults live in :mod:`fxcarry.constants` and are passed in.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from . import constants as const


def _resample_alias(freq: str) -> str:
    """Map a public-facing frequency code to the pandas resample alias,
    falling back to the raw code on pandas versions that don't recognize the
    modern alias (e.g. "ME" was only added in pandas 2.2; older/newer
    pandas releases may only understand "M" or vice versa)."""
    alias = const.RESAMPLE_ALIAS.get(freq, freq)
    try:
        pd.tseries.frequencies.to_offset(alias)
        return alias
    except ValueError:
        return freq


def _ticker_to_ccy_map(tickers: dict[str, tuple[str, str]], ticker_index: int) -> dict[str, str]:
    return {tks[ticker_index]: ccy for ccy, tks in tickers.items()}


# Columns identifying the long/tidy shape that Rust-powered xbbg (>=1.0)
# returns by default: one row per (ticker, date, field) observation.
_LONG_FORMAT_COLUMNS = {"ticker", "field", "value"}


def _normalize_to_wide(raw: pd.DataFrame) -> pd.DataFrame:
    """Normalize a raw parquet frame into the wide ``(ticker, field)``
    MultiIndex-column shape (indexed by date) expected by :func:`_split_fields`,
    regardless of which xbbg version produced it:

      - classic (pre-1.0) xbbg: already wide, ``(ticker, field)`` MultiIndex
        columns, indexed by date.
      - Rust-powered xbbg (>=1.0), default output: long/tidy, one row per
        observation with ``ticker``, ``date``, ``field``, ``value`` columns.
    """
    if isinstance(raw.columns, pd.MultiIndex):
        if not isinstance(raw.index, pd.DatetimeIndex):
            raw.index = pd.to_datetime(raw.index)
        return raw

    if _LONG_FORMAT_COLUMNS.issubset(set(raw.columns)):
        date_col = "date" if "date" in raw.columns else (raw.index.name or "index")
        long_df = raw if "date" in raw.columns else raw.reset_index().rename(
            columns={raw.index.name or "index": date_col}
        )
        wide = long_df.pivot(index=date_col, columns=["ticker", "field"], values="value")
        wide.index = pd.to_datetime(wide.index)
        wide.index.name = None
        return wide

    raise ValueError(
        "Unrecognized raw frame shape: expected either a classic xbbg-style "
        "wide (ticker, field) MultiIndex-column frame, or a long/tidy frame "
        f"with columns including {sorted(_LONG_FORMAT_COLUMNS)}; got "
        f"columns={list(raw.columns)[:8]}."
    )


def _split_fields(
    raw: pd.DataFrame,
    tickers: dict[str, tuple[str, str]],
    ticker_index: int,
) -> dict[str, pd.DataFrame]:
    """Split a wide (ticker, field) MultiIndex-column frame (already
    normalized via :func:`_normalize_to_wide`) into ``{"mid": df, "bid": df,
    "ask": df}`` with columns relabeled to ISO codes.
    """
    ticker_to_ccy = _ticker_to_ccy_map(tickers, ticker_index)

    out: dict[str, pd.DataFrame] = {}
    field_level_values = set(raw.columns.get_level_values(-1))
    for bbg_field, key in const.FIELD_TO_KEY.items():
        if bbg_field not in field_level_values:
            continue
        sub = raw.xs(bbg_field, axis=1, level=-1)
        sub = sub.rename(columns=ticker_to_ccy)
        keep = [c for c in sub.columns if c in ticker_to_ccy.values()]
        sub = sub.loc[:, keep]
        sub = sub.loc[:, ~sub.columns.duplicated()]
        sub = sub.sort_index(axis=1)
        out[key] = sub

    if not out:
        raise ValueError(
            f"None of the expected fields {list(const.FIELD_TO_KEY)} were found "
            f"in the raw frame's field level ({sorted(field_level_values)})."
        )
    return out


def _snap_to_freq(frames: dict[str, pd.DataFrame], freq: str | None) -> dict[str, pd.DataFrame]:
    if not freq:
        return {key: df.sort_index() for key, df in frames.items()}
    alias = _resample_alias(freq)
    return {key: df.sort_index().resample(alias).last() for key, df in frames.items()}


def _load_ticker_panel(
    path: str | Path,
    tickers: dict[str, tuple[str, str]],
    ticker_index: int,
    freq: str | None,
) -> dict[str, pd.DataFrame]:
    raw = pd.read_parquet(path)
    wide = _normalize_to_wide(raw)
    frames = _split_fields(wide, tickers, ticker_index=ticker_index)
    return _snap_to_freq(frames, freq)


def load_spot(
    path: str | Path,
    freq: str = const.DEFAULT_FREQ,
    tickers: dict[str, tuple[str, str]] | None = None,
) -> dict[str, pd.DataFrame]:
    """Load raw spot parquet into ``{"mid": df, "bid": df, "ask": df}``
    (each shaped dates x currencies, columns as ISO codes)."""
    tickers = const.DEFAULT_TICKERS if tickers is None else tickers
    return _load_ticker_panel(path, tickers, ticker_index=0, freq=freq)


def load_fwd_points(
    path: str | Path,
    freq: str = const.DEFAULT_FREQ,
    tickers: dict[str, tuple[str, str]] | None = None,
) -> dict[str, pd.DataFrame]:
    """Load raw 1M forward-points parquet into the same
    ``{"mid": df, "bid": df, "ask": df}`` structure as :func:`load_spot`."""
    tickers = const.DEFAULT_TICKERS if tickers is None else tickers
    return _load_ticker_panel(path, tickers, ticker_index=1, freq=freq)


def load_yield_series(
    path: str | Path,
    freq: str = const.DEFAULT_FREQ,
    field: str = const.PX_LAST,
    periods_per_year: float | None = None,
) -> pd.Series:
    """Load a single-ticker annualized-yield quote (e.g. a T-bill proxy) and
    convert it to a periodic *simple* rate: ``(yield_pct / 100) / periods_per_year``.

    Generic on purpose: reusable for any risk-free-rate-style ticker, not
    just the BER Figure-1 T-bill leg. ``periods_per_year`` defaults to the
    value implied by ``freq`` via :data:`fxcarry.constants.PERIODS_PER_YEAR`.
    """
    raw = pd.read_parquet(path)
    wide = _normalize_to_wide(raw)
    field_level_values = set(wide.columns.get_level_values(-1))
    if field in field_level_values:
        ser = wide.xs(field, axis=1, level=-1).iloc[:, 0]
    else:
        ser = wide.iloc[:, 0]

    ser = ser.sort_index()
    if freq:
        ser = ser.resample(_resample_alias(freq)).last()

    ppy = periods_per_year if periods_per_year is not None else const.PERIODS_PER_YEAR.get(
        freq, const.DEFAULT_ANNUALIZATION
    )
    return (ser / 100.0) / ppy


def coverage_summary(df: pd.DataFrame) -> pd.DataFrame:
    """Per-column coverage report: first/last non-null date and count.

    Useful as a data-quality check ("for each currency, check the date
    range of non-null spot values").
    """
    rows = {}
    for col in df.columns:
        s = df[col].dropna()
        rows[col] = {
            "first_valid": s.index.min() if not s.empty else pd.NaT,
            "last_valid": s.index.max() if not s.empty else pd.NaT,
            "n_obs": int(s.shape[0]),
        }
    return pd.DataFrame(rows).T


def validate_bid_ask(mid: pd.DataFrame, bid: pd.DataFrame, ask: pd.DataFrame) -> pd.DataFrame:
    """Boolean (date x currency) frame flagging bid <= mid <= ask violations
    (a data-quality check). ``False``/``NaN`` = OK."""
    common = mid.columns.intersection(bid.columns).intersection(ask.columns)
    violation = (bid[common] > mid[common]) | (mid[common] > ask[common])
    return violation.reindex(columns=mid.columns, fill_value=False)
