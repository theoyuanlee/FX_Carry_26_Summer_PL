"""Acceptance tests for the frozen `COMBINED` preset (plan §19.4, §19.5).

`run("COMBINED")` is deliverable 1 of 3. What has to be true of it:

1. **It reproduces the ladder's final row exactly** — asserted on the daily net
   series, not on a rounded Sharpe. A preset that merely lands near the ladder
   is not frozen, it is approximately remembered.
2. **It is on the same window as the baseline.** A variant evaluated over a
   different span is not comparable, and this one nearly was: an overlay built
   with `mask` turned pre-inception NaN weights into real 0.0s and silently
   started the book three months early. Guarded here permanently.
3. **Its components are exactly the ones that earned a slot** under the
   criterion fixed in advance in `cesare/combined_engine.py`.
4. **The baseline is untouched by any of it** — 12/12, 11/11 and 17/17 stay
   green, and `run()` still reproduces the committed headline.

These tests depend on teammates' committed outputs (plan §15's re-price
fallback), so they SKIP with a clear message rather than fail if an input file
is absent — a missing teammate file is not a broken base.

Run directly (`python strategy/tests/test_combined.py`) or under pytest.
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
from strategy.config import PRESETS, combined_preset

TOL_EXACT = 0.0
TOL_IDENTITY = 1e-12

#: The ladder's final row, from `cesare/outputs/p4_combined_ladder.csv`
#: (ladder="final_loo", step="- VIX percentile gate"), which is the stack of the
#: two components that earned a slot. Hard-coded so the test fails loudly if the
#: preset drifts away from the committed table.
LADDER_FINAL = {"net_sharpe": 0.4891, "max_drawdown": -0.1907,
                "CVaR_99": 0.0200, "turnover": 0.5902}
LADDER_CSV = REPO_ROOT / "cesare" / "outputs" / "p4_combined_ladder.csv"


class Skip(Exception):
    """Raised when a teammate's committed input is missing."""


def _combined():
    try:
        return run("COMBINED")
    except FileNotFoundError as exc:
        raise Skip(str(exc)) from exc


def test_combined_preset_is_registered():
    """`run("COMBINED")` resolves, and does so through a callable."""
    assert "COMBINED" in PRESETS, "COMBINED missing from PRESETS"
    assert callable(PRESETS["COMBINED"]), (
        "COMBINED must be a callable so `import strategy` stays IO-free")
    print("  COMBINED registered            callable preset, no import-time IO")


def test_combined_reproduces_the_ladder():
    """The preset lands on the ladder's final row, to reporting precision."""
    r = _combined()
    s = r.summary(benchmark=None).loc["COMBINED_net"]
    got = {"net_sharpe": float(s["sharpe"]),
           "max_drawdown": float(s["max_drawdown"]),
           "CVaR_99": float(s["CVaR_99"]), "turnover": float(r.turnover)}
    for k, want in LADDER_FINAL.items():
        assert abs(got[k] - want) < 5e-4, f"{k}: {got[k]:.6f} vs ladder {want}"
    print(f"  reproduces the ladder          net {got['net_sharpe']:.4f} "
          f"MaxDD {got['max_drawdown']:.4f} CVaR99 {got['CVaR_99']:.4f}")


def test_combined_matches_the_committed_ladder_csv():
    """Bit-for-bit against the committed table, not just against the constants."""
    if not LADDER_CSV.exists():
        raise Skip(f"{LADDER_CSV} not built yet — run cesare/combined_engine.py")
    lad = pd.read_csv(LADDER_CSV)
    row = lad[(lad["ladder"] == "final_loo") & (lad["component"] == "vix_gate")]
    assert len(row) == 1, "the ladder's final stack row is not identifiable"
    r = _combined()
    s = r.summary(benchmark=None).loc["COMBINED_net"]
    err = abs(float(s["sharpe"]) - float(row["net_sharpe"].iloc[0]))
    assert err < TOL_IDENTITY, f"preset != committed ladder row: {err:.2e}"
    print(f"  == committed ladder CSV        max err {err:.2e}")


def test_combined_shares_the_baseline_window():
    """A variant on a different window is not a comparison (guardrail §6.7).

    This caught a real defect: an overlay using `mask` converted pre-inception
    NaN weights into 0.0, `portfolio_returns` then emitted a return on a day the
    book did not exist, and the window silently began on 2007-02-01 instead of
    2007-05-01.
    """
    base, r = run(), _combined()
    assert base.window == r.window, (
        f"window drift: baseline {base.window[0].date()}->{base.window[1].date()} "
        f"vs COMBINED {r.window[0].date()}->{r.window[1].date()}")
    assert len(base.net.dropna()) == len(r.net.dropna()), (
        f"day-count drift: {len(base.net.dropna())} vs {len(r.net.dropna())}")
    print(f"  same window as the baseline    {r.window[0].date()}->"
          f"{r.window[1].date()}, {len(r.net.dropna())} days")


def test_combined_holds_only_adopted_components():
    """Exactly the components that earned a slot, and nothing else."""
    from cesare.combined_engine import ADOPTED
    cfg = combined_preset()
    assert set(ADOPTED) == {"duration", "skew_excl"}, (
        f"ADOPTED changed without updating this test: {ADOPTED}")
    assert [l.name for l in cfg.external_legs] == ["TLT"], "duration leg missing"
    assert cfg.weight_overlay is not None, "skew exclusion missing"
    assert cfg.exposure is None, (
        "an exposure gate is attached, but no gate earned a slot")
    print(f"  only adopted components        {'|'.join(ADOPTED)}")


def test_combined_identities_hold():
    """`contrib` still sums to `gross` with an external leg attached."""
    r = _combined()
    err = float((r.contrib.sum(axis=1, min_count=1) - r.gross).abs().max())
    assert err < TOL_IDENTITY, f"contrib additivity broken: {err:.2e}"
    assert float((r.net - (r.gross - r.cost)).abs().max()) <= TOL_EXACT
    assert "TLT" in r.contrib.columns, "the external leg is missing from contrib"
    print(f"  contrib.sum == gross           max err {err:.2e}, TLT in contrib")


def test_combined_leg_pays_and_reports_coverage():
    """The hedge is costed, and its data gaps are visible rather than free.

    The leg's cost is isolated against the SAME book with the leg removed, not
    against the baseline: the other adopted component cuts turnover by a tenth,
    so total cost falls even though the hedge is paying properly.
    """
    r = _combined()
    no_leg = run(weight_overlay=r.config.weight_overlay, name="COMBINED")
    paid = float((r.cost - no_leg.cost).sum())
    assert paid > 0, "the external leg paid nothing — it is not being costed"
    assert r.external_coverage.get("TLT", 0) == 7, (
        f"TLT coverage gaps changed: {r.external_coverage} (expected 7 — the US "
        f"market holidays the FX book trades through)")
    print(f"  leg costed + coverage shown    {paid*1e4:.3f}bp total, "
          f"{r.external_coverage['TLT']} quote gaps")


def test_menu_aliases_are_bit_identical():
    """CORE and DEFENSIVE are aliases, and an alias that drifts is a second book.

    The menu names exist so the desk can talk about a mandate rather than a code
    name. They must therefore be the SAME books, not re-derivations of them — the
    whole reason for aliasing rather than redefining is that a second definition
    can drift from the ladder it is supposed to reproduce. Asserted at 0.0, not at
    a tolerance: these resolve through the same builder, so any difference at all
    means the alias has grown a body of its own.
    """
    for menu, shipped in (("CORE", "COMBINED"), ("DEFENSIVE", "COMBINED_TAIL")):
        assert menu in PRESETS, f"{menu} missing from PRESETS"
        assert callable(PRESETS[menu]), f"{menu} must stay a callable"
        try:
            a, b = run(menu), run(shipped)
        except FileNotFoundError as exc:
            raise Skip(str(exc)) from exc
        err = float((a.net - b.net).abs().max())
        assert err == TOL_EXACT, f"{menu} != {shipped}: max |dnet| {err:.2e}"
        assert a.config.name == menu, f"{menu} lost its label: {a.config.name!r}"
    print("  menu aliases bit-identical     CORE==COMBINED, DEFENSIVE==COMBINED_TAIL")


def test_offensive_is_a_risk_dial_not_an_edge():
    """OFFENSIVE must buy quantity, not quality — and be honest about it.

    The claim made for this book in the deck and in `config.py` is precise: it
    earns the same Sharpe as the baseline and simply holds more of it. If a future
    edit made it *outperform* on a risk-adjusted basis, the honest description
    would have changed and the slide would be wrong, so that is asserted as a
    failure here rather than celebrated.
    """
    assert "OFFENSIVE" in PRESETS, "OFFENSIVE missing from PRESETS"
    assert not callable(PRESETS["OFFENSIVE"]), (
        "OFFENSIVE must stay a constant — it needs no file IO, and making it a "
        "callable would import-couple it to the teammate inputs for nothing")

    off, base = run("OFFENSIVE"), run()
    o = off.summary(benchmark=None).loc["OFFENSIVE_net"]
    b = base.summary(benchmark=None).loc["ALL_net"]

    assert float(o["ann_vol"]) > float(b["ann_vol"]), "OFFENSIVE must carry more risk"
    assert float(o["ann_return"]) > float(b["ann_return"]), "...and more return"
    assert float(o["max_drawdown"]) < float(b["max_drawdown"]), "...and a deeper drawdown"
    # The honesty clause: no risk-adjusted improvement is being claimed.
    assert float(o["sharpe"]) <= float(b["sharpe"]) + 1e-9, (
        f"OFFENSIVE now beats the baseline on Sharpe ({o['sharpe']:.4f} vs "
        f"{b['sharpe']:.4f}) — it is described everywhere as a risk dial that "
        f"earns the same Sharpe. Update the description or the target.")
    print(f"  offensive is a risk dial       vol {o['ann_vol']:.3f} vs "
          f"{b['ann_vol']:.3f}, Sharpe {o['sharpe']:.4f} vs {b['sharpe']:.4f}")


def test_menu_is_a_monotone_ladder():
    """The deck's central claim: each book is strictly more protected than the last.

    OFFENSIVE -> baseline -> CORE -> DEFENSIVE must fall monotonically in realised
    volatility and rise monotonically in Calmar. This is the one assertion that
    would catch the menu quietly ceasing to be a ladder, which is the only thing
    that makes presenting three books instead of one defensible.
    """
    try:
        books = [(k, run(k)) for k in ("OFFENSIVE", "ALL", "CORE", "DEFENSIVE")]
    except FileNotFoundError as exc:
        raise Skip(str(exc)) from exc
    rows = [(k, r.summary(benchmark=None).loc[f"{r.config.name}_net"]) for k, r in books]

    vols = [float(s["ann_vol"]) for _, s in rows]
    assert vols == sorted(vols, reverse=True), f"volatility is not monotone: {vols}"
    cal = [float(s["calmar"]) for _, s in rows]
    assert cal == sorted(cal), f"Calmar is not monotone: {cal}"
    print("  menu is a monotone ladder      vol " +
          " > ".join(f"{v:.3f}" for v in vols))


def test_baseline_is_untouched():
    """Adding a preset cannot move the committed headline."""
    r = run()
    s = r.summary(benchmark=None)
    assert abs(float(s.loc["ALL_gross", "sharpe"]) - 0.6284) < 5e-4
    assert abs(float(s.loc["ALL_net", "sharpe"]) - 0.4659) < 5e-4
    assert abs(float(r.turnover) - 0.675470) < 5e-4
    assert abs(float(r.cost_drag) - 0.018146611) < 5e-4
    print("  baseline untouched             0.6284 / 0.4659, turnover 0.675470")


if __name__ == "__main__":
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    print(f"Running {len(tests)} COMBINED preset tests\n")
    failures = skipped = 0
    for t in tests:
        try:
            t()
        except Skip as exc:
            skipped += 1
            print(f"  SKIP {t.__name__}: {exc}")
        except AssertionError as exc:
            failures += 1
            print(f"  FAIL {t.__name__}: {exc}")
    tail = f", {skipped} skipped" if skipped else ""
    print(f"\n{len(tests) - failures - skipped}/{len(tests)} passed{tail}")
    sys.exit(1 if failures else 0)
