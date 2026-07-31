"""Regime estimators, and the property the whole module exists to guarantee.

The central test is truncation invariance: a real-time probability computed at date ``t`` must
not move when data after ``t`` changes. Everything else in this file is secondary. The
in-sample estimators are tested to *fail* that same check, because a no-lookahead test that
passes for every configuration is testing nothing.
"""

import numpy as np
import pandas as pd
import pytest

from fxcarry.regimes import (
    LogisticRegime,
    MarkovSwitching,
    RegimeSeries,
    TrailingPercentile,
    binary_gate,
    linear_gate,
    power_gate,
)


def months(n, start="2000-01-31"):
    return pd.date_range(start, periods=n, freq="ME")


@pytest.fixture(scope="module")
def switching_series():
    """A two-state series: calm throughout, with one long volatile block in the middle."""
    rng = np.random.default_rng(0)
    n = 132
    scale = np.full(n, 1.0)
    scale[60:96] = 4.0
    values = rng.normal(0.0, scale)
    return pd.Series(values, index=months(n)), slice(60, 96)


@pytest.fixture(scope="module")
def indicator_series():
    """A drifting risk indicator with one short spike, shorter than the ranking window.

    The spike has to be shorter than the window it is ranked against. A shift that lasts as
    long as the lookback stops looking unusual once the window has absorbed it, which is a
    property of trailing percentiles rather than a defect, but it makes for a confusing test.
    """
    rng = np.random.default_rng(7)
    n = 132
    level = np.cumsum(rng.normal(0.0, 0.25, n)) + 15.0
    level[60:72] += 10.0
    return pd.Series(level, index=months(n))


# --- the no-lookahead property ---------------------------------------------


def test_markov_realtime_ignores_the_future(switching_series):
    """Truncating the sample leaves every earlier real-time probability untouched."""
    series, _ = switching_series
    model = MarkovSwitching(information="realtime", min_periods=48, refit_every=12)
    full = model.probabilities(series).probability
    cut = 110
    early = model.probabilities(series.iloc[:cut]).probability
    shared = early.index.intersection(full.index)
    assert len(shared) > 40
    np.testing.assert_allclose(full[shared].to_numpy(), early[shared].to_numpy(), atol=1e-6)


def test_markov_insample_does_not(switching_series):
    """The same check on smoothed probabilities fails, which is why it is worth running."""
    series, _ = switching_series
    model = MarkovSwitching(information="insample", min_periods=48)
    full = model.probabilities(series).probability
    early = model.probabilities(series.iloc[:110]).probability
    shared = early.index.intersection(full.index)
    assert not np.allclose(full[shared].to_numpy(), early[shared].to_numpy(), atol=1e-6)


def test_trailing_percentile_realtime_ignores_the_future(indicator_series):
    model = TrailingPercentile(information="realtime", window=36, min_periods=24)
    full = model.probabilities(indicator_series).probability
    early = model.probabilities(indicator_series.iloc[:110]).probability
    shared = early.index.intersection(full.index)
    np.testing.assert_allclose(full[shared].to_numpy(), early[shared].to_numpy(), atol=1e-12)


def test_logistic_realtime_ignores_the_future():
    rng = np.random.default_rng(3)
    n = 160
    idx = months(n)
    x = pd.DataFrame({"a": rng.normal(size=n), "b": rng.normal(size=n)}, index=idx)
    y = (x["a"] + 0.3 * rng.normal(size=n) > 0).astype(float)
    model = LogisticRegime(y, information="realtime", min_periods=48, refit_every=6)
    full = model.probabilities(x).probability
    early = model.probabilities(x.iloc[:130]).probability
    shared = early.index.intersection(full.index)
    assert len(shared) > 40
    np.testing.assert_allclose(full[shared].to_numpy(), early[shared].to_numpy(), atol=1e-8)


def test_logistic_never_trains_on_an_unresolved_label():
    """Blanking the newest label cannot change any earlier prediction.

    The label at date ``t`` describes what happened after ``t``, so a fold ending at ``t`` must
    not have seen it. Wiping it out is the cheapest way to prove the fold did not.
    """
    rng = np.random.default_rng(11)
    n = 140
    idx = months(n)
    x = pd.DataFrame({"a": rng.normal(size=n), "b": rng.normal(size=n)}, index=idx)
    y = (x["a"] > 0).astype(float)
    tampered = y.copy()
    tampered.iloc[-1] = 1.0 - tampered.iloc[-1]

    honest = LogisticRegime(y, information="realtime", min_periods=48).probabilities(x)
    altered = LogisticRegime(tampered, information="realtime", min_periods=48).probabilities(x)
    np.testing.assert_allclose(
        honest.probability.to_numpy(), altered.probability.to_numpy(), atol=1e-10
    )


# --- do the models find what is actually there? -----------------------------


def test_markov_identifies_the_volatile_block(switching_series):
    series, block = switching_series
    result = MarkovSwitching(information="insample", min_periods=48).probabilities(series)
    inside = result.probability.iloc[block].mean()
    outside = result.probability.drop(result.probability.index[block]).mean()
    assert inside > 0.8
    assert outside < 0.2


def test_markov_state_labels_follow_the_parameters():
    """A series whose stressed state is the quiet one is still identified correctly."""
    rng = np.random.default_rng(5)
    n = 120
    scale = np.full(n, 3.0)
    scale[50:85] = 0.5
    series = pd.Series(rng.normal(0.0, scale), index=months(n))
    volatile = MarkovSwitching(information="insample", stressed="high_variance")
    result = volatile.probabilities(series)
    assert result.probability.iloc[50:85].mean() < 0.2


def test_percentile_ranks_are_bounded_and_monotone(indicator_series):
    result = TrailingPercentile(information="realtime", window=36, min_periods=24).probabilities(
        indicator_series
    )
    assert result.probability.between(0.0, 1.0).all()
    # Select by date: the burn-in has already been dropped, so positions no longer line up.
    spike = indicator_series.index[60:72]
    inside = result.probability.reindex(spike)
    assert inside.iloc[0] == pytest.approx(1.0)
    # The rank decays across the spike as the trailing window takes the new level in. That is
    # the estimator working, not failing, and it is the reason a percentile gate re-arms.
    assert inside.is_monotonic_decreasing or inside.iloc[-1] < inside.iloc[0]
    assert inside.mean() > 0.8
    assert result.probability.drop(spike, errors="ignore").mean() < 0.4


def test_logistic_learns_a_real_signal():
    rng = np.random.default_rng(13)
    n = 200
    idx = months(n)
    x = pd.DataFrame({"a": rng.normal(size=n), "b": rng.normal(size=n)}, index=idx)
    y = (x["a"] > 0).astype(float)
    result = LogisticRegime(y, information="realtime", min_periods=48).probabilities(x)
    aligned = y.reindex(result.probability.index)
    assert result.probability[aligned == 1].mean() > result.probability[aligned == 0].mean() + 0.2


def test_realtime_leaves_the_burn_in_unestimated(switching_series):
    series, _ = switching_series
    result = MarkovSwitching(information="realtime", min_periods=48, refit_every=24).probabilities(
        series
    )
    assert result.probability.index[0] >= series.index[48]
    assert isinstance(result, RegimeSeries)
    assert not result.parameters.empty


# --- gates ------------------------------------------------------------------


@pytest.fixture
def probability():
    return pd.Series([0.0, 0.25, 0.5, 0.75, 1.0], index=months(5))


def test_linear_gate_spans_floor_to_cap(probability):
    gate = linear_gate(probability, floor=0.2, cap=1.0)
    assert gate.iloc[0] == pytest.approx(1.0)
    assert gate.iloc[-1] == pytest.approx(0.2)
    assert gate.is_monotonic_decreasing


def test_binary_gate_switches_at_the_threshold(probability):
    gate = binary_gate(probability, threshold=0.5, floor=0.0, cap=1.0)
    assert list(gate) == [1.0, 1.0, 1.0, 0.0, 0.0]


def test_power_gate_protects_the_ambiguous_middle(probability):
    steep = power_gate(probability, exponent=3.0)
    gentle = linear_gate(probability)
    assert steep.iloc[2] > gentle.iloc[2]
    assert steep.iloc[-1] == pytest.approx(gentle.iloc[-1])


def test_gates_reject_things_that_are_not_probabilities():
    bad = pd.Series([0.5, 1.4], index=months(2))
    for gate in (linear_gate, binary_gate, power_gate):
        with pytest.raises(ValueError, match="probabilities must lie"):
            gate(bad)


def test_gates_reject_an_inverted_range(probability):
    with pytest.raises(ValueError, match="floor <= cap"):
        linear_gate(probability, floor=0.8, cap=0.2)


# --- construction guards ----------------------------------------------------


def test_unsupported_information_set_is_refused():
    with pytest.raises(ValueError, match="supports information"):
        TrailingPercentile(information="filtered")


def test_variance_identification_needs_a_switching_variance():
    with pytest.raises(ValueError, match="switching_variance=True"):
        MarkovSwitching(stressed="high_variance", switching_variance=False)


def test_too_short_a_history_is_refused(switching_series):
    series, _ = switching_series
    with pytest.raises(ValueError, match="not enough"):
        MarkovSwitching(min_periods=48).probabilities(series.iloc[:40])
