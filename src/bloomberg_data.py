from __future__ import annotations
import asyncio
import time
from pathlib import Path
from typing import Iterable

import pandas as pd
from xbbg import blp


# =========================
# 1. Global settings
# =========================

START_DATE = "2007-01-01"
END_DATE = pd.Timestamp.today().strftime("%Y-%m-%d")

# Save output next to this .py file, not in whatever directory you happen to run Python from.
# If you prefer another location, replace this with an absolute path, e.g.
# OUT_DIR = Path(r"C:\\temp\\bloomberg_fx_carry_raw")
SCRIPT_DIR = Path(__file__).resolve().parent
OUT_DIR = SCRIPT_DIR / "bloomberg_fx_carry_raw"
OUT_DIR.mkdir(parents=True, exist_ok=True)

PRICE_FIELDS = ["PX_LAST", "PX_BID", "PX_ASK"]
LAST_FIELD = ["PX_LAST"]

CHUNK_SIZE = 40
SLEEP_SECONDS = 0.25

# Optional: set this to a list if you only want to rerun specific groups.
# Example:
# RUN_GROUPS = ["em_fx_spot_forward"]
RUN_GROUPS = None


# =========================
# 2. Helpers
# =========================

def unique_keep_order(items: Iterable[str]) -> list[str]:
    seen = set()
    out = []
    for x in items:
        if x and x not in seen:
            out.append(x)
            seen.add(x)
    return out


def chunks(items: list[str], n: int):
    for i in range(0, len(items), n):
        yield items[i:i + n]


def ensure_pandas_df(obj) -> pd.DataFrame:
    """
    Convert a Bloomberg/xbbg result into a pandas DataFrame.

    Some environments return a DataFrame-like object that does not expose
    pandas' `.empty` attribute. Converting immediately makes the rest of the
    code stable.
    """
    if obj is None:
        return pd.DataFrame()

    if isinstance(obj, pd.DataFrame):
        return obj

    # Polars, Spark-like, and some wrapper DataFrames expose one of these.
    if hasattr(obj, "to_pandas"):
        return obj.to_pandas()

    if hasattr(obj, "toPandas"):
        return obj.toPandas()

    # Last-resort conversion for array/list/dict-like objects.
    try:
        return pd.DataFrame(obj)
    except Exception as exc:
        raise TypeError(
            f"Bloomberg returned an object of type {type(obj)!r}, "
            "and it could not be converted to a pandas DataFrame."
        ) from exc


def is_empty_df(obj) -> bool:
    """Safe emptiness check for pandas and DataFrame-like objects."""
    if obj is None:
        return True

    if hasattr(obj, "empty"):
        return bool(obj.empty)

    if hasattr(obj, "shape"):
        shape = obj.shape
        return len(shape) >= 2 and (shape[0] == 0 or shape[1] == 0)

    try:
        return len(obj) == 0
    except TypeError:
        return False


def normalize_bdh_to_long(df: pd.DataFrame) -> pd.DataFrame:
    """
    Convert Bloomberg / xbbg historical output to long format:
        date, ticker, field, value

    This version is defensive against several xbbg/pandas output shapes:
    1. normal xbbg output: index=date, columns=MultiIndex(ticker, field)
    2. simple wide output: index=date, columns=tickers
    3. already-long output: columns include date, ticker, field, value
    4. already-date-column output that also has a column named "value"

    The previous versions failed because:
    - reset_index() could collide with an existing "date" column;
    - melt(value_name="value") fails if a column named "value" already exists.
    """
    df = ensure_pandas_df(df)

    if is_empty_df(df):
        return pd.DataFrame(columns=["date", "ticker", "field", "value"])

    df = df.copy()

    # Case 0: Bloomberg/xbbg result is already in long format.
    # Normalize column names case-insensitively, but preserve the actual columns.
    lower_to_actual = {str(c).strip().lower(): c for c in df.columns}
    required = {"date", "ticker", "field", "value"}
    if required.issubset(lower_to_actual):
        out = df[[
            lower_to_actual["date"],
            lower_to_actual["ticker"],
            lower_to_actual["field"],
            lower_to_actual["value"],
        ]].copy()
        out.columns = ["date", "ticker", "field", "value"]
        return out

    # Case 1: typical xbbg BDH output with MultiIndex columns: (ticker, field)
    if isinstance(df.columns, pd.MultiIndex):
        # Use a temporary index name so reset_index never collides with an
        # existing column named "date".
        df.index.name = "__date_index__"

        try:
            stacked = df.stack(list(range(df.columns.nlevels)), future_stack=True)
        except TypeError:
            # Older pandas does not support future_stack.
            stacked = df.stack(list(range(df.columns.nlevels)))

        long = stacked.reset_index()

        # Expected columns after stacking 2-level MultiIndex:
        # __date_index__, level_1(ticker), level_2(field), value
        if long.shape[1] == 4:
            long.columns = ["date", "ticker", "field", "value"]
        else:
            # Fallback for unusual column depths: combine non-date/non-value
            # levels into ticker and mark field as UNKNOWN.
            value_col = long.columns[-1]
            date_col = long.columns[0]
            level_cols = list(long.columns[1:-1])
            long = long.rename(columns={date_col: "date", value_col: "value"})
            long["ticker"] = long[level_cols].astype(str).agg("|".join, axis=1)
            long["field"] = "UNKNOWN"
            long = long[["date", "ticker", "field", "value"]]

        return long

    # Case 2 / 3: simple wide output.
    # Do NOT blindly call reset_index() after naming the index "date", because
    # the DataFrame may already contain a "date" column.
    if any(str(c).strip().lower() == "date" for c in df.columns):
        date_col = next(c for c in df.columns if str(c).strip().lower() == "date")
        wide = df.copy().rename(columns={date_col: "date"})
    else:
        wide = df.reset_index()
        # Rename the first column, whatever it is called, to date.
        wide = wide.rename(columns={wide.columns[0]: "date"})

    value_cols = [c for c in wide.columns if c != "date"]

    if not value_cols:
        return pd.DataFrame(columns=["date", "ticker", "field", "value"])

    # Important: pandas.melt(value_name="value") raises an error if a column
    # named "value" already exists. Use a temporary output column name, then rename.
    melted_value_col = "__bbg_value__"
    while melted_value_col in wide.columns:
        melted_value_col = "_" + melted_value_col

    long = wide.melt(
        id_vars="date",
        value_vars=value_cols,
        var_name="ticker",
        value_name=melted_value_col,
    )
    long = long.rename(columns={melted_value_col: "value"})
    long["field"] = "UNKNOWN"
    long = long[["date", "ticker", "field", "value"]]

    return long


def save_group_from_long(name: str, long: pd.DataFrame, failures: list[dict]) -> None:
    """
    Save one downloaded group.

    This script normalizes every Bloomberg response chunk into long format first,
    then concatenates chunks vertically. This is important because recent xbbg
    async BDH may already return long-format data with repeated columns:
        date, ticker, field, value

    The previous version concatenated chunks horizontally and then removed
    duplicate column names, which accidentally kept only the first chunk.
    """
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    long_path = OUT_DIR / f"{name}_long.parquet"
    csv_path = OUT_DIR / f"{name}_long.csv"
    wide_path = OUT_DIR / f"{name}_wide.parquet"
    fail_path = OUT_DIR / f"{name}_failures.csv"

    long = ensure_pandas_df(long)

    if not is_empty_df(long):
        # Ensure canonical column order.
        needed = ["date", "ticker", "field", "value"]
        missing_cols = [c for c in needed if c not in long.columns]
        if missing_cols:
            raise ValueError(f"{name}: long data is missing columns: {missing_cols}")

        long = long[needed].copy()
        long = long.drop_duplicates(subset=["date", "ticker", "field"], keep="last")

        long.to_parquet(long_path, index=False)
        long.to_csv(csv_path, index=False)

        # Also save a wide version for convenience.
        # If pivot fails for some unusual object dtype issue, long output is still preserved.
        try:
            wide = (
                long.pivot_table(
                    index="date",
                    columns=["ticker", "field"],
                    values="value",
                    aggfunc="last",
                )
                .sort_index()
            )
            wide.to_parquet(wide_path)
        except Exception as exc:
            print(f"Warning: could not create wide file for {name}: {exc}")

    if failures:
        pd.DataFrame(failures).to_csv(fail_path, index=False)
    elif fail_path.exists():
        # Remove stale failure logs from previous broken runs.
        fail_path.unlink()


# Backward-compatible alias. Do not use this for new code.
def save_group(name: str, df_wide: pd.DataFrame, failures: list[dict]) -> None:
    long = normalize_bdh_to_long(df_wide)
    save_group_from_long(name, long, failures)


async def safe_bdh(
    tickers,
    fields: list[str],
    start_date: str,
    end_date: str,
) -> pd.DataFrame:
    """
    Fetch Bloomberg historical data and return a real pandas DataFrame.

    Why async?
    Some recent xbbg versions have a sync bdh() compatibility issue where
    xbbg itself tries to access `.empty` on a non-pandas DataFrame-like object.
    Using abdh() avoids that path in many environments.
    """
    if hasattr(blp, "abdh"):
        raw = await blp.abdh(
            tickers=tickers,
            flds=fields,
            start_date=start_date,
            end_date=end_date,
        )
    else:
        # Fallback for older xbbg versions that do not expose abdh().
        # Run sync bdh() in a thread so this function remains awaitable.
        raw = await asyncio.to_thread(
            blp.bdh,
            tickers=tickers,
            flds=fields,
            start_date=start_date,
            end_date=end_date,
        )

    return ensure_pandas_df(raw)



async def download_bdh_group(
    name: str,
    tickers: list[str],
    fields: list[str],
    start_date: str = START_DATE,
    end_date: str = END_DATE,
    chunk_size: int = CHUNK_SIZE,
) -> pd.DataFrame:
    """
    Download one group of Bloomberg historical data.

    Critical fix:
    We normalize each chunk into long format and concatenate vertically.
    This preserves all chunks. The previous version concatenated already-long
    chunks horizontally, then dropped duplicate columns, so only the first
    chunk survived in the saved CSV/parquet.
    """
    tickers = unique_keep_order(tickers)
    long_frames: list[pd.DataFrame] = []
    failures: list[dict] = []

    print(f"\n=== Downloading {name} ===")
    print(f"Tickers: {len(tickers)} | Fields: {fields}")

    # ---- First pass: chunked download ----
    for idx, tick_chunk in enumerate(chunks(tickers, chunk_size), start=1):
        print(f"  Chunk {idx}: {len(tick_chunk)} tickers")

        try:
            df = await safe_bdh(
                tickers=tick_chunk,
                fields=fields,
                start_date=start_date,
                end_date=end_date,
            )

            long = normalize_bdh_to_long(df)

            if not is_empty_df(long):
                long_frames.append(long)
            else:
                failures.append({
                    "group": name,
                    "ticker": ",".join(tick_chunk),
                    "fields": ",".join(fields),
                    "error": "Empty dataframe for chunk",
                })

        except Exception as chunk_error:
            print(f"    Chunk failed. Retrying ticker by ticker. Error: {chunk_error}")

            for t in tick_chunk:
                try:
                    df_one = await safe_bdh(
                        tickers=t,
                        fields=fields,
                        start_date=start_date,
                        end_date=end_date,
                    )

                    long_one = normalize_bdh_to_long(df_one)

                    if not is_empty_df(long_one):
                        long_frames.append(long_one)
                    else:
                        failures.append({
                            "group": name,
                            "ticker": t,
                            "fields": ",".join(fields),
                            "error": "Empty dataframe",
                        })

                except Exception as ticker_error:
                    failures.append({
                        "group": name,
                        "ticker": t,
                        "fields": ",".join(fields),
                        "error": repr(ticker_error),
                    })

                await asyncio.sleep(SLEEP_SECONDS)

        await asyncio.sleep(SLEEP_SECONDS)

    if long_frames:
        out_long = pd.concat(long_frames, axis=0, ignore_index=True)
        out_long = out_long.drop_duplicates(subset=["date", "ticker", "field"], keep="last")
    else:
        out_long = pd.DataFrame(columns=["date", "ticker", "field", "value"])

    # ---- Second pass: identify tickers that did not appear in a successful chunk ----
    fetched_tickers = set(out_long["ticker"].dropna().astype(str).unique()) if not out_long.empty else set()
    missing_after_chunks = [t for t in tickers if t not in fetched_tickers]

    if missing_after_chunks:
        print(f"  Missing after chunk pass: {len(missing_after_chunks)} tickers. Retrying one by one.")

        retry_long_frames: list[pd.DataFrame] = []

        for t in missing_after_chunks:
            try:
                df_one = await safe_bdh(
                    tickers=t,
                    fields=fields,
                    start_date=start_date,
                    end_date=end_date,
                )
                long_one = normalize_bdh_to_long(df_one)

                if not is_empty_df(long_one) and t in set(long_one["ticker"].dropna().astype(str).unique()):
                    retry_long_frames.append(long_one)
                else:
                    failures.append({
                        "group": name,
                        "ticker": t,
                        "fields": ",".join(fields),
                        "error": "Ticker not present in Bloomberg output after retry",
                    })

            except Exception as ticker_error:
                failures.append({
                    "group": name,
                    "ticker": t,
                    "fields": ",".join(fields),
                    "error": repr(ticker_error),
                })

            await asyncio.sleep(SLEEP_SECONDS)

        if retry_long_frames:
            out_long = pd.concat([out_long] + retry_long_frames, axis=0, ignore_index=True)
            out_long = out_long.drop_duplicates(subset=["date", "ticker", "field"], keep="last")

    # Save missing-ticker audit, even if there are no Python exceptions.
    final_fetched = set(out_long["ticker"].dropna().astype(str).unique()) if not out_long.empty else set()
    still_missing = [t for t in tickers if t not in final_fetched]

    missing_path = OUT_DIR / f"{name}_missing_tickers.csv"
    if still_missing:
        pd.DataFrame({
            "group": name,
            "missing_ticker": still_missing,
            "reason": "No rows returned by Bloomberg/xbbg for this ticker and date range",
        }).to_csv(missing_path, index=False)
    elif missing_path.exists():
        missing_path.unlink()

    save_group_from_long(name, out_long, failures)

    print(f"Finished {name}. Fetched tickers: {len(final_fetched)} / {len(tickers)}")
    print(f"Still missing tickers: {len(still_missing)}")
    print(f"Failures: {len(failures)}")

    return out_long


def save_ticker_manifest(groups: dict[str, dict]) -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    rows = []
    for group_name, spec in groups.items():
        for ticker in spec["tickers"]:
            rows.append({
                "group": group_name,
                "ticker": ticker,
                "fields": ",".join(spec["fields"]),
            })
    pd.DataFrame(rows).to_csv(OUT_DIR / "ticker_manifest.csv", index=False)


# =========================
# 3. Ticker universe
# =========================

# ---------- G10 FX ----------

G10_CORE = ["AUD", "CAD", "CHF", "EUR", "GBP", "JPY", "NOK", "NZD", "SEK"]
G10_OPTIONAL = ["DKK", "HKD"]

FX_FORWARD_TENORS = ["1W", "1M", "3M", "6M", "12M"]

g10_spot = [f"{ccy} Curncy" for ccy in G10_CORE + G10_OPTIONAL]
g10_forwards = [
    f"{ccy}{tenor} Curncy"
    for ccy in G10_CORE + G10_OPTIONAL
    for tenor in FX_FORWARD_TENORS
]


# ---------- EM FX ----------

em_spot = [
    "MXN Curncy",
    "ZAR Curncy",
    "BRL Curncy",
    "KRW Curncy",
    "IDR Curncy",
    "MYR Curncy",
    "PHP Curncy",
    "CLP Curncy",
    "COP Curncy",
    "PEN Curncy",
    "SGD Curncy",
    "CNH Curncy",
    "CNY Curncy",
    "INR Curncy",
    "THB Curncy",
    "PLN Curncy",
    "HUF Curncy",
    "TRY Curncy",
    "ILS Curncy",
]

# Deliverable / offshore forwards where the simple XXX{tenor} convention often works.
em_forward_simple_ccy = [
    "MXN", "ZAR", "MYR", "PHP", "SGD", "CNH", "CNY",
    "THB", "PLN", "HUF", "TRY", "ILS",
]

em_simple_forwards = [
    f"{ccy}{tenor} Curncy"
    for ccy in em_forward_simple_ccy
    for tenor in ["1M", "3M", "6M", "12M"]
]

# NDF / special Bloomberg conventions.
em_special_forward_roots = {
    "BRL_NDF": "BCN",
    "KRW_ONSHORE": "KWO",
    "IDR_ONSHORE": "IHO",
    "PHP_NDF": "PPN",
    "CLP_NDF": "CHN",
    "COP_NDF": "CLN",
    "PEN_NDF": "PSN",
}

em_special_forwards = [
    f"{root}{tenor} Curncy"
    for root in em_special_forward_roots.values()
    for tenor in ["1M", "3M", "6M", "12M"]
]

# Possible INR convention. These may fail depending on your Bloomberg setup.
em_check_forwards = [
    "INR1M Curncy", "INR3M Curncy", "INR6M Curncy", "INR12M Curncy",
    "IRN1M Curncy", "IRN3M Curncy", "IRN6M Curncy", "IRN12M Curncy",
]

em_forwards = em_simple_forwards + em_special_forwards + em_check_forwards


# ---------- FX Options ----------

OPTION_TENORS = ["1W", "1M", "3M", "6M", "1Y"]
OPTION_TYPES = ["V", "25R", "25B", "10R", "10B"]

g10_option_pairs = [
    "EURUSD",
    "USDJPY",
    "GBPUSD",
    "USDCHF",
    "USDCAD",
    "AUDUSD",
    "NZDUSD",
    "USDNOK",
    "USDSEK",
    "USDDKK",
    "USDHKD",
]

em_option_pairs = [
    "USDMXN",
    "USDZAR",
    "USDBRL",
    "USDKRW",
    "USDSGD",
    "USDCNH",
    "USDCNY",
    "USDINR",
    "USDTRY",
    "USDPLN",
    "USDHUF",
    "USDTHB",
    "USDILS",
]

def make_option_tickers(pairs: list[str]) -> list[str]:
    return [
        f"{pair}{opt_type}{tenor} Curncy"
        for pair in pairs
        for opt_type in OPTION_TYPES
        for tenor in OPTION_TENORS
    ]

g10_fx_options = make_option_tickers(g10_option_pairs)
em_fx_options = make_option_tickers(em_option_pairs)


# ---------- Global risk / regime ----------

global_risk = [
    "VIX Index",
    "MOVE Index",
    "DXY Curncy",
    "SPX Index",
    "NDX Index",
    "RTY Index",
    "MXWO Index",
    "MXEF Index",
    "JPMVXYGL Index",
    "JPMVXYG7 Index",
    "JPMVXYEM Index",
    "BCOM Index",
    "CL1 Comdty",
    "CO1 Comdty",
    "XAU Curncy",
    "HG1 Comdty",
    "USGG2YR Index",
    "USGG10YR Index",
    "USYC2Y10 Index",
]


# ---------- G10 interest rates ----------

g10_ois = [
    # USD
    "USSO1Z Curncy", "USSOA Curncy", "USOSFRA Curncy",
    "USSOC Curncy", "USOSFRC Curncy", "USOSFRF Curncy",

    # EUR
    "EUSWE1Z Curncy", "EUSWEA Curncy", "EESWEA Curncy",
    "EUSWEC Curncy", "EESWEC Curncy", "EESWEF Curncy",

    # GBP
    "BPSWS1Z Curncy", "BPSWSA Curncy", "BPSWSC Curncy", "BPSWSF Curncy",

    # JPY
    "JYSO1Z Curncy", "JYSOA Curncy", "JYSOC Curncy", "JYSOF Curncy",

    # CHF
    "SFSNTA Curncy", "SFSNTC Curncy", "SFSNTF Curncy",

    # AUD
    "ADSO1Z Curncy", "ADSOA Curncy", "ADSOC Curncy", "ADSOF Curncy",

    # CAD
    "CDSO1Z Curncy", "CDSOA Curncy", "CDSOC Curncy", "CDSOF Curncy",

    # NZD
    "NDSO1Z Curncy", "NDSOA Curncy", "NDSOC Curncy", "NDSOF Curncy",

    # SEK
    "SKSWTN1Z Curncy", "SKSWTNA Curncy", "SKSWTNC Curncy", "SKSWTNF Curncy",

    # SGD / HKD optional
    "SDSOAA Curncy", "SDSOAC Curncy", "SDSOAF Curncy",
    "HDDRA Curncy", "HDDRC Curncy", "HDDRF Curncy",
]

g10_ibor = [
    # USD
    "US0001W Index", "US0001M Index", "US0003M Index", "US0012M Index",

    # EUR
    "EUR001W Index", "EUR001M Index", "EUR003M Index", "EUR012M Index",

    # GBP
    "BP0001W Index", "BP0001M Index", "BP0003M Index", "BP0012M Index",

    # JPY
    "JY0001W Index", "JY0001M Index", "JY0003M Index", "JY0012M Index",

    # CHF
    "SF0001W Index", "SF0001M Index", "SF0003M Index", "SF0012M Index",

    # AUD
    "ADDR1Z Curncy", "ADBB1M Curncy", "ADBB3M Curncy", "ADBB12M Curncy",

    # CAD
    "CDOR01 Index", "CDOR03 Index", "CDOR12 Index",

    # NOK
    "NIBOR1W Index", "NIBOR1M Index", "NIBOR3M Index", "NIBOR12M Index",

    # NZD
    "NDBB1M Curncy", "NDBB3M Curncy", "NDBB12M Curncy",

    # SEK
    "STIB1W Index", "STIB1M Index", "STIB3M Index", "STIB12M Index",
]


# ---------- EM interest rates ----------

em_interest_rates = [
    # BRL
    "BZSTSETA Index", "BCCDIO Curncy", "BCSWAPD Curncy",

    # MXN
    "MXONBR Index", "MXIBTIIE Index", "MPSWC Index", "MPSW1A Index",

    # ZAR
    "JIBA1M Index", "JIBA3M Index", "JIBA12M Index",

    # KRW
    "KOCRD Index", "KRBO1M Index", "KWCDC Index", "KWSWO1 Index",

    # IDR
    "IDBIRATE Index", "JIIN1M Index", "IDRE1MO Index", "IHSWOOA Curncy",

    # MYR
    "KLIB1M Index", "KLIB3M Index", "MRSWQO1 Index",

    # PHP
    "PREF1MO Index", "PREF3MO Index", "PPSWO1 Index",

    # CLP
    "CLTN30DS Curncy", "CHSWPC Index", "CHSWP1 Index",

    # COP
    "CORRRMIN Index", "DTF RATE Index", "COMM1YR Index", "CLSWA Curncy",

    # PEN
    "PRRRONUS Index", "PRBOPRBI Index", "PRBOPRB3 Index", "PRBOPRB1 Index",
]


# ---------- Macro market proxies ----------

macro_market_proxies = [
    # US macro / financial condition examples
    "CPI YOY Index",
    "CPURNSA Index",
    "GDP CUR$ Index",
    "M2% YOY Index",
    "BFCIUS Index",
    "FEDL01 Index",
    "SOFRRATE Index",

    # Developed-market government yields
    "USGG2YR Index", "USGG10YR Index",
    "GDBR2 Index", "GDBR10 Index",
    "GUKG2 Index", "GUKG10 Index",
    "GJGB2 Index", "GJGB10 Index",
    "GCAN2YR Index", "GCAN10YR Index",
    "GACGB2 Index", "GACGB10 Index",

    # Commodities
    "BCOM Index",
    "CL1 Comdty",
    "CO1 Comdty",
    "XAU Curncy",
    "HG1 Comdty",
]


def load_manual_macro_tickers(path: str | Path = "manual_macro_tickers.csv") -> list[str]:
    """
    Optional:
    Create manual_macro_tickers.csv with one column named 'ticker'.

    This is for country macro data exported from:
        ECST <GO>
        ECO <GO>

    Example CSV:
        ticker
        CPI YOY Index
        GDP CUR$ Index
        ...
    """
    path = Path(path)
    if not path.exists():
        return []

    df = pd.read_csv(path)
    if "ticker" not in df.columns:
        raise ValueError("manual_macro_tickers.csv must contain a column named 'ticker'.")

    return df["ticker"].dropna().astype(str).str.strip().tolist()


manual_macro_tickers = load_manual_macro_tickers()


# =========================
# 4. Download groups
# =========================

GROUPS = {
    "g10_fx_spot_forward": {
        "tickers": g10_spot + g10_forwards,
        "fields": PRICE_FIELDS,
    },
    "em_fx_spot_forward": {
        "tickers": em_spot + em_forwards,
        "fields": PRICE_FIELDS,
    },
    "g10_fx_options": {
        "tickers": g10_fx_options,
        "fields": PRICE_FIELDS,
    },
    "em_fx_options": {
        "tickers": em_fx_options,
        "fields": PRICE_FIELDS,
    },
    "global_risk": {
        "tickers": global_risk,
        "fields": LAST_FIELD,
    },
    "g10_interest_rates": {
        "tickers": g10_ois + g10_ibor,
        "fields": LAST_FIELD,
    },
    "em_interest_rates": {
        "tickers": em_interest_rates,
        "fields": LAST_FIELD,
    },
    "macro_market_proxies": {
        "tickers": macro_market_proxies,
        "fields": LAST_FIELD,
    },
    "manual_macro_tickers": {
        "tickers": manual_macro_tickers,
        "fields": LAST_FIELD,
    },
}



def audit_saved_outputs() -> pd.DataFrame:
    """
    Compare requested tickers in GROUPS with tickers that actually appear
    in each saved *_long.csv file.

    Saves:
        download_coverage_summary.csv
        missing_tickers_by_group.csv
    """
    rows = []
    missing_rows = []

    for group_name, spec in GROUPS.items():
        requested = unique_keep_order(spec["tickers"])
        if not requested:
            continue

        path = OUT_DIR / f"{group_name}_long.csv"
        if path.exists():
            try:
                df = pd.read_csv(path, usecols=["ticker"])
                fetched = set(df["ticker"].dropna().astype(str).unique())
            except Exception as exc:
                fetched = set()
                missing_rows.append({
                    "group": group_name,
                    "ticker": "__FILE_READ_ERROR__",
                    "note": repr(exc),
                })
        else:
            fetched = set()

        missing = [t for t in requested if t not in fetched]
        extra = sorted(fetched - set(requested))

        rows.append({
            "group": group_name,
            "requested": len(requested),
            "fetched": len(fetched),
            "missing": len(missing),
            "extra": len(extra),
            "csv_exists": path.exists(),
        })

        for t in missing:
            missing_rows.append({
                "group": group_name,
                "ticker": t,
                "note": "requested but not found in saved long CSV",
            })

    summary = pd.DataFrame(rows).sort_values("group")
    summary_path = OUT_DIR / "download_coverage_summary.csv"
    missing_path = OUT_DIR / "missing_tickers_by_group.csv"

    summary.to_csv(summary_path, index=False)
    pd.DataFrame(missing_rows).to_csv(missing_path, index=False)

    print("\n=== Coverage audit ===")
    print(summary.to_string(index=False))
    print(f"\nSaved coverage summary to: {summary_path}")
    print(f"Saved missing ticker list to: {missing_path}")

    return summary


async def main() -> None:
    save_ticker_manifest(GROUPS)

    all_results = {}

    groups_to_run = GROUPS
    if RUN_GROUPS is not None:
        groups_to_run = {k: GROUPS[k] for k in RUN_GROUPS}

    for group_name, spec in groups_to_run.items():
        tickers = unique_keep_order(spec["tickers"])
        fields = spec["fields"]

        if not tickers:
            print(f"\nSkipping {group_name}: no tickers.")
            continue

        df = await download_bdh_group(
            name=group_name,
            tickers=tickers,
            fields=fields,
        )
        all_results[group_name] = df

    print("\nAll done.")
    print(f"Output folder: {OUT_DIR.resolve()}")
    print("Check *_failures.csv and *_missing_tickers.csv files for truly invalid tickers, no-data tickers, or entitlement issues.")
    audit_saved_outputs()


if __name__ == "__main__":
    asyncio.run(main())
