import numpy as np
import pandas as pd
import pytest

from fxcarry.options import Black76

MODEL = Black76()
TAU = 0.25


def test_put_call_parity():
    call = MODEL.value("call", 1.10, 1.05, 0.12, TAU, discount=0.99)
    put = MODEL.value("put", 1.10, 1.05, 0.12, TAU, discount=0.99)
    assert call - put == pytest.approx(0.99 * (1.10 - 1.05))


def test_zero_vol_collapses_to_discounted_intrinsic():
    assert MODEL.value("call", 1.10, 1.05, 0.0, TAU, 0.99) == pytest.approx(0.99 * 0.05)
    assert MODEL.value("put", 1.10, 1.05, 0.0, TAU, 0.99) == pytest.approx(0.0)


def test_a_missing_vol_stays_missing_rather_than_becoming_a_free_option():
    assert np.isnan(MODEL.value("call", 1.10, 1.05, np.nan, TAU, 0.99))


def test_value_rises_with_vol_and_the_call_falls_with_the_strike():
    assert MODEL.value("call", 1.10, 1.10, 0.16, TAU) > MODEL.value("call", 1.10, 1.10, 0.08, TAU)
    assert MODEL.value("call", 1.10, 1.20, 0.12, TAU) < MODEL.value("call", 1.10, 1.00, 0.12, TAU)


def test_an_option_is_never_worth_less_than_nothing():
    for strike in (0.5, 1.0, 1.1, 2.0):
        assert MODEL.value("call", 1.10, strike, 0.12, TAU) >= 0.0
        assert MODEL.value("put", 1.10, strike, 0.12, TAU) >= 0.0


@pytest.mark.parametrize("delta", [0.05, 0.10, 0.25])
@pytest.mark.parametrize("kind", ["call", "put"])
def test_strike_and_delta_invert_each_other(delta, kind):
    k = MODEL.strike_from_delta(delta, kind, 1.10, 0.12, TAU, base_rate=0.03)
    back = MODEL.delta(kind, 1.10, k, 0.12, TAU, base_rate=0.03)
    assert abs(back) == pytest.approx(delta)


def test_a_lower_delta_put_strikes_further_out():
    k25 = MODEL.strike_from_delta(0.25, "put", 1.10, 0.12, TAU)
    k10 = MODEL.strike_from_delta(0.10, "put", 1.10, 0.12, TAU)
    assert k10 < k25 < 1.10


def test_a_lower_delta_call_strikes_further_out_the_other_way():
    k25 = MODEL.strike_from_delta(0.25, "call", 1.10, 0.12, TAU)
    k10 = MODEL.strike_from_delta(0.10, "call", 1.10, 0.12, TAU)
    assert k10 > k25 > 1.10


def test_the_delta_neutral_strike_sits_just_above_the_forward():
    k = MODEL.atm_strike(1.10, 0.12, TAU)
    assert k > 1.10
    assert k == pytest.approx(1.10 * np.exp(0.5 * 0.12**2 * TAU))


def test_a_straddle_at_that_strike_really_is_delta_neutral():
    k = MODEL.atm_strike(1.10, 0.12, TAU)
    net = MODEL.delta("call", 1.10, k, 0.12, TAU) + MODEL.delta("put", 1.10, k, 0.12, TAU)
    assert net == pytest.approx(0.0, abs=1e-12)


def test_pandas_goes_in_and_pandas_comes_out():
    idx = pd.date_range("2020-01-31", periods=3, freq="ME")
    forward = pd.Series([1.10, 1.11, 1.12], index=idx)
    out = MODEL.value("call", forward, 1.10, 0.12, TAU)
    assert isinstance(out, pd.Series) and out.index.equals(idx)
    assert (out.diff().dropna() > 0).all()


def test_an_unknown_option_kind_is_refused():
    with pytest.raises(ValueError, match="straddle"):
        MODEL.value("straddle", 1.10, 1.10, 0.12, TAU)
    with pytest.raises(ValueError, match="straddle"):
        MODEL.strike_from_delta(0.25, "straddle", 1.10, 0.12, TAU)
