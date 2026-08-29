"""Acceptance tests for the base strategy.

The contract this file enforces:

1. The default config reproduces the project's committed headline numbers
   (`evidence/strategy_summary_stats.csv`) to floating-point noise. If
   this fails, every downstream extension's comparison is invalid.
2. The result's internal identities hold exactly — per-currency contributions
   sum to the book return, and the return decomposition sums to the total.
   Attribution notebooks assert these too; they must be true here first.
3. The overlay hooks are no-ops at their neutral settings, so an extension
   measures its own effect and not a plumbing artefact.

Run directly (`python strategy/tests/test_reconciliation.py`) or under pytest.
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

# VENDORED: `parents[2]` (the repo root) in the shared base -> `parents[1]`,
# the `final/` package root, which is the only thing this suite needs on the
# path. Position 0 is deliberate: it guarantees `import strategy` resolves to
# the vendored engine even when a repo-root `strategy/` is also importable.
PACKAGE_ROOT = Path(__file__).resolve().parents[1]
if str(PACKAGE_ROOT) not in sys.path:
    sys.path.insert(0, str(PACKAGE_ROOT))

from strategy import ALL_BASELINE, G10_BASELINE, StrategyConfig, fx_utils as fx, run

COMMITTED = PACKAGE_ROOT / "evidence" / "strategy_summary_stats.csv"

# Tolerances: the pipeline should be bit-for-bit identical to the notebook, but
# the committed CSV is round-tripped through text, so allow float32-ish slack
# against the file and demand exactness for internal identities.
TOL_VS_CSV = 5e-4
TOL_IDENTITY = 1e-12


def _committed() -> pd.DataFrame:
    return pd.read_csv(COMMITTED, index_col=0)


def _sharpe(result, which: str) -> float:
    s = result.summary(benchmark=None)
    return float(s.loc[[i for i in s.index if i.endswith(which)][0], "sharpe"])


def test_all_book_matches_committed():
    """The default ALL book == the published combined track."""
    r = run()
    ref = _committed()
    for which, row in (("gross", "ALL_gross"), ("net", "ALL_net")):
        got, want = _sharpe(r, which), ref.loc[row, "sharpe"]
        assert abs(got - want) < TOL_VS_CSV, f"{row}: {got:.6f} vs committed {want:.6f}"
    stats = r.summary(benchmark=None)
    for which, row in (("gross", "ALL_gross"), ("net", "ALL_net")):
        idx = [i for i in stats.index if i.endswith(which)][0]
        for col in ("ann_return", "ann_vol", "max_drawdown", "skew"):
            got, want = float(stats.loc[idx, col]), ref.loc[row, col]
            assert abs(got - want) < TOL_VS_CSV, f"{row}.{col}: {got} vs {want}"
    assert len(r.universe) == 27
    assert str(r.window[0].date()) == "2007-05-01"
    print(f"  ALL   gross {_sharpe(r,'gross'):.4f} net {_sharpe(r,'net'):.4f}  "
          f"(committed {ref.loc['ALL_gross','sharpe']:.4f} / "
          f"{ref.loc['ALL_net','sharpe']:.4f})")


def test_g10_book_matches_committed():
    """The G10 preset == the published G10 track."""
    r = run("G10")
    ref = _committed()
    for which, row in (("gross", "G10_gross"), ("net", "G10_net")):
        got, want = _sharpe(r, which), ref.loc[row, "sharpe"]
        assert abs(got - want) < TOL_VS_CSV, f"{row}: {got:.6f} vs committed {want:.6f}"
    assert len(r.universe) == 9
    print(f"  G10   gross {_sharpe(r,'gross'):.4f} net {_sharpe(r,'net'):.4f}  "
          f"(committed {ref.loc['G10_gross','sharpe']:.4f} / "
          f"{ref.loc['G10_net','sharpe']:.4f})")


def test_contributions_sum_to_book_return():
    """Σ per-currency contribution == gross, exactly (attribution depends on it)."""
    r = run()
    diff = (r.contrib.sum(axis=1, min_count=1) - r.gross).abs().max()
    assert diff < TOL_IDENTITY, f"contrib additivity broken: max err {diff:.2e}"
    print(f"  contrib.sum == gross           max err {diff:.2e}")


def test_return_decomposition_is_additive():
    """xret == spot_component + carry_component, exactly."""
    r = run()
    recomposed = r.spot_component + r.carry_component
    diff = (recomposed - r.xret).abs().max().max()
    assert diff < TOL_IDENTITY, f"decomposition broken: max err {diff:.2e}"
    print(f"  spot + carry == xret           max err {diff:.2e}")


def test_net_is_gross_minus_cost():
    r = run()
    diff = (r.net - (r.gross - r.cost)).abs().max()
    assert diff < TOL_IDENTITY, f"net != gross - cost: max err {diff:.2e}"
    assert (r.cost.dropna() >= 0).all(), "costs must be non-negative"
    print(f"  net == gross - cost            max err {diff:.2e}")


def test_unit_exposure_is_a_noop():
    """A constant exposure of 1.0 must leave the book untouched.

    This is the guard that an overlay measures its own effect: if the plumbing
    changed the answer at neutral settings, every gate would look like alpha.
    """
    base = run()
    ones = pd.Series(1.0, index=base.panels.xret.index)
    gated = run(exposure=ones)
    diff = (gated.net - base.net).abs().max()
    assert diff < TOL_IDENTITY, f"unit exposure changed the book: max err {diff:.2e}"
    print(f"  exposure=1.0 no-op             max err {diff:.2e}")


def test_identity_weight_overlay_is_a_noop():
    base = run()
    passthrough = run(weight_overlay=lambda w, ctx: w)
    diff = (passthrough.net - base.net).abs().max()
    assert diff < TOL_IDENTITY, f"identity overlay changed the book: max err {diff:.2e}"
    print(f"  identity weight_overlay no-op  max err {diff:.2e}")


def test_halved_exposure_halves_risk_and_pays_costs():
    """Sanity-check the direction of the exposure hook, and that it is not free."""
    base = run()
    half = run(exposure=pd.Series(0.5, index=base.panels.xret.index))
    vol_ratio = half.net.std() / base.net.std()
    assert 0.45 < vol_ratio < 0.55, f"halving exposure gave vol ratio {vol_ratio:.3f}"
    assert half.cost.sum() < base.cost.sum(), "smaller book should cost less to trade"
    assert half.cost.sum() > 0, "an overlaid book must still pay transaction costs"
    print(f"  exposure=0.5 vol ratio {vol_ratio:.3f}, costs scale with notional")


def test_post_hoc_repricing_matches_a_rebuild():
    """`cost_from_weights` / `returns_from_weights` == rebuilding with the knob set.

    Arjun's cost and lag stresses re-price a stored weight panel instead of
    rebuilding ~80 books; the two paths must agree or the audit is measuring
    something else.
    """
    base = run()
    rebuilt = run(cost_multiple=2.0)
    reprice = base.cost_from_weights(base.weights, multiple=2.0)
    diff = (reprice - rebuilt.cost).abs().max()
    assert diff < TOL_IDENTITY, f"cost re-pricing mismatch: {diff:.2e}"

    rebuilt_lag = run(extra_lag=2)
    reprice_r = base.returns_from_weights(base.weights.shift(2))
    diff_r = (reprice_r.dropna() - rebuilt_lag.gross.reindex(reprice_r.dropna().index)
              ).abs().max()
    assert diff_r < TOL_IDENTITY, f"lag re-pricing mismatch: {diff_r:.2e}"
    print(f"  post-hoc re-pricing == rebuild max err {max(diff, diff_r):.2e}")


def test_config_knobs_change_the_book():
    """Each swept knob must actually move the result (guards silent no-ops)."""
    base_sharpe = _sharpe(run(), "net")
    for override in ({"weighting": "equal"}, {"n_buckets": 3}, {"rebal": "QE"},
                     {"vol_target": 0.15}, {"max_leg_share": 1.00},
                     {"vol_window": 120}, {"extra_lag": 3},
                     {"universe": "G10"}, {"tenor": "3M"}):
        got = _sharpe(run(**override), "net")
        assert not np.isclose(got, base_sharpe, atol=1e-9), \
            f"{override} had no effect on the book"
    print("  all 9 config knobs move the book")


def test_vol_target_none_leaves_unit_book():
    r = run(vol_target=None)
    assert (r.weights.fillna(0) == r.weights_unit.fillna(0)).all().all()
    gross_leverage = r.weights.abs().sum(axis=1).dropna()
    assert abs(gross_leverage[gross_leverage > 0].median() - 2.0) < 1e-9, \
        "unit book should be gross 2 (1 per leg)"
    print("  vol_target=None -> unit gross-2 book")


def test_explicit_universe_and_reslice():
    dropped = run(universe=[c for c in run().universe if c != "TRY"], name="ex-TRY")
    assert "TRY" not in dropped.universe and len(dropped.universe) == 26
    crisis = run().reslice("2008-01-01", "2009-06-30")
    assert crisis.window[0] == pd.Timestamp("2008-01-01")
    assert len(crisis.net) < 400
    print(f"  universe edit + reslice ok (ex-TRY net "
          f"{_sharpe(dropped,'net'):.3f}, 2008-09 net {_sharpe(crisis,'net'):.3f})")


if __name__ == "__main__":
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    print(f"Running {len(tests)} acceptance tests against {COMMITTED.name}\n")
    failures = 0
    for t in tests:
        try:
            t()
        except AssertionError as exc:
            failures += 1
            print(f"  FAIL {t.__name__}: {exc}")
    print(f"\n{len(tests) - failures}/{len(tests)} passed")
    sys.exit(1 if failures else 0)
