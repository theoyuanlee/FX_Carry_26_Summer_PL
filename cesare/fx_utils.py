"""Shared helpers for the FX carry project.

Data loading, currency-return construction (spot and forward-implied carry),
performance statistics and factor regressions. Used by the notebooks in
notebooks/ and, later, by the strategy backtests.
"""

from pathlib import Path

import numpy as np
import pandas as pd
import statsmodels.api as sm

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
# notebooks/data_visualization.ipynb).
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
    """
    rows = {}
    for col in returns.columns:
        r = returns[col].dropna()
        if len(r) < min_obs:
            continue
        ann_mu = r.mean() * ANN_DAYS
        ann_sd = r.std() * np.sqrt(ANN_DAYS)
        q05, q01 = r.quantile(0.05), r.quantile(0.01)
        row = {
            "start": r.index[0].date(), "end": r.index[-1].date(), "n_days": len(r),
            "ann_return": ann_mu, "ann_vol": ann_sd, "daily_variance": r.var(),
            "skew": r.skew(), "excess_kurtosis": r.kurt(),
            "sharpe": ann_mu / ann_sd if ann_sd > 0 else np.nan,
            "max_drawdown": max_drawdown(r),
            "VaR_95": -q05, "VaR_99": -q01,
            "CVaR_95": -r[r <= q05].mean(), "CVaR_99": -r[r <= q01].mean(),
            "hit_rate": (r > 0).mean(),
            "best_day": r.max(), "worst_day": r.min(),
            "autocorr_1d": r.autocorr(1),
        }
        if benchmark is not None:
            active = (returns[col] - benchmark).dropna()
            te = active.std() * np.sqrt(ANN_DAYS)
            row["info_ratio"] = active.mean() * ANN_DAYS / te if te > 0 else np.nan
        rows[col] = row
    return pd.DataFrame(rows).T


# ---------------------------------------------------------------------------
# Factors and regressions
# ---------------------------------------------------------------------------

def dollar_factor(xret: pd.DataFrame) -> pd.Series:
    """DOL: equal-weighted long-all-currencies-vs-USD excess return (LRV)."""
    return xret.mean(axis=1).rename("DOL")


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
                    max_leg_share: float = 0.40) -> pd.DataFrame:
    """Daily weight panel of an inverse-vol long/short carry sort.

    On each rebalance date (last observation per `rebal` period) currencies are
    sorted on carry into n_buckets; the top bucket is held long, the bottom
    short. Within each leg weights are proportional to 1/trailing-vol
    (vol_window days, needing >= vol_window//2 observations, which gates late
    entrants like CNH), normalised to gross 1 per side (book gross 2, net 0),
    with any single name capped at max_leg_share of its leg. A rebalance date
    with fewer than min_per_leg names per bucket keeps the previous weights.
    Weights are forward-filled to trading days and shifted one day — applied
    from the next trading day, mirroring carry_hml_factor (no lookahead).
    Note: signals are per-column last observations of the period, so a gappy
    currency can contribute a slightly stale (intra-month) carry reading.
    """
    cols = carry_ann.columns.intersection(xret.columns)
    if universe is not None:
        cols = cols.intersection(universe)
    signal = carry_ann[cols].resample(rebal).last()
    vol = xret[cols].rolling(vol_window, min_periods=vol_window // 2).std()
    vol_rb = vol.resample(rebal).last()

    rows = {}
    for dt in signal.index:
        valid = pd.concat([signal.loc[dt].rename("carry"),
                           vol_rb.loc[dt].rename("vol")], axis=1).dropna()
        valid = valid[valid["vol"] > 0]
        k = len(valid) // n_buckets
        if k < min_per_leg:
            continue
        w = pd.Series(0.0, index=cols)
        for names, sign in ((valid["carry"].nlargest(k).index, 1.0),
                            (valid["carry"].nsmallest(k).index, -1.0)):
            leg = (1.0 / valid.loc[names, "vol"])
            leg /= leg.sum()
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
