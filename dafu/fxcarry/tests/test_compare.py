"""Aligning books and scoring them together."""

import numpy as np
import pandas as pd
import pytest

from fxcarry.compare import Comparison


def days(n, start="2010-01-01"):
    return pd.bdate_range(start, periods=n)


@pytest.fixture
def books():
    rng = np.random.default_rng(0)
    idx = days(500)
    base = pd.Series(rng.normal(0.0004, 0.007, 500), index=idx)
    return pd.DataFrame({"baseline": base, "gated": base * 0.6, "noise": base + 0.0002})


def test_alignment_keeps_only_shared_days(books):
    late = books["gated"].iloc[50:]
    comparison = Comparison({"baseline": books["baseline"], "gated": late})
    assert comparison.returns.index[0] == late.index[0]
    assert len(comparison.returns) == len(late)


def test_no_shared_days_is_an_error(books):
    early = books["baseline"].iloc[:100]
    late = books["gated"].iloc[300:]
    with pytest.raises(ValueError, match="share no dates"):
        Comparison({"a": early, "b": late})


def test_the_baseline_has_no_active_return(books):
    relative = Comparison(books, baseline="baseline").relative()
    assert relative.loc["baseline", "active_return"] == pytest.approx(0.0, abs=1e-12)
    assert relative.loc["baseline", "sharpe_delta"] == pytest.approx(0.0, abs=1e-12)
    assert relative.loc["baseline", "beta_to_baseline"] == pytest.approx(1.0)


def test_scaling_a_book_leaves_its_sharpe_alone(books):
    """`gated` is the baseline times a constant, so only its volatility should differ."""
    relative = Comparison(books, baseline="baseline").relative()
    assert relative.loc["gated", "sharpe"] == pytest.approx(relative.loc["baseline", "sharpe"])
    assert relative.loc["gated", "ann_vol"] == pytest.approx(
        0.6 * relative.loc["baseline", "ann_vol"]
    )
    assert relative.loc["gated", "corr_to_baseline"] == pytest.approx(1.0)


def test_rescaling_puts_every_book_on_the_baseline_volatility(books):
    rescaled = Comparison(books, baseline="baseline").rescaled()
    assert rescaled.std().std() == pytest.approx(0.0, abs=1e-12)


def test_an_unknown_baseline_is_refused(books):
    with pytest.raises(ValueError, match="is not one of"):
        Comparison(books, baseline="missing")


def test_save_and_load_round_trip(books, tmp_path):
    path = tmp_path / "books.parquet"
    Comparison(books).save(path)
    reloaded = Comparison.load(path, baseline="baseline")
    # Parquet keeps the dates but not the index's inferred frequency, which carries no data.
    pd.testing.assert_frame_equal(
        reloaded.returns, Comparison(books).returns, check_freq=False
    )


def test_subperiods_split_the_sample(books):
    comparison = Comparison(books)
    windows = {"first": ("2010-01-01", "2010-12-31"), "second": ("2011-01-01", "2011-12-31")}
    table = comparison.subperiods(windows)
    assert list(table.index) == ["first", "second"]
    assert set(table.columns) == set(books.columns)


def test_adding_a_book_realigns(books):
    comparison = Comparison(books[["baseline"]])
    extended = comparison.with_series(later=books["gated"].iloc[100:])
    assert list(extended.returns.columns) == ["baseline", "later"]
    assert len(extended.returns) == len(books) - 100
