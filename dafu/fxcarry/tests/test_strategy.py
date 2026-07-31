import numpy as np
import pandas as pd
import pytest

from fxcarry.curves import SpotForward
from fxcarry.options import VerticalSpread
from fxcarry.quotes import Quotes
from fxcarry.strategy import (
    BidAskCost,
    Book,
    Bucket,
    Carry,
    EqualLong,
    HalfSpreadCost,
    Momentum,
    SignEqualWeight,
    SpreadWeighted,
    TopBottom,
)
from fxcarry.vol import Smile

TAU = 1.0 / 12.0
IDX = pd.date_range("2020-01-31", periods=6, freq="ME")


def curves_from(spot, fwd, half=0.0):
    return SpotForward(
        Quotes(spot, spot * (1 - half), spot * (1 + half)),
        Quotes(fwd, fwd * (1 - half), fwd * (1 + half)),
        TAU,
    )


def flat_book(n=4, half=0.0):
    cols = [f"C{i}" for i in range(n)]
    spot = pd.DataFrame(1.0, index=IDX, columns=cols)
    # forwards below spot, so every currency yields more than the dollar and C3 most of all
    fwd = pd.DataFrame({c: 1.0 - 0.001 * (i + 1) for i, c in enumerate(cols)}, index=IDX)
    return curves_from(spot, fwd, half)


def test_top_bottom_is_long_the_high_carry_and_short_the_low():
    row = TopBottom(k=1).weights(flat_book().carry).iloc[0]
    assert row["C3"] == pytest.approx(1.0) and row["C0"] == pytest.approx(-1.0)
    assert row[["C1", "C2"]].abs().sum() == pytest.approx(0.0)


def test_weights_are_a_dollar_a_side_and_net_to_zero():
    row = TopBottom(k=2).weights(flat_book().carry).iloc[0]
    assert row[row > 0].sum() == pytest.approx(1.0)
    assert row[row < 0].sum() == pytest.approx(-1.0)
    assert row.sum() == pytest.approx(0.0)


def test_spread_weighting_leans_on_the_wider_carry():
    row = SpreadWeighted().weights(flat_book().carry).iloc[0].abs()
    assert row["C3"] > row["C1"]
    assert row.sum() == pytest.approx(1.0)


def test_sign_weighting_holds_everything_it_can_score():
    row = SignEqualWeight().weights(flat_book().carry).iloc[0]
    assert row.abs().sum() == pytest.approx(1.0)
    assert (row > 0).all()          # every carry is positive in this book


def test_equal_long_ignores_the_ranking_entirely():
    row = EqualLong().weights(flat_book().carry).iloc[0]
    assert np.allclose(row.to_numpy(), 0.25)


def test_buckets_partition_the_cross_section():
    scores = flat_book().carry
    held = sum(Bucket(2, i).weights(scores).iloc[0].abs().gt(0).sum() for i in (1, 2))
    assert held == 4


def test_a_currency_with_no_score_gets_no_weight():
    curves = flat_book()
    scores = curves.carry.copy()
    scores.iloc[0, 2] = np.nan
    assert SignEqualWeight().weights(scores).iloc[0, 2] == 0.0
    assert SignEqualWeight().weights(scores).iloc[0].abs().sum() == pytest.approx(1.0)


def test_momentum_scores_the_return_that_has_already_happened():
    # forward equal to spot, so there is no carry and the excess return is the move
    spot = pd.DataFrame({"A": [1.0, 1.1, 1.1, 1.1, 1.1, 1.1], "B": 1.0}, index=IDX)
    curves = curves_from(spot, spot.copy())
    scores = Momentum().scores(curves)
    assert scores["A"].iloc[1] == pytest.approx(np.log(1.1))
    assert scores["A"].iloc[2] == pytest.approx(0.0)     # the move is over by then


def test_a_longer_lookback_keeps_the_move_in_view():
    spot = pd.DataFrame({"A": [1.0, 1.1, 1.1, 1.1, 1.1, 1.1], "B": 1.0}, index=IDX)
    curves = curves_from(spot, spot.copy())
    assert Momentum(lookback=3).scores(curves)["A"].iloc[3] == pytest.approx(np.log(1.1))


def test_a_lookback_below_one_is_refused():
    with pytest.raises(ValueError, match="at least 1"):
        Momentum(lookback=0)


def test_the_position_in_force_is_the_one_chosen_a_period_earlier():
    book = Book(flat_book(), Carry(), TopBottom(k=1))
    chosen, held = book.weights(), book.holdings()
    pd.testing.assert_frame_equal(held.iloc[1:], chosen.shift(1).iloc[1:])
    assert (held.iloc[0] == 0).all()


def test_perfect_foresight_makes_money_which_proves_the_lag_bites():
    rng = np.random.default_rng(0)
    cols = ["A", "B", "C", "D"]
    idx = pd.date_range("2020-01-31", periods=36, freq="ME")
    spot = pd.DataFrame(
        1.0 + rng.normal(0, 0.02, size=(36, 4)).cumsum(axis=0), index=idx, columns=cols
    )
    curves = curves_from(spot, spot.copy())

    class Oracle(Carry):
        def scores(self, curves):
            return curves.forward_return.shift(-1)      # next period's outcome, today

    honest = Book(curves, Carry(), TopBottom(k=1)).returns().mean()
    cheat = Book(curves, Oracle(), TopBottom(k=1)).returns().mean()
    assert cheat > 0 and cheat > 5 * abs(honest)


def test_a_book_with_no_overlay_is_just_the_weighted_forward_return():
    curves = flat_book()
    book = Book(curves, Carry(), TopBottom(k=1))
    manual = (book.holdings() * curves.forward_return).sum(axis=1, min_count=1)
    pd.testing.assert_series_equal(book.returns(), manual, check_names=False)


def test_costs_only_ever_subtract():
    curves = flat_book(half=0.0005)
    book = Book(curves, Carry(), TopBottom(k=1), costs=BidAskCost(curves))
    gross, net = book.returns(net=False), book.returns(net=True)
    assert (net.dropna() < gross.dropna()).all()


def test_a_half_spread_model_charges_the_roll_and_the_switch():
    curves = flat_book()
    roll = pd.DataFrame(0.0001, index=IDX, columns=curves.currencies)
    outright = pd.DataFrame(0.001, index=IDX, columns=curves.currencies)
    book = Book(curves, Carry(), TopBottom(k=1), costs=HalfSpreadCost(roll, outright))
    charged = book.costs.cost(book.holdings())
    # two legs at a dollar apiece, never switching after the first month
    assert charged.iloc[-1] == pytest.approx(2 * 0.0001)
    assert charged.iloc[1] > charged.iloc[-1]     # the initial switch costs more


def test_turnover_is_zero_when_the_ranking_never_moves():
    book = Book(flat_book(), Carry(), TopBottom(k=1))
    assert book.turnover().iloc[2:].abs().max() == pytest.approx(0.0)


def test_nav_compounds_the_net_series():
    book = Book(flat_book(), Carry(), TopBottom(k=1))
    r = book.returns().fillna(0.0)
    assert book.nav().iloc[-1] == pytest.approx((1.0 + r).prod())


def test_buckets_come_back_side_by_side():
    got = Book(flat_book(), Carry(), TopBottom(k=1)).buckets(2)
    assert list(got.columns) == [1, 2]
    # the high-carry bucket and the low one are not the same series
    assert not np.allclose(got[1].dropna(), got[2].dropna())


def overlay_curves():
    cols = ["A", "B"]
    spot = pd.DataFrame({"A": [1.00] * 6, "B": [1.00] * 6}, index=IDX)
    # A yields more than the dollar and is bought; B yields less and is sold
    fwd = pd.DataFrame({"A": [0.99] * 6, "B": [1.01] * 6}, index=IDX)
    return curves_from(spot, fwd), cols


def panel_smile(cols):
    def frame(value):
        return pd.DataFrame(value, index=IDX, columns=cols)

    return Smile(
        atm=frame(0.12),
        risk_reversal={10: frame(-0.03), 25: frame(-0.02)},
        butterfly={10: frame(0.012), 25: frame(0.005)},
    )


def test_an_overlay_needs_a_smile_and_says_so_at_construction():
    curves, _ = overlay_curves()
    with pytest.raises(ValueError, match="smile"):
        Book(curves, Carry(), TopBottom(k=1), overlay=VerticalSpread(25, 10, "put"))


def test_selling_the_near_rung_lifts_the_book_when_nothing_moves():
    curves, cols = overlay_curves()
    smile = panel_smile(cols)
    plain = Book(curves, Carry(), TopBottom(k=1))
    sold = Book(curves, Carry(), TopBottom(k=1),
                overlay=VerticalSpread(25, 10, "put"), smile=smile)
    # spot never moves, so both options expire worthless and the credit is kept
    assert (sold.returns().dropna() > plain.returns().dropna()).all()


def test_reversing_the_rungs_reverses_the_pickup():
    curves, cols = overlay_curves()
    smile = panel_smile(cols)
    plain = Book(curves, Carry(), TopBottom(k=1)).returns()
    sold = Book(curves, Carry(), TopBottom(k=1),
                overlay=VerticalSpread(25, 10, "put"), smile=smile).returns()
    bought = Book(curves, Carry(), TopBottom(k=1),
                  overlay=VerticalSpread(10, 25, "put"), smile=smile).returns()
    pd.testing.assert_series_equal(sold - plain, plain - bought, check_names=False)


def test_the_overlay_sits_on_the_crash_side_of_each_leg():
    curves, cols = overlay_curves()
    book = Book(curves, Carry(), TopBottom(k=1),
                overlay=VerticalSpread(25, 10, "put"), smile=panel_smile(cols))
    kinds = book.overlay_kinds()
    # A trades at a forward premium so it is bought, and is protected with puts
    assert (kinds["A"].dropna() == "put").all()
    assert (kinds["B"].dropna() == "call").all()
