"""Performance and risk metrics for return series."""

from __future__ import annotations

import numpy as np
import pandas as pd
import statsmodels.api as sm

from . import constants as const


def sharpe_ratio(
    returns: pd.Series | pd.DataFrame,
    annualize: float = const.DEFAULT_ANNUALIZATION,
) -> float | pd.Series:
    """Annualized Sharpe ratio: ``mean / std * sqrt(annualize)``."""
    mean = returns.mean()
    std = returns.std()
    return (mean / std) * np.sqrt(annualize)


def max_drawdown(cumulative: pd.Series) -> float:
    """Maximum peak-to-trough drawdown of a cumulative NAV/index series."""
    running_max = cumulative.cummax()
    drawdown = cumulative / running_max - 1.0
    return float(drawdown.min())


def skewness(returns: pd.Series | pd.DataFrame) -> float | pd.Series:
    """Sample skewness."""
    return returns.skew()


def kurtosis(returns: pd.Series | pd.DataFrame, excess: bool = True) -> float | pd.Series:
    """Sample kurtosis. ``excess=True`` (default) returns Fisher (excess,
    normal=0) kurtosis, matching pandas' own ``.kurt()``."""
    k = returns.kurt()
    return k if excess else k + 3.0


def turnover(weights: pd.DataFrame) -> pd.Series:
    """Average absolute change in weights per rebalance (date x currency ->
    a per-date Series)."""
    return weights.diff().abs().mean(axis=1)


def newey_west_se(returns: pd.Series, lags: int | None = None) -> float:
    """HAC (Newey-West) standard error for the sample mean of `returns`."""
    lags = const.DEFAULT_NW_LAGS if lags is None else lags
    clean = returns.dropna()
    x = np.ones((len(clean), 1))
    model = sm.OLS(clean.to_numpy(), x).fit(cov_type="HAC", cov_kwds={"maxlags": lags})
    return float(model.bse[0])


def summary_table(
    returns: pd.Series | pd.DataFrame,
    annualize: float = const.DEFAULT_ANNUALIZATION,
    nw_lags: int | None = None,
) -> pd.DataFrame:
    """Table with mean, std, Sharpe, skew, kurtosis, and NW standard error of
    the mean -- one row per column of `returns` (the standard carry-strategy
    "Table 1" layout)."""
    if isinstance(returns, pd.Series):
        returns = returns.to_frame(name=returns.name or "return")

    rows: dict[str, dict[str, float]] = {}
    for col in returns.columns:
        s = returns[col].dropna()
        rows[col] = {
            "mean_ann": s.mean() * annualize,
            "std_ann": s.std() * np.sqrt(annualize),
            "sharpe": sharpe_ratio(s, annualize),
            "skew": skewness(s),
            "kurtosis": kurtosis(s),
            "nw_se_mean_ann": newey_west_se(s, lags=nw_lags) * annualize,
            "n_obs": s.shape[0],
        }
    return pd.DataFrame(rows).T
