from __future__ import annotations

import numpy as np
import pandas as pd

TRADING_DAYS = 252


def safe_log_return(prices: pd.DataFrame) -> pd.DataFrame:
    """Compute log returns after excluding non-positive prices."""
    return np.log(prices.where(prices > 0)).diff()


def forward_implied_carry(
    spot: pd.DataFrame,
    forward: pd.DataFrame,
    tenor_months: int = 1,
) -> pd.DataFrame:
    """
    Annualized log forward-implied carry.

    Assumes spot and forward are expressed in the same quotation convention.
    """
    if tenor_months <= 0:
        raise ValueError("tenor_months must be positive")
    return np.log(spot / forward) * (12.0 / tenor_months)


def annualized_vol(
    returns: pd.DataFrame | pd.Series,
    window: int = 60,
) -> pd.DataFrame | pd.Series:
    min_periods = max(20, window // 3)
    return returns.rolling(window, min_periods=min_periods).std() * np.sqrt(TRADING_DAYS)


def build_monthly_state_features(
    carry_returns: pd.Series,
    market_features: pd.DataFrame,
    carry_dispersion: pd.Series | None = None,
) -> pd.DataFrame:
    """Build laggable monthly state variables for the regime model."""
    monthly_return = (1.0 + carry_returns.fillna(0.0)).resample("ME").prod() - 1.0

    features = market_features.resample("ME").last().ffill()
    features = (
        features.pct_change()
        .replace([np.inf, -np.inf], np.nan)
        .add_suffix("_change")
    )

    features["carry_volatility_3m"] = monthly_return.rolling(3).std()
    features["carry_momentum_3m"] = (
        (1.0 + monthly_return).rolling(3).apply(np.prod, raw=True) - 1.0
    )
    features["carry_momentum_12m"] = (
        (1.0 + monthly_return).rolling(12).apply(np.prod, raw=True) - 1.0
    )

    wealth = (1.0 + monthly_return).cumprod()
    features["carry_drawdown"] = wealth / wealth.cummax() - 1.0

    if carry_dispersion is not None:
        features["carry_dispersion"] = carry_dispersion.resample("ME").last()

    features["target_next_positive"] = (monthly_return.shift(-1) > 0).astype(float)
    features["next_return"] = monthly_return.shift(-1)
    return features
