from __future__ import annotations

import numpy as np
import pandas as pd

TRADING_DAYS = 252


def maximum_drawdown(returns: pd.Series) -> float:
    wealth = (1.0 + returns.fillna(0.0)).cumprod()
    drawdown = wealth / wealth.cummax() - 1.0
    return float(drawdown.min()) if len(drawdown) else np.nan


def summary_statistics(
    returns: pd.Series,
    turnover: pd.Series | None = None,
    periods_per_year: int = TRADING_DAYS,
) -> pd.Series:
    clean = returns.dropna()
    if clean.empty:
        return pd.Series(dtype=float)

    annual_return = (1.0 + clean).prod() ** (periods_per_year / len(clean)) - 1.0
    annual_volatility = clean.std(ddof=1) * np.sqrt(periods_per_year)
    downside_volatility = clean[clean < 0].std(ddof=1) * np.sqrt(periods_per_year)
    max_dd = maximum_drawdown(clean)

    result = {
        "annual_return": annual_return,
        "annual_volatility": annual_volatility,
        "sharpe": annual_return / annual_volatility if annual_volatility > 0 else np.nan,
        "sortino": annual_return / downside_volatility if downside_volatility > 0 else np.nan,
        "maximum_drawdown": max_dd,
        "calmar": annual_return / abs(max_dd) if max_dd < 0 else np.nan,
        "hit_rate": (clean > 0).mean(),
        "observations": len(clean),
    }

    if turnover is not None:
        aligned_turnover = turnover.reindex(clean.index).fillna(0.0)
        result["annual_turnover"] = aligned_turnover.mean() * periods_per_year

    return pd.Series(result)


def performance_by_condition(
    returns: pd.Series,
    condition: pd.Series,
    periods_per_year: int = 12,
) -> pd.DataFrame:
    frame = pd.concat(
        [returns.rename("return"), condition.rename("condition")],
        axis=1,
    ).dropna()

    rows = []
    for label, group in frame.groupby("condition", observed=True):
        stats = summary_statistics(
            group["return"],
            periods_per_year=periods_per_year,
        )
        stats["condition"] = str(label)
        rows.append(stats)

    if not rows:
        return pd.DataFrame()

    return pd.DataFrame(rows).set_index("condition")
