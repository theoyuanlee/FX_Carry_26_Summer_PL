"""Reference tables: ticker catalogs, market conventions and analytics defaults.

Data only. Everything here is a literal a human wrote down once by reading a terminal or a
market convention, so nothing in this module computes. The classes that give these tables
behaviour live in :mod:`fxcarry.catalog`.
"""

from __future__ import annotations

# --------------------------------------------------------------------------
# Quoted fields
# --------------------------------------------------------------------------
PX_LAST = "PX_LAST"
PX_BID = "PX_BID"
PX_ASK = "PX_ASK"
FIELDS: list[str] = [PX_LAST, PX_BID, PX_ASK]

# Field name to the attribute it lands on once quotes are split into sides.
FIELD_TO_KEY: dict[str, str] = {PX_LAST: "mid", PX_BID: "bid", PX_ASK: "ask"}

# --------------------------------------------------------------------------
# Currency catalog: ISO code -> (spot ticker, 1M forward-points ticker)
# --------------------------------------------------------------------------
SPOT_FWD_TICKERS: dict[str, tuple[str, str]] = {
    "AUD": ("AUDUSD Curncy", "AUD1M Curncy"),
    "BRL": ("USDBRL Curncy", "BCN1M Curncy"),  # NDF root (BRL1M does not load)
    "CAD": ("USDCAD Curncy", "CAD1M Curncy"),
    "CHF": ("USDCHF Curncy", "CHF1M Curncy"),
    "CNH": ("USDCNH Curncy", "CNH1M Curncy"),  # offshore RMB, history from 2010-08
    "CLP": ("USDCLP Curncy", "CHN1M Curncy"),  # NDF root
    "COP": ("USDCOP Curncy", "CLN1M Curncy"),  # NDF root
    "CZK": ("USDCZK Curncy", "CZK1M Curncy"),
    "DKK": ("USDDKK Curncy", "DKK1M Curncy"),
    "EUR": ("EURUSD Curncy", "EUR1M Curncy"),
    "GBP": ("GBPUSD Curncy", "GBP1M Curncy"),
    "HKD": ("USDHKD Curncy", "HKD1M Curncy"),
    "HUF": ("USDHUF Curncy", "HUF1M Curncy"),
    "IDR": ("USDIDR Curncy", "IHO1M Curncy"),  # NDF root (IDR1M does not load)
    "ILS": ("USDILS Curncy", "ILS1M Curncy"),
    # INR and TWD forwards trade as NDFs under the IRN and NTN roots. The plain
    # INR1M and TWD1M tickers return nothing.
    "INR": ("USDINR Curncy", "IRN1M Curncy"),
    "JPY": ("USDJPY Curncy", "JPY1M Curncy"),
    "KRW": ("USDKRW Curncy", "KRW1M Curncy"),
    "KWD": ("USDKWD Curncy", "KWD1M Curncy"),
    "MXN": ("USDMXN Curncy", "MXN1M Curncy"),
    "MYR": ("USDMYR Curncy", "MYR1M Curncy"),
    "NOK": ("USDNOK Curncy", "NOK1M Curncy"),
    "NZD": ("NZDUSD Curncy", "NZD1M Curncy"),
    "PEN": ("USDPEN Curncy", "PSN1M Curncy"),  # NDF root
    "PHP": ("USDPHP Curncy", "PHP1M Curncy"),
    "PLN": ("USDPLN Curncy", "PLN1M Curncy"),
    # RUB tradable through the February 2022 freeze; consumers must cap it
    # there (post-freeze BGN prints are not executable).
    "RON": ("USDRON Curncy", "RON1M Curncy"),
    "RUB": ("USDRUB Curncy", "RUB1M Curncy"),
    "SAR": ("USDSAR Curncy", "SAR1M Curncy"),
    "SEK": ("USDSEK Curncy", "SEK1M Curncy"),
    "SGD": ("USDSGD Curncy", "SGD1M Curncy"),
    "THB": ("USDTHB Curncy", "THB1M Curncy"),
    "TRY": ("USDTRY Curncy", "TRY1M Curncy"),
    "TWD": ("USDTWD Curncy", "NTN1M Curncy"),
    "ZAR": ("USDZAR Curncy", "ZAR1M Curncy"),
}

# Currencies the euro replaced in 1999, so their data ends 1998-12-31. Held
# separately because they no longer trade, which is a fact about the world
# rather than a choice about which currencies to study.
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

# --------------------------------------------------------------------------
# Forward-point scale: quoted pips to price units. "default" covers the rest.
# --------------------------------------------------------------------------
POINT_SCALE: dict[str, float] = {
    "JPY": 100.0,
    "HUF": 100.0,
    # KRW points are quoted in whole won rather than hundredths. The check that
    # settles it: the scale reconciling the 1M forward discount against the
    # KRW-minus-USD 3M rate differential comes out near 1, with JPY near 100
    # and ZAR near 10,000 as controls on the same test.
    "KRW": 1.0,
    # The remaining non-default scales were each fixed the same way, by asking
    # which divisor makes the implied 1M carry agree with a plausible rate
    # differential. A scale wrong by a factor of 100 shows up as a discount
    # roughly 1 percent of its true size, which is unmistakable.
    "IDR": 1.0,
    "INR": 100.0,
    "THB": 100.0,
    "TWD": 1.0,
    "CLP": 1.0,
    "COP": 1.0,
    "PHP": 1.0,
    "default": 10000.0,
}

# --------------------------------------------------------------------------
# Resampling and analytics defaults
# --------------------------------------------------------------------------
DEFAULT_FREQ = "M"  # public frequency code used throughout the API

# Public code to the pandas offset alias used internally, so call sites stay
# clear of pandas deprecating the bare "M" and "A" aliases.
RESAMPLE_ALIAS: dict[str, str] = {"M": "ME", "W": "W", "D": "D", "Y": "YE"}

# How many return observations make a year. Scales means and volatilities.
# Never used to convert an interest rate: that is a day count, below.
PERIODS_PER_YEAR: dict[str, float] = {"D": 252.0, "W": 52.0, "M": 12.0, "Y": 1.0}
DEFAULT_ANNUALIZATION: float = PERIODS_PER_YEAR["M"]

# Money-market day count: the denominator turning an annualized quoted yield
# into the interest actually accrued over a period. A different question from
# PERIODS_PER_YEAR above, and the two are easy to conflate.
DAY_COUNT: dict[str, float] = {"USD": 360.0, "EUR": 360.0, "JPY": 360.0,
                               "CHF": 360.0, "GBP": 365.0, "AUD": 365.0,
                               "NZD": 365.0, "CAD": 365.0, "default": 360.0}

DEFAULT_NW_LAGS = 6  # Newey-West HAC lag default

# --------------------------------------------------------------------------
# Where the data lives
# --------------------------------------------------------------------------
# The parquet pulls are tracked by DVC and never committed, so a fresh clone carries the
# .dvc pointer files and none of the data. These strings are what the "no such file" error
# tells the reader to do about it, and they are here rather than inline so that changing
# the remote is a one-line edit.

#: Public dataset holding the DVC objects. Read-only, and needs no account.
DATA_REMOTE_URL = "https://huggingface.co/datasets/dafuzhu/fxcarry-data"

#: Where to go when `dvc` itself is missing.
DVC_INSTALL_URL = "https://dvc.org/doc/install"

#: What to install. The HTTP extra is what lets DVC read the remote above.
DVC_INSTALL_HINT = 'pip install "dvc[http]"'

# --------------------------------------------------------------------------
# Option surface: tenor grid, wing deltas, quote source
# --------------------------------------------------------------------------
# The whole liquid forward curve plus the long end. Sparse legs come back empty.
FWD_TENORS: list[str] = ["1W", "2W", "1M", "2M", "3M", "6M", "9M", "12M", "18M", "2Y"]

# ATM term structure, and the risk-reversal / butterfly wings at every tenor and
# delta, down to the 5-delta deep tail (thin for many pairs, kept where it quotes).
_SURFACE_TENORS = ["1W", "1M", "2M", "3M", "6M", "9M", "1Y", "18M", "2Y"]
VOL_TENORS: list[str] = list(_SURFACE_TENORS)      # at-the-money term structure
SMILE_TENORS: list[str] = list(_SURFACE_TENORS)    # wings, quoted at every tenor
VOL_DELTAS: list[int] = [5, 10, 25]                # wing deltas; 5 is the deep tail
VOL_SOURCE: str = "BGN"                            # generic quote-source suffix

# EM and NDF coverage varies and starts later -- verify start dates on the
# terminal before trusting the deep-EM legs.
VOL_CURRENCIES: list[str] = [
    "AUD", "CAD", "CHF", "DKK", "EUR", "GBP", "JPY", "NOK", "NZD", "SEK",
    "MXN", "ZAR", "SGD", "PLN", "HUF", "CZK", "KRW", "TWD", "INR",
    # thinner emerging-market surfaces, mostly 1M and 3M only
    "BRL", "TRY", "CNH", "THB", "ILS",
    "HKD", "RUB", "RON", "CLP", "COP", "IDR", "MYR", "PEN", "PHP",
]

# Dollar indices (FX): broad, non-currency-specific dollar measures.
DOLLAR_INDEX_TICKERS: dict[str, str] = {
    "DXY": "DXY Curncy",     # ICE US dollar index (verify: Curncy vs Index)
    "BBDXY": "BBDXY Index",  # Bloomberg dollar spot index
}

# --------------------------------------------------------------------------
# Money-market rate curves. Benchmarks share no naming pattern, so this is an
# explicit map rather than anything a regex could recover.
# --------------------------------------------------------------------------
RATE_TENORS: list[str] = ["1M", "3M", "6M", "12M"]  # money-market grid (matches short forwards)
SHORT_RATE_TICKERS: dict[str, dict[str, str]] = {
    # --- LIBOR family: 4-char prefix + zero-padded tenor (US0003M = USD 3M) ---
    "USD": {"1M": "US0001M Index",
             "3M": "US0003M Index",
             "6M": "US0006M Index",
             "12M": "US0012M Index"},
    "EUR": {"1M": "EUR001M Index",
             "3M": "EUR003M Index",
             "6M": "EUR006M Index",
             "12M": "EUR012M Index"},
    "GBP": {"1M": "BP0001M Index",
             "3M": "BP0003M Index",
             "6M": "BP0006M Index",
             "12M": "BP0012M Index"},
    "JPY": {"1M": "JY0001M Index",
             "3M": "JY0003M Index",
             "6M": "JY0006M Index",
             "12M": "JY0012M Index"},
    "CHF": {"1M": "SF0001M Index",
             "3M": "SF0003M Index",
             "6M": "SF0006M Index",
             "12M": "SF0012M Index"},
    # --- other G10: own benchmarks, tenors that exist (VERIFY the codes) ---
    "CAD": {"1M": "CDOR01 Index", "3M": "CDOR03 Index", "6M": "CDOR06 Index"},
    "AUD": {"1M": "BBSW1M Index", "3M": "BBSW3M Index", "6M": "BBSW6M Index"},
    "NZD": {"1M": "NDBB1M Index", "3M": "NDBB3M Index"},          # BKBM (mainly short)
    "SEK": {"1M": "STIB1M Index", "3M": "STIB3M Index", "6M": "STIB6M Index"},
    "NOK": {"3M": "NIBOR3M Index", "6M": "NIBOR6M Index"},
    "DKK": {"3M": "CIBO03M Index", "6M": "CIBO06M Index"},
    # --- EM: local benchmark at its real tenors (VERIFY every one; priority) ---
    "MXN": {"1M": "MXIBTIIE Index"},                              # TIIE 28d ~ 1M
    "ZAR": {"3M": "JIBA3M Index", "6M": "JIBA6M Index"},          # JIBAR
    "KRW": {"3M": "KWCDC Curncy"},                                # 91d CD
    "PLN": {"1M": "WIBR1M Index", "3M": "WIBR3M Index", "6M": "WIBR6M Index"},   # WIBOR
    "HUF": {"1M": "BUBOR01M Index", "3M": "BUBOR03M Index", "6M": "BUBOR06M Index"},  # BUBOR
    "CZK": {"1M": "PRIB01M Index", "3M": "PRIB03M Index", "6M": "PRIB06M Index"},     # PRIBOR
    "SGD": {"1M": "SORF1M Index", "3M": "SORF3M Index"},          # SGD money-market
    "TWD": {"3M": "TAIBOR3M Index"},                             # TAIBOR
    # INR quotes a 3M OIS rather than a liquid term deposit benchmark.
    "INR": {"3M": "IRSWO3 Curncy"},
}

# Reverse of SHORT_RATE_TICKERS: ticker -> (iso, tenor).
RATE_TICKER_TO_KEY: dict[str, tuple[str, str]] = {
    ticker: (iso, tenor)
    for iso, curve in SHORT_RATE_TICKERS.items()
    for tenor, ticker in curve.items()
}

# --------------------------------------------------------------------------
# Economic releases: indicator definitions and per-country tickers.
# --------------------------------------------------------------------------
MACRO_INDICATORS: dict[str, tuple[str, str, str, int]] = {
    "cpi_yoy":    ("CPI, year on year %",            "M", "pct_yoy", 1),
    "cpi_idx":    ("CPI index level",                "M", "index",   1),
    "ppi_yoy":    ("PPI, year on year %",            "M", "pct_yoy", 1),
    "gdp_yoy":    ("Real GDP, year on year %",       "Q", "pct_yoy", 2),
    "ip_yoy":     ("Industrial production, yoy %",   "M", "pct_yoy", 2),
    "unemp":      ("Unemployment rate %",            "M", "pct",     1),
    "retail_yoy": ("Retail sales, year on year %",   "M", "pct_yoy", 1),
    "trade_bal":  ("Trade balance, level",           "M", "level",   2),
    "curr_acct":  ("Current account, level",         "Q", "level",   3),
    "m2":         ("Money supply M2, level",         "M", "level",   1),
    "pmi":        ("Manufacturing PMI",              "M", "index",   0),
    "conf":       ("Consumer confidence",            "M", "index",   0),
    "reserves":   ("FX reserves, level",             "M", "level",   1),
    "gov10y":     ("10Y government bond yield %",     "D", "pct",     0),
    "equity":     ("Headline equity index",          "D", "index",   0),
    # Book ch. 26 releases that are mainly a US phenomenon (populated for USD;
    # add other countries' analogues on the terminal if wanted).
    "payroll":    ("Employment / payroll change",    "M", "level",   1),
    "durables":   ("Durable goods orders, mom %",     "M", "pct_mom", 1),
    "housing":    ("Housing starts, level",          "M", "level",   1),
    "leading":    ("Leading index, mom %",            "M", "pct_mom", 1),
}

MACRO_TICKERS: dict[str, dict[str, str]] = {
    # ---- United States (reference block, the most reliable) ----
    "USD": {
        "cpi_yoy": "CPI YOY Index", "cpi_idx": "CPI INDX Index",
        "ppi_yoy": "FDIUFDYO Index", "gdp_yoy": "GDP CYOY Index",
        "ip_yoy": "IP  YOY Index", "unemp": "USURTOT Index",
        "retail_yoy": "RSTAYOY Index", "trade_bal": "USTBTOT Index",
        "curr_acct": "USCABAL Index", "pmi": "NAPMPMI Index", "m2": "M2 Index",
        "conf": "CONCCONF Index", "gov10y": "USGG10YR Index", "equity": "SPX Index",
        "payroll": "NFP TCH Index", "durables": "DGNOCHNG Index",
        "housing": "NHSPSTOT Index", "leading": "LEI CHNG Index",
    },
    # ---- Euro area ----
    "EUR": {
        "cpi_yoy": "ECCPEMUY Index", "ppi_yoy": "EUPPEMUY Index",
        "gdp_yoy": "EUGNEMUY Index", "ip_yoy": "EUIPEMUY Index",
        "unemp": "UMRTEMU Index", "retail_yoy": "RSSAEMUY Index",
        "trade_bal": "XTTBEZ Index", "pmi": "MPMIEZMA Index",
        "conf": "EUCCEMU Index", "gov10y": "GDBR10 Index", "equity": "SX5E Index",
        "m2": "ECMAM2 Index",
    },
    # ---- Japan ----
    "JPY": {
        "cpi_yoy": "JNCPIYOY Index", "gdp_yoy": "JGDPNSAQ Index",
        "ip_yoy": "JNIPYOY Index", "unemp": "JNUE Index",
        "trade_bal": "JNTBAL Index", "pmi": "MPMIJPMA Index",
        "gov10y": "GJGB10 Index", "equity": "NKY Index",
        "m2": "JMNSM2 Index", "reserves": "JNFR Index",
    },
    # ---- United Kingdom ----
    "GBP": {
        "cpi_yoy": "UKRPCJYR Index", "ppi_yoy": "UKOPYOYR Index",
        "gdp_yoy": "UKGRYBZY Index", "ip_yoy": "UKIPIYOY Index",
        "unemp": "UKUEILOR Index", "retail_yoy": "UKRVAUYY Index",
        "trade_bal": "UKTBTTBA Index", "pmi": "MPMIGBMA Index",
        "gov10y": "GUKG10 Index", "equity": "UKX Index",
        "m2": "UKM4 Index",  # UK headlines M4, not M2
    },
    # ---- Switzerland ----
    "CHF": {
        "cpi_yoy": "SZCPIYOY Index", "gdp_yoy": "SZGDPCYY Index",
        "unemp": "SZUERA Index", "pmi": "SVMEPMI Index",
        "gov10y": "GSWISS10 Index", "equity": "SMI Index",
        "m2": "SZMSM2 Index", "reserves": "SZFXRES Index",
    },
    # ---- Canada ----
    "CAD": {
        "cpi_yoy": "CACPIYOY Index", "gdp_yoy": "CGE9YOY Index",
        "unemp": "CANLXEMR Index", "trade_bal": "CATBTOTB Index",
        "ip_yoy": "CAIPYOY Index", "gov10y": "GCAN10YR Index", "equity": "SPTSX Index",
        "m2": "CAMSM2 Index",
    },
    # ---- Australia (CPI and GDP are quarterly) ----
    "AUD": {
        "cpi_yoy": "AUCPIYOY Index", "gdp_yoy": "AUNAGDPY Index",
        "unemp": "AULFUNEM Index", "trade_bal": "AUITGSB Index",
        "gov10y": "GACGB10 Index", "equity": "AS51 Index",
    },
    # ---- New Zealand (CPI quarterly) ----
    "NZD": {
        "cpi_yoy": "NZCPIYOY Index", "gdp_yoy": "NZGDPYOY Index",
        "unemp": "NZLTUNR Index", "gov10y": "GNZGB10 Index", "equity": "NZSE50FG Index",
    },
    # ---- Sweden ----
    "SEK": {
        "cpi_yoy": "SWCPIYOY Index", "gdp_yoy": "SWGDPAYY Index",
        "unemp": "SWUER Index", "gov10y": "GSGB10YR Index", "equity": "OMX Index",
    },
    # ---- Norway ----
    "NOK": {
        "cpi_yoy": "NOCPIYOY Index", "gdp_yoy": "NOGDPCYY Index",
        "unemp": "NORAUERT Index", "gov10y": "GNOR10YR Index", "equity": "OBX Index",
    },
    # ---- Denmark ----
    "DKK": {
        "cpi_yoy": "DNCPIYOY Index", "unemp": "DNUER Index",
        "gov10y": "GDGB10YR Index", "equity": "KFX Index",
    },
    # ---- Mexico ----
    "MXN": {
        "cpi_yoy": "MXCPYOY Index", "gdp_yoy": "MXNGDPPY Index",
        "unemp": "MXUER Index", "trade_bal": "MXTBBALN Index",
        "gov10y": "GMXN10YR Index", "equity": "MEXBOL Index",
        "reserves": "MXIRIRES Index",
    },
    # ---- South Africa ----
    "ZAR": {
        "cpi_yoy": "SACPIYOY Index", "gdp_yoy": "SAGDPYOY Index",
        "unemp": "SAUER Index", "trade_bal": "SATBAL Index",
        "gov10y": "GSAB10YR Index", "equity": "JALSH Index",
        "reserves": "SAFXRES Index",
    },
    # ---- Korea ----
    "KRW": {
        "cpi_yoy": "KOCPIYOY Index", "gdp_yoy": "KOGDPYOY Index",
        "unemp": "KOEAUEMP Index", "trade_bal": "KOTBADJ Index",
        "gov10y": "GVSK10YR Index", "equity": "KOSPI Index",
        "reserves": "KOFRTOT Index",
    },
    # ---- Singapore ----
    "SGD": {
        "cpi_yoy": "SICPIYOY Index", "gdp_yoy": "SGDPYOY Index",
        "unemp": "SGUER Index", "gov10y": "MASB10Y Index", "equity": "FSSTI Index",
        "reserves": "SGDOFFR Index",
    },
    # ---- Czech Republic ----
    "CZK": {
        "cpi_yoy": "CZCPYOY Index", "gdp_yoy": "CZGDPYOY Index",
        "unemp": "CZUER Index", "gov10y": "CZGB10YR Index", "equity": "PX Index",
    },
    # ---- Hungary ----
    "HUF": {
        "cpi_yoy": "HUCPIYY Index", "gdp_yoy": "HUGDPYOY Index",
        "unemp": "HUUER Index", "gov10y": "GHGB10YR Index", "equity": "BUX Index",
    },
    # ---- Poland ----
    "PLN": {
        "cpi_yoy": "POCPIYOY Index", "gdp_yoy": "POGDPYOY Index",
        "unemp": "POUER Index", "gov10y": "POGB10YR Index", "equity": "WIG Index",
    },
    # ---- Taiwan ----
    "TWD": {
        "cpi_yoy": "TWCPYOY Index", "gdp_yoy": "TWGDPYOY Index",
        "gov10y": "TWGB10Y Index", "equity": "TWSE Index",
        "reserves": "TWTRESRV Index",
    },
    # ---- India ----
    "INR": {
        "cpi_yoy": "INFUTOTY Index", "gdp_yoy": "IGQEAGGY Index",
        "ip_yoy": "INPIINDY Index", "gov10y": "GIND10YR Index", "equity": "SENSEX Index",
        "reserves": "INFXREST Index",
    },
    # HKD is a hard USD peg and KWD / SAR are pegged oil exporters, so their
    # macro releases carry little independent FX signal; add blocks here only if
    # a specific question needs them.
}

