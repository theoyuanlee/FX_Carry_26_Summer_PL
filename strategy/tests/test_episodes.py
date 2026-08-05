"""Acceptance tests for the frozen evaluation windows and the two base fixes.

Deliberately a SEPARATE file from `test_reconciliation.py`. That runner collects
`test_*` out of its own `globals()`, so adding a case there would turn the
documented "12/12 passed" into "13/13" and invalidate the string quoted in the
README, in agent rule 3, and in `overview.html`. The base's twelve acceptance
tests are the base's contract; these are the episode module's.

What this file enforces:

1. The windows are **frozen**. Exact keys, exact dates. A window silently
   re-picked after seeing a result is the failure mode the whole per-window
   standard exists to prevent, so it is a test, not a convention.
2. `ERAS` really partitions the sample, which is what licenses "this era
   produced X% of the book's return".
3. **The F1 regression.** Every `STRESS` window reports, including the four
   under 120 trading days — and the annualised columns stay blank there.
4. **The F2 guard.** The tenor-indexed roll leg is an exact no-op at the
   committed baseline. This is the assertion that decides whether the cost fix
   may ship at all.
5. The per-leg decomposition reconciles to `gross` at floating-point exactness,
   not "close enough".

Run directly (`python strategy/tests/test_episodes.py`) or under pytest.
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from strategy import fx_utils as fx, run
from strategy.episodes import (ERAS, SHORT_WINDOW_DAYS, STRESS, compare_windows,
                               leg_decomposition, report_windows)

TOL_IDENTITY = 1e-12
TOL_VS_PLAN = 1e-3

SAMPLE_START, SAMPLE_END = "2007-05-01", "2026-06-30"

#: Committed baseline cost figures (plan §15 acceptance, `dafu/outputs/meta.json`,
#: `cesare/outputs/stage3_dynamic_comparison.csv` row ALL_voltgt_net).
BASELINE_COST_DRAG = 0.018146611265764313
BASELINE_TURNOVER = 0.6754702284294828

#: The frozen dates. Duplicated here ON PURPOSE — a test that imports the values
#: it is checking cannot detect an edit to them.
ERAS_FROZEN = {
    "pre-crisis 2007-08": ("2007-05-01", "2008-08-31"),
    "GFC 2008-09": ("2008-09-01", "2009-06-30"),
    "recovery 2009-11": ("2009-07-01", "2011-06-30"),
    "euro crisis 2011-12": ("2011-07-01", "2012-12-31"),
    "taper + EM 2013-16": ("2013-01-01", "2016-12-31"),
    "calm 2017-19": ("2017-01-01", "2019-12-31"),
    "covid 2020": ("2020-01-01", "2020-12-31"),
    "tightening 2021-23": ("2021-01-01", "2023-12-31"),
    "recent 2024-26": ("2024-01-01", "2026-06-30"),
}
STRESS_FROZEN = {
    "gfc_2008": ("2008-09-01", "2009-06-30"),
    "euro_2011": ("2011-07-01", "2012-12-31"),
    "taper_2013": ("2013-05-01", "2013-09-30"),
    "china_em_2015": ("2015-06-01", "2016-02-29"),
    "covid_2020": ("2020-02-01", "2020-04-30"),
    "rates_2022": ("2022-01-01", "2022-10-31"),
    "oil_2026": ("2026-02-01", "2026-05-31"),
    "semis_2026": ("2026-04-01", "2026-06-30"),
}

#: Plan §19.2 acceptance targets: (n_days, cum net return, net max drawdown).
STRESS_TARGETS = {
    "gfc_2008": (217, -0.059, -0.178),
    "euro_2011": (392, -0.051, -0.190),
    "taper_2013": (109, -0.129, -0.191),
    "china_em_2015": (196, -0.052, -0.099),
    "covid_2020": (64, -0.196, -0.240),
    "rates_2022": (216, 0.255, -0.066),
    "oil_2026": (85, 0.101, -0.018),
    "semis_2026": (65, 0.117, -0.018),
}


def test_windows_are_frozen():
    """Exact keys and dates. The lock that stops a window being re-picked."""
    assert list(ERAS) == list(ERAS_FROZEN), "ERAS keys changed"
    assert list(STRESS) == list(STRESS_FROZEN), "STRESS keys changed"
    for name, dates in ERAS_FROZEN.items():
        assert ERAS[name] == dates, f"ERAS[{name!r}] moved: {ERAS[name]} != {dates}"
    for name, dates in STRESS_FROZEN.items():
        assert STRESS[name] == dates, f"STRESS[{name!r}] moved: {STRESS[name]} != {dates}"
    print(f"  windows frozen                 {len(ERAS)} eras, {len(STRESS)} stress")


def test_eras_tile_the_sample():
    """ERAS partitions 2007-05-01 -> 2026-06-30: no gap, no overlap."""
    spans = [(pd.Timestamp(a), pd.Timestamp(z)) for a, z in ERAS.values()]
    assert spans == sorted(spans), "ERAS are not in chronological order"
    assert spans[0][0] == pd.Timestamp(SAMPLE_START)
    assert spans[-1][1] == pd.Timestamp(SAMPLE_END)
    for (_, end), (start, _) in zip(spans, spans[1:]):
        gap = (start - end).days
        assert gap == 1, f"ERAS not contiguous at {end.date()} -> {start.date()} ({gap}d)"
    print("  ERAS tile the sample           no gap, no overlap")


def test_eras_shares_sum_to_total():
    """Per-era shares of P&L sum to 100% — what makes the share column honest."""
    rep = report_windows(run(), ERAS, which="both")
    for basis, grp in rep.groupby("basis"):
        total = grp["share_pnl"].sum()
        assert abs(total - 1.0) < TOL_IDENTITY, f"{basis} shares sum to {total!r}"
    n = rep.groupby("basis")["n_days"].sum().iloc[0]
    assert n == len(run().net.dropna()), f"eras cover {n} days, book has {len(run().net.dropna())}"
    print(f"  ERAS P&L shares sum to 1.0     both bases, {n} days covered")


def test_short_windows_are_populated():
    """F1 REGRESSION. Every STRESS window reports, including the sub-120-day ones.

    Before the `min_obs` passthrough, `summary()` returned an empty (0, 0) frame
    for any window under 120 trading days, so oil 2026 (85d), semis 2026 (65d),
    the COVID crash (64d) and the taper tantrum (109d) were all unreportable —
    every window the desk named personally, plus the second-worst window in the
    sample. That is the defect this asserts against.
    """
    rep = report_windows(run(), STRESS, which="both")
    assert len(rep) == 2 * len(STRESS)
    short = 0
    for _, row in rep.iterrows():
        w = row["window"]
        assert row["n_days"] > 0, f"{w}: no days"
        for col in ("cum_return", "max_drawdown", "worst_day", "hit_rate", "cost_drag"):
            assert pd.notna(row[col]), f"{w}/{row['basis']}: {col} is NaN"
        if row["n_days"] < SHORT_WINDOW_DAYS:
            short += 1
            for col in ("sharpe", "ann_return", "ann_vol"):
                assert pd.isna(row[col]), \
                    f"{w}: annualised {col} quoted off {row['n_days']} days (§6.8)"
        else:
            assert pd.notna(row["sharpe"]), f"{w}: sharpe missing on a long window"
    assert short == 8, f"expected 4 short windows x 2 bases, got {short}"
    print(f"  short windows populated        {len(rep)} rows, {short} with annualised blanked")


def test_stress_table_matches_the_plan():
    """The reproduced STRESS table == the §19.2 acceptance targets."""
    rep = report_windows(run(), STRESS, which="net").set_index("window")
    for name, (n_days, cum, mdd) in STRESS_TARGETS.items():
        row = rep.loc[name]
        assert int(row["n_days"]) == n_days, \
            f"{name}: {int(row['n_days'])} days vs plan {n_days}"
        assert abs(float(row["cum_return"]) - cum) < TOL_VS_PLAN, \
            f"{name}: cum {float(row['cum_return']):.4f} vs plan {cum}"
        assert abs(float(row["max_drawdown"]) - mdd) < TOL_VS_PLAN, \
            f"{name}: mdd {float(row['max_drawdown']):.4f} vs plan {mdd}"
    print(f"  STRESS table == plan §19.2     all {len(STRESS_TARGETS)} windows")


def test_resliced_episode_reconciles():
    """A window's stats match `summary_stats` computed directly on that slice."""
    base = run()
    rep = report_windows(base, ERAS, which="net").set_index("window")
    for name, (start, end) in ERAS.items():
        direct = fx.summary_stats(
            pd.DataFrame({"x": base.net.loc[start:end]}), min_obs=20)
        got, want = float(rep.loc[name, "sharpe"]), float(direct.loc["x", "sharpe"])
        assert abs(got - want) < TOL_IDENTITY, f"{name}: {got} vs direct {want}"
        cum = (1.0 + base.net.loc[start:end].dropna()).prod() - 1.0
        assert abs(float(rep.loc[name, "cum_return"]) - cum) < 1e-9, \
            f"{name}: cum_return does not match compounding"
    print("  resliced stats == direct       all eras, incl. cum_return identity")


def test_leg_decomposition_reconciles():
    """Long/short x carry/spot sums to `gross` at floating-point exactness.

    The plan's provisional figures came from a reconstruction that summed to
    7.32% against a 7.03% book. The requirement is reconciliation, not proximity.
    """
    r = run()
    for freq in (None, "ME", "QE", "YE"):
        d = leg_decomposition(r, freq)
        err = float(d["resid"].abs().max())
        assert err < TOL_IDENTITY, f"freq={freq}: max|resid| {err:.2e}"
        assert len(d) > 0
    daily = leg_decomposition(r, None)
    legs = daily[["carry_long", "carry_short", "spot_long", "spot_short"]]
    ann = legs.mean() * fx.ANN_DAYS
    assert abs(float(daily["total"].sum()) - float(r.gross.dropna().sum())) < TOL_IDENTITY
    assert ann["carry_long"] > 0 and ann["spot_long"] < 0, \
        "expected the long leg to accrue carry and give back spot"
    print(f"  leg split == gross             max|resid| "
          f"{float(leg_decomposition(r, None)['resid'].abs().max()):.2e}; "
          f"carry_long {ann['carry_long']:+.4f} spot_long {ann['spot_long']:+.4f}")


def test_baseline_cost_drag_unchanged():
    """F2 GUARD. The tenor-indexed roll leg is an exact no-op at (1M, ME).

    `roundtrip_cost` used to bill the roll on the rebalance grid rather than the
    forward-tenor grid. The fix may only ship if it changes nothing at the
    committed baseline — every published number depends on it. The structural
    half of the assertion is that at 1M x month-end the roll mask still equals
    the rebalance mask, which is why the numeric half holds.
    """
    r = run()
    assert abs(r.cost_drag - BASELINE_COST_DRAG) < 1e-9, \
        f"cost drag moved: {r.cost_drag:.12f} vs {BASELINE_COST_DRAG:.12f}"
    assert abs(r.turnover - BASELINE_TURNOVER) < 1e-9, \
        f"turnover moved: {r.turnover:.12f} vs {BASELINE_TURNOVER:.12f}"

    w = r.weights.fillna(0.0)
    cols = w.columns.intersection(r.panels.hs_outright.columns)
    dw = w[cols].diff()
    dw.iloc[0] = w[cols].iloc[0]
    changed = dw.abs().sum(axis=1) > 0
    roll = fx.roll_schedule(w[cols], changed, "1M")
    assert roll.equals(changed), \
        f"roll mask != rebalance mask at (1M, ME): {int((roll ^ changed).sum())} days differ"
    print(f"  F2 no-op at baseline           drag {r.cost_drag:.9f}, "
          f"roll mask == rebal mask ({int(roll.sum())} days)")


def test_roll_schedule_follows_the_tenor():
    """Off the baseline the roll cadence follows the tenor, not the rebalance."""
    r = run()
    w = r.weights.fillna(0.0)
    cols = w.columns.intersection(r.panels.hs_outright.columns)
    dw = w[cols].diff()
    dw.iloc[0] = w[cols].iloc[0]
    changed = dw.abs().sum(axis=1) > 0
    counts = {t: int(fx.roll_schedule(w[cols], changed, t).sum())
              for t in ("1M", "3M", "6M", "12M")}
    assert counts["1M"] == int(changed.sum()), "1M must roll on every rebalance"
    for a, b in (("1M", "3M"), ("3M", "6M"), ("6M", "12M")):
        assert counts[a] > counts[b], f"{a} should roll more often than {b}: {counts}"
    assert 18 <= counts["12M"] <= 21, f"12M should roll ~once a year, got {counts['12M']}"
    # And the defect's signature is gone: a longer tenor no longer costs more.
    assert run(tenor="12M").cost_drag < 0.048, "12M drag still at its pre-fix level"
    print(f"  roll cadence follows tenor     {counts}")


def test_short_window_repr():
    """F1b REGRESSION. Echoing a short-window result must not raise."""
    covid = run().reslice(*STRESS["covid_2020"])
    text = repr(covid)
    assert "too short" in text and "2020-02-01" in text, text
    assert covid.summary(benchmark=None).empty, "default min_obs should still refuse"
    assert len(covid.summary(benchmark=None, min_obs=20)) == 2
    print(f"  short-window repr is safe      {text}")


def test_compare_windows_shape():
    """windows x variants for one metric, in window order."""
    base = run()
    table = compare_windows({"baseline": base, "G10": run("G10")}, STRESS,
                            metric="max_drawdown")
    assert list(table.index) == list(STRESS)
    assert list(table.columns) == ["baseline", "G10"]
    assert table.notna().all().all(), "compare_windows left a hole"
    print(f"  compare_windows                {table.shape[0]}x{table.shape[1]}, no holes")


if __name__ == "__main__":
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    print(f"Running {len(tests)} episode tests\n")
    failures = 0
    for t in tests:
        try:
            t()
        except AssertionError as exc:
            failures += 1
            print(f"  FAIL {t.__name__}: {exc}")
    print(f"\n{len(tests) - failures}/{len(tests)} passed")
    sys.exit(1 if failures else 0)
