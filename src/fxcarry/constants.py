"""Collective home for hard-coded values used across the fxcarry library.

Nothing outside this module should hard-code a Bloomberg ticker, a currency
list, a quote-inversion flag, a forward-point scale factor, a file name, or
an annualization/lag default. To extend the currency universe, add a pull
source, or change a convention, edit this file only -- every other module
(``io``, ``conventions``, ``panel``, ``signals``, ``portfolio``, ``costs``,
``backtest``, ``metrics``) reads its defaults from here.
"""

from __future__ import annotations

# --------------------------------------------------------------------------
# Bloomberg field names
# --------------------------------------------------------------------------
PX_LAST = "PX_LAST"
PX_BID = "PX_BID"
PX_ASK = "PX_ASK"
FIELDS: list[str] = [PX_LAST, PX_BID, PX_ASK]

# Maps a raw Bloomberg field name to the short key used in the {"mid","bid","ask"}
# dicts returned by fxcarry.io.load_spot / load_fwd_points.
FIELD_TO_KEY: dict[str, str] = {PX_LAST: "mid", PX_BID: "bid", PX_ASK: "ask"}
KEY_TO_FIELD: dict[str, str] = {v: k for k, v in FIELD_TO_KEY.items()}

# --------------------------------------------------------------------------
# Currency universe(s): ISO code -> (spot ticker, 1M forward-points ticker)
# --------------------------------------------------------------------------
# BER (2011) 20-currency universe ("Carry Trade and Momentum in Currency
# Markets"). This is the default universe for the light replication.
BER20_TICKERS: dict[str, tuple[str, str]] = {
    "AUD": ("AUDUSD Curncy", "AUD1M Curncy"),
    "CAD": ("USDCAD Curncy", "CAD1M Curncy"),
    "DKK": ("USDDKK Curncy", "DKK1M Curncy"),
    "EUR": ("EURUSD Curncy", "EUR1M Curncy"),
    "JPY": ("USDJPY Curncy", "JPY1M Curncy"),
    "NZD": ("NZDUSD Curncy", "NZD1M Curncy"),
    "NOK": ("USDNOK Curncy", "NOK1M Curncy"),
    "SEK": ("USDSEK Curncy", "SEK1M Curncy"),
    "CHF": ("USDCHF Curncy", "CHF1M Curncy"),
    "GBP": ("GBPUSD Curncy", "GBP1M Curncy"),
    "ZAR": ("USDZAR Curncy", "ZAR1M Curncy"),
    "SGD": ("USDSGD Curncy", "SGD1M Curncy"),
    "HKD": ("USDHKD Curncy", "HKD1M Curncy"),
    "KRW": ("USDKRW Curncy", "KRW1M Curncy"),
    "MXN": ("USDMXN Curncy", "MXN1M Curncy"),
    "CZK": ("USDCZK Curncy", "CZK1M Curncy"),
    "HUF": ("USDHUF Curncy", "HUF1M Curncy"),
    "PLN": ("USDPLN Curncy", "PLN1M Curncy"),
}

# LRV (2011) has a broader universe. Kept separate so it can be merged in
# later without touching any code, e.g.:
#   from fxcarry import constants as const
#   full_universe = {**const.BER20_TICKERS, **const.LRV_EXTRA_TICKERS}
LRV_EXTRA_TICKERS: dict[str, tuple[str, str]] = {
    "INR": ("USDINR Curncy", "INR1M Curncy"),
    "IDR": ("USDIDR Curncy", "IDR1M Curncy"),
    "KWD": ("USDKWD Curncy", "KWD1M Curncy"),
    "MYR": ("USDMYR Curncy", "MYR1M Curncy"),
    "PHP": ("USDPHP Curncy", "PHP1M Curncy"),
    "SAR": ("USDSAR Curncy", "SAR1M Curncy"),
    "TWD": ("USDTWD Curncy", "TWD1M Curncy"),
    "THB": ("USDTHB Curncy", "THB1M Curncy"),
}

# Pre-euro legacy currencies (data ends 1998-12-31); add to a merged universe
# dict the same way as LRV_EXTRA_TICKERS above if/when needed.
LEGACY_EURO_TICKERS: dict[str, tuple[str, str]] = {
    "ATS": ("USDATS Curncy", "ATS1M Curncy"),
    "BEF": ("USDBEF Curncy", "BEF1M Curncy"),
    "FIM": ("USDFIM Curncy", "FIM1M Curncy"),
    "FRF": ("USDFRF Curncy", "FRF1M Curncy"),
    "DEM": ("USDDEM Curncy", "DEM1M Curncy"),
    "GRD": ("USDGRD Curncy", "GRD1M Curncy"),
    "IEP": ("USDIEP Curncy", "IEP1M Curncy"),
    "ITL": ("USDITL Curncy", "ITL1M Curncy"),
    "NLG": ("USDNLG Curncy", "NLG1M Curncy"),
    "PTE": ("USDPTE Curncy", "PTE1M Curncy"),
    "ESP": ("USDESP Curncy", "ESP1M Curncy"),
}

# The universe actually used by default across the library/notebooks. Point
# this at a different (or merged) dict to change the whole pipeline's
# currency coverage without editing any function body.
DEFAULT_TICKERS: dict[str, tuple[str, str]] = BER20_TICKERS

# Risk-free / T-bill proxy for total-return (NAV) compounding, BER Figure-1
# style. Quoted as an annualized yield in percent (e.g. 5.25 => 5.25%/yr).
TBILL_TICKER = "GB1M Index"

# --------------------------------------------------------------------------
# Quote conventions
# --------------------------------------------------------------------------
# Currencies Bloomberg quotes as USD-per-1-FCU (the inverse of the papers'
# FCU-per-USD convention). Flip these via conventions.to_fccu_per_usd(...).
INVERTED: set[str] = {"AUD", "EUR", "GBP", "NZD"}

# Forward-point scale factor by currency (Bloomberg "pips" -> price units).
# "default" applies to any currency not listed explicitly.
POINT_SCALE: dict[str, float] = {
    "JPY": 100.0,
    "HUF": 100.0,
    "KRW": 100.0,
    "IDR": 100.0,
    "default": 10000.0,
}


def point_scale(ccy: str, scale_map: dict[str, float] | None = None) -> float:
    """Forward-point scale factor for `ccy`, falling back to the default."""
    scale_map = POINT_SCALE if scale_map is None else scale_map
    return scale_map.get(ccy, scale_map.get("default", 10000.0))


# --------------------------------------------------------------------------
# Pull window defaults
# --------------------------------------------------------------------------
DEFAULT_START_DATE = "1983-11-01"
DEFAULT_END_DATE = "2026-06-30"

# --------------------------------------------------------------------------
# Resampling / analytics defaults
# --------------------------------------------------------------------------
DEFAULT_FREQ = "M"  # public-facing frequency code used throughout the API

# Maps a public-facing frequency code to the pandas resample offset alias
# actually used internally (keeps call sites future-proof against pandas
# deprecating bare "M"/"A" aliases).
RESAMPLE_ALIAS: dict[str, str] = {"M": "ME", "W": "W", "D": "D", "Y": "YE"}

PERIODS_PER_YEAR: dict[str, float] = {"D": 252.0, "W": 52.0, "M": 12.0, "Y": 1.0}
DEFAULT_ANNUALIZATION: float = PERIODS_PER_YEAR["M"]
DEFAULT_NW_LAGS = 6  # Newey-West HAC lag default

# --------------------------------------------------------------------------
# Raw parquet file names
# --------------------------------------------------------------------------
SPOT_FILE = "spot_daily.parquet"
FWD_FILE = "fwd_points_1m_daily.parquet"
TBILL_FILE = "tbill_daily.parquet"
