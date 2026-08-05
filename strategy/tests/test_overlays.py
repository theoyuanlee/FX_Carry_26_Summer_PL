"""Acceptance tests for the composition layer and `ExternalLeg` (plan §19.4).

The contract this file enforces:

1. **Everything added in v1.2.0 is an exact no-op at its neutral setting.**
   `external_legs=()`, `compose_exposure()` and `compose_overlays()` must leave
   the book bit-identical, because otherwise the combined-engine ladder measures
   plumbing rather than components. Asserted to 0.0e+00, not to a tolerance.
2. **A leg earns exactly `Σ w·r` and pays exactly `Σ|Δw|·cost_bps/1e4`** — with
   the weight sampled on the rebalance grid and lagged one period, so a hedge
   ratio estimated at month-end t cannot trade on the information that produced
   it.
3. **`compose_overlays` refuses a gross increase.** That assertion is the whole
   composition contract: an overlay that re-normalises back up undoes the gate
   that ran before it and then takes credit for its drawdown improvement.
4. **`contrib.sum(axis=1) == gross` survives a leg being attached** — the
   attribution guarantee must not quietly lapse the moment someone bolts on a
   bond.

A separate file from `test_reconciliation.py` on purpose: that runner collects
`test_*` from its own `globals()`, so adding cases there would turn the
documented "12/12 passed" — quoted in the README, in agent rule 3 and in
`cesare/presentations/overview.html` — into "17/17".

Run directly (`python strategy/tests/test_overlays.py`) or under pytest.
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from strategy import run
from strategy.overlays import (ExternalLeg, compose_exposure, compose_overlays)

TOL_EXACT = 0.0
TOL_IDENTITY = 1e-12


def _base():
    return run()


def _max_abs(a: pd.Series, b: pd.Series) -> float:
    return float((a - b).abs().max())


# ---------------------------------------------------------------------------
# 1. No-ops
# ---------------------------------------------------------------------------

def test_external_legs_default_is_a_noop():
    """`external_legs=()` leaves gross, cost and net bit-identical."""
    a, b = _base(), run(external_legs=())
    errs = [_max_abs(getattr(a, k), getattr(b, k)) for k in ("gross", "cost", "net")]
    assert max(errs) <= TOL_EXACT, f"external_legs=() moved the book: {errs}"
    assert b.external.empty, "no legs should leave `external` empty"
    print(f"  external_legs=() no-op         max err {max(errs):.2e}")


def test_compose_exposure_empty_is_a_noop():
    """`compose_exposure()` with no gates == fully invested, exactly."""
    a, b = _base(), run(exposure=compose_exposure(), name="ALL")
    err = _max_abs(a.net, b.net)
    assert err <= TOL_EXACT, f"empty compose_exposure moved the book: {err:.2e}"
    print(f"  compose_exposure() no-op       max err {err:.2e}")


def test_compose_overlays_empty_is_a_noop():
    """`compose_overlays()` with no overlays == the identity, exactly."""
    a, b = _base(), run(weight_overlay=compose_overlays(), name="ALL")
    err = _max_abs(a.net, b.net)
    assert err <= TOL_EXACT, f"empty compose_overlays moved the book: {err:.2e}"
    print(f"  compose_overlays() no-op       max err {err:.2e}")


def test_baseline_reconciliation_survives_v120():
    """The four headline numbers are untouched by the new machinery."""
    r = _base()
    stats = r.summary(benchmark=None)
    got = {"gross": float(stats.iloc[0]["sharpe"]), "net": float(stats.iloc[1]["sharpe"]),
           "turnover": float(r.turnover), "drag": float(r.cost_drag)}
    want = {"gross": 0.6284, "net": 0.4659, "turnover": 0.675470, "drag": 0.018146611}
    for k, v in want.items():
        assert abs(got[k] - v) < 5e-4, f"{k}: {got[k]:.6f} vs {v}"
    print(f"  baseline unchanged             gross {got['gross']:.4f} net {got['net']:.4f} "
          f"turnover {got['turnover']:.6f} drag {got['drag']:.9f}")


# ---------------------------------------------------------------------------
# 2. compose_exposure semantics
# ---------------------------------------------------------------------------

def test_compose_exposure_is_a_commutative_product():
    """Gates multiply, and the order they are passed in cannot matter."""
    idx = pd.date_range("2010-01-01", periods=400, freq="B")
    g1 = pd.Series(np.where(np.arange(400) % 3 == 0, 0.5, 1.0), index=idx)
    g2 = pd.Series(np.where(np.arange(400) % 5 == 0, 0.25, 1.0), index=idx)
    ab, ba = compose_exposure(g1, g2), compose_exposure(g2, g1)
    assert _max_abs(ab, g1 * g2) <= TOL_IDENTITY, "not the product"
    assert _max_abs(ab, ba) <= TOL_IDENTITY, "composition is order-dependent"
    both = ab[(g1 == 0.5) & (g2 == 0.25)]
    assert len(both) and np.allclose(both, 0.125), "two vetoes must compound"
    print(f"  compose_exposure product       order-free, {len(both)} double-veto days")


def test_compose_exposure_treats_a_short_gate_as_invested():
    """Where one gate has no opinion the other one decides, alone.

    The `fx_utils.exposure_scalar` convention: a missing signal is not a reason
    to be out of the market. Getting this backwards would let a late-starting
    gate silently zero the years before it.
    """
    idx = pd.date_range("2010-01-01", periods=200, freq="B")
    early = pd.Series(0.5, index=idx)
    late = pd.Series(0.5, index=idx[100:])
    out = compose_exposure(early, late)
    assert list(out.index) == list(idx), "output must span the union of inputs"
    assert np.allclose(out.iloc[:100], 0.5), "the silent gate must not de-risk"
    assert np.allclose(out.iloc[100:], 0.25), "both gates must apply once live"
    print(f"  short gate reads as invested   {100} days at 0.5, {100} at 0.25")


def test_late_gate_leaves_pre_history_bit_identical():
    """End-to-end: a gate starting in 2015 cannot change 2007-2014 by a cent.

    This is the property that matters — a model fitted from 2015 must not be
    handed a free 'avoided 2008'. `core._apply_exposure` fills pre-history with
    1.0; this asserts it on the book itself rather than on the helper.
    """
    base = _base()
    gate = pd.Series(0.5, index=base.gross.loc["2015-01-01":].index)
    gated = run(exposure=compose_exposure(gate), name="ALL")
    pre = base.net.loc[:"2014-12-31"]
    err = _max_abs(pre, gated.net.loc[:"2014-12-31"])
    assert err <= TOL_EXACT, f"a 2015 gate moved pre-2015 returns: {err:.2e}"
    post = _max_abs(base.net.loc["2015-06-01":], gated.net.loc["2015-06-01":])
    assert post > 0, "the gate never took effect"
    print(f"  late gate leaves pre-history   {len(pre)} days identical (0.00e+00)")


def test_compose_exposure_clips():
    """`floor`/`cap` bound the product; the default floor forbids a sign flip."""
    idx = pd.date_range("2010-01-01", periods=10, freq="B")
    out = compose_exposure(pd.Series(-2.0, index=idx))
    assert np.allclose(out, 0.0), "default floor=0 must block a negative exposure"
    capped = compose_exposure(pd.Series(3.0, index=idx), cap=1.0)
    assert np.allclose(capped, 1.0), "cap must bind"
    print("  compose_exposure clipping      floor blocks sign flip, cap binds")


# ---------------------------------------------------------------------------
# 3. compose_overlays semantics
# ---------------------------------------------------------------------------

def _trim(factor: float, name: str):
    def overlay(weights, ctx):
        return weights * factor
    overlay.__name__ = name
    return overlay


def test_compose_overlays_chains_left_to_right():
    """Two trims compose multiplicatively and both are actually applied."""
    chained = run(weight_overlay=compose_overlays(_trim(0.5, "half"),
                                                  _trim(0.5, "half_again")),
                  name="quarter")
    direct = run(weight_overlay=_trim(0.25, "quarter"), name="quarter")
    err = _max_abs(chained.net, direct.net)
    assert err <= TOL_IDENTITY, f"chain != single equivalent trim: {err:.2e}"
    print(f"  compose_overlays chaining      0.5*0.5 == 0.25, err {err:.2e}")


def test_compose_overlays_rejects_a_gross_increase():
    """The contract: overlays scale down, never re-normalise back up."""
    try:
        run(weight_overlay=compose_overlays(_trim(1.5, "lever_up")), name="bad")
    except ValueError as exc:
        assert "increased gross exposure" in str(exc), f"wrong error: {exc}"
        print("  gross-non-increasing enforced  ValueError raised as required")
        return
    raise AssertionError("an overlay that levers up was allowed through")


def test_compose_overlays_sees_the_same_ctx():
    """Every step receives the base book's ctx, not the running weights."""
    seen = []

    def probe(weights, ctx):
        seen.append(float(ctx.weights_unit.abs().sum(axis=1).max()))
        return weights * 0.5

    run(weight_overlay=compose_overlays(probe, probe), name="probe")
    assert len(seen) == 2 and seen[0] == seen[1], (
        f"ctx differed between steps: {seen}")
    print(f"  compose_overlays shares ctx    both steps saw gross {seen[0]:.4f}")


# ---------------------------------------------------------------------------
# 4. ExternalLeg
# ---------------------------------------------------------------------------

def _synthetic_leg(base, weight, cost_bps=0.0, name="synth"):
    """A deterministic +1bp/day instrument, so w·r is checkable by hand."""
    rets = pd.Series(0.0001, index=base.gross.index, name=name)
    return ExternalLeg(returns=rets, weight=weight, cost_bps=cost_bps, name=name)


def test_external_leg_adds_w_times_r_exactly():
    """gross(with leg) - gross(base) == w·r, to floating-point exactness."""
    base = _base()
    leg = _synthetic_leg(base, weight=0.25)
    r = run(external_legs=(leg,), name="ALL")
    delta = (r.gross - base.gross).dropna()
    assert np.allclose(delta, 0.25 * 0.0001, atol=1e-18), "leg P&L is wrong"
    assert _max_abs(r.cost, base.cost) <= TOL_EXACT, "a 0bp leg must be free"
    print(f"  leg earns w*r                  {len(delta)} days at {0.25*1e-4:.2e}")


def test_external_leg_pays_its_own_cost():
    """cost delta == Σ|Δw|·cost_bps/1e4, inception trade included."""
    base = _base()
    idx = base.gross.index
    w = pd.Series(0.0, index=idx)
    w.loc[idx[idx >= "2015-01-01"]] = 0.5          # one step, mid-sample
    leg = _synthetic_leg(base, weight=w, cost_bps=10.0)
    r = run(external_legs=(leg,), name="ALL")
    paid = float((r.cost - base.cost).sum())
    # |Delta w| = 0.5 at the single step (the position starts flat, so the
    # inception trade itself is zero-sized).
    assert abs(paid - 0.5 * 10.0 / 1e4) < 1e-12, f"charged {paid:.8f}"
    print(f"  leg pays |dw|*bps              charged {paid*1e4:.4f}bp for a 0.5 step")


def test_external_leg_weight_is_lagged():
    """A weight known at month-end t is effective at t+1, never at t."""
    base = _base()
    idx = base.gross.index
    switch = pd.Timestamp("2015-01-30")             # a month-end trading day
    w = pd.Series(0.0, index=idx)
    w.loc[idx >= switch] = 1.0
    leg = _synthetic_leg(base, weight=w)
    r = run(external_legs=(leg,), name="ALL")
    delta = (r.gross - base.gross).dropna()
    assert abs(float(delta.loc[switch])) < 1e-18, (
        "the leg traded on the day its weight was set — lookahead")
    live = delta[delta.abs() > 0]
    assert len(live), "the leg never turned on"
    first = live.index[0]
    assert first > switch, f"leg went live on {first.date()}, not after {switch.date()}"
    assert (first - switch).days <= 7, (
        f"leg took until {first.date()} to go live — more than one rebalance lag")
    print(f"  leg weight is lagged           set {switch.date()}, live {first.date()}")


def test_contrib_still_sums_to_gross_with_a_leg():
    """The attribution guarantee survives an added instrument."""
    base = _base()
    r = run(external_legs=(_synthetic_leg(base, weight=0.25),), name="ALL")
    err = float((r.contrib.sum(axis=1, min_count=1) - r.gross).abs().max())
    assert err < TOL_IDENTITY, f"contrib additivity broken with a leg: {err:.2e}"
    assert "synth" in r.contrib.columns, "the leg is missing from contrib"
    print(f"  contrib.sum == gross w/ leg    max err {err:.2e}")


def test_external_leg_missing_quotes_are_counted():
    """A day the leg holds but has no quote earns nothing — and is reported."""
    base = _base()
    rets = pd.Series(0.0001, index=base.gross.index, name="gappy")
    holes = base.gross.index[100:110]
    rets.loc[holes] = np.nan
    r = run(external_legs=(ExternalLeg(returns=rets, weight=1.0, name="gappy"),),
            name="ALL")
    assert r.external_coverage["gappy"] == len(holes), (
        f"coverage gap miscounted: {r.external_coverage}")
    assert np.allclose(r.external.loc[holes, "gappy"].dropna(), 0.0)
    print(f"  leg coverage gaps reported     {r.external_coverage['gappy']} silent-zero days")


def test_external_leg_rejects_duplicate_names():
    """Duplicate leg names would double-count in `contrib`."""
    base = _base()
    a = _synthetic_leg(base, 0.1, name="dup")
    try:
        run(external_legs=(a, a), name="ALL")
    except ValueError as exc:
        assert "unique" in str(exc), f"wrong error: {exc}"
        print("  duplicate leg names rejected   ValueError raised as required")
        return
    raise AssertionError("duplicate leg names were allowed")


if __name__ == "__main__":
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    print(f"Running {len(tests)} overlay/external-leg tests\n")
    failures = 0
    for t in tests:
        try:
            t()
        except AssertionError as exc:
            failures += 1
            print(f"  FAIL {t.__name__}: {exc}")
    print(f"\n{len(tests) - failures}/{len(tests)} passed")
    sys.exit(1 if failures else 0)
