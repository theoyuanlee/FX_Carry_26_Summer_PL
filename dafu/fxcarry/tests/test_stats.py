import numpy as np
import pandas as pd
import pytest

from fxcarry.stats import (
    HAC,
    FactorModel,
    LinearSDF,
    Performance,
    Realized,
    RollingOLS,
    Shrinkage,
)


def test_sharpe_is_the_annualized_ratio_by_hand():
    r = pd.Series([0.01, -0.005, 0.02, 0.0, 0.015])
    p = Performance(r, periods_per_year=12)
    assert p.sharpe == pytest.approx(r.mean() / r.std() * np.sqrt(12))
    assert p.mean == pytest.approx(r.mean() * 12)
    assert p.volatility == pytest.approx(r.std() * np.sqrt(12))


def test_a_constant_positive_series_never_draws_down():
    assert Performance(pd.Series([0.01] * 10)).max_drawdown == pytest.approx(0.0)


def test_drawdown_is_measured_from_the_running_peak():
    assert Performance(pd.Series([0.5, -0.5])).max_drawdown == pytest.approx(-0.5)


def test_win_rate_and_worst_period_read_off_the_sample():
    r = pd.Series([0.01, -0.02, 0.03, -0.01])
    p = Performance(r)
    assert p.win_rate == pytest.approx(0.5)
    assert p.worst == pytest.approx(-0.02)


def test_cvar_averages_the_tail_and_never_exceeds_the_quantile():
    r = pd.Series(np.arange(-0.10, 0.10, 0.01))
    p = Performance(r)
    assert p.cvar(0.10) == pytest.approx(r.nsmallest(2).mean())
    assert p.cvar(0.10) <= r.quantile(0.10)


def test_a_summary_reports_one_row_per_column():
    frame = pd.DataFrame({"a": [0.01, 0.02, -0.01], "b": [0.0, 0.01, 0.02]})
    table = Performance(frame).summary()
    assert list(table.index) == ["a", "b"]
    assert {"mean", "volatility", "sharpe", "skew", "n_obs"} <= set(table.columns)


def test_hac_at_zero_lags_is_the_plain_sample_covariance():
    rng = np.random.default_rng(1)
    g = rng.normal(size=(200, 2))
    assert np.allclose(HAC(lags=0).covariance(g), np.cov(g.T, bias=True))


def test_hac_widens_the_error_on_a_persistent_series():
    rng = np.random.default_rng(2)
    smooth = pd.Series(rng.normal(size=400)).rolling(20).mean().dropna().reset_index(drop=True)
    assert HAC(lags=12).mean_se(smooth) > HAC(lags=0).mean_se(smooth)


def test_a_t_statistic_is_the_mean_over_its_own_standard_error():
    r = pd.Series([0.01, -0.005, 0.02, 0.0, 0.015] * 10)
    hac = HAC(lags=3)
    assert hac.t_stat(r) == pytest.approx(r.mean() / hac.mean_se(r))


def test_realized_volatility_recovers_a_known_daily_scale():
    idx = pd.date_range("2020-01-01", periods=250, freq="B")
    rng = np.random.default_rng(3)
    daily = pd.DataFrame({"A": rng.normal(0, 0.01, len(idx))}, index=idx)
    vol = Realized().volatility(daily, freq="M")
    assert vol["A"].mean() == pytest.approx(0.01, rel=0.25)
    pd.testing.assert_series_equal(Realized().factor(daily), vol.mean(axis=1))


def test_a_factor_that_is_the_asset_prices_it_exactly():
    rng = np.random.default_rng(4)
    f = pd.Series(rng.normal(0.01, 0.04, 200), name="F")
    assets = pd.DataFrame({"A": 2.0 * f, "B": -1.0 * f})
    fit = FactorModel(assets, f).fit()
    assert fit.loc["A", "F_beta"] == pytest.approx(2.0)
    assert fit.loc["A", "alpha"] == pytest.approx(0.0, abs=1e-12)
    assert fit.loc["A", "r2"] == pytest.approx(1.0)
    assert fit.loc["B", "F_beta"] == pytest.approx(-1.0)


def test_the_sdf_prices_assets_built_to_be_priced():
    rng = np.random.default_rng(5)
    f = pd.Series(rng.normal(0.01, 0.04, 400), name="F")
    assets = pd.DataFrame(
        {f"A{i}": b * f + rng.normal(0, 0.001, 400) for i, b in enumerate([0.5, 1.0, 1.5, 2.0])}
    )
    res = LinearSDF(assets, f).fit()
    assert res.r2 > 0.9
    assert res.pricing_errors.abs().max() < 0.01
    assert res.n_assets == 4 and res.n_factors == 1


def test_rolling_ols_uses_only_the_past():
    idx = pd.date_range("2020-01-31", periods=60, freq="ME")
    x = pd.Series(np.arange(60.0), index=idx)
    y = 3.0 * x + 1.0
    out = RollingOLS(min_periods=5).fit(y, x)
    assert np.isnan(out["beta"].iloc[3])
    assert out["beta"].iloc[-1] == pytest.approx(3.0)
    assert out["alpha"].iloc[-1] == pytest.approx(1.0)


def test_a_rolling_window_forgets_what_an_expanding_one_keeps():
    idx = pd.date_range("2020-01-31", periods=60, freq="ME")
    x = pd.Series(np.arange(60.0), index=idx)
    y = pd.Series(np.where(x < 30, 3.0 * x, 100.0 + 1.0 * x), index=idx)
    expanding = RollingOLS(min_periods=5).fit(y, x)["beta"].iloc[-1]
    windowed = RollingOLS(window=12, min_periods=5).fit(y, x)["beta"].iloc[-1]
    assert windowed == pytest.approx(1.0)
    assert abs(expanding - 1.0) > abs(windowed - 1.0)


def test_shrinkage_pulls_everything_in_when_the_spread_is_all_noise():
    est = pd.Series([0.0, 1.0, 2.0], index=list("abc"))
    out = Shrinkage.cross_section(est, pd.Series([10.0] * 3, index=list("abc")))
    assert out["weight"].min() > 0.99
    assert out["shrunk"].std() < est.std() / 10


def test_shrinkage_leaves_precise_estimates_alone():
    est = pd.Series([0.0, 1.0, 2.0], index=list("abc"))
    out = Shrinkage.cross_section(est, pd.Series([1e-6] * 3, index=list("abc")))
    assert out["weight"].max() < 0.01
    assert np.allclose(out["shrunk"].to_numpy(), est.to_numpy(), atol=1e-4)


def test_blending_respects_its_endpoints():
    assert Shrinkage.blend(1.0, 5.0, 0.0) == pytest.approx(1.0)
    assert Shrinkage.blend(1.0, 5.0, 1.0) == pytest.approx(5.0)
    with pytest.raises(ValueError, match=r"\[0, 1\]"):
        Shrinkage.blend(1.0, 5.0, 1.5)
