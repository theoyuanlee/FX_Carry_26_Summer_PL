"""Minimal G10 FX carry backtester."""

from pathlib import Path

import numpy as np
import pandas as pd

# Shared, git-tracked parquet data at the repo root (read-only). Resolved from
# this file's location so it works regardless of the notebook's cwd.
RAW_DIR = Path(__file__).resolve().parent.parent / "data" / "raw"

ANN_DAYS = 252

# The 9 floating G10 currencies. Pegged HKD and DKK are dropped (they carry no
# tradable rate differential), matching cesare's UNIVERSE_G10.
G10_FLOAT = ["AUD", "CAD", "CHF", "EUR", "GBP", "JPY", "NOK", "NZD", "SEK"]

# Bloomberg quotes these as USD-per-FX (e.g. "EUR Curncy" = EURUSD); every other
# G10 currency is quoted FX-per-USD (e.g. "JPY Curncy" = USDJPY) and is inverted.
USD_PER_FX = {"EUR", "GBP", "AUD", "NZD"}

# Divisor turning Bloomberg forward points into outright-quote units
# (outright forward = spot + points / scale). 1e4 for all G10 except JPY (1e2).
FWD_SCALE = {ccy: 1e4 for ccy in G10_FLOAT}
FWD_SCALE["JPY"] = 1e2

TENOR_MONTHS = {"1W": 0.25, "1M": 1, "3M": 3, "6M": 6, "12M": 12}


# ---------------------------------------------------------------------------
# Loading
# ---------------------------------------------------------------------------

def load_wide(group: str, field: str = "PX_LAST") -> pd.DataFrame:
    """Load ``data/raw/{group}_wide.parquet`` as a float DataFrame, datetime index.

    Columns keep the Bloomberg ticker minus its yellow-key suffix
    ("AUD Curncy" -> "AUD"). The parquet columns are a MultiIndex
    ``['ticker', 'field']``; we select one ``field`` (default last price).
    """
    df = pd.read_parquet(RAW_DIR / f"{group}_wide.parquet")
    df = df.xs(field, level="field", axis=1)
    df.index = pd.to_datetime(df.index)
    df = df.apply(pd.to_numeric, errors="coerce").sort_index()
    df.columns = [c.rsplit(" ", 1)[0] if c.endswith((" Curncy", " Index", " Comdty"))
                  else c for c in df.columns]
    return df


# ---------------------------------------------------------------------------
# Currency panel: spots, carry, excess returns
# ---------------------------------------------------------------------------

def spots_usd_per_fx(px: pd.DataFrame, universe: list[str] = G10_FLOAT) -> pd.DataFrame:
    """Spot panel re-expressed as USD per unit of foreign currency.

    An increase always means the foreign currency appreciated vs USD, so a
    positive spot log-return is a gain for a long-FX position.
    """
    out = {}
    for ccy in universe:
        if ccy in px.columns:
            out[ccy] = px[ccy] if ccy in USD_PER_FX else 1.0 / px[ccy]
    return pd.DataFrame(out)


def carry_panel(px: pd.DataFrame, tenor: str = "1M",
                universe: list[str] = G10_FLOAT) -> pd.DataFrame:
    """Annualised forward-implied carry of being long each currency vs USD.

    carry = ln(S/F) in USD-per-FX terms, annualised by 12/months. Under covered
    interest parity this equals the interest-rate differential (foreign minus
    USD): the yield you earn buying the currency forward, before any spot move.
    A high positive carry is a high-yielder (long candidate); negative is a
    low-yielder (short candidate).
    """
    months = TENOR_MONTHS[tenor]
    out = {}
    for ccy in universe:
        point_col = f"{ccy}{tenor}"
        if ccy not in px.columns or point_col not in px.columns:
            continue
        spot = px[ccy]
        fwd = spot + px[point_col] / FWD_SCALE[ccy]
        log_fp = np.log(fwd / spot)
        # USD-per-FX quotes: carry = ln(S/F) = -log_fp; FX-per-USD: ln(F/S) = +log_fp
        out[ccy] = (-log_fp if ccy in USD_PER_FX else log_fp) * (12 / months)
    return pd.DataFrame(out)


def excess_returns(spots_usd: pd.DataFrame, carry_ann: pd.DataFrame) -> pd.DataFrame:
    """Daily currency excess returns (long FX vs USD via 1M forwards).

    Approximation: spot log-return plus the *previous* day's annualised carry
    accrued over 1/252. Ignores roll timing and costs but matches the standard
    academic construction closely at daily frequency.
    """
    common = spots_usd.columns.intersection(carry_ann.columns)
    spot_ret = np.log(spots_usd[common]).diff()
    accrual = carry_ann[common].shift(1) / ANN_DAYS
    return spot_ret + accrual


# ---------------------------------------------------------------------------
# Portfolio construction and returns
# ---------------------------------------------------------------------------

def carry_portfolio(carry_ann: pd.DataFrame, xret: pd.DataFrame, n_buckets: int = 3,
                    rebal: str = "ME", min_per_leg: int = 2) -> pd.DataFrame:
    """Daily weight panel of an equal-weight long/short carry sort.

    On each rebalance date (last observation per ``rebal`` period, "ME" =
    month-end) currencies are ranked on carry into ``n_buckets``; the top bucket
    is held long and the bottom short, each equally weighted to gross 1 per side
    (book gross 2, dollar-neutral). A date with fewer than ``min_per_leg`` names
    per bucket keeps the previous weights. Weights are forward-filled to trading
    days and shifted one day, so they take effect the next day (no lookahead).
    """
    cols = carry_ann.columns.intersection(xret.columns)
    signal = carry_ann[cols].resample(rebal).last()

    rows = {}
    for dt in signal.index:
        valid = signal.loc[dt].dropna()
        k = len(valid) // n_buckets
        if k < min_per_leg:
            continue
        w = pd.Series(0.0, index=cols)
        w[valid.nlargest(k).index] = 1.0 / k    # long the k highest-carry names
        w[valid.nsmallest(k).index] = -1.0 / k  # short the k lowest-carry names
        rows[dt] = w

    weights = pd.DataFrame(rows).T
    return weights.reindex(xret.index, method="ffill").shift(1)


def portfolio_returns(weights: pd.DataFrame, xret: pd.DataFrame,
                      name: str = "G10_carry") -> pd.Series:
    """Daily portfolio return Sum(w * r), min_count=1 so pre-inception days stay NaN.

    Summing weighted log excess returns is a daily-frequency approximation of the
    true portfolio return; fine at these vol levels.
    """
    common = weights.columns.intersection(xret.columns)
    return (weights[common] * xret[common]).sum(axis=1, min_count=1).rename(name)


# ---------------------------------------------------------------------------
# Performance statistics
# ---------------------------------------------------------------------------

def max_drawdown(returns: pd.Series) -> float:
    """Maximum drawdown of the compounded wealth curve of daily returns."""
    wealth = (1 + returns.dropna()).cumprod()
    return float((wealth / wealth.cummax() - 1).min())


def summary_stats(returns: pd.DataFrame) -> pd.DataFrame:
    """Core per-column performance stats for daily return series."""
    out = {}
    for col in returns.columns:
        r = returns[col].dropna()
        ann_mu = r.mean() * ANN_DAYS
        ann_sd = r.std() * np.sqrt(ANN_DAYS)
        out[col] = {
            "start": r.index[0].date(),
            "end": r.index[-1].date(),
            "n_days": len(r),
            "ann_return": ann_mu,
            "ann_vol": ann_sd,
            "sharpe": ann_mu / ann_sd if ann_sd > 0 else np.nan,
            "max_drawdown": max_drawdown(r),
            "hit_rate": (r > 0).mean(),
        }
    return pd.DataFrame(out).T
