import numpy as np
import pandas as pd
import pytest

from fxcarry.quotes import FrameSource, ParquetSource, Quotes

LABELS = {"EURUSD Curncy": "EUR", "USDJPY Curncy": "JPY"}


def long_frame(tickers=("EURUSD Curncy", "USDJPY Curncy")):
    dates = pd.date_range("2020-01-01", periods=40, freq="D")
    rows = []
    for i, tk in enumerate(tickers):
        base = 1.10 + i
        for step, date in enumerate(dates):
            mid = base + step / 1000
            rows += [
                {"ticker": tk, "date": date, "field": "PX_LAST", "value": mid},
                {"ticker": tk, "date": date, "field": "PX_BID", "value": mid - 0.001},
                {"ticker": tk, "date": date, "field": "PX_ASK", "value": mid + 0.001},
            ]
    return pd.DataFrame(rows)


def test_quotes_come_back_aligned_and_labelled():
    q = FrameSource(long_frame()).quotes(LABELS)
    assert list(q.columns) == ["EUR", "JPY"]
    assert q.mid.index.equals(q.bid.index) and q.mid.index.equals(q.ask.index)
    assert (q.bid < q.mid).all().all() and (q.mid < q.ask).all().all()


def test_resampling_takes_the_last_print_in_the_period():
    daily = FrameSource(long_frame()).quotes(LABELS)
    monthly = FrameSource(long_frame()).quotes(LABELS, freq="M")
    assert len(monthly.index) == 2
    assert monthly.mid.loc["2020-01-31", "EUR"] == pytest.approx(
        daily.mid.loc["2020-01-31", "EUR"]
    )


def test_inverting_twice_is_the_identity():
    q = FrameSource(long_frame()).quotes(LABELS)
    back = q.invert().invert()
    pd.testing.assert_frame_equal(back.mid, q.mid)
    pd.testing.assert_frame_equal(back.bid, q.bid)
    pd.testing.assert_frame_equal(back.ask, q.ask)


def test_inverting_swaps_the_sides_so_the_spread_stays_open():
    q = FrameSource(long_frame()).quotes(LABELS)
    inv = q.invert(["JPY"])
    assert (inv.bid["JPY"] < inv.ask["JPY"]).all()
    assert inv.bid["JPY"].iloc[0] == pytest.approx(1.0 / q.ask["JPY"].iloc[0])
    pd.testing.assert_series_equal(inv.bid["EUR"], q.bid["EUR"])   # untouched


def test_crossed_flags_only_the_broken_cell():
    q = FrameSource(long_frame()).quotes(LABELS)
    bad = q.bid.copy()
    bad.iloc[3, 0] = 99.0
    flags = Quotes(q.mid, bad, q.ask).crossed()
    assert flags.iloc[3, 0] and flags.to_numpy().sum() == 1


def test_apply_only_ever_meets_matching_sides():
    q = FrameSource(long_frame()).quotes(LABELS)
    scaled = Quotes(q.mid * 10, q.bid * 10, q.ask * 10)
    seen = []

    def record(a, b):
        seen.append((a.iloc[0, 0], b.iloc[0, 0]))
        return a + b

    q.apply(record, scaled)
    assert len(seen) == 3
    assert all(b == pytest.approx(10 * a) for a, b in seen)


def test_half_spread_is_relative_to_mid_by_default():
    q = FrameSource(long_frame()).quotes(LABELS)
    absolute = q.half_spread(relative=False)
    assert absolute.iloc[0, 0] == pytest.approx(0.001)
    assert q.half_spread().iloc[0, 0] == pytest.approx(0.001 / q.mid.iloc[0, 0])


def test_panel_and_series_read_single_fields():
    src = FrameSource(long_frame())
    panel = src.panel(LABELS, field="PX_BID", freq="M")
    assert list(panel.columns) == ["EUR", "JPY"] and len(panel) == 2
    s = src.series("EURUSD Curncy", freq="M")
    assert isinstance(s, pd.Series) and len(s) == 2


def test_a_missing_side_is_an_error_not_a_silent_gap():
    frame = long_frame()
    frame = frame[frame["field"] != "PX_ASK"]
    with pytest.raises(ValueError, match="PX_ASK"):
        FrameSource(frame).quotes(LABELS)


def test_a_frame_that_is_not_long_is_refused_at_the_door():
    with pytest.raises(ValueError, match="ticker"):
        FrameSource(pd.DataFrame({"EUR": [1.0], "JPY": [2.0]}))


def test_coverage_reports_first_last_and_count():
    q = FrameSource(long_frame()).quotes(LABELS)
    holed = q.mid.copy()
    holed.iloc[:5, 0] = np.nan
    cov = Quotes(holed, q.bid, q.ask).coverage()
    assert cov.loc["EUR", "n_obs"] == 35
    assert cov.loc["EUR", "first_valid"] == q.index[5]


def test_a_later_parquet_wins_where_two_pulls_disagree(tmp_path):
    early = long_frame()
    late = early.copy()
    late.loc[late["field"] == "PX_LAST", "value"] = 99.0
    (a, b) = tmp_path / "a.parquet", tmp_path / "b.parquet"
    early.to_parquet(a)
    late.to_parquet(b)
    q = ParquetSource(a, b).quotes(LABELS)
    assert (q.mid == 99.0).all().all()
    # and the other order restores the original
    assert ParquetSource(b, a).quotes(LABELS).mid.iloc[0, 0] != 99.0
