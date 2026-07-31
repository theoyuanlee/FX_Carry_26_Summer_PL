"""Estimating things from return series.

:class:`Performance` describes a series. :class:`HAC` carries a lag choice and produces
autocorrelation-robust standard errors. :class:`Realized` turns daily observations into
period-frequency volatility. :class:`FactorModel` and :class:`LinearSDF` are the two
estimators that ask whether a set of factors explains a set of returns.
:class:`RollingOLS` and :class:`Shrinkage` are domain-free tools.

Nothing here knows what a currency is.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd
import statsmodels.api as sm
from scipy import stats

from fxcarry import reference


def _as_frame(x: pd.Series | pd.DataFrame, default_name: str) -> pd.DataFrame:
    """A one-column frame from a series, or the frame unchanged."""
    if isinstance(x, pd.Series):
        return x.to_frame(name=x.name or default_name)
    return x


class HAC:
    """Heteroskedasticity and autocorrelation consistent covariance, at a fixed lag.

    Holding the lag as state means it travels as one object rather than as an integer repeated
    at every call site.

    Attributes:
        lags: Number of Newey-West lags. Zero gives the plain sample covariance.
    """

    def __init__(self, lags: int | None = None):
        self.lags = reference.DEFAULT_NW_LAGS if lags is None else lags

    def covariance(self, moments) -> np.ndarray:
        """Long-run covariance of a ``T`` by ``k`` array of moment series.

        Columns are demeaned first, so raw realizations can be passed in. Lag ``j`` enters with
        the Bartlett weight ``1 - j/(lags+1)``, which is what keeps the estimate positive
        semi-definite.
        """
        arr = np.asarray(moments, dtype=float)
        if arr.ndim == 1:
            arr = arr[:, None]
        n = arr.shape[0]
        arr = arr - arr.mean(axis=0)
        cov = arr.T @ arr / n
        for lag in range(1, self.lags + 1):
            weight = 1.0 - lag / (self.lags + 1.0)
            gamma = arr[lag:].T @ arr[:-lag] / n
            cov = cov + weight * (gamma + gamma.T)
        return cov

    def mean_se(self, series: pd.Series) -> float:
        """Standard error of the sample mean, robust to serial correlation."""
        clean = pd.Series(series).dropna()
        model = sm.OLS(clean.to_numpy(float), np.ones((len(clean), 1)))
        return float(model.fit(cov_type="HAC", cov_kwds={"maxlags": self.lags}).bse[0])

    def t_stat(self, series: pd.Series) -> float:
        """Sample mean over its own robust standard error."""
        clean = pd.Series(series).dropna()
        return float(clean.mean() / self.mean_se(clean))

    def moment_ses(self, series: pd.Series) -> pd.Series:
        """Standard errors for the mean, standard deviation, Sharpe, skew and excess kurtosis.

        These are the figures conventionally printed beneath a moments table. They come from
        stacking the estimating equations for the first four central moments, taking their
        long-run covariance, and applying the delta method. Per-period, so annualize them the
        same way as the point estimates they sit under.
        """
        x = pd.Series(series).dropna().to_numpy(float)
        n = x.size
        mu = x.mean()
        dev = x - mu
        m2, m3, m4 = (float(np.mean(dev**p)) for p in (2, 3, 4))

        g = np.column_stack([dev, dev**2 - m2, dev**3 - m3, dev**4 - m4])
        s_mat = self.covariance(g)
        jac = np.array(
            [
                [-1.0, 0.0, 0.0, 0.0],
                [0.0, -1.0, 0.0, 0.0],
                [-3.0 * m2, 0.0, -1.0, 0.0],
                [-4.0 * m3, 0.0, 0.0, -1.0],
            ]
        )
        jac_inv = np.linalg.inv(jac)
        var = jac_inv @ s_mat @ jac_inv.T / n

        sd = np.sqrt(m2)
        gradients = {
            "mean": np.array([1.0, 0.0, 0.0, 0.0]),
            "volatility": np.array([0.0, 0.5 / sd, 0.0, 0.0]),
            "sharpe": np.array([1.0 / sd, -0.5 * mu * m2**-1.5, 0.0, 0.0]),
            "skew": np.array([0.0, -1.5 * m3 * m2**-2.5, m2**-1.5, 0.0]),
            "excess_kurtosis": np.array([0.0, -2.0 * m4 * m2**-3.0, 0.0, m2**-2.0]),
        }
        return pd.Series(
            {name: float(np.sqrt(grad @ var @ grad)) for name, grad in gradients.items()}
        )


class Performance:
    """What a return series did.

    Rates are annualized with ``periods_per_year``; shape statistics are left per-period
    because they do not scale.

    Attributes:
        returns: One series, or a frame of them.
        periods_per_year: Observations that make a year.
    """

    def __init__(
        self,
        returns: pd.Series | pd.DataFrame,
        periods_per_year: float = reference.DEFAULT_ANNUALIZATION,
    ):
        self.returns = returns
        self.periods_per_year = periods_per_year

    @property
    def _clean(self):
        return self.returns.dropna()

    @property
    def mean(self):
        """Annualized mean return."""
        return self._clean.mean() * self.periods_per_year

    @property
    def volatility(self):
        """Annualized standard deviation."""
        return self._clean.std() * np.sqrt(self.periods_per_year)

    @property
    def sharpe(self):
        """Annualized mean over annualized standard deviation."""
        return self.mean / self.volatility

    @property
    def skew(self):
        """Sample skewness, per period."""
        return self._clean.skew()

    @property
    def kurtosis(self):
        """Excess kurtosis, per period, so a normal sample sits at zero."""
        return self._clean.kurt()

    @property
    def win_rate(self):
        """Share of periods with a strictly positive return."""
        return (self._clean > 0).mean()

    @property
    def worst(self):
        """Worst single period."""
        return self._clean.min()

    def cvar(self, level: float = 0.05):
        """Mean of the worst ``level`` share of periods.

        Averages the tail rather than reading its edge, so one very bad period is visible where
        a quantile would hide it.
        """
        clean = self._clean
        if isinstance(clean, pd.DataFrame):
            return clean.apply(lambda col: Performance(col, self.periods_per_year).cvar(level))
        cutoff = max(1, int(np.floor(level * len(clean))))
        return clean.nsmallest(cutoff).mean()

    def nav(self):
        """Compounded value of one unit invested, missing periods treated as flat."""
        return (1.0 + self.returns.fillna(0.0)).cumprod()

    def drawdown(self):
        """Shortfall from the running peak, at every point."""
        nav = self.nav()
        return nav / nav.cummax() - 1.0

    @property
    def max_drawdown(self):
        """Deepest shortfall from a running peak."""
        return self.drawdown().min()

    def summary(self, hac: HAC | None = None, with_se: bool = False) -> pd.DataFrame:
        """One row per series, with the usual statistics and optionally their standard errors.

        Args:
            hac: Lag choice for the standard errors; a default HAC when None.
            with_se: Also report standard errors for every moment, not just the mean.
        """
        hac = HAC() if hac is None else hac
        frame = _as_frame(self.returns, "return")
        rows: dict[str, dict[str, float]] = {}
        for col in frame.columns:
            one = Performance(frame[col].dropna(), self.periods_per_year)
            row = {
                "mean": one.mean,
                "volatility": one.volatility,
                "sharpe": one.sharpe,
                "skew": one.skew,
                "kurtosis": one.kurtosis,
                "win_rate": one.win_rate,
                "worst": one.worst,
                "max_drawdown": one.max_drawdown,
                "mean_se": hac.mean_se(one.returns) * self.periods_per_year,
                "n_obs": len(one.returns),
            }
            if with_se:
                se = hac.moment_ses(one.returns)
                root = np.sqrt(self.periods_per_year)
                row |= {
                    "volatility_se": se["volatility"] * root,
                    "sharpe_se": se["sharpe"] * root,
                    "skew_se": se["skew"],
                    "kurtosis_se": se["excess_kurtosis"],
                }
            rows[col] = row
        return pd.DataFrame(rows).T


class Realized:
    """Period-frequency volatility estimated from higher-frequency observations.

    Attributes:
        periods_per_year: Observations that make a year, for annualizing.
    """

    def __init__(self, periods_per_year: float = reference.DEFAULT_ANNUALIZATION):
        self.periods_per_year = periods_per_year

    def volatility(self, observations: pd.DataFrame, freq: str = "M") -> pd.DataFrame:
        """Standard deviation within each period, one column per input column."""
        alias = reference.RESAMPLE_ALIAS.get(freq, freq)
        return observations.resample(alias).std()

    def factor(self, observations: pd.DataFrame, freq: str = "M") -> pd.Series:
        """Cross-sectional average of the per-column realized volatility, one number a period."""
        return self.volatility(observations, freq).mean(axis=1)


class FactorModel:
    """Time-series regression of test assets on factors.

    Estimates ``z_it = a_i + f_t' b_i + e_it`` one asset at a time and reports the intercept,
    the loadings, their robust standard errors and the fit.

    Attributes:
        assets: Test-asset returns, one column each.
        factors: Factor returns, one column each.
        hac: Lag choice for the standard errors.
    """

    def __init__(
        self,
        assets: pd.Series | pd.DataFrame,
        factors: pd.Series | pd.DataFrame,
        hac: HAC | None = None,
    ):
        self.assets = _as_frame(assets, "asset")
        self.factors = _as_frame(factors, "factor")
        self.hac = HAC() if hac is None else hac

    def fit(self) -> pd.DataFrame:
        """One row per asset: an intercept and its standard error, a loading and standard error
        for each factor, and the regression fit."""
        rows: dict[str, dict[str, float]] = {}
        for name in self.assets.columns:
            joined = pd.concat(
                [self.assets[name].rename("_y"), self.factors], axis=1
            ).dropna()
            y = joined["_y"].to_numpy(float)
            x = sm.add_constant(joined[self.factors.columns].to_numpy(float))
            res = sm.OLS(y, x).fit(cov_type="HAC", cov_kwds={"maxlags": self.hac.lags})

            row = {"alpha": float(res.params[0]), "alpha_se": float(res.bse[0])}
            for j, factor in enumerate(self.factors.columns, start=1):
                row[f"{factor}_beta"] = float(res.params[j])
                row[f"{factor}_se"] = float(res.bse[j])
            row["r2"] = float(res.rsquared)
            rows[name] = row
        return pd.DataFrame(rows).T


@dataclass(frozen=True)
class SDFResult:
    """An estimated linear discount factor and how well it prices its test assets."""

    b: pd.Series
    b_se: pd.Series
    risk_premia: pd.Series
    risk_premia_se: pd.Series
    predicted: pd.Series
    realized: pd.Series
    pricing_errors: pd.Series
    r2: float
    j_stat: float
    j_pvalue: float
    n_assets: int
    n_factors: int


class LinearSDF:
    """Linear stochastic discount factor estimated by the generalized method of moments.

    The discount factor is ``m = 1 - (f - mu)' b`` and the moment condition is that every test
    asset prices to zero, ``E[z m] = 0``. Setting ``mu`` to the sample factor mean concentrates
    the moments to ``z_bar - D b`` with ``D`` the covariance of returns with factors, so the
    estimator is ``b = (D'WD)^-1 D'W z_bar``.

    The first stage weights with the identity, which is the same thing as regressing mean
    returns on ``D`` across assets. Iterating updates the weight to the inverse long-run
    covariance of the moments and re-solves until it settles.

    Attributes:
        assets: Test-asset returns.
        factors: Factor returns.
        hac: Lag choice for the weighting matrix and standard errors.
        iterate: Whether to iterate to the efficient weight.
    """

    def __init__(
        self,
        assets: pd.DataFrame,
        factors: pd.Series | pd.DataFrame,
        hac: HAC | None = None,
        iterate: bool = True,
        max_iter: int = 50,
        tol: float = 1e-12,
    ):
        self.assets = _as_frame(assets, "asset")
        self.factors = _as_frame(factors, "factor")
        self.hac = HAC() if hac is None else hac
        self.iterate = iterate
        self.max_iter = max_iter
        self.tol = tol

    def fit(self) -> SDFResult:
        """Estimate the loadings and report how well they price the cross-section."""
        joined = pd.concat([self.assets, self.factors], axis=1).dropna()
        z = joined[self.assets.columns].to_numpy(float)
        f = joined[self.factors.columns].to_numpy(float)
        n_periods, n = z.shape
        k = f.shape[1]

        f_dm = f - f.mean(axis=0)
        z_bar = z.mean(axis=0)
        d_mat = (z.T @ f_dm) / n_periods
        sigma_f = (f_dm.T @ f_dm) / n_periods

        def moments(b_vec: np.ndarray) -> np.ndarray:
            return z * (1.0 - (f_dm @ b_vec))[:, None]

        w_mat = np.eye(n)
        b = np.linalg.solve(d_mat.T @ w_mat @ d_mat, d_mat.T @ w_mat @ z_bar)
        if self.iterate:
            for _ in range(self.max_iter):
                w_mat = np.linalg.pinv(self.hac.covariance(moments(b)))
                b_new = np.linalg.solve(d_mat.T @ w_mat @ d_mat, d_mat.T @ w_mat @ z_bar)
                settled = np.max(np.abs(b_new - b)) < self.tol
                b = b_new
                if settled:
                    break

        s_mat = self.hac.covariance(moments(b))
        predicted = d_mat @ b
        errors = z_bar - predicted

        ss_res = float(np.sum(errors**2))
        ss_tot = float(np.sum((z_bar - z_bar.mean()) ** 2))
        r2 = 1.0 - ss_res / ss_tot if ss_tot > 0 else float("nan")

        # Sandwich covariance. With the iterated weight this collapses to (D'S^-1 D)^-1 / T.
        dtw = d_mat.T @ w_mat
        bread = np.linalg.inv(dtw @ d_mat)
        var_b = bread @ (dtw @ s_mat @ w_mat @ d_mat) @ bread / n_periods
        premia = sigma_f @ b
        var_premia = sigma_f @ var_b @ sigma_f.T

        dof = n - k
        if self.iterate:
            j_stat = float(n_periods * errors @ np.linalg.pinv(s_mat) @ errors)
        else:
            proj = np.eye(n) - d_mat @ bread @ dtw
            j_stat = float(n_periods * errors @ np.linalg.pinv(proj @ s_mat @ proj.T) @ errors)

        names = list(self.factors.columns)
        assets = list(self.assets.columns)
        return SDFResult(
            b=pd.Series(b, index=names, name="b"),
            b_se=pd.Series(np.sqrt(np.diag(var_b)), index=names, name="b_se"),
            risk_premia=pd.Series(premia, index=names, name="risk_premium"),
            risk_premia_se=pd.Series(np.sqrt(np.diag(var_premia)), index=names, name="se"),
            predicted=pd.Series(predicted, index=assets, name="predicted"),
            realized=pd.Series(z_bar, index=assets, name="realized"),
            pricing_errors=pd.Series(errors, index=assets, name="pricing_error"),
            r2=r2,
            j_stat=j_stat,
            j_pvalue=float(stats.chi2.sf(j_stat, dof)) if dof > 0 else float("nan"),
            n_assets=n,
            n_factors=k,
        )


class RollingOLS:
    """Per-column univariate regression whose row ``t`` sees only data up to ``t``.

    Expanding by default, or over a trailing window. Computed from running sums, so a long
    panel costs almost nothing.

    Attributes:
        window: Trailing window length, or None to expand.
        min_periods: Valid pairs required before an estimate appears. At least three, since
            the residual variance spends two degrees of freedom.
    """

    def __init__(self, window: int | None = None, min_periods: int = 24):
        self.window = window
        self.min_periods = max(int(min_periods), 3)

    def fit(self, y, x) -> dict:
        """Regress ``y`` on ``x`` with an intercept, column by column.

        Returns:
            A dict with ``alpha``, ``beta``, ``beta_se`` and ``nobs``, shaped like the inputs.

        Raises:
            ValueError: If the two inputs do not share an index and column set.
        """
        squeeze = isinstance(y, pd.Series) and isinstance(x, pd.Series)
        y_df = y.to_frame("y") if isinstance(y, pd.Series) else y
        x_df = x.to_frame("y") if isinstance(x, pd.Series) else x
        if not y_df.index.equals(x_df.index) or list(y_df.columns) != list(x_df.columns):
            raise ValueError("y and x must share the same index and columns.")

        valid = x_df.notna() & y_df.notna()
        xv, yv = x_df.where(valid), y_df.where(valid)

        def running(frame: pd.DataFrame) -> pd.DataFrame:
            if self.window is None:
                return frame.expanding(min_periods=1).sum()
            return frame.rolling(self.window, min_periods=1).sum()

        n = running(valid.astype(float))
        sx, sy = running(xv), running(yv)
        sxx, syy, sxy = running(xv**2), running(yv**2), running(xv * yv)

        den = n * sxx - sx**2
        enough = (n >= self.min_periods) & (den > 0)
        den = den.where(enough)

        beta = (n * sxy - sx * sy) / den
        alpha = (sy - beta * sx) / n.where(enough)
        # Cancellation can push the residual sum slightly negative before the square root.
        sse = (syy - alpha * sy - beta * sxy).clip(lower=0.0)
        beta_se = np.sqrt(sse / (n - 2.0) * n / den)

        out = {"alpha": alpha, "beta": beta, "beta_se": beta_se, "nobs": n.where(enough)}
        return {k: v["y"] for k, v in out.items()} if squeeze else out


class Shrinkage:
    """Pulling noisy estimates toward a target, trading a little bias for less variance."""

    @staticmethod
    def blend(raw, target, weight):
        """Convex combination ``(1 - weight) * raw + weight * target``.

        Raises:
            ValueError: If any weight falls outside ``[0, 1]``.
        """
        w = np.asarray(weight, dtype=float)
        finite = w[np.isfinite(w)]
        if finite.size and (finite.min() < 0.0 or finite.max() > 1.0):
            raise ValueError(
                f"weights must lie in [0, 1]; got [{finite.min():.4g}, {finite.max():.4g}]."
            )
        return raw * (1.0 - weight) + target * weight

    @staticmethod
    def cross_section(
        estimates: pd.Series,
        ses: pd.Series,
        target: float | None = None,
    ) -> pd.DataFrame:
        """Empirical-Bayes shrinkage of noisy estimates toward a common target.

        Each observation is a true value plus noise of known variance, and the true values are
        themselves spread around the target with unknown variance. Method of moments estimates
        that spread as the observed dispersion less the average noise, and the weight on the
        target for one unit is its noise variance over the total. Noisy units move a long way,
        precise ones barely at all. When the dispersion is no larger than the noise, the
        cross-section is indistinguishable from everyone equalling the target and everything
        collapses onto it.

        Returns:
            A frame indexed like ``estimates`` with ``shrunk`` and ``weight``. Units missing an
            estimate or a standard error pass through untouched.
        """
        est = estimates.astype(float)
        var = ses.astype(float).reindex(est.index) ** 2
        out = pd.DataFrame({"shrunk": est, "weight": np.nan}, index=est.index)

        usable = est.notna() & var.notna()
        if usable.sum() < 2:
            out.loc[usable, "weight"] = 0.0
            return out

        e, v = est[usable], var[usable]
        centre = float(e.mean()) if target is None else float(target)
        spread = max(0.0, float(e.var(ddof=1)) - float(v.mean()))
        denominator = v + spread
        w = pd.Series(np.where(denominator > 0, v / denominator, 1.0), index=e.index)

        out.loc[usable, "weight"] = w
        out.loc[usable, "shrunk"] = Shrinkage.blend(e, centre, w)
        return out
