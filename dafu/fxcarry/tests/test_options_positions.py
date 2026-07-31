import numpy as np
import pytest

from fxcarry.options import (
    Black76,
    Combination,
    Forward,
    MarketState,
    NoOverlay,
    SingleWing,
    Vanilla,
    VerticalSpread,
)
from fxcarry.vol import Smile

TAU = 0.25
SMILE = Smile(atm=0.12, risk_reversal={10: -0.03, 25: -0.02},
              butterfly={10: 0.012, 25: 0.005})
MARKET = MarketState(forward=1.10, tenor=TAU, discount=0.99,
                     base_rate=0.03, smile=SMILE, model=Black76())
GRID = np.linspace(0.70, 1.50, 801)


def test_a_forward_costs_nothing_and_pays_the_move():
    f = Forward(1.10)
    assert f.price(MARKET) == pytest.approx(0.0)
    assert f.payoff(1.15) == pytest.approx(0.05)
    assert f.payoff(1.05) == pytest.approx(-0.05)


def test_an_option_expires_into_its_intrinsic_value():
    call = Vanilla("call", 1.12, 0.12)
    assert call.payoff(1.20) == pytest.approx(0.08)
    assert call.payoff(1.00) == pytest.approx(0.0)
    assert Vanilla("put", 1.08, 0.12).payoff(1.00) == pytest.approx(0.08)


def test_an_option_prices_through_the_market_it_is_handed():
    call = Vanilla("call", 1.12, 0.12)
    assert call.price(MARKET) == pytest.approx(
        MARKET.model.value("call", 1.10, 1.12, 0.12, TAU, discount=0.99)
    )


def test_from_delta_reads_its_strike_and_its_vol_off_the_smile():
    put = Vanilla.from_delta(25, "put", MARKET)
    assert put.vol == pytest.approx(SMILE.vol(25, "put"))
    back = MARKET.model.delta("put", MARKET.forward, put.strike, put.vol, TAU,
                              base_rate=MARKET.base_rate)
    assert abs(back) == pytest.approx(0.25)


def test_from_delta_without_a_smile_says_what_is_missing():
    bare = MarketState(forward=1.10, tenor=TAU)
    with pytest.raises(ValueError, match="smile"):
        Vanilla.from_delta(25, "put", bare)


def test_arithmetic_builds_the_position_you_said_out_loud():
    near, far = Vanilla("put", 1.05, 0.13), Vanilla("put", 1.00, 0.14)
    spread = far - near
    assert isinstance(spread, Combination) and len(spread.legs) == 2
    assert spread.payoff(0.95) == pytest.approx(far.payoff(0.95) - near.payoff(0.95))
    assert (2 * near).payoff(1.00) == pytest.approx(2 * near.payoff(1.00))
    assert (-near).price(MARKET) == pytest.approx(-near.price(MARKET))


def test_three_legs_stay_flat_instead_of_nesting():
    a, b, c = (Vanilla("put", k, 0.13) for k in (1.05, 1.00, 0.95))
    assert len((a - b + c).legs) == 3


def test_a_combination_is_the_weighted_sum_of_its_legs():
    near, far = Vanilla("put", 1.05, 0.13), Vanilla("put", 1.00, 0.14)
    combo = Combination(((-1.0, near), (1.0, far)))
    assert combo.price(MARKET) == pytest.approx(far.price(MARKET) - near.price(MARKET))
    assert combo.payoff(0.90) == pytest.approx(far.payoff(0.90) - near.payoff(0.90))


def test_the_loss_on_a_vertical_spread_is_the_strike_gap():
    near, far = Vanilla("put", 1.05, 0.13), Vanilla("put", 1.00, 0.14)
    assert (far - near).worst_case(GRID) == pytest.approx(-(1.05 - 1.00), abs=1e-3)


def test_owning_the_near_rung_bounds_the_loss_at_nothing():
    near, far = Vanilla("put", 1.05, 0.13), Vanilla("put", 1.00, 0.14)
    assert (near - far).worst_case(GRID) == pytest.approx(0.0, abs=1e-12)


def test_selling_the_near_rung_is_a_credit_and_owning_it_a_debit():
    sold = VerticalSpread(25, 10, "put").build(MARKET)
    bought = VerticalSpread(10, 25, "put").build(MARKET)
    assert sold.price(MARKET) < 0        # net premium received
    assert bought.price(MARKET) > 0      # net premium paid
    assert sold.price(MARKET) == pytest.approx(-bought.price(MARKET))


def test_reversing_the_rungs_reverses_the_payoff_everywhere():
    sold = VerticalSpread(25, 10, "put").build(MARKET)
    bought = VerticalSpread(10, 25, "put").build(MARKET)
    assert np.allclose([sold.payoff(x) for x in GRID], [-bought.payoff(x) for x in GRID])


def test_the_sold_spread_gives_up_at_most_its_strike_gap():
    sold = VerticalSpread(25, 10, "put").build(MARKET)
    strikes = sorted(leg.strike for _, leg in sold.legs)
    gap = strikes[1] - strikes[0]
    assert sold.worst_case(GRID) == pytest.approx(-gap, abs=1e-3)


def test_a_ratio_spread_is_the_same_class_with_other_numbers():
    ratio = VerticalSpread(25, 10, "put", quantities=(-1.0, 2.0)).build(MARKET)
    assert len(ratio.legs) == 2
    assert ratio.legs[1][0] == pytest.approx(2.0)


def test_a_single_wing_is_one_leg_and_no_overlay_is_none():
    assert len(SingleWing(25, "put").build(MARKET).legs) == 1
    empty = NoOverlay().build(MARKET)
    assert empty.legs == () and empty.price(MARKET) == 0.0 and empty.payoff(1.5) == 0.0


def test_a_call_overlay_protects_the_other_side():
    calls = VerticalSpread(25, 10, "call").build(MARKET)
    assert all(leg.kind == "call" for _, leg in calls.legs)
    assert calls.payoff(1.50) < 0 and calls.payoff(0.80) == pytest.approx(0.0)
