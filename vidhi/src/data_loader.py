from __future__ import annotations

import re
from pathlib import Path
from typing import Iterable

import numpy as np
import pandas as pd


KNOWN_CURRENCIES = {
    "AUD", "BRL", "CAD", "CHF", "CLP", "CNH", "CNY", "COP", "CZK", "DKK",
    "EUR", "GBP", "HUF", "IDR", "ILS", "INR", "JPY", "KRW", "MXN", "MYR",
    "NOK", "NZD", "PHP", "PLN", "RON", "RUB", "SEK", "SGD", "THB", "TRY",
    "TWD", "USD", "ZAR",
}

# Currencies commonly quoted as USD per foreign currency.
USD_PER_FX_DEFAULT = {"AUD", "EUR", "GBP", "NZD"}

SPOT_HINTS = ("SPOT", "PX_LAST", "LAST", "CLOSE")
FORWARD_HINTS = ("1M", "1MO", "1 MONTH", "FWD", "FORWARD")


def _flatten_columns(columns: pd.Index) -> list[str]:
    if isinstance(columns, pd.MultiIndex):
        return [
            "__".join(str(part) for part in col if str(part) not in {"", "None"})
            for col in columns
        ]
    return [str(c) for c in columns]


def normalize_frame(df: pd.DataFrame) -> pd.DataFrame:
    """Return a numeric, date-indexed frame with flattened columns."""
    out = df.copy()
    out.columns = _flatten_columns(out.columns)

    if not isinstance(out.index, pd.DatetimeIndex):
        date_candidates = [
            c for c in out.columns
            if c.lower() in {"date", "datetime", "timestamp", "index"}
            or "date" in c.lower()
        ]
        if date_candidates:
            date_col = date_candidates[0]
            out[date_col] = pd.to_datetime(out[date_col], errors="coerce")
            out = out.set_index(date_col)
        else:
            parsed = pd.to_datetime(out.index, errors="coerce")
            if parsed.notna().mean() < 0.8:
                raise ValueError("Could not identify a usable date index.")
            out.index = parsed

    out.index = pd.to_datetime(out.index, errors="coerce")
    out = out.loc[~out.index.isna()].sort_index()
    out = out.loc[~out.index.duplicated(keep="last")]
    out = out.apply(pd.to_numeric, errors="coerce")
    return out.dropna(axis=1, how="all")


def read_parquet(path: str | Path) -> pd.DataFrame:
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"Missing required file: {path}")
    return normalize_frame(pd.read_parquet(path))


def inventory_data(data_dir: str | Path) -> tuple[pd.DataFrame, pd.DataFrame]:
    data_dir = Path(data_dir)
    file_rows: list[dict] = []
    column_rows: list[dict] = []

    for path in sorted(data_dir.glob("*")):
        if path.suffix.lower() not in {".parquet", ".csv", ".xlsx"}:
            continue

        row = {
            "file": path.name,
            "suffix": path.suffix.lower(),
            "size_mb": path.stat().st_size / 1e6,
        }

        try:
            if path.suffix.lower() == ".parquet":
                df = pd.read_parquet(path)
            elif path.suffix.lower() == ".csv":
                df = pd.read_csv(path, nrows=200)
            else:
                df = pd.read_excel(path, nrows=200)

            row.update(
                {
                    "rows_loaded": len(df),
                    "columns": len(df.columns),
                    "status": "ok",
                }
            )
            for col in _flatten_columns(df.columns):
                column_rows.append({"file": path.name, "column": col})
        except Exception as exc:
            row.update(
                {
                    "rows_loaded": np.nan,
                    "columns": np.nan,
                    "status": f"error: {exc}",
                }
            )

        file_rows.append(row)

    return pd.DataFrame(file_rows), pd.DataFrame(column_rows)


def select_columns(df: pd.DataFrame, patterns: Iterable[str]) -> pd.DataFrame:
    regex = re.compile("|".join(re.escape(p) for p in patterns), flags=re.IGNORECASE)
    cols = [c for c in df.columns if regex.search(str(c))]
    return df.loc[:, cols].copy()


def _compact(text: str) -> str:
    return re.sub(r"[^A-Z0-9]", "", str(text).upper())


FORWARD_ROOT_ALIASES = {
    "BCN": "BRL",
    "CHN": "CNY",
    "CLN": "CLP",
    "IHO": "IDR",
    "KWN": "KRW",
    "NTN": "TWD",
    "PPN": "PHP",
    "IRN": "INR",
    "MRN": "MYR",
}

INVERT_TO_USD_PER_FX = {
    "BRL", "CAD", "CHF", "CLP", "CNH", "CNY", "COP", "CZK", "DKK",
    "HUF", "IDR", "ILS", "INR", "JPY", "KRW", "MXN", "MYR", "NOK",
    "PHP", "PLN", "RON", "RUB", "SEK", "SGD", "THB", "TRY", "TWD",
    "ZAR",
}


def parse_bloomberg_fx_column(column: str) -> dict | None:
    """Parse labels such as AUD Curncy__PX_LAST or BCN1M Curncy__PX_LAST."""
    text = str(column).upper().strip()
    match = re.match(
        r"^([A-Z]{3})(?:(1W|1M|3M|6M|12M))?\s+CURNCY__(PX_LAST|PX_BID|PX_ASK)$",
        text,
    )
    if not match:
        return None
    root, tenor, field = match.groups()
    return {"root": root, "tenor": tenor or "SPOT", "field": field}


def _choose_best_field(group: pd.DataFrame) -> pd.Series | None:
    if group.empty:
        return None
    priority = {"PX_LAST": 0, "PX_BID": 1, "PX_ASK": 2}
    ranked = group.copy()
    ranked["field_priority"] = ranked["field"].map(priority).fillna(99)
    return ranked.sort_values(
        ["field_priority", "coverage"],
        ascending=[True, False],
    ).iloc[0]


def discover_fx_columns(
    df: pd.DataFrame,
    minimum_non_null_fraction: float = 0.50,
) -> tuple[dict[str, str], dict[str, str], dict[str, bool], pd.DataFrame]:
    """
    Match the actual Bloomberg schema used by the project.

    Spot example: AUD Curncy__PX_LAST
    Forward example: AUD1M Curncy__PX_LAST
    EM/NDF example: BCN1M Curncy__PX_LAST maps to BRL
    """
    rows = []
    for column in df.columns:
        parsed = parse_bloomberg_fx_column(column)
        if parsed is None:
            continue
        coverage = float(df[column].notna().mean())
        if coverage < minimum_non_null_fraction:
            continue
        rows.append({
            "column": str(column),
            "root": parsed["root"],
            "tenor": parsed["tenor"],
            "field": parsed["field"],
            "coverage": coverage,
        })

    metadata = pd.DataFrame(rows)
    if metadata.empty:
        raise ValueError(
            "No columns matched the expected Bloomberg schema, such as "
            "'AUD Curncy__PX_LAST' or 'AUD1M Curncy__PX_LAST'."
        )

    spot_rows = metadata[metadata["tenor"].eq("SPOT")]
    forward_rows = metadata[metadata["tenor"].eq("1M")]

    alias_roots = {}
    for root, currency in FORWARD_ROOT_ALIASES.items():
        alias_roots.setdefault(currency, []).append(root)

    currencies = sorted(
        root for root in set(spot_rows["root"]) if root in KNOWN_CURRENCIES
    )

    spot_map = {}
    forward_map = {}
    inversion_map = {}
    diagnostics = []

    for currency in currencies:
        spot_choice = _choose_best_field(
            spot_rows[spot_rows["root"].eq(currency)]
        )
        possible_forward_roots = [currency] + alias_roots.get(currency, [])
        forward_choice = _choose_best_field(
            forward_rows[forward_rows["root"].isin(possible_forward_roots)]
        )

        if spot_choice is None:
            status = "missing_spot"
        elif forward_choice is None:
            status = "missing_1m_forward"
        else:
            status = "ok"
            spot_map[currency] = str(spot_choice["column"])
            forward_map[currency] = str(forward_choice["column"])
            inversion_map[currency] = currency in INVERT_TO_USD_PER_FX

        diagnostics.append({
            "currency": currency,
            "spot_column": None if spot_choice is None else spot_choice["column"],
            "forward_column": None if forward_choice is None else forward_choice["column"],
            "forward_root": None if forward_choice is None else forward_choice["root"],
            "invert_to_usd_per_fx": currency in INVERT_TO_USD_PER_FX,
            "status": status,
        })

    return (
        spot_map,
        forward_map,
        inversion_map,
        pd.DataFrame(diagnostics).sort_values("currency"),
    )


def build_fx_panels(
    df: pd.DataFrame,
    minimum_currencies: int = 6,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """Build spot and 1M forward panels in USD-per-foreign-currency terms."""
    spot_map, forward_map, inversion_map, diagnostics = discover_fx_columns(df)

    if len(spot_map) < minimum_currencies:
        raise RuntimeError(
            f"Only {len(spot_map)} currencies were matched. "
            "Inspect outputs/fx_field_diagnostics.csv."
        )

    spot = pd.DataFrame({ccy: df[col] for ccy, col in spot_map.items()})
    forward = pd.DataFrame({ccy: df[col] for ccy, col in forward_map.items()})

    for currency, invert in inversion_map.items():
        if invert:
            spot[currency] = 1.0 / spot[currency]
            forward[currency] = 1.0 / forward[currency]

    common = sorted(set(spot.columns) & set(forward.columns))
    return spot[common], forward[common], diagnostics
