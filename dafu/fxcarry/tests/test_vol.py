import pandas as pd
import pytest

from fxcarry.catalog import Catalog
from fxcarry.quotes import FrameSource
from fxcarry.vol import Smile, VolSurface


def test_unpacking_the_smile_round_trips_to_the_quotes():
    s = Smile(atm=0.10, risk_reversal={25: -0.02}, butterfly={25: 0.005})
    call, put = s.vol(25, "call"), s.vol(25, "put")
    assert call - put == pytest.approx(-0.02)
    assert (call + put) / 2 - 0.10 == pytest.approx(0.005)


def test_no_delta_means_at_the_money_on_either_side():
    s = Smile(atm=0.10, risk_reversal={25: -0.02}, butterfly={25: 0.005})
    assert s.vol() == pytest.approx(0.10)
    assert s.vol(side="put") == pytest.approx(0.10)


def test_an_unquoted_delta_is_refused_rather_than_interpolated():
    s = Smile(atm=0.10, risk_reversal={25: -0.02}, butterfly={25: 0.005})
    with pytest.raises(KeyError):
        s.vol(15, "call")


def test_an_unknown_side_is_refused():
    s = Smile(atm=0.10, risk_reversal={25: -0.02}, butterfly={25: 0.005})
    with pytest.raises(ValueError, match="straddle"):
        s.vol(25, "straddle")


def test_deltas_are_reported_in_quoted_order():
    s = Smile(atm=0.10, risk_reversal={25: -0.02, 10: -0.03},
              butterfly={25: 0.005, 10: 0.012})
    assert s.deltas == (10, 25)


def test_a_smile_can_hold_a_whole_history():
    idx = pd.date_range("2020-01-31", periods=3, freq="ME")
    s = Smile(
        atm=pd.Series([0.10, 0.11, 0.12], index=idx),
        risk_reversal={25: pd.Series([-0.02] * 3, index=idx)},
        butterfly={25: pd.Series([0.005] * 3, index=idx)},
    )
    call = s.vol(25, "call")
    assert isinstance(call, pd.Series) and len(call) == 3
    assert call.iloc[1] == pytest.approx(0.11 + 0.005 - 0.01)


def vol_frame():
    dates = pd.date_range("2020-01-01", periods=31, freq="D")
    rows = []
    for pair, atm, rr in [("EURUSD", 8.0, -1.0), ("USDJPY", 9.0, -2.0)]:
        for date in dates:
            rows += [
                {"ticker": f"{pair}V1M BGN Curncy", "date": date,
                 "field": "PX_LAST", "value": atm},
                {"ticker": f"{pair}25R1M BGN Curncy", "date": date,
                 "field": "PX_LAST", "value": rr},
                {"ticker": f"{pair}25B1M BGN Curncy", "date": date,
                 "field": "PX_LAST", "value": 0.5},
            ]
    return pd.DataFrame(rows)


def surface():
    return VolSurface.from_source(FrameSource(vol_frame()), Catalog.default())


def test_quoted_vol_points_arrive_as_decimals():
    assert surface().smile("EUR", "1M", freq="M").vol().iloc[0] == pytest.approx(0.08)


def test_the_wings_are_oriented_to_the_foreign_currency():
    surf = surface()
    eur = surf.smile("EUR", "1M", freq="M")     # EURUSD: base is the euro
    jpy = surf.smile("JPY", "1M", freq="M")     # USDJPY: base is the dollar
    # a euro call is the quoted call, so the quoted risk reversal stands
    assert (eur.vol(25, "call") - eur.vol(25, "put")).iloc[0] == pytest.approx(-0.01)
    # a yen call is the quoted put, so the sign of the risk reversal turns over
    assert (jpy.vol(25, "call") - jpy.vol(25, "put")).iloc[0] == pytest.approx(+0.02)


def test_orientation_leaves_the_butterfly_alone():
    surf = surface()
    for iso in ("EUR", "JPY"):
        s = surf.smile(iso, "1M", freq="M")
        curvature = (s.vol(25, "call") + s.vol(25, "put")) / 2 - s.vol()
        assert curvature.iloc[0] == pytest.approx(0.005)


def test_the_atm_panel_spans_currencies():
    panel = surface().atm_panel("1M", freq="M")
    assert list(panel.columns) == ["EUR", "JPY"]
    assert panel.loc["2020-01-31", "JPY"] == pytest.approx(0.09)


def test_asking_for_a_currency_with_no_surface_says_so():
    with pytest.raises(KeyError, match="ZAR"):
        surface().smile("ZAR", "1M")


def test_a_panel_smile_spans_currencies_and_keeps_each_orientation():
    panel = surface().panel_smile("1M", freq="M")
    assert list(panel.atm.columns) == ["EUR", "JPY"]
    assert panel.deltas == (25,)
    rr = panel.vol(25, "call") - panel.vol(25, "put")
    assert rr.loc["2020-01-31", "EUR"] == pytest.approx(-0.01)
    assert rr.loc["2020-01-31", "JPY"] == pytest.approx(+0.02)


def test_a_panel_smile_agrees_with_the_single_currency_one():
    surf = surface()
    panel = surf.panel_smile("1M", freq="M")
    one = surf.smile("EUR", "1M", freq="M")
    pd.testing.assert_series_equal(
        panel.vol(25, "put")["EUR"], one.vol(25, "put"), check_names=False
    )


def test_a_panel_smile_can_be_narrowed_to_chosen_currencies():
    assert list(surface().panel_smile("1M", freq="M", currencies=["JPY"]).atm.columns) == ["JPY"]
