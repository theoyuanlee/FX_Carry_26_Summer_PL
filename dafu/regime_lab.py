"""Plumbing between the team's shared panels and fxcarry's regime estimators.

Nothing here decides anything. It loads the risk and macro series the project already has,
puts them on a month-end grid, and hands them to `fxcarry.regimes` in the shape those
estimators expect. The financial choices — which state counts as stressed, how much to
de-risk, when to re-estimate — belong to the models and the gates, not to a loader.

Two conventions run through the whole file and both exist to stop the future leaking in:

* every series is sampled with `.last()` at month end, never averaged over the month, so a
  value dated ``t`` was observable at the close of ``t``;
* every derived feature is a level or a trailing transformation, never a centred or forward
  one. A rolling mean that peeks one period ahead is invisible in a chart and worth a
  surprising amount of Sharpe.

Import it from a notebook in this folder after putting the repo root and the vendored library
on the path::

    import sys; sys.path.insert(0, ".."); sys.path.insert(0, "fxcarry/src")
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

from strategy import fx_utils as fx

REPO_ROOT = Path(__file__).resolve().parents[1]
OUTPUTS = Path(__file__).resolve().parent / "outputs"

#: Episodes worth reading separately. Chosen from the FX record rather than from this book's
#: own drawdowns, which would be picking the sub-periods after seeing the answer.
EPISODES: dict[str, tuple[str, str]] = {
    "pre-crisis 2007-08": ("2007-05-01", "2008-08-31"),
    "GFC 2008-09": ("2008-09-01", "2009-06-30"),
    "recovery 2009-11": ("2009-07-01", "2011-06-30"),
    "euro crisis 2011-12": ("2011-07-01", "2012-12-31"),
    "taper + EM 2013-16": ("2013-01-01", "2016-12-31"),
    "calm 2017-19": ("2017-01-01", "2019-12-31"),
    "covid 2020": ("2020-01-01", "2020-12-31"),
    "tightening 2021-23": ("2021-01-01", "2023-12-31"),
    "recent 2024-26": ("2024-01-01", "2026-06-30"),
}


def month_end(frame: pd.Series | pd.DataFrame) -> pd.Series | pd.DataFrame:
    """The last observation of each month, which is what was on the screen at the close."""
    return frame.resample("ME").last()


def risk_series(name: str, group: str = "global_risk") -> pd.Series:
    """One column of a shared wide panel, at month end."""
    return month_end(fx.load_wide(group)[name]).rename(name)


def fx_volatility() -> pd.Series:
    """JPMorgan global FX implied volatility, the risk gauge closest to what a carry book owns.

    VIX is the reflex choice and it is highly correlated with this, but a carry book is short
    FX volatility rather than short equity volatility, and in 2013 and 2018 the two disagreed
    about which was happening.
    """
    return risk_series("JPMVXYGL").rename("fx_vol")


def book_volatility(monthly_returns: pd.Series, window: int = 3) -> pd.Series:
    """Trailing annualised volatility of the book itself, from its own monthly returns."""
    return monthly_returns.rolling(window).std() * np.sqrt(12.0)


def carry_dispersion(signal: pd.DataFrame) -> pd.Series:
    """Month-end cross-sectional spread of the carry signal — how much there is to sort on.

    A carry book earns nothing when every currency yields the same, so the dispersion of the
    signal is a conditioning variable in its own right, and one that has nothing to do with
    volatility.
    """
    return month_end(signal.std(axis=1)).rename("carry_dispersion")


def build_features(monthly_returns: pd.Series, signal: pd.DataFrame) -> pd.DataFrame:
    """Month-end conditioning variables for the supervised model.

    Eleven series in four groups: the level of risk (three implied volatility measures), the
    change in risk, the price of money and credit (the curve slope and a financial conditions
    index), and what the book itself has been doing lately. Levels and changes are both here
    because a regime is as much about direction as height — volatility at 20 and falling is
    not the state volatility at 20 and rising is.

    Args:
        monthly_returns: The book's own month-end returns, for the trailing-volatility feature.
        signal: The daily carry panel the book sorts on, for the dispersion feature.
    """
    risk = fx.load_wide("global_risk")
    macro = fx.load_wide("macro_market_proxies")

    vix = month_end(risk["VIX"])
    fxvol = month_end(risk["JPMVXYGL"])
    move = month_end(risk["MOVE"])
    spx = month_end(risk["SPX"])
    dxy = month_end(risk["DXY"])

    features = pd.DataFrame(
        {
            "log_vix": np.log(vix),
            "log_fx_vol": np.log(fxvol),
            "log_move": np.log(move),
            "d_log_vix": np.log(vix).diff(),
            "d_log_fx_vol": np.log(fxvol).diff(),
            "d_log_move": np.log(move).diff(),
            "slope_2s10s": month_end(risk["USYC2Y10"]),
            "financial_conditions": month_end(macro["BFCIUS"]),
            "spx_3m": spx.pct_change(3),
            "dxy_3m": dxy.pct_change(3),
            "book_vol_3m": book_volatility(monthly_returns),
        }
    )
    features["carry_dispersion"] = carry_dispersion(signal)
    return features.dropna()


def loss_labels(monthly_returns: pd.Series) -> pd.Series:
    """One where the *following* month lost money, dated by the month that had to predict it.

    Dating is the whole game. The label sitting at ``t`` describes ``t+1``, so it does not
    resolve until the end of ``t+1``; `fxcarry.regimes.LogisticRegime` knows this and only
    ever trains on labels that had already landed. Handing it a label dated at the month it
    describes would quietly let every fold see its own answer.
    """
    return (monthly_returns.shift(-1) < 0).astype(float).rename("loss_next_month")


def vix_percentile_gate(low_mult: float = 0.5) -> pd.Series:
    """The project's incumbent gate: half risk when VIX is in the top fifth of three years.

    Carried along as the bar to clear. A new model that cannot beat the rule already in the
    repository has not earned the parameters it costs.
    """
    return fx.exposure_scalar(
        fx.load_wide("global_risk")["VIX"], lookback=756, q=0.80, low_mult=low_mult
    )


def variant_table(results: dict, benchmark: str | None = None) -> pd.DataFrame:
    """Headline numbers for a set of runs, gross and net side by side.

    Args:
        results: Label to `StrategyResult`.
        benchmark: Passed through to `StrategyResult.summary`.
    """
    rows = {}
    for label, result in results.items():
        summary = result.summary(benchmark=benchmark)
        gross = summary.loc[[i for i in summary.index if i.endswith("_gross")][0]]
        net = summary.loc[[i for i in summary.index if i.endswith("_net")][0]]
        rows[label] = {
            "gross_sharpe": gross["sharpe"],
            "net_sharpe": net["sharpe"],
            "ann_return": net["ann_return"],
            "ann_vol": net["ann_vol"],
            "max_dd": net["max_drawdown"],
            "calmar": net["calmar"],
            "skew": net["skew"],
            "cvar_95": net["CVaR_95"],
            "turnover": result.turnover,
            "cost_drag": result.cost_drag,
        }
    return pd.DataFrame(rows).T.astype(float)


def average_exposure(result) -> float:
    """Mean gross notional held, relative to the ungated book.

    Reads how much of the sample a gate spent out of the market, which is the number that
    explains most of the difference in a headline return before any timing skill is involved.
    """
    return float(result.weights.abs().sum(axis=1).mean())
