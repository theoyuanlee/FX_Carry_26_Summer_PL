"""Putting several books side by side without re-running any of them.

A comparison is only worth reading if every book in it covers the same days, so the first
thing :class:`Comparison` does is intersect the calendars. After that it is a thin layer over
:class:`~fxcarry.stats.Performance`: a table, a set of wealth curves, drawdowns, and the
statistics that only make sense relative to a chosen baseline.

The part that matters in practice is :meth:`Comparison.save`. A backtest that has to be
re-run before its numbers can be plotted next to yours is a backtest you will stop plotting.
Writing the aligned return series to one file means a book estimated elsewhere — in another
package, another notebook, on another machine — travels as data, and the comparison survives
long after whatever produced it has moved on.

Two comparisons deserve care. A gate that spends part of the sample out of the market has a
lower volatility than the book it gates, so its return is lower even when its timing was
perfect; :meth:`Comparison.rescaled` divides that out by putting every series on the
baseline's realised volatility. That is not an implementable portfolio — the scaling is only
known afterwards — but it separates "held less risk" from "held it at the right times", which
is the only question a gate is really being asked.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from fxcarry import reference
from fxcarry.stats import HAC, Performance


class Comparison:
    """Return series from several books, aligned to a common window and scored together.

    Attributes:
        returns: One column per book, over the days all of them share.
        periods_per_year: Observations that make a year, for annualising.
        baseline: Column the relative statistics are measured against.
    """

    def __init__(
        self,
        returns: pd.DataFrame | dict[str, pd.Series],
        periods_per_year: float = reference.PERIODS_PER_YEAR["D"],
        baseline: str | None = None,
    ):
        frame = pd.DataFrame(returns) if not isinstance(returns, pd.DataFrame) else returns.copy()
        if frame.empty or frame.shape[1] == 0:
            raise ValueError("a comparison needs at least one return series.")
        frame = frame.sort_index().dropna(how="all")
        # Intersect rather than union: a book that starts late would otherwise be credited
        # with flat days it never traded, which flatters exactly the books that need scrutiny.
        common = frame.notna().all(axis=1)
        if not common.any():
            raise ValueError("the series share no dates once aligned.")
        first, last = common.idxmax(), common[::-1].idxmax()
        self.returns = frame.loc[first:last]
        self.periods_per_year = periods_per_year
        if baseline is None:
            baseline = str(frame.columns[0])
        if baseline not in self.returns.columns:
            raise ValueError(f"baseline {baseline!r} is not one of {list(self.returns.columns)}.")
        self.baseline = baseline

    # -- construction --------------------------------------------------------

    @classmethod
    def load(cls, path, **kwargs) -> "Comparison":
        """Read a saved comparison back, so the books need not exist any more."""
        return cls(pd.read_parquet(path), **kwargs)

    def save(self, path) -> None:
        """Write the aligned return series to parquet.

        This is what makes a book portable. Everything below is derived from these columns, so
        the file is the comparison.
        """
        self.returns.to_parquet(path)

    def with_series(self, **series: pd.Series) -> "Comparison":
        """The same comparison plus more books, realigned."""
        merged = pd.concat([self.returns, pd.DataFrame(series)], axis=1)
        return Comparison(merged, self.periods_per_year, self.baseline)

    # -- levels --------------------------------------------------------------

    def nav(self) -> pd.DataFrame:
        """Compounded value of one unit in each book."""
        return (1.0 + self.returns.fillna(0.0)).cumprod()

    def drawdown(self) -> pd.DataFrame:
        """Shortfall from each book's own running peak."""
        nav = self.nav()
        return nav / nav.cummax() - 1.0

    def rescaled(self) -> pd.DataFrame:
        """Every book levered onto the baseline's realised volatility.

        Not implementable, and not meant to be: the scaling factor is a full-sample number. It
        answers the narrower question of whether a book earned more per unit of risk actually
        taken, with the size of the position divided out.
        """
        vol = self.returns.std()
        target = float(vol[self.baseline])
        return self.returns.mul(target / vol.replace(0.0, np.nan), axis=1)

    # -- statistics ----------------------------------------------------------

    def table(self, hac: HAC | None = None) -> pd.DataFrame:
        """One row per book: the usual performance statistics, on the common window."""
        return Performance(self.returns, self.periods_per_year).summary(hac=hac)

    def relative(self, hac: HAC | None = None) -> pd.DataFrame:
        """Each book against the baseline: what it added, and whether that is distinguishable.

        The active return is the difference of the two series, so its Sharpe ratio is an
        information ratio and its ``t`` statistic asks the only question worth asking of an
        overlay — whether the sample can tell it apart from doing nothing.
        """
        hac = HAC() if hac is None else hac
        base = self.returns[self.baseline]
        root = np.sqrt(self.periods_per_year)
        rows: dict[str, dict[str, float]] = {}
        for name in self.returns.columns:
            book, active = self.returns[name], self.returns[name] - base
            stats = Performance(book, self.periods_per_year)
            row = {
                "sharpe": stats.sharpe,
                "sharpe_delta": stats.sharpe - Performance(base, self.periods_per_year).sharpe,
                "ann_return": stats.mean,
                "ann_vol": stats.volatility,
                "max_drawdown": stats.max_drawdown,
                "skew": stats.skew,
                "active_return": active.mean() * self.periods_per_year,
                "tracking_error": active.std() * root,
                # Both moments at the same degrees of freedom, or the baseline's beta to
                # itself comes out slightly off one and every other beta inherits the bias.
                "beta_to_baseline": float(np.cov(book, base, ddof=1)[0, 1] / np.var(base, ddof=1)),
                "corr_to_baseline": float(book.corr(base)),
            }
            row["info_ratio"] = (
                row["active_return"] / row["tracking_error"] if row["tracking_error"] > 0 else np.nan
            )
            row["active_t"] = hac.t_stat(active) if active.abs().sum() > 0 else np.nan
            rows[name] = row
        return pd.DataFrame(rows).T

    def subperiods(self, windows: dict[str, tuple[str, str]], field: str = "sharpe") -> pd.DataFrame:
        """One statistic per book per window, for reading stability rather than the headline.

        Args:
            windows: Label to ``(start, end)``, both inclusive.
            field: Any column of :meth:`table`.
        """
        rows = {}
        for label, (start, end) in windows.items():
            slice_ = self.returns.loc[start:end]
            if slice_.empty:
                continue
            rows[label] = Performance(slice_, self.periods_per_year).summary()[field]
        return pd.DataFrame(rows).T

    # -- pictures ------------------------------------------------------------

    def plot_nav(self, ax=None, log: bool = True, **kwargs):
        """Wealth curves. Log scale by default, so equal slopes mean equal growth."""
        ax = self._axis(ax)
        self.nav().plot(ax=ax, **kwargs)
        if log:
            ax.set_yscale("log")
        ax.set_ylabel("growth of 1")
        ax.axhline(1.0, color="0.6", lw=0.8, zorder=0)
        return ax

    def plot_drawdown(self, ax=None, **kwargs):
        """Drawdown paths, where a gate either earns its keep or does not."""
        ax = self._axis(ax)
        self.drawdown().plot(ax=ax, **kwargs)
        ax.set_ylabel("drawdown")
        ax.axhline(0.0, color="0.6", lw=0.8, zorder=0)
        return ax

    @staticmethod
    def _axis(ax):
        if ax is not None:
            return ax
        import matplotlib.pyplot as plt

        return plt.subplots(figsize=(10, 4))[1]
