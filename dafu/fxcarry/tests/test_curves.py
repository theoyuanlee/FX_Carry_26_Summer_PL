import numpy as np
import pandas as pd
import pytest

from fxcarry.catalog import Catalog
from fxcarry.curves import SpotForward
from fxcarry.quotes import Quotes

TAU = 1.0 / 12.0


def two_sided(mid, half=0.0):
    return Quotes(mid, mid - half, mid + half)


def native_inputs():
    idx = pd.date_range("2020-01-31", periods=3, freq="ME")
    spot = pd.DataFrame({"EUR": [1.10, 1.11, 1.12], "JPY": [110.0, 111.0, 112.0]}, index=idx)
    points = pd.DataFrame({"EUR": [10.0, 10.0, 10.0], "JPY": [-20.0, -20.0, -20.0]}, index=idx)
    return two_sided(spot, 0.0005), two_sided(points, 0.5)


def built():
    return SpotForward.from_quotes(*native_inputs(), catalog=Catalog.default(), tenor=TAU)


def test_points_are_added_natively_then_the_quote_is_flipped():
    sf = built()
    # EUR is already dollars per euro: F = 1.10 + 10/10000
    assert sf.forward.mid.loc["2020-01-31", "EUR"] == pytest.approx(1.1010)
    # JPY is yen per dollar: F = 110.00 + (-20)/100 = 109.80, then inverted
    assert sf.forward.mid.loc["2020-01-31", "JPY"] == pytest.approx(1.0 / 109.80)
    assert sf.spot.mid.loc["2020-01-31", "JPY"] == pytest.approx(1.0 / 110.0)


def test_inverting_before_adding_points_would_be_a_different_number():
    wrong = 1.0 / 110.0 + (-20.0) / 100.0
    assert built().forward.mid.loc["2020-01-31", "JPY"] != pytest.approx(wrong)


def test_inverting_the_quote_keeps_the_spread_open():
    sf = built()
    assert (sf.spot.bid["JPY"] < sf.spot.ask["JPY"]).all()
    assert (sf.forward.bid["JPY"] < sf.forward.ask["JPY"]).all()


def test_excess_return_is_indexed_at_settlement_and_has_no_look_ahead():
    sf = built()
    rx = sf.excess_return
    assert rx.iloc[0].isna().all()          # nothing settles in the first month
    expected = np.log(sf.spot.mid["EUR"].iloc[1]) - np.log(sf.forward.mid["EUR"].iloc[0])
    assert rx["EUR"].iloc[1] == pytest.approx(expected)


def test_a_currency_that_is_dear_forward_is_the_low_yielder():
    sf = built()
    # EUR forward above spot in dollars per euro: you pay to hold it, so carry is negative
    assert (sf.carry["EUR"] < 0).all()
    assert sf.carry["EUR"].iloc[0] == pytest.approx(-np.log(1.1010 / 1.10) * 12.0)


def test_carry_is_what_the_leg_earns_if_spot_does_not_move():
    idx = pd.date_range("2020-01-31", periods=3, freq="ME")
    spot = pd.DataFrame({"EUR": [1.10, 1.10, 1.10]}, index=idx)
    fwd = pd.DataFrame({"EUR": [1.09, 1.09, 1.09]}, index=idx)
    sf = SpotForward(two_sided(spot), two_sided(fwd), TAU)
    assert sf.carry["EUR"].iloc[0] * TAU == pytest.approx(sf.excess_return["EUR"].iloc[1])


def test_carry_agrees_with_the_rate_differential_it_implies():
    idx = pd.date_range("2020-01-31", periods=2, freq="ME")
    r_d, r_f = 0.05, 0.02
    spot = pd.DataFrame({"EUR": [1.10, 1.10]}, index=idx)
    fwd = spot * np.exp((r_d - r_f) * TAU)
    sf = SpotForward(two_sided(spot), two_sided(fwd), TAU)
    assert sf.carry["EUR"].iloc[0] == pytest.approx(r_f - r_d)


def test_forward_return_and_excess_return_agree_to_first_order():
    sf = built()
    simple = sf.forward_return["EUR"].iloc[1]
    logged = sf.excess_return["EUR"].iloc[1]
    assert np.log1p(simple) == pytest.approx(logged)


def test_crossing_the_spread_costs_money_on_both_sides():
    sf = built()
    gross = sf.excess_return["EUR"].iloc[1]
    assert sf.net_excess_return("long")["EUR"].iloc[1] < gross
    assert sf.net_excess_return("short")["EUR"].iloc[1] < -gross


def test_an_unknown_side_is_refused():
    with pytest.raises(ValueError, match="flat"):
        built().net_excess_return("flat")


def test_cip_recovers_the_rate_that_built_the_forward():
    idx = pd.date_range("2020-01-31", periods=2, freq="ME")
    r_d, r_f = 0.05, 0.02
    spot = pd.DataFrame({"EUR": [1.10, 1.10]}, index=idx)
    fwd = spot * np.exp((r_d - r_f) * TAU)
    sf = SpotForward(two_sided(spot), two_sided(fwd), TAU)
    got = sf.implied_foreign_rate(pd.Series(r_d, index=idx))
    assert got["EUR"].iloc[0] == pytest.approx(r_f)


def test_basis_is_zero_when_covered_parity_holds():
    idx = pd.date_range("2020-01-31", periods=2, freq="ME")
    r_d, r_f = 0.05, 0.02
    spot = pd.DataFrame({"EUR": [1.10, 1.10]}, index=idx)
    fwd = spot * np.exp((r_d - r_f) * TAU)
    sf = SpotForward(two_sided(spot), two_sided(fwd), TAU)
    basis = sf.basis(pd.DataFrame({"EUR": [r_f, r_f]}, index=idx), pd.Series(r_d, index=idx))
    assert basis["EUR"].abs().max() == pytest.approx(0.0, abs=1e-12)


def test_only_currencies_present_on_both_legs_survive():
    spot_q, pts_q = native_inputs()
    pts_q = pts_q.select(["EUR"])
    sf = SpotForward.from_quotes(spot_q, pts_q, Catalog.default(), TAU)
    assert sf.currencies == ["EUR"]
