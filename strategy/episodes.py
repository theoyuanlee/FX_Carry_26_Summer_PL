"""Frozen evaluation windows, and the per-window reports built on them.

The desk's standing requirement since 2026-07-29 (plan §6.8, §19.2): a result is
reported **per stress window**, and whole-sample statistics are supporting
evidence only. The reason is the strategy's known failure mode — returns compound
from carry accrual and spot appreciation, so one large loss breaks the
compounding path, and minimising large losses is worth more than adding
incremental gains. A rule that lifts the full-sample Sharpe while making the
crisis eras worse is a rule this book does not want, and only a per-window table
shows that.

Two dicts, and the distinction between them is the whole point:

* `ERAS` **partitions** the sample, so per-era shares of P&L sum to 100%. That is
  what makes "this era produced X% of the book's return" an honest statement
  rather than a cherry-pick, and it is the answer to "you picked your windows".
* `STRESS` is a set of tight, tail-focused event windows. They may overlap and
  sit inside eras, because they answer the different question: *did the book
  preserve capital*. Shares of P&L are not meaningful across them.

Both are **frozen**. Adding a window later is allowed; silently changing one is
not, because every cross-workstream comparison depends on everybody using the
same windows. `tests/test_episodes.py::test_windows_are_frozen` asserts the exact
keys and dates — that lock is what stops anyone re-picking a window after seeing
a result.

This module implements **no new statistics**. Everything is
`StrategyResult.reslice()` plus `fx_utils.summary_stats`, and the one derived
quantity (`cum_return`) is recovered from `summary_stats`'s own `cagr`.

    from strategy import run
    from strategy.episodes import ERAS, STRESS, report_windows, leg_decomposition

    res = run()
    print(report_windows(res, STRESS, which="both"))
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from . import fx_utils as fx

__all__ = ["ERAS", "STRESS", "SHORT_WINDOW_DAYS", "report_windows",
           "compare_windows", "leg_decomposition"]


#: Contiguous partition of the sample, 2007-05-01 -> 2026-06-30.
#:
#: Copied **verbatim** (keys and dates) from `dafu/regime_lab.py:36`, where the
#: same constant is named `EPISODES`. Verbatim on purpose: it keeps Dafu's
#: committed `dafu/outputs/episodes_sharpe.csv` valid and makes his port a
#: one-line `from strategy.episodes import ERAS as EPISODES`. The windows were
#: chosen from the FX record rather than from this book's own drawdowns, which
#: would be picking the sub-periods after seeing the answer.
ERAS: dict[str, tuple[str, str]] = {
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

#: Tight, tail-focused event windows. Overlapping and nesting inside `ERAS` is
#: allowed and expected — these ask whether the book preserved capital, not how
#: the sample decomposes.
#:
#: Two of these exist because the aggregate hid them. The 2013 taper tantrum is
#: the second-worst window in the sample and is invisible in every episode list
#: the repo had before this module: it is buried inside the "taper + EM 2013-16"
#: era, which shows a *positive* number. The two 2026 shocks were named by the
#: desk on 2026-07-22 and sat inside a "recent" bucket. `rates_2022` is the
#: control — carry's *best* crisis — so the table cannot be read as a list of
#: disasters chosen to flatter a hedge.
STRESS: dict[str, tuple[str, str]] = {
    "gfc_2008": ("2008-09-01", "2009-06-30"),        # Lehman
    "euro_2011": ("2011-07-01", "2012-12-31"),       # EZ sovereign
    "taper_2013": ("2013-05-01", "2013-09-30"),      # taper tantrum
    "china_em_2015": ("2015-06-01", "2016-02-29"),   # CNY devaluation
    "covid_2020": ("2020-02-01", "2020-04-30"),      # worst window in the sample
    "rates_2022": ("2022-01-01", "2022-10-31"),      # control: carry's best crisis
    "oil_2026": ("2026-02-01", "2026-05-31"),        # desk-nominated, Jul 22
    "semis_2026": ("2026-04-01", "2026-06-30"),      # desk-nominated, Jul 22
}

#: Below this many trading days, annualised ratios are suppressed (plan §6.8).
#: Annualising a Sharpe off 64 days of COVID is noise wearing a decimal point.
#: Four of the eight `STRESS` windows are under this bar, including both windows
#: the desk named personally — which is why this module exists.
SHORT_WINDOW_DAYS = 120

#: Columns blanked on windows shorter than `SHORT_WINDOW_DAYS`.
_ANNUALISED = ("ann_return", "ann_vol", "sharpe")

_COLUMNS = ["window", "basis", "start", "end", "n_days", "cum_return",
            "ann_return", "ann_vol", "sharpe", "max_drawdown", "worst_day",
            "hit_rate", "cost_drag", "share_pnl"]


def _bases(which: str) -> tuple[str, ...]:
    if which == "both":
        return ("gross", "net")
    if which in ("gross", "net"):
        return (which,)
    raise ValueError(f"which must be 'gross', 'net' or 'both', got {which!r}")


def report_windows(result, windows: dict[str, tuple[str, str]] = ERAS,
                   which: str = "net", min_obs: int = 20) -> pd.DataFrame:
    """One row per window: what the book did inside it.

    Columns: window, basis, start, end, n_days, cum_return, ann_return, ann_vol,
    sharpe, max_drawdown, worst_day, hit_rate, cost_drag, share_pnl.

    `sharpe` and the `ann_*` columns are **NaN when n_days < SHORT_WINDOW_DAYS**,
    per plan guardrail §6.8 — so nobody quotes an annualised Sharpe off 64 days
    of COVID. `cum_return`, `max_drawdown`, `worst_day` and `n_days` are the
    metrics a short window may quote, and they are always populated.
    `cost_drag` is annualised but kept, because a mean cost rate is stable at
    short horizons in a way a risk-adjusted ratio is not.

    `min_obs` is passed to `StrategyResult.summary`, which passes it to
    `fx_utils.summary_stats`. It defaults to 20 rather than the engine's 120
    because these windows are deliberately short; the *suppression* of
    annualised figures is handled separately and does not move with it.

    `share_pnl` is the window's arithmetic sum of daily returns over the whole
    book's, so on `ERAS` the column sums to exactly 1.0 (it partitions the
    sample). On `STRESS` the windows overlap, so the column is informative but
    does not sum to anything in particular.

    `which="both"` emits a gross and a net row per window, which is what plan
    §6.3 asks every table for.
    """
    bases = _bases(which)
    label = result.config.label()
    totals = {b: float(getattr(result, b).dropna().sum()) for b in bases}
    rows = []
    for name, (start, end) in windows.items():
        sub = result.reslice(start, end)
        stats = sub.summary(benchmark=None, min_obs=min_obs)
        for basis in bases:
            series = getattr(sub, basis).dropna()
            row: dict[str, object] = {c: np.nan for c in _COLUMNS}
            row.update(window=name, basis=basis, n_days=len(series),
                       start=pd.Timestamp(start).date(), end=pd.Timestamp(end).date())
            key = f"{label}_{basis}"
            if key in stats.index:
                s = stats.loc[key]
                n = int(s["n_days"])
                # cum_return is recovered from summary_stats' own cagr rather
                # than recomputed, so this module implements no new statistic:
                # cagr = P**(252/n) - 1  =>  P = (1 + cagr)**(n/252).
                row.update(
                    cum_return=(1.0 + float(s["cagr"])) ** (n / fx.ANN_DAYS) - 1.0,
                    ann_return=float(s["ann_return"]), ann_vol=float(s["ann_vol"]),
                    sharpe=float(s["sharpe"]), max_drawdown=float(s["max_drawdown"]),
                    worst_day=float(s["worst_day"]), hit_rate=float(s["hit_rate"]))
                if n < SHORT_WINDOW_DAYS:
                    row.update({c: np.nan for c in _ANNUALISED})
            if len(series):
                row["cost_drag"] = float(sub.cost_drag)
                if totals[basis]:
                    row["share_pnl"] = float(series.sum()) / totals[basis]
            rows.append(row)
    return pd.DataFrame(rows, columns=_COLUMNS)


def compare_windows(results: dict[str, "object"],
                    windows: dict[str, tuple[str, str]] = ERAS,
                    metric: str = "max_drawdown", which: str = "net",
                    min_obs: int = 20) -> pd.DataFrame:
    """Windows x variants for one metric — the table that goes in the deck.

    `results` maps a variant name to a `StrategyResult`. The default metric is
    `max_drawdown` rather than `sharpe` on purpose: under the objective the desk
    stated on 2026-07-29 the drawdown column is the one that decides.
    """
    cols = {}
    for name, res in results.items():
        rep = report_windows(res, windows=windows, which=which, min_obs=min_obs)
        if metric not in rep.columns:
            raise ValueError(f"metric must be one of {_COLUMNS}, got {metric!r}")
        cols[name] = rep.set_index("window")[metric]
    return pd.DataFrame(cols).reindex(list(windows))


def leg_decomposition(result, freq: str | None = "ME") -> pd.DataFrame:
    """Long-leg vs short-leg x carry vs spot contribution, per period.

    The Jul 15 desk ask — "decompose the rate differential month-by-month,
    split short leg vs long leg" — and the answer to "where does the risk sit
    and where do the gains come from".

    Derived from the two identities the base already tests exactly, not from a
    reconstruction: `xret == spot_component + carry_component` and
    `contrib.sum(axis=1) == gross`. Splitting the weights with `clip` is what
    makes it exact — `w.clip(lower=0)` returns either the original float or
    exactly `0.0`, so every product is either `w*x` or a true zero and the four
    legs re-sum to `gross` up to summation order. The `resid` column carries the
    proof; `tests/test_episodes.py` requires it under 1e-12.

    The one subtlety, and it is worth 8e-3 a day if you miss it: the components
    must be masked to where `xret` itself is present. A name can have a spot
    return on a day its carry is missing, and on such a day `xret` is NaN, so
    `portfolio_returns` drops the name from `gross` entirely — while an unmasked
    spot leg would happily keep counting it. The book's decomposition has to
    recognise exactly the observations the book's P&L recognises.

    `freq=None` returns the daily frame; otherwise any pandas resample alias
    (`"ME"`, `"QE"`, `"YE"`). Note plan guardrail §6.10: only right-labelled
    aliases are safe here.
    """
    cols = result.weights.columns.intersection(result.panels.xret.columns)
    lo, hi = result.window
    w = result.weights[cols].loc[lo:hi]
    live = result.panels.xret[cols].loc[lo:hi].notna()
    carry = result.panels.carry_component[cols].loc[lo:hi].where(live)
    spot = result.panels.spot_component[cols].loc[lo:hi].where(live)

    w_long, w_short = w.clip(lower=0), w.clip(upper=0)
    daily = pd.DataFrame({
        "carry_long": (w_long * carry).sum(axis=1, min_count=1),
        "carry_short": (w_short * carry).sum(axis=1, min_count=1),
        "spot_long": (w_long * spot).sum(axis=1, min_count=1),
        "spot_short": (w_short * spot).sum(axis=1, min_count=1),
    })
    daily["total"] = daily.sum(axis=1, min_count=1)
    daily["gross"] = result.gross.reindex(daily.index)
    daily["resid"] = daily["total"] - daily["gross"]
    daily = daily.loc[daily["gross"].notna()]
    if freq is None:
        return daily
    out = daily.resample(freq).sum(min_count=1)
    out.index.name = "period"
    return out
