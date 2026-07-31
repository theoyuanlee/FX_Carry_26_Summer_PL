"""Saying which state the world is in, and how much of that answer is hindsight.

A regime model claims that a return series is drawn from one of a small number of states —
a calm one and a stressed one, in every model here — and reports how likely the stressed
state was on each date. What the strategy does with that number is a separate decision,
handled by the gate functions at the bottom of the module.

The interesting difficulty is not the estimation. It is that almost every convenient way to
report a regime probability looks backwards. A smoothed probability at 2008-09 is the model's
opinion having seen 2009 through 2026; a filtered probability at that date only reads the past,
but the parameters that drive the filter were still estimated on the whole sample. Neither is
available to somebody standing there at the time, and both flatter a timing rule. So every
estimator here takes an ``information`` argument naming which of the three it is:

``"insample"``
    Parameters and state inference both use the whole sample. Not implementable. Present so
    the size of the illusion can be measured rather than assumed away.
``"filtered"``
    Parameters from the whole sample, states inferred recursively. Halfway house, and the one
    most often published without comment.
``"realtime"``
    Parameters re-estimated on an expanding window, states inferred recursively. Nothing at
    date ``t`` touches data after ``t``. The only one a backtest can honestly spend.

Everything returns a :class:`RegimeSeries` whose ``probability`` is indexed by the date it
became knowable, matching the rest of the library: no estimator here shifts anything, and the
consumer applies whatever execution lag its book requires.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field

import numpy as np
import pandas as pd
import statsmodels.api as sm
from statsmodels.tsa.regime_switching.markov_regression import MarkovRegression

#: The three information sets, ordered from most hindsight to none.
INFORMATION_SETS = ("insample", "filtered", "realtime")


@dataclass(frozen=True)
class RegimeSeries:
    """A stress probability path and the record of what produced it.

    Attributes:
        probability: Probability of the stressed state, indexed by the date it was knowable.
        states: Probability of every state, one column each, on the same index.
        parameters: One row per estimation, indexed by the date of the data it was fitted on.
            A single row for the full-sample fits; one per refit under ``"realtime"``.
        information: Which information set produced it, one of :data:`INFORMATION_SETS`.
        name: Label for tables and legends.
    """

    probability: pd.Series
    states: pd.DataFrame
    parameters: pd.DataFrame = field(default_factory=pd.DataFrame)
    information: str = "realtime"
    name: str = ""

    @property
    def stressed_share(self) -> float:
        """Average stress probability, the share of the sample the model calls stressed."""
        return float(self.probability.mean())

    def rename(self, name: str) -> "RegimeSeries":
        """The same path under a different label."""
        return RegimeSeries(
            self.probability.rename(name), self.states, self.parameters, self.information, name
        )


class RegimeModel(ABC):
    """Reads a history and says how likely the stressed state was on each date.

    Subclasses differ in what they read and how they decide, not in what they return. The
    training target of a supervised model is part of its specification and is supplied at
    construction, so that every model exposes the same one-argument call.

    Attributes:
        information: Which of :data:`INFORMATION_SETS` the estimator is allowed to use.
        name: Label carried through to the returned :class:`RegimeSeries`.
    """

    supported: tuple[str, ...] = INFORMATION_SETS

    def __init__(self, information: str = "realtime", name: str = ""):
        if information not in self.supported:
            raise ValueError(
                f"{type(self).__name__} supports information in {self.supported}, "
                f"got {information!r}."
            )
        self.information = information
        self.name = name or type(self).__name__

    @abstractmethod
    def probabilities(self, history) -> RegimeSeries:
        """Probability of the stressed state on each date of ``history``."""


class MarkovSwitching(RegimeModel):
    """Two-state Markov switching, with the states inferred rather than declared.

    The series is modelled as a constant plus noise whose mean and variance both depend on an
    unobserved state that follows a Markov chain. Nothing tells the estimator which state is
    the bad one, so it is identified after the fact from the fitted parameters — by variance
    for a return series, where the stressed state is the volatile one, or by mean for a series
    like a volatility index, where stress shows up as a level shift rather than a spread.

    Under ``"realtime"`` the parameters are re-estimated every ``refit_every`` periods on all
    data available at the time, and between refits the filter runs forward on the most recent
    parameter set. The state labels are re-identified at every refit, since the estimator is
    free to number them differently each time and a silent flip would invert the gate.

    Choose ``stressed`` from what the series *is*, before running anything. For a profit and
    loss series the bad state is the one that loses money, ``"low_mean"``; for a series in
    volatility changes it is the one where volatility jumps, ``"high_mean"``. ``"high_variance"``
    reads well and is usually wrong: on a return series the higher-variance state is often
    simply normal trading, with the quiet state doing the work of catching a handful of
    outliers, and a gate built on it de-risks most of the sample for no reason. Picking the
    rule that backtests best is a second helping of the hindsight this class exists to measure.

    Attributes:
        stressed: How to identify the stressed state — ``"high_variance"``, ``"high_mean"`` or
            ``"low_mean"``.
        switching_variance: Whether the variance switches. Required for ``"high_variance"``.
        min_periods: Observations required before the first ``"realtime"`` estimate appears.
        refit_every: Periods between parameter re-estimations under ``"realtime"``.
    """

    def __init__(
        self,
        information: str = "realtime",
        stressed: str = "high_variance",
        switching_variance: bool = True,
        min_periods: int = 60,
        refit_every: int = 12,
        name: str = "",
    ):
        super().__init__(information, name)
        if stressed not in ("high_variance", "high_mean", "low_mean"):
            raise ValueError(
                f"stressed must be high_variance/high_mean/low_mean, got {stressed!r}."
            )
        if stressed == "high_variance" and not switching_variance:
            raise ValueError(
                "identifying the stressed state by variance needs switching_variance=True."
            )
        if min_periods < 12:
            raise ValueError(f"min_periods must be at least 12, got {min_periods}.")
        if refit_every < 1:
            raise ValueError(f"refit_every must be at least 1, got {refit_every}.")
        self.stressed = stressed
        self.switching_variance = switching_variance
        self.min_periods = min_periods
        self.refit_every = refit_every

    def _model(self, series: pd.Series) -> MarkovRegression:
        return MarkovRegression(
            series.astype(float),
            k_regimes=2,
            trend="c",
            switching_variance=self.switching_variance,
        )

    def _stressed_state(self, params: pd.Series) -> int:
        """Which of the two fitted states is the bad one.

        Read off the parameters rather than assumed, because the likelihood is invariant to
        relabelling the states and the optimiser picks an order for its own reasons.
        """
        if self.stressed == "high_variance":
            key = "sigma2"
            pick = np.argmax
        else:
            key = "const"
            pick = np.argmax if self.stressed == "high_mean" else np.argmin
        values = [float(params[f"{key}[{i}]"]) for i in (0, 1)]
        return int(pick(values))

    @staticmethod
    def _fit(model: MarkovRegression, start_params: np.ndarray | None):
        """Maximum likelihood, retried from the default start if a warm start wanders off."""
        try:
            return model.fit(start_params=start_params, disp=False)
        except Exception:
            return model.fit(disp=False)

    def probabilities(self, history: pd.Series) -> RegimeSeries:
        """Stress probability on each date, under this model's information set.

        Args:
            history: The series whose state is in question — a strategy's own returns, or a
                risk indicator from outside it.

        Returns:
            A :class:`RegimeSeries`. Under ``"realtime"`` the first ``min_periods`` dates are
            missing, since no parameters had been estimated yet.
        """
        series = pd.Series(history).dropna().astype(float)
        if len(series) <= self.min_periods:
            raise ValueError(
                f"{len(series)} observations is not enough for min_periods="
                f"{self.min_periods}."
            )

        if self.information in ("insample", "filtered"):
            res = self._fit(self._model(series), None)
            state = self._stressed_state(res.params)
            probs = (
                res.smoothed_marginal_probabilities
                if self.information == "insample"
                else res.filtered_marginal_probabilities
            )
            states = pd.DataFrame(np.asarray(probs), index=series.index, columns=["calm", "stressed"])
            if state == 0:
                states = states.iloc[:, ::-1].set_axis(["calm", "stressed"], axis=1)
            params = res.params.to_frame(series.index[-1]).T
            return RegimeSeries(
                states["stressed"].rename(self.name), states, params, self.information, self.name
            )

        # Real time. Parameters are only ever fitted on data that had already happened, and
        # between refits the filter carries them forward over the new observations.
        values = pd.Series(np.nan, index=series.index, name=self.name)
        rows: dict[pd.Timestamp, pd.Series] = {}
        params_now: pd.Series | None = None
        state = 0
        for i in range(self.min_periods, len(series)):
            if params_now is None or (i - self.min_periods) % self.refit_every == 0:
                warm = None if params_now is None else np.asarray(params_now, dtype=float)
                try:
                    res = self._fit(self._model(series.iloc[:i]), warm)
                    params_now = res.params
                    state = self._stressed_state(params_now)
                    rows[series.index[i - 1]] = params_now
                except Exception:
                    # Keep the previous parameter set rather than dropping the date: a failed
                    # re-estimation is a reason to trust the old fit, not to leave the market.
                    if params_now is None:
                        continue
            filtered = self._model(series.iloc[: i + 1]).filter(
                np.asarray(params_now, dtype=float)
            )
            values.iloc[i] = float(
                np.asarray(filtered.filtered_marginal_probabilities)[-1, state]
            )

        states = pd.DataFrame({"calm": 1.0 - values, "stressed": values})
        params = pd.DataFrame(rows).T if rows else pd.DataFrame()
        return RegimeSeries(values.dropna(), states, params, self.information, self.name)


class TrailingPercentile(RegimeModel):
    """Where an observable risk indicator sits in its own recent history.

    No latent state and nothing to estimate: the stress score is the fraction of the trailing
    window the current reading exceeds. It is the honest benchmark for the switching models,
    because most of what a regime model knows about a crisis is that volatility was high, and
    a percentile rank knows that too. If a Markov chain cannot beat this, the chain is not
    earning its parameters.

    The score is a rank rather than a probability, which is the point: it is bounded in
    ``[0, 1]``, monotone in the indicator, and free of distributional assumptions.

    Attributes:
        window: Trailing periods the rank is taken over, or None to expand from the start.
        min_periods: Observations required before a rank appears.
    """

    supported = ("insample", "realtime")

    def __init__(
        self,
        information: str = "realtime",
        window: int | None = 60,
        min_periods: int = 36,
        name: str = "",
    ):
        super().__init__(information, name)
        if window is not None and window < 2:
            raise ValueError(f"window must be at least 2, got {window}.")
        self.window = window
        self.min_periods = min_periods

    def probabilities(self, history: pd.Series) -> RegimeSeries:
        """Trailing percentile rank of the indicator, on each date.

        Args:
            history: The risk indicator — an implied volatility index, a spread, anything
                where higher means worse.
        """
        series = pd.Series(history).dropna().astype(float)
        if self.information == "insample":
            values = series.rank(pct=True)
        elif self.window is None:
            values = series.expanding(min_periods=self.min_periods).apply(
                lambda w: float((w[:-1] < w[-1]).mean()), raw=True
            )
        else:
            values = series.rolling(self.window, min_periods=self.min_periods).apply(
                lambda w: float((w[:-1] < w[-1]).mean()), raw=True
            )
        values = values.dropna().rename(self.name)
        states = pd.DataFrame({"calm": 1.0 - values, "stressed": values})
        return RegimeSeries(values, states, pd.DataFrame(), self.information, self.name)


class LogisticRegime(RegimeModel):
    """Stress probability learned from macro and market features, one fold at a time.

    Where the switching models find their own states, this one is told what a bad outcome is
    and asked which conditions precede it. The outcome is supplied at construction and is
    dated by when it was *decided*, not when it was observed: a label saying "the month after
    this one lost money" belongs to the earlier date, and the estimator only ever trains on
    labels whose outcome had already resolved. That one rule is what keeps an expanding-window
    classifier honest, and it is easy to lose.

    Standardisation runs inside the fold as well, using only the features seen so far. A
    scaler fitted on the whole sample leaks the future through the mean and the variance, and
    the leak is large enough to matter over a sample containing 2008.

    Attributes:
        outcome: Binary labels, indexed by the date the predicting features are dated.
        ridge: L2 penalty. Keeps the fit from separating on a short early fold.
        min_periods: Resolved labels required before the first prediction.
        refit_every: Periods between coefficient re-estimations.
    """

    supported = ("insample", "realtime")

    def __init__(
        self,
        outcome: pd.Series,
        information: str = "realtime",
        ridge: float = 1.0,
        min_periods: int = 60,
        refit_every: int = 1,
        name: str = "",
    ):
        super().__init__(information, name)
        if ridge < 0:
            raise ValueError(f"ridge must be non-negative, got {ridge}.")
        self.outcome = pd.Series(outcome).dropna().astype(float)
        self.ridge = ridge
        self.min_periods = min_periods
        self.refit_every = max(int(refit_every), 1)

    def _coefficients(self, x: np.ndarray, y: np.ndarray) -> np.ndarray | None:
        """Ridge-penalised logit coefficients, or None where the fit will not settle."""
        if len(np.unique(y)) < 2:
            return None
        design = sm.add_constant(x, has_constant="add")
        try:
            if self.ridge > 0:
                fit = sm.Logit(y, design).fit_regularized(
                    alpha=self.ridge, L1_wt=0.0, disp=False
                )
            else:
                fit = sm.Logit(y, design).fit(disp=False)
            params = np.asarray(fit.params, dtype=float)
            return params if np.all(np.isfinite(params)) else None
        except Exception:
            return None

    @staticmethod
    def _predict(coefficients: np.ndarray, row: np.ndarray) -> float:
        z = float(coefficients[0] + coefficients[1:] @ row)
        return float(1.0 / (1.0 + np.exp(-np.clip(z, -30.0, 30.0))))

    def probabilities(self, history: pd.DataFrame) -> RegimeSeries:
        """Predicted probability of the bad outcome, on each date of ``history``.

        Args:
            history: Features, one column each, on the same dates as the outcome.
        """
        features = pd.DataFrame(history).astype(float)
        features = features.loc[:, features.notna().any()].dropna()
        labels = self.outcome.reindex(features.index)
        if features.empty:
            raise ValueError("no complete feature rows to fit on.")

        if self.information == "insample":
            usable = labels.notna()
            scaled = (features - features.mean()) / features.std(ddof=0).replace(0.0, np.nan)
            scaled = scaled.fillna(0.0)
            coefficients = self._coefficients(
                scaled[usable].to_numpy(float), labels[usable].to_numpy(float)
            )
            if coefficients is None:
                raise ValueError("the full-sample logit did not converge.")
            values = pd.Series(
                [self._predict(coefficients, row) for row in scaled.to_numpy(float)],
                index=scaled.index,
                name=self.name,
            )
            states = pd.DataFrame({"calm": 1.0 - values, "stressed": values})
            return RegimeSeries(values, states, pd.DataFrame(), self.information, self.name)

        values = pd.Series(np.nan, index=features.index, name=self.name)
        rows: dict[pd.Timestamp, pd.Series] = {}
        coefficients: np.ndarray | None = None
        columns = list(features.columns)
        for i in range(len(features)):
            # Labels resolve one period after the features they are attached to, so the newest
            # trainable pair at date t is the one dated t-1 — its outcome landed today.
            train = features.iloc[:i]
            target = labels.iloc[:i]
            complete = target.notna()
            if complete.sum() < self.min_periods:
                continue
            if coefficients is None or i % self.refit_every == 0:
                centre, spread = train.mean(), train.std(ddof=0).replace(0.0, np.nan)
                scaled = ((train - centre) / spread).fillna(0.0)
                fitted = self._coefficients(
                    scaled[complete].to_numpy(float), target[complete].to_numpy(float)
                )
                if fitted is not None:
                    coefficients = fitted
                    rows[features.index[i]] = pd.Series(
                        coefficients, index=["const"] + columns
                    )
            if coefficients is None:
                continue
            centre, spread = train.mean(), train.std(ddof=0).replace(0.0, np.nan)
            row = ((features.iloc[i] - centre) / spread).fillna(0.0).to_numpy(float)
            values.iloc[i] = self._predict(coefficients, row)

        states = pd.DataFrame({"calm": 1.0 - values, "stressed": values})
        params = pd.DataFrame(rows).T if rows else pd.DataFrame()
        return RegimeSeries(values.dropna(), states, params, self.information, self.name)


# ---------------------------------------------------------------------------
# Gates — turning a stress probability into how much of the book to hold
# ---------------------------------------------------------------------------
#
# Kept separate from the models on purpose. The question of what state the world is in and the
# question of how much risk that justifies are answered by different people with different
# evidence, and pairing every model with every gate is how you find out which half of a result
# came from which.


def _validated(probability: pd.Series) -> pd.Series:
    clean = pd.Series(probability).dropna().astype(float)
    if clean.empty:
        raise ValueError("the probability series is empty.")
    if clean.min() < -1e-9 or clean.max() > 1 + 1e-9:
        raise ValueError(
            f"probabilities must lie in [0, 1]; got [{clean.min():.4g}, {clean.max():.4g}]."
        )
    return clean.clip(0.0, 1.0)


def linear_gate(probability: pd.Series, floor: float = 0.0, cap: float = 1.0) -> pd.Series:
    """Hold ``cap`` when the stressed state is impossible and ``floor`` when it is certain.

    The gentlest reading of a probability: exposure falls in a straight line as conviction
    rises, so a model that is merely uneasy trims rather than exits. Because it never jumps, it
    also trades less than a threshold rule, which matters once the trades are costed.
    """
    if not 0.0 <= floor <= cap:
        raise ValueError(f"need 0 <= floor <= cap, got floor={floor}, cap={cap}.")
    return (cap - (cap - floor) * _validated(probability)).rename("exposure")


def binary_gate(
    probability: pd.Series, threshold: float = 0.5, floor: float = 0.0, cap: float = 1.0
) -> pd.Series:
    """Hold ``cap`` below the threshold and ``floor`` above it.

    What a regime model is usually asked for, and the version most exposed to the threshold
    being chosen after seeing the answer. Sweep it rather than picking one.
    """
    if not 0.0 <= floor <= cap:
        raise ValueError(f"need 0 <= floor <= cap, got floor={floor}, cap={cap}.")
    if not 0.0 <= threshold <= 1.0:
        raise ValueError(f"threshold must lie in [0, 1], got {threshold}.")
    clean = _validated(probability)
    return pd.Series(np.where(clean > threshold, floor, cap), index=clean.index, name="exposure")


def power_gate(probability: pd.Series, exponent: float = 2.0, floor: float = 0.0) -> pd.Series:
    """Linear in the probability raised to a power, so only real conviction de-risks.

    An exponent above one leaves exposure near full through the ambiguous middle and cuts hard
    at the top, which is the shape a manager who dislikes false alarms actually wants.
    """
    if exponent <= 0:
        raise ValueError(f"exponent must be positive, got {exponent}.")
    return (1.0 - (1.0 - floor) * _validated(probability) ** exponent).rename("exposure")
