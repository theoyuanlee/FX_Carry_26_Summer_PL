"""Shared helpers for the FX carry project.

Data loading, currency-return construction (spot and forward-implied carry),
performance statistics and factor regressions. Used by the notebooks in
cesare/ and, later, by the strategy backtests.
"""

from pathlib import Path

import numpy as np
import pandas as pd
import statsmodels.api as sm
from scipy.optimize import minimize  # only for mvo_weights (Stage 4); scipy ships with statsmodels

RAW_DIR = Path(__file__).resolve().parent.parent / "data" / "raw"

ANN_DAYS = 252

# ---------------------------------------------------------------------------
# Universe and Bloomberg quoting conventions
# ---------------------------------------------------------------------------

G10 = ["AUD", "CAD", "CHF", "DKK", "EUR", "GBP", "HKD", "JPY", "NOK", "NZD", "SEK"]
EM = ["BRL", "CLP", "CNH", "CNY", "COP", "HUF", "IDR", "ILS", "INR", "KRW",
      "MXN", "MYR", "PEN", "PHP", "PLN", "SGD", "THB", "TRY", "ZAR"]
ALL_CCY = G10 + EM

# Bloomberg quotes these as USD-per-FX (e.g. "EUR Curncy" = EURUSD); every
# other currency is quoted FX-per-USD (e.g. "JPY Curncy" = USDJPY).
USD_PER_FX = {"EUR", "GBP", "AUD", "NZD"}

# Forward-point ticker root per currency. NDF roots are used where outright
# forwards are not traded/downloaded (BRL, CLP, COP, IDR, INR, KRW, PEN).
# CNY outright forwards failed to download; CNH forwards cover offshore RMB.
FWD_ROOT = {ccy: ccy for ccy in ALL_CCY}
FWD_ROOT.update({
    "BRL": "BCN", "CLP": "CHN", "COP": "CLN", "IDR": "IHO",
    "INR": "IRN", "KRW": "KWO", "PEN": "PSN", "CNY": None,
})

# Divisor turning Bloomberg forward points into outright-quote units
# (outright forward = spot + points / scale). Verified empirically: with
# these scales the median implied 12M carry per currency lines up with the
# known interest-rate differential vs USD (see the validation table in
# cesare/data_visualization.ipynb).
FWD_SCALE = {ccy: 1e4 for ccy in ALL_CCY}
FWD_SCALE.update({
    "JPY": 1e2, "HUF": 1e2, "INR": 1e2, "THB": 1e2,
    "CLP": 1.0, "COP": 1.0, "IDR": 1.0, "KRW": 1.0, "PHP": 1.0,
})

TENOR_MONTHS = {"1M": 1, "3M": 3, "6M": 6, "12M": 12}


# ---------------------------------------------------------------------------
# Loading
# ---------------------------------------------------------------------------

def load_wide(group: str, field: str = "PX_LAST") -> pd.DataFrame:
    """Load data/raw/{group}_wide.parquet as float DataFrame, datetime index.

    Columns keep the Bloomberg ticker minus its yellow-key suffix
    ("AUD Curncy" -> "AUD", "VIX Index" -> "VIX").
    """
    df = pd.read_parquet(RAW_DIR / f"{group}_wide.parquet")
    df = df.xs(field, level="field", axis=1)
    df.index = pd.to_datetime(df.index)
    df = df.apply(pd.to_numeric, errors="coerce").sort_index()
    df.columns = [c.rsplit(" ", 1)[0] if c.endswith((" Curncy", " Index", " Comdty"))
                  else c for c in df.columns]
    return df


# ---------------------------------------------------------------------------
# Currency panel: spots, carry, returns
# ---------------------------------------------------------------------------

def spots_usd_per_fx(g10_px: pd.DataFrame, em_px: pd.DataFrame) -> pd.DataFrame:
    """Spot panel re-expressed as USD per unit of foreign currency.

    An increase always means the foreign currency appreciated vs USD.
    """
    out = {}
    for ccy in ALL_CCY:
        src = g10_px if ccy in G10 else em_px
        if ccy in src.columns:
            out[ccy] = src[ccy] if ccy in USD_PER_FX else 1.0 / src[ccy]
    return pd.DataFrame(out)


def carry_panel(g10_px: pd.DataFrame, em_px: pd.DataFrame, tenor: str = "1M") -> pd.DataFrame:
    """Annualised forward-implied carry of being long each currency vs USD.

    carry = ln(S/F) in USD-per-FX terms, annualised by 12/months. Under CIP
    this equals the interest differential (foreign minus USD), so it is the
    carry earned by buying the currency forward, before any spot move.
    """
    months = TENOR_MONTHS[tenor]
    out = {}
    for ccy in ALL_CCY:
        src = g10_px if ccy in G10 else em_px
        root = FWD_ROOT.get(ccy)
        if root is None or ccy not in src.columns or f"{root}{tenor}" not in src.columns:
            continue
        spot = src[ccy]
        fwd = spot + src[f"{root}{tenor}"] / FWD_SCALE[ccy]
        log_fp = np.log(fwd / spot)
        # USD-per-FX quotes: ln(S/F) = -log_fp; FX-per-USD quotes: ln(F/S) = +log_fp
        out[ccy] = (-log_fp if ccy in USD_PER_FX else log_fp) * (12 / months)
    return pd.DataFrame(out)


def excess_returns(spots_usd: pd.DataFrame, carry_ann: pd.DataFrame) -> pd.DataFrame:
    """Daily currency excess returns (long FX vs USD via 1M forwards).

    Approximation: spot log return plus the previous day's annualised carry
    accrued over 1/252. This ignores roll timing and transaction costs but
    matches the standard academic construction closely at daily frequency.
    """
    common = spots_usd.columns.intersection(carry_ann.columns)
    spot_ret = np.log(spots_usd[common]).diff()
    accrual = carry_ann[common].shift(1) / ANN_DAYS
    return spot_ret + accrual


def spot_log_returns(spots_usd: pd.DataFrame) -> pd.DataFrame:
    """Daily spot log returns in USD-per-FX terms (+ = FX appreciation)."""
    return np.log(spots_usd).diff()


def momentum_panel(xret: pd.DataFrame, lookback: int = 63, skip: int = 0) -> pd.DataFrame:
    """Trailing cumulative excess-return momentum signal, one column per currency.

    The signal at each day is the sum of the last `lookback` daily excess returns
    (spot move plus accrued carry, `excess_returns` convention) — not spot-only,
    since the carry accrual is part of what a trend follower actually realises.
    `lookback` in {21, 63, 252} spans the 1/3/12-month horizons of Burnside et al.
    (2011) and Menkhoff et al. (2012b); `skip` (default 0) drops the most recent
    `skip` days for the equity-style 12-2 gap, kept only for robustness checks as
    the FX momentum literature does not use it. Returned as a daily panel, no
    lookahead by construction (only past returns enter the trailing sum); it is
    consumed exactly like `carry_panel` — `carry_portfolio` samples it month-end
    and shifts one day, so the effective signal never sees its own or future days.
    """
    mom = xret.rolling(lookback, min_periods=lookback // 2).sum()
    return mom.shift(skip) if skip else mom


def realized_skew_panel(returns: pd.DataFrame, window: int = 252,
                        min_periods: int | None = None) -> pd.DataFrame:
    """Trailing realised (physical) skewness of daily returns, one column per currency.

    The signal at each day is the sample skewness of the last `window` daily
    returns — the physical-measure crash asymmetry a long-FX position has
    actually experienced, the realised counterpart to the option-implied skew in
    `implied_skew_panel`. Fed the daily `excess_returns` panel (the `xret`
    convention) so the skewness reflects the tradable carry-inclusive return;
    negative = crash-prone (fat left tail). `window` defaults to 252d (≈1y): third
    moments are noisy, so the skewness literature (Amaya et al. 2015; Li, Sarno &
    Zinna 2023) uses long estimation windows, and `min_periods` defaults to
    window // 2 (the library's warm-up convention). Trailing windows only, so no
    lookahead by construction — consumed exactly like `momentum_panel`, sampled
    month-end and shifted one day downstream so the effective signal never sees
    its own or future days.
    """
    mp = window // 2 if min_periods is None else min_periods
    return returns.rolling(window, min_periods=mp).skew()


# ---------------------------------------------------------------------------
# Performance statistics
# ---------------------------------------------------------------------------

def max_drawdown(returns: pd.Series) -> float:
    """Maximum drawdown of the compounded wealth curve of daily returns."""
    wealth = (1 + returns.dropna()).cumprod()
    return float((wealth / wealth.cummax() - 1).min())


def summary_stats(returns: pd.DataFrame, benchmark: pd.Series | None = None,
                  min_obs: int = 120) -> pd.DataFrame:
    """Per-column performance/distribution stats for daily return series.

    VaR/CVaR are historical, reported as positive daily loss numbers.
    If `benchmark` is given, adds an information ratio vs that series.
    cagr compounds daily values as simple returns (the max_drawdown wealth-curve
    convention; log-vs-simple is second-order at these vol levels), sortino uses
    the full-sample lower partial moment of order 2 vs a zero target, and
    calmar = cagr / |max drawdown|.
    """
    rows = {}
    for col in returns.columns:
        r = returns[col].dropna()
        if len(r) < min_obs:
            continue
        ann_mu = r.mean() * ANN_DAYS
        ann_sd = r.std() * np.sqrt(ANN_DAYS)
        q05, q01 = r.quantile(0.05), r.quantile(0.01)
        mdd = max_drawdown(r)
        cagr = (1 + r).prod() ** (ANN_DAYS / len(r)) - 1
        downside = np.sqrt((r.clip(upper=0) ** 2).mean()) * np.sqrt(ANN_DAYS)
        row = {
            "start": r.index[0].date(), "end": r.index[-1].date(), "n_days": len(r),
            "ann_return": ann_mu, "ann_vol": ann_sd, "daily_variance": r.var(),
            "skew": r.skew(), "excess_kurtosis": r.kurt(),
            "sharpe": ann_mu / ann_sd if ann_sd > 0 else np.nan,
            "max_drawdown": mdd,
            "VaR_95": -q05, "VaR_99": -q01,
            "CVaR_95": -r[r <= q05].mean(), "CVaR_99": -r[r <= q01].mean(),
            "hit_rate": (r > 0).mean(),
            "best_day": r.max(), "worst_day": r.min(),
            "autocorr_1d": r.autocorr(1),
            "cagr": cagr,
            "sortino": ann_mu / downside if downside > 0 else np.nan,
            "calmar": cagr / abs(mdd) if mdd != 0 else np.nan,
        }
        if benchmark is not None:
            active = (returns[col] - benchmark).dropna()
            te = active.std() * np.sqrt(ANN_DAYS)
            row["info_ratio"] = active.mean() * ANN_DAYS / te if te > 0 else np.nan
        rows[col] = row
    return pd.DataFrame(rows).T


def turnover(weights: pd.DataFrame, rebal: str = "ME") -> float:
    """Average one-sided turnover per rebalance period: mean over live periods of Σ|Δw|/2.

    Daily absolute weight changes are summed within each `rebal` period and
    halved (one-sided convention: fully liquidating and rebuilding a gross-2
    book counts as 2.0, i.e. buys only). The average runs from the first
    period with any live weight so pre-inception zeros don't dilute it; the
    inception trade itself is excluded (the first diff is NaN). Weights are
    expected daily and forward-filled, the `carry_portfolio` /
    `vol_target_weights` output convention.
    """
    w = weights.fillna(0.0)
    daily_to = w.diff().abs().sum(axis=1)
    per_period = daily_to.resample(rebal).sum() / 2
    live = w.abs().sum(axis=1).resample(rebal).sum() > 0
    live_periods = per_period[live.cummax()]
    return float(live_periods.mean()) if len(live_periods) else np.nan


# ---------------------------------------------------------------------------
# Factors and regressions
# ---------------------------------------------------------------------------

def dollar_factor(xret: pd.DataFrame) -> pd.Series:
    """DOL: equal-weighted long-all-currencies-vs-USD excess return (LRV)."""
    return xret.mean(axis=1).rename("DOL")


def zscore_xs(panel: pd.DataFrame) -> pd.DataFrame:
    """Cross-sectional z-score of a signal panel, standardised per date.

    Each row (date) is demeaned and divided by its own cross-sectional standard
    deviation across currencies, so signals on different natural scales — e.g.
    annualised carry vs cumulative-return momentum — become comparable before
    they are blended. Row-wise and stateless, so it introduces no lookahead; the
    downstream `carry_portfolio` still samples month-end and shifts one day.
    """
    return panel.sub(panel.mean(axis=1), axis=0).div(panel.std(axis=1), axis=0)


def xs_residual(y: pd.DataFrame, x: pd.DataFrame, add_const: bool = True) -> pd.DataFrame:
    """Cross-sectional residual of panel `y` regressed on panel `x`, per date.

    Each row (date) is an independent OLS of the currencies' `y` values on their
    `x` values — with an intercept unless add_const=False — and the returned panel
    holds the residuals y - y_hat, i.e. the part of `y` orthogonal to `x` in the
    cross-section. Used to build "clean carry": carry stripped of the component
    the option-implied crash skew explains (Jurek 2014, "Crash-Neutral Currency
    Carry Trades"), then sorted like raw carry. `x` is aligned to `y`'s calendar
    (reindexed to y.index), so the residual panel lives on y's dates. Only
    currencies with both values present on a date enter that date's fit; a date
    with fewer than 3 valid names,
    or with no cross-sectional variation in `x`, yields NaNs. Row-wise and
    stateless like `zscore_xs`, so it introduces no lookahead; the downstream
    `carry_portfolio` still samples month-end and shifts one day.
    """
    cols = y.columns.intersection(x.columns)
    Y = y[cols].to_numpy(dtype=float)
    X = x.reindex(y.index)[cols].to_numpy(dtype=float)
    mask = np.isfinite(Y) & np.isfinite(X)
    Xm, Ym = np.where(mask, X, np.nan), np.where(mask, Y, np.nan)
    n = mask.sum(axis=1)
    safe_n = np.where(n > 0, n, 1)
    if add_const:
        xd = Xm - (np.nansum(Xm, axis=1) / safe_n)[:, None]
        yd = Ym - (np.nansum(Ym, axis=1) / safe_n)[:, None]
    else:
        xd, yd = Xm, Ym
    sxx = np.nansum(xd * xd, axis=1)
    sxy = np.nansum(xd * yd, axis=1)
    with np.errstate(divide="ignore", invalid="ignore"):
        beta = sxy / sxx
    resid = yd - beta[:, None] * xd
    resid[(n < 3) | (sxx == 0) | ~np.isfinite(sxx)] = np.nan
    return pd.DataFrame(resid, index=y.index, columns=cols)


def carry_hml_factor(xret: pd.DataFrame, carry_ann: pd.DataFrame) -> pd.Series:
    """HML_FX: long top-third / short bottom-third by implied carry (LRV).

    Sorted on month-end 1M forward-implied carry, rebalanced monthly,
    weights applied from the next trading day (no lookahead).
    """
    common = xret.columns.intersection(carry_ann.columns)
    signal = carry_ann[common].resample("ME").last()
    weights = pd.DataFrame(0.0, index=signal.index, columns=common)
    for dt, row in signal.iterrows():
        valid = row.dropna()
        if len(valid) < 6:
            continue
        k = len(valid) // 3
        weights.loc[dt, valid.nlargest(k).index] = 1.0 / k
        weights.loc[dt, valid.nsmallest(k).index] = -1.0 / k
    daily_w = weights.reindex(xret.index, method="ffill").shift(1)
    return (daily_w * xret[common]).sum(axis=1, min_count=1).rename("HML_FX")


def nw_regression(y: pd.Series, X: pd.DataFrame, lags: int = 5,
                  min_obs: int = 250) -> dict | None:
    """OLS of y on X with Newey-West (HAC) standard errors.

    Returns {n, r2, alpha_ann, alpha_t, beta_<f>, t_<f>} or None if too
    few overlapping observations.
    """
    df = pd.concat([y.rename("_y"), X], axis=1).dropna()
    if len(df) < min_obs:
        return None
    exog = sm.add_constant(df[X.columns])
    res = sm.OLS(df["_y"], exog).fit(cov_type="HAC", cov_kwds={"maxlags": lags})
    out = {"n": int(res.nobs), "r2": res.rsquared,
           "alpha_ann": res.params["const"] * ANN_DAYS, "alpha_t": res.tvalues["const"]}
    for f in X.columns:
        out[f"beta_{f}"] = res.params[f]
        out[f"t_{f}"] = res.tvalues[f]
    return out


def regression_table(xret: pd.DataFrame, factors: pd.DataFrame, lags: int = 5) -> pd.DataFrame:
    """Run nw_regression of every currency on the factor set; tidy table."""
    rows = {}
    for ccy in xret.columns:
        res = nw_regression(xret[ccy], factors, lags=lags)
        if res is not None:
            rows[ccy] = res
    return pd.DataFrame(rows).T


# ---------------------------------------------------------------------------
# Phase-2 supplemental groups: risk-free, onshore rates, benchmarks, EM risk
# ---------------------------------------------------------------------------
# Source: data/raw/FX_extra_data.xlsx -> converted to parquet by
# src/convert_extra_xlsx.py, so these load through load_wide() like any group.

USD_RF = "USGG3M"                                # US 3M T-bill, risk-free anchor
USD_LIBOR = {"1M": "US0001M", "3M": "US0003M"}   # CIP-consistent USD leg (g10_interest_rates)

# Onshore money-market fixing per currency and tenor (in percent), used for
# CIP-basis checks: forward-implied carry vs onshore interest differential.
# Caveats: INR uses MIBOR-OIS (IRSWO); the o/n NSERO fixing is spiky and GIND3M
# (T-bill) is also available. CNH uses onshore SHIBOR (SHIF) as a China-rate
# proxy -- it is NOT the offshore CNH funding rate.
ONSHORE_RATES = {
    "HUF": {"1M": "BUBOR01M", "3M": "BUBOR03M"},
    "PLN": {"1M": "WIBR1M", "3M": "WIBR3M"},
    "TRY": {"1M": "TRLIB1M", "3M": "TRLIB3M"},
    "ILS": {"1M": "TELBOR01M", "3M": "TELBOR03M"},
    "THB": {"1M": "THFX1M", "3M": "THFX3M"},
    "INR": {"1M": "IRSWOA", "3M": "IRSWOC"},
    "DKK": {"1M": "CIBO01M", "3M": "CIBO03M"},
    "HKD": {"1M": "HIHD01M", "3M": "HIHD03M"},
    "CNH": {"1M": "SHIF1M", "3M": "SHIF3M"},
}


def load_rates_panel() -> pd.DataFrame:
    """All money-market fixings for CIP checks (percent), one wide frame by ticker.

    Combines onshore EM fixings, DKK/HKD gap fixings, the USD risk-free anchor
    and USD LIBOR legs, date-aligned.
    """
    frames = [load_wide("em_onshore_rates"), load_wide("g10_rates_gaps"),
              load_wide("usd_riskfree")]
    g10r = load_wide("g10_interest_rates")
    frames.append(g10r[[t for t in USD_LIBOR.values() if t in g10r.columns]])
    return pd.concat(frames, axis=1).sort_index()


def onshore_rate(ccy: str, tenor: str, rates: pd.DataFrame | None = None) -> pd.Series | None:
    """Onshore fixing for (ccy, tenor) as a decimal rate (percent / 100)."""
    tk = ONSHORE_RATES.get(ccy, {}).get(tenor)
    if tk is None:
        return None
    rates = load_rates_panel() if rates is None else rates
    if tk not in rates.columns:
        return None
    return (rates[tk] / 100.0).rename(ccy)


def interest_diff_vs_usd(tenor: str = "3M", rates: pd.DataFrame | None = None) -> pd.DataFrame:
    """Onshore foreign rate minus USD LIBOR (annual decimal), per currency.

    The CIP-implied carry: under covered interest parity this equals the
    forward-implied carry (carry_panel). USD leg is LIBOR at the same tenor.
    """
    rates = load_rates_panel() if rates is None else rates
    usd_tk = USD_LIBOR.get(tenor)
    if usd_tk is None or usd_tk not in rates.columns:
        raise ValueError(f"No USD LIBOR leg for tenor {tenor!r}")
    usd = rates[usd_tk] / 100.0
    out = {}
    for ccy in ONSHORE_RATES:
        s = onshore_rate(ccy, tenor, rates)
        if s is not None:
            out[ccy] = s - usd
    return pd.DataFrame(out)


def cip_basis(g10_px: pd.DataFrame, em_px: pd.DataFrame, tenor: str = "3M",
              rates: pd.DataFrame | None = None) -> pd.DataFrame:
    """Cross-currency basis: forward-implied carry minus onshore rate differential.

    ~0 where covered interest parity holds (deliverable currencies); materially
    non-zero and persistent for NDF currencies (convertibility/basis premium).
    Both legs are annualised decimals, aligned on common currencies and dates.
    """
    carry = carry_panel(g10_px, em_px, tenor=tenor)
    diff = interest_diff_vs_usd(tenor=tenor, rates=rates)
    common = carry.columns.intersection(diff.columns)
    return (carry[common] - diff[common]).dropna(how="all")


def basis_stress_index(basis: pd.DataFrame, method: str = "zmean",
                       window: int = 252) -> pd.Series:
    """Aggregate dollar-funding-stress gauge from the cross-currency-basis panel.

    A time-series proxy for how scarce/expensive synthetic USD funding is:
    higher = more stress. When dollar funding tightens, the (NDF-heavy EM) basis
    widens negative, so the index rises. Motivated by the dollar / bank-leverage /
    CIP-basis "triangle" of Avdjiev, Du, Koch & Shin (2019) and the CIP-deviation
    intermediary story of Du, Tepper & Verdelhan (2018); as a carry de-risking
    conditioner it operationalises the funding-liquidity channel of Brunnermeier,
    Nagel & Pedersen (2009). `method` sets how the cross-section is aggregated:
    - "zmean" (default): mean over names of each currency's trailing-`window`
      z-score of the basis, negated. Standardising per name first stops a single
      wide-basis currency (e.g. TRY, whose basis averages ~+370bps here) from
      dominating and isolates common funding pressure -- so defined, the index
      peaks at Lehman (2008-09) and the COVID dollar squeeze (2020-12).
    - "mean"/"median": negated cross-sectional mean / (outlier-robust) median.
    - "worst": negated cross-sectional min (the single most-stressed name).
    No lookahead: a contemporaneous (trailing-window for "zmean") aggregate of
    `basis`, consumed like any signal -- sampled month-end and shifted one day
    downstream by exposure_scalar / vol_target_weights. Units follow `basis`
    (annualised decimals) except "zmean", which is unitless; either way only the
    trailing-percentile rank enters exposure_scalar, so the scale is immaterial.
    """
    if method not in ("zmean", "mean", "median", "worst"):
        raise ValueError(f"method must be one of zmean/mean/median/worst, got {method!r}")
    if method == "zmean":
        mu = basis.rolling(window, min_periods=window // 4).mean()
        sd = basis.rolling(window, min_periods=window // 4).std()
        idx = -((basis - mu) / sd).mean(axis=1)
    elif method == "mean":
        idx = -basis.mean(axis=1)
    elif method == "median":
        idx = -basis.median(axis=1)
    else:
        idx = -basis.min(axis=1)
    return idx.rename("basis_stress")


def load_benchmarks() -> pd.DataFrame:
    """Carry benchmark index levels (DBHVG10U, FXCTEM8, DBHVBUSI)."""
    return load_wide("fx_carry_benchmarks")


def benchmark_returns() -> pd.DataFrame:
    """Daily log returns of the carry benchmark indices."""
    return np.log(load_benchmarks()).diff()


def load_em_risk() -> pd.Series:
    """JPM EMBI Global sovereign spread (basis points)."""
    return load_wide("em_risk")["JPEIGLSP"].rename("EMBI_spread")


# ---------------------------------------------------------------------------
# Portfolio construction: bucket sorts, vol targeting, transaction costs
# ---------------------------------------------------------------------------

def carry_portfolio(carry_ann: pd.DataFrame, xret: pd.DataFrame, n_buckets: int = 3,
                    rebal: str = "ME", vol_window: int = 60, min_per_leg: int = 2,
                    universe: list[str] | None = None,
                    max_leg_share: float = 0.40,
                    filter_signal: pd.DataFrame | None = None,
                    weighting: str = "inv_vol", cov_window: int = 250) -> pd.DataFrame:
    """Daily weight panel of a long/short carry sort, weighted within each leg.

    On each rebalance date (last observation per `rebal` period) currencies are
    sorted on carry into n_buckets; the top bucket is held long, the bottom
    short. Within each leg weights follow `weighting`, are normalised to gross 1
    per side (book gross 2, net 0), with any single name capped at
    max_leg_share of its leg. A rebalance date with fewer than min_per_leg names
    per bucket keeps the previous weights. Weights are forward-filled to trading
    days and shifted one day — applied from the next trading day, mirroring
    carry_hml_factor (no lookahead). Note: signals are per-column last
    observations of the period, so a gappy currency can contribute a slightly
    stale (intra-month) carry reading.

    `weighting` selects the within-leg scheme (Stage 4 comparison):
    - "inv_vol" (default): proportional to 1/trailing-vol (vol_window days,
      needing >= vol_window//2 obs, which gates late entrants like CNH).
    - "equal": 1/k per name.
    - "erc": equal risk contribution (erc_weights) on the leg's shrunk_cov.
    - "mvo": max-Sharpe (mvo_weights) with mu = sign*carry on the leg's
      shrunk_cov.
    For "erc"/"mvo" the covariance is a Ledoit-Wolf estimate over the trailing
    `cov_window` days up to the rebalance date, computed on the leg's own names
    (a small, well-conditioned block); a leg with fewer than
    max(2*len(names), vol_window) complete rows falls back to inv_vol for that
    leg. Because the covariance uses data only up to dt and the panel is
    shifted one day at the end, the optimised schemes add no lookahead. The
    default preserves the exact inverse-vol behaviour of earlier stages.

    `filter_signal` (optional, same panel shape) applies a directional double
    sort after bucketing: long-leg names are kept only where filter_signal >= 0
    and short-leg names only where filter_signal <= 0, then each leg is
    re-normalised over its survivors (the max_leg_share cap still binds). This
    is the momentum-filter overlay (long high-carry that is also trending up,
    short low-carry that is also trending down); a leg with no survivors that
    period is simply left flat. filter_signal is sampled month-end and enters at
    t-1 like the carry signal, so the overlay adds no lookahead.
    """
    if weighting not in ("equal", "inv_vol", "erc", "mvo"):
        raise ValueError(f"weighting must be equal/inv_vol/erc/mvo, got {weighting!r}")
    cols = carry_ann.columns.intersection(xret.columns)
    if universe is not None:
        cols = cols.intersection(universe)
    xr = xret[cols]
    signal = carry_ann[cols].resample(rebal).last()
    vol = xr.rolling(vol_window, min_periods=vol_window // 2).std()
    vol_rb = vol.resample(rebal).last()
    filt = filter_signal[cols].resample(rebal).last() if filter_signal is not None else None

    rows = {}
    for dt in signal.index:
        valid = pd.concat([signal.loc[dt].rename("carry"),
                           vol_rb.loc[dt].rename("vol")], axis=1).dropna()
        valid = valid[valid["vol"] > 0]
        k = len(valid) // n_buckets
        if k < min_per_leg:
            continue
        w = pd.Series(0.0, index=cols)
        f = filt.loc[dt] if filt is not None else None
        hist = xr.loc[:dt] if weighting in ("erc", "mvo") else None
        for names, sign in ((valid["carry"].nlargest(k).index, 1.0),
                            (valid["carry"].nsmallest(k).index, -1.0)):
            if f is not None:
                fn = f.reindex(names)
                names = names[(fn >= 0).values] if sign > 0 else names[(fn <= 0).values]
                if len(names) == 0:
                    continue
            if weighting == "equal":
                leg = pd.Series(1.0, index=names)
            elif weighting == "inv_vol":
                leg = (1.0 / valid.loc[names, "vol"])
            else:
                sub = hist[list(names)]
                if len(sub.tail(cov_window).dropna(how="any")) < max(2 * len(names), vol_window):
                    leg = (1.0 / valid.loc[names, "vol"])  # cov not estimable -> inv_vol
                else:
                    cov = shrunk_cov(sub, window=cov_window)
                    if weighting == "erc":
                        leg = erc_weights(cov)
                    else:
                        mu = (sign * valid.loc[names, "carry"]).to_numpy()
                        leg = mvo_weights(mu, cov, gross=1.0, max_share=max_leg_share)
            leg = leg / leg.sum()
            for _ in range(10):
                if not (leg > max_leg_share + 1e-12).any():
                    break
                leg = leg.clip(upper=max_leg_share)
                leg /= leg.sum()
            w[names] = sign * leg
        rows[dt] = w
    weights = pd.DataFrame(rows).T
    return weights.reindex(xret.index, method="ffill").shift(1)


def vol_target_weights(weights: pd.DataFrame, xret: pd.DataFrame, target: float = 0.10,
                       window: int = 60, rebal: str = "ME", lev_cap: float = 4.0,
                       vol_floor: float = 0.01) -> pd.DataFrame:
    """Scale a daily weight panel to an annualised portfolio vol target.

    The scalar is target / trailing realised vol of the unit book's own return
    series — not an ex-ante w'Σw: with ~27 assets a 60-day sample covariance is
    noisy/near-singular, while the unit book's realised vol already embeds all
    correlations and the book composition only changes monthly. The scalar is
    sampled at rebalance dates, capped at lev_cap, floored at vol_floor
    annualised vol, and applied from the next trading day (no lookahead).
    """
    common = weights.columns.intersection(xret.columns)
    r_unit = (weights[common] * xret[common]).sum(axis=1, min_count=1)
    vol = r_unit.rolling(window, min_periods=window // 2).std() * np.sqrt(ANN_DAYS)
    scalar = (target / vol.clip(lower=vol_floor)).clip(upper=lev_cap)
    scalar_rb = scalar.resample(rebal).last()
    daily = scalar_rb.reindex(weights.index, method="ffill").shift(1)
    return weights.mul(daily, axis=0)


# ---------------------------------------------------------------------------
# Within-leg weighting schemes (Stage 4): shrinkage cov, ERC, mean-variance
# ---------------------------------------------------------------------------

def shrunk_cov(xret: pd.DataFrame, window: int = 250) -> pd.DataFrame:
    """Ledoit-Wolf shrinkage covariance toward a scaled-identity target.

    Takes a daily-return frame, uses its last `window` complete-case rows
    (tail(window) then dropna(how="any"), so the sample covariance is genuinely
    PSD rather than a pairwise pseudo-cov), demeans each column and forms the
    MLE sample covariance S = X'X / t. Shrinks toward F = mu*I with
    mu = trace(S)/N (Ledoit & Wolf 2004, the single-parameter `cov1Para`
    estimator), at the closed-form optimal intensity
    delta* = clip((pi_hat / gamma_hat) / t, 0, 1), where
    pi_hat = sum((X^2)'(X^2)/t - S^2) and gamma_hat = ||S - F||_F^2. Returns
    delta*F + (1-delta*)S as a DataFrame labelled by the surviving columns.

    NOT annualised: both consumers (erc_weights and the fixed-budget max-Sharpe
    in mvo_weights) are invariant to Sigma -> c*Sigma, so scaling by ANN_DAYS
    would be a no-op — kept as a plain daily estimator. Too-few-rows and
    universe selection are the caller's responsibility (see carry_portfolio),
    which keeps this helper pure; given >= 2 complete rows it always returns a
    symmetric positive-definite matrix.
    """
    data = xret.tail(window).dropna(how="any")
    cols = data.columns
    X = data.to_numpy(dtype=float)
    t, n = X.shape
    X = X - X.mean(axis=0)
    S = (X.T @ X) / t
    mu = np.trace(S) / n
    F = mu * np.eye(n)
    Xsq = X ** 2
    pi_hat = ((Xsq.T @ Xsq) / t - S ** 2).sum()
    gamma = np.sum((S - F) ** 2)
    delta = float(np.clip((pi_hat / gamma) / t, 0.0, 1.0)) if gamma > 0 else 0.0
    sigma = delta * F + (1.0 - delta) * S
    return pd.DataFrame(sigma, index=cols, columns=cols)


def erc_weights(cov, max_iter: int = 1000, tol: float = 1e-8):
    """Long-only equal-risk-contribution weights via cyclical coordinate descent.

    Solves the strictly-convex log-barrier program
    min 1/2 w'Sigma w - (1/N) sum log w_i, w > 0, whose stationary point
    equalises the risk contributions RC_i = w_i (Sigma w)_i (Spinu 2013;
    Griveau-Billion, Richard & Roncalli 2013). Each coordinate update takes the
    positive root of y_i Sigma_ii + c_i - b/y_i = 0 with
    c_i = sum_{j!=i} y_j Sigma_ij and b = 1/N, sweeping cyclically from an
    inverse-vol warm start; the update runs on the raw y (the log-barrier fixed
    point y_i (Sigma y)_i = b), while convergence is measured on the normalised
    weights y/sum(y) against `tol` for interpretability. Returns weights summing
    to 1 (positive). A diagonal Sigma converges in one sweep to
    w_i proportional to 1/sigma_i — i.e. reduces exactly to inverse-vol.

    No single-name cap here: the cap is applied outside by carry_portfolio's
    existing clip-and-renormalise loop, exactly as for inverse-vol.
    """
    S = np.asarray(cov, dtype=float)
    n = S.shape[0]
    if n == 1:
        w = np.ones(1)
    else:
        b = 1.0 / n
        y = 1.0 / np.sqrt(np.diag(S))
        w = y / y.sum()
        for _ in range(max_iter):
            w_prev = y / y.sum()
            for i in range(n):
                c = S[i] @ y - S[i, i] * y[i]
                a = S[i, i]
                y[i] = (-c + np.sqrt(c * c + 4.0 * a * b)) / (2.0 * a)
            w = y / y.sum()
            if np.max(np.abs(w - w_prev)) < tol:
                break
    return pd.Series(w, index=cov.index) if isinstance(cov, pd.DataFrame) else w


def mvo_weights(mu, cov, gross: float = 1.0, max_share: float = 0.40):
    """Long-only max-Sharpe weights under leg-gross and single-name-cap constraints.

    Maximises (mu'w) / sqrt(w'Sigma w) subject to w >= 0, sum(w) = gross,
    w <= max_share, via SLSQP on the negative Sharpe ratio (a tiny
    trace-proportional ridge on Sigma guarantees strict positive-definiteness).
    mu is the observable forward-implied carry — no return forecasting.

    Precondition (caller's responsibility): pass mu = sign * carry so that
    shorting a low/negative-carry name reads as positive expected profit;
    mvo_weights is sign-agnostic and always returns positive weights summing to
    `gross`, with carry_portfolio applying `sign` outside. Guards: if a leg is
    too small for the cap (n * max_share < gross) the cap is relaxed to
    eff_cap = max(max_share, gross/n) — matching inverse-vol's effective
    equal-weight collapse in the same case; if mu has no positive entry the
    max-Sharpe objective is ill-posed and we fall back to min-variance under the
    same constraints; if the optimiser fails we fall back to equal weight. The
    result is always finite and feasible, so the caller never sees NaNs.
    """
    mu = np.asarray(mu, dtype=float)
    S = np.asarray(cov, dtype=float)
    n = len(mu)
    idx = cov.index if isinstance(cov, pd.DataFrame) else None
    eff_cap = max(max_share, gross / n)
    S = S + 1e-10 * (np.trace(S) / n) * np.eye(n)
    bounds = [(0.0, eff_cap)] * n
    cons = ({"type": "eq", "fun": lambda w: w.sum() - gross},)
    w0 = np.full(n, gross / n)

    def _solve(objective):
        r = minimize(objective, w0, method="SLSQP", bounds=bounds,
                     constraints=cons, options={"maxiter": 200, "ftol": 1e-12})
        w = r.x if r.success else w0
        w = np.clip(w, 0.0, eff_cap)
        return w * (gross / w.sum())

    if np.any(mu > 0):
        w = _solve(lambda w: -(mu @ w) / np.sqrt(w @ S @ w + 1e-18))
    else:
        w = _solve(lambda w: w @ S @ w)
    return pd.Series(w, index=idx) if idx is not None else w


def exposure_scalar(indicator: pd.Series, lookback: int = 756, q: float = 0.80,
                    low_mult: float = 0.5, rebal: str = "ME",
                    method: str = "binary") -> pd.Series:
    """Daily de-risking multiplier from a trailing-percentile threshold on a risk indicator.

    Generalises the crash hedge to any conditioning series (VIX, aggregate IV,
    risk reversals, EMBI): the indicator's trailing `lookback`-day percentile
    rank (756d ≈ 3y; min_periods = lookback // 2, the library's window // 2
    convention) is sampled at `rebal` dates, mapped to a multiplier, then
    forward-filled and shifted one day — effective the next trading day, no
    lookahead. Note the quantile uses ~756 daily observations, not the 36
    month-end points of the original ad-hoc notebook hedge.
    - method="binary": 1.0 while the rank is at or below `q`, `low_mult` above
      it (halve exposure in the top quintile at the defaults).
    - method="linear": ramp from 1.0 at rank `q` down to `low_mult` at rank
      1.0, identical to binary below `q` — the flagged continuous refinement.
    Missing indicator values and the burn-in period map to 1.0 (no signal →
    fully invested), so the returned daily Series is NaN-free in
    [low_mult, 1.0] and can never null out valid weights. Apply it as
    w.mul(s.reindex(w.index, method="ffill").fillna(1.0), axis=0).
    """
    if method not in ("binary", "linear"):
        raise ValueError(f"method must be 'binary' or 'linear', got {method!r}")
    pct = indicator.rolling(lookback, min_periods=lookback // 2).rank(pct=True)
    me = pct.resample(rebal).last()
    if method == "binary":
        s_me = pd.Series(np.where(me > q, low_mult, 1.0), index=me.index)
    else:
        ramp = ((me - q) / (1.0 - q)).clip(0.0, 1.0)
        s_me = (1.0 - (1.0 - low_mult) * ramp).fillna(1.0)
    daily = s_me.reindex(indicator.index, method="ffill").shift(1).fillna(1.0)
    daily.name = indicator.name
    return daily


def regime_classify(indicators: pd.DataFrame, lookback: int = 756,
                    breaks: tuple[float, float] = (0.70, 0.90)) -> pd.DataFrame:
    """Percentile-composite market-regime classifier: Low / Moderate / Crisis.

    Each indicator column (VIX, aggregate FX ATM implied vol, EMBI spread, ...)
    is ranked into its own trailing `lookback`-day percentile (756d ≈ 3y,
    min_periods = lookback // 2 — the library's window // 2 convention); the
    composite is the row-mean of the available ranks. Regimes are cut at
    asymmetric `breaks` on the composite: `composite <= breaks[0]` -> Low,
    `<= breaks[1]` -> Moderate, else Crisis. Asymmetric because crisis is a tail
    state — equal terciles would mislabel a third of history "crisis".

    Trailing windows only, so the label at date t uses data through t and adds
    no lookahead as a descriptive series; when it drives allocation it must be
    lagged (resample at rebalance + shift one day), exactly like exposure_scalar.
    Returns a daily frame: each indicator's `<name>_rank`, the `composite`, and
    the `regime` label (NaN through the burn-in where no rank is available yet).
    """
    ranks = indicators.rolling(lookback, min_periods=lookback // 2).rank(pct=True)
    composite = ranks.mean(axis=1).rename("composite")
    lo, hi = breaks
    regime = pd.cut(composite, bins=[-np.inf, lo, hi, np.inf],
                    labels=["Low", "Moderate", "Crisis"])
    out = ranks.add_suffix("_rank")
    out["composite"] = composite
    out["regime"] = regime.astype(object).where(composite.notna())
    return out


def portfolio_returns(weights: pd.DataFrame, xret: pd.DataFrame,
                      name: str = "portfolio") -> pd.Series:
    """Daily portfolio return Σ w·r (min_count=1 so pre-inception days stay NaN).

    Summing weighted log excess returns is a daily-frequency approximation of
    the true portfolio return; fine at these vol levels.
    """
    common = weights.columns.intersection(xret.columns)
    return (weights[common] * xret[common]).sum(axis=1, min_count=1).rename(name)


def forward_halfspreads(tenor: str = "1M", winsor_q: float = 0.99,
                        ffill_limit: int = 5) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Relative half-spreads per currency for forward trading and rolling.

    Returns (hs_outright, hs_points), both as fractions of mid notional:
    - hs_outright: (F_ask - F_bid) / (2 F_mid) with F_side built from spot
      bid/ask plus forward points bid/ask on the same side (points get the
      same FWD_SCALE division as carry_panel) — the cost of crossing the full
      outright forward, paid on notional that is newly transacted.
    - hs_points: points spread only, (P_ask - P_bid)/scale / (2 S_mid) — the
      cost of rolling a maintained position via an FX swap whose spot leg
      crosses at mid.
    Relative half-spreads are invariant to quote inversion, so no USD-per-FX
    handling is needed. Cleaning: crossed quotes clipped at 0, per-currency
    winsorisation at winsor_q, forward-fill up to ffill_limit days (some EM
    bid columns are gappy: ZAR ~95%, CNH ~81% coverage).
    """
    fields = {f: pd.concat([load_wide("g10_fx_spot_forward", f),
                            load_wide("em_fx_spot_forward", f)], axis=1)
              for f in ("PX_BID", "PX_ASK", "PX_LAST")}
    hs_out, hs_pts = {}, {}
    for ccy in ALL_CCY:
        root = FWD_ROOT.get(ccy)
        fwd_tk = None if root is None else f"{root}{tenor}"
        if fwd_tk is None or ccy not in fields["PX_LAST"].columns \
                or fwd_tk not in fields["PX_LAST"].columns:
            continue
        scale = FWD_SCALE[ccy]
        s_bid, s_ask, s_mid = (fields[f][ccy] for f in ("PX_BID", "PX_ASK", "PX_LAST"))
        p_bid, p_ask = fields["PX_BID"][fwd_tk], fields["PX_ASK"][fwd_tk]
        f_bid = s_bid + p_bid / scale
        f_ask = s_ask + p_ask / scale
        f_mid = s_mid + (p_bid + p_ask) / (2 * scale)
        hs_out[ccy] = (f_ask - f_bid) / (2 * f_mid)
        hs_pts[ccy] = (p_ask - p_bid) / scale / (2 * s_mid)

    def _clean(d: dict) -> pd.DataFrame:
        df = pd.DataFrame(d).clip(lower=0)
        df = df.apply(lambda s: s.clip(upper=s.quantile(winsor_q)))
        return df.ffill(limit=ffill_limit)

    return _clean(hs_out), _clean(hs_pts)


def roundtrip_cost(weights: pd.DataFrame, hs_outright: pd.DataFrame,
                   hs_points: pd.DataFrame | None = None) -> pd.Series:
    """Daily transaction-cost series (return units, >= 0) for a weight panel.

    Charged on the days weights actually change (the rebalance effective day,
    since monthly weights are forward-filled between rebalances):
    - turnover leg: Σ |Δw| · hs_outright — changed notional crosses the full
      outright-forward spread;
    - roll leg (if hs_points given): Σ min(|w_old|, |w_new|) · hs_points —
      maintained notional rolls its 1M forward via an FX swap and pays only
      the points spread. Charging the outright on the full book instead would
      roughly double costs (gross-2 book, 12 rolls/yr).
    Spreads are forward-filled and gap-filled with the per-currency median so
    a missing quote never silently zeroes a real cost.
    """
    w = weights.fillna(0.0)
    common = w.columns.intersection(hs_outright.columns)
    dropped = [c for c in w.columns if c not in common]
    if dropped:
        raise ValueError(f"No half-spread series for {dropped}")

    def _prep(hs: pd.DataFrame) -> pd.DataFrame:
        hs = hs[common].reindex(w.index).ffill()
        return hs.fillna(hs.median())

    dw = w[common].diff()
    dw.iloc[0] = w[common].iloc[0]
    cost = (dw.abs() * _prep(hs_outright)).sum(axis=1, min_count=1)
    if hs_points is not None:
        held = np.minimum(w[common].abs(), w[common].shift(1).abs().fillna(0.0))
        rebal_day = dw.abs().sum(axis=1) > 0
        roll = (held * _prep(hs_points)).sum(axis=1, min_count=1).where(rebal_day, 0.0)
        cost = cost.add(roll, fill_value=0.0)
    return cost.rename("tcost")


def vol_surface_panel(kind: str = "ATM", tenor: str = "1M", delta: int = 25) -> pd.DataFrame:
    """FX option vol-surface points per currency (vol points, columns = ccys).

    kind="ATM" loads {pair}V{tenor}; kind="RR" the {pair}{delta}R{tenor} risk
    reversal; kind="BF" the butterfly. Pair names follow market convention
    (AUDUSD/EURUSD/GBPUSD/NZDUSD are FX-first, the rest USD-first). RR values
    are sign-normalised to crash-positive: positive always means FX puts rich
    vs USD (crash fear for a long-FX carry position), which requires flipping
    the FX-first pairs. Coverage: all G10 pairs, 13 EM currencies (no
    CLP/COP/IDR/MYR/PEN/PHP options were downloaded).
    """
    opts = pd.concat([load_wide("g10_fx_options"), load_wide("em_fx_options")], axis=1)
    suffix = {"ATM": f"V{tenor}", "RR": f"{delta}R{tenor}", "BF": f"{delta}B{tenor}"}
    if kind not in suffix:
        raise ValueError(f"kind must be ATM/RR/BF, got {kind!r}")
    out = {}
    for ccy in ALL_CCY:
        pair = f"{ccy}USD" if ccy in USD_PER_FX else f"USD{ccy}"
        tk = f"{pair}{suffix[kind]}"
        if tk not in opts.columns:
            continue
        s = opts[tk]
        if kind == "RR" and ccy in USD_PER_FX:
            s = -s  # FX-first pair: RR = FX-call minus FX-put -> flip to crash-positive
        out[ccy] = s
    return pd.DataFrame(out)


def implied_skew_panel(tenor: str = "1M", delta: int = 25,
                       standardize: bool = True) -> pd.DataFrame:
    """Option-implied crash skew per currency from the risk reversal.

    The 25-delta risk reversal is the market price of the smile's slope — how much
    richer out-of-the-money FX puts are than calls — and is the first-order,
    model-free read on the risk-neutral skewness of each currency vs USD. Built on
    `vol_surface_panel("RR")`, already sign-normalised crash-positive: positive =
    puts rich = the market pricing a fat left tail (crash) for a long-FX carry
    position, so it is the *negative* of the risk-neutral skewness. If
    `standardize` (default) the RR is divided by the ATM vol
    (`vol_surface_panel("ATM")`) to give the dimensionless "smile skew" RR/ATM
    (Malz 1997), comparable across currencies on very different vol levels; the
    ATM-scaled slope preserves the cross-sectional ranking the sort relies on. A
    full Bakshi-Kapadia-Madan model-free skewness would need the whole strike
    chain, which the 3-point (ATM/RR/BF) surface here does not provide. Purely
    contemporaneous per date, so it introduces no lookahead — consumed like
    `carry_panel`, sampled month-end and shifted one day downstream.
    """
    rr = vol_surface_panel("RR", tenor=tenor, delta=delta)
    if not standardize:
        return rr
    atm = vol_surface_panel("ATM", tenor=tenor)
    common = rr.columns.intersection(atm.columns)
    return rr[common] / atm[common].replace(0.0, np.nan)
