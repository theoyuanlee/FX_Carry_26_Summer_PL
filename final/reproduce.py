"""Reproduce the headline table. One command, no arguments, no configuration.

    python final/reproduce.py

Runs the four books from the vendored engine and vendored data, asserts every
published number, and prints the headline table and the component verdicts.
**Exits non-zero if anything has moved**, so this doubles as the smoke test a
reader can run six months from now to find out whether the package still stands
up.

Takes a few minutes: `run("COMBINED")` builds the baseline twice (the component
registry re-prices the base to fit the hedge ratio), and nothing here is cached
between books on purpose — a reproduction that reuses state is not a
reproduction.

What it does NOT print, deliberately: D2's 1.69 Sharpe. That result is real and
is written up in `report/08_volatility_risk_premium.md`, but it is monthly, on a
21-name option universe, and gross of option bid/ask, so putting it in a table
beside costed daily books would manufacture exactly the false comparability the
whole evidence layer is built to prevent. It has a row in the verdict table,
where the basis is stated.
"""

from __future__ import annotations

import sys
import time
from pathlib import Path

PACKAGE_ROOT = Path(__file__).resolve().parent
if str(PACKAGE_ROOT) not in sys.path:
    sys.path.insert(0, str(PACKAGE_ROOT))

from strategy import run
from strategy.episodes import STRESS, report_windows

#: The published numbers, and the tolerance each is asserted at. These are the
#: contract: if a change moves one of them, that is a deliberate decision to be
#: propagated everywhere, not a rounding difference to be waved through.
#: Sources: evidence/strategy_summary_stats.csv (ALL, G10) and
#: evidence/p4_combined_ladder.csv (COMBINED = final_loo -vix; COMBINED_TAIL =
#: final rung 3).
TARGETS = {
    "ALL": {"gross_sharpe": 0.6284, "net_sharpe": 0.4659,
            "turnover": 0.675470, "cost_drag": 0.018146611},
    "G10": {"gross_sharpe": 0.1669, "net_sharpe": 0.1191},
    "COMBINED": {"gross_sharpe": 0.6331, "net_sharpe": 0.4891,
                 "max_drawdown": -0.1907, "CVaR_99": 0.0200, "turnover": 0.5902},
    "COMBINED_TAIL": {"gross_sharpe": 0.6808, "net_sharpe": 0.5323,
                      "max_drawdown": -0.1907, "CVaR_99": 0.0189, "turnover": 0.6051},
    # The delivered menu. CORE and DEFENSIVE are aliases, so they are asserted
    # against the SAME numbers as the books they alias -- that identity is the
    # point of checking them here rather than trusting the alias.
    "OFFENSIVE": {"gross_sharpe": 0.6217, "net_sharpe": 0.4606,
                  "max_drawdown": -0.4124, "CVaR_99": 0.0430, "turnover": 0.9785},
    "CORE": {"gross_sharpe": 0.6331, "net_sharpe": 0.4891,
             "max_drawdown": -0.1907, "CVaR_99": 0.0200, "turnover": 0.5902},
    "DEFENSIVE": {"gross_sharpe": 0.6808, "net_sharpe": 0.5323,
                  "max_drawdown": -0.1907, "CVaR_99": 0.0189, "turnover": 0.6051},
}

LABELS = {
    "ALL": "run()            baseline, 27 currencies",
    "G10": 'run("G10")       9 currencies',
    "COMBINED": 'run("COMBINED")  THE STRATEGY — baseline + duration hedge + bad-skew exclusion',
    "COMBINED_TAIL": 'run("COMBINED_TAIL")  NOT SHIPPED — the documented alternative (+ VIX gate)',
    "OFFENSIVE": 'run("OFFENSIVE")  MENU — no overlays, 15% vol target; calm-macro mandate',
    "CORE": 'run("CORE")       MENU — the shipped book under its menu name (== COMBINED)',
    "DEFENSIVE": 'run("DEFENSIVE")  MENU — stress mandate (== COMBINED_TAIL)',
}

TOL = 5e-4


def _stats(result, preset: str) -> dict:
    s = result.summary(benchmark=None)
    g, n = s.loc[f"{preset}_gross"], s.loc[f"{preset}_net"]
    return {"gross_sharpe": float(g["sharpe"]), "net_sharpe": float(n["sharpe"]),
            "ann_return": float(n["ann_return"]), "ann_vol": float(n["ann_vol"]),
            "max_drawdown": float(n["max_drawdown"]), "CVaR_99": float(n["CVaR_99"]),
            "skew": float(n["skew"]), "turnover": float(result.turnover),
            "cost_drag": float(result.cost_drag), "n_days": int(n["n_days"])}


def main() -> int:
    t0 = time.time()
    print(f"\n{'=' * 96}\nFX CARRY — reproducing the headline table")
    print(f"package: {PACKAGE_ROOT}\n{'=' * 96}")

    books, failures = {}, []
    for preset in TARGETS:
        print(f"  running {preset} ...", end="", flush=True)
        try:
            books[preset] = _stats(run(preset), preset)
            print(" done")
        except FileNotFoundError as exc:
            print(" FAILED")
            failures.append(f"{preset}: {exc}")

    if failures:
        print("\nCould not build every book:")
        for f in failures:
            print(f"  {f}")
        return 1

    # ---- headline table ---------------------------------------------------
    print(f"\n{'-' * 96}\nHEADLINE\n{'-' * 96}")
    print(f"{'Book':<20} {'Gross':>8} {'Net':>8} {'AnnRet':>8} {'AnnVol':>8} "
          f"{'MaxDD':>9} {'CVaR99':>8} {'Skew':>7} {'Turnover':>9} {'Drag':>7}")
    for preset, s in books.items():
        print(f"{preset:<20} {s['gross_sharpe']:>8.4f} {s['net_sharpe']:>8.4f} "
              f"{s['ann_return']:>7.2%} {s['ann_vol']:>8.2%} {s['max_drawdown']:>9.2%} "
              f"{s['CVaR_99']:>8.4f} {s['skew']:>7.2f} {s['turnover']:>9.4f} "
              f"{s['cost_drag']:>6.2%}")
    print()
    for preset in books:
        print(f"  {LABELS[preset]}")

    # ---- assertions -------------------------------------------------------
    print(f"\n{'-' * 96}\nCHECKING AGAINST THE PUBLISHED NUMBERS\n{'-' * 96}")
    drift = []
    for preset, wanted in TARGETS.items():
        for key, want in wanted.items():
            got = books[preset][key]
            ok = abs(got - want) < TOL
            if not ok:
                drift.append(f"{preset}.{key}: {got:.6f} != {want} (published)")
            print(f"  {'OK  ' if ok else 'DRIFT'} {preset:<14} {key:<14} "
                  f"{got:>12.6f}   published {want}")

    # ---- per window, because whole-sample alone is not a result -----------
    print(f"\n{'-' * 96}\nTHE STRATEGY PER STRESS WINDOW (net; guardrail §6.8)\n{'-' * 96}")
    w = report_windows(run("COMBINED"), STRESS, which="net")
    cols = [c for c in ("window", "start", "end", "n_days", "cum_return",
                        "max_drawdown", "worst_day", "sharpe") if c in w.columns]
    print(w[cols].to_string(index=False) if cols else w.to_string())
    print("\n  Annualised ratios are blank under 120 trading days by design — annualising a Sharpe")
    print("  off 64 days of COVID is noise wearing a decimal point.")

    # ---- the verdict table ------------------------------------------------
    import verdicts
    verdicts.main()

    # ---- the shape of the result, in one paragraph ------------------------
    base, comb = books["ALL"], books["COMBINED"]
    print(f"{'-' * 96}\nWHAT THE STRATEGY ACTUALLY BUYS\n{'-' * 96}")
    print(f"  Net Sharpe moves {base['net_sharpe']:.4f} -> {comb['net_sharpe']:.4f}, which is not "
          f"significant and is not the point.")
    print(f"  MaxDD  {base['max_drawdown']:.2%} -> {comb['max_drawdown']:.2%}   "
          f"({(comb['max_drawdown'] - base['max_drawdown']) * 100:+.2f}pp)")
    print(f"  CVaR99 {base['CVaR_99']:.4f} -> {comb['CVaR_99']:.4f}   "
          f"({comb['CVaR_99'] / base['CVaR_99'] - 1:+.1%})")
    print(f"  Skew   {base['skew']:.2f} -> {comb['skew']:.2f}")
    print(f"  Vol    {base['ann_vol']:.2%} -> {comb['ann_vol']:.2%}  <- the combined book runs at "
          f"8.8%, not the 10% target,")
    print("         so part of the drawdown improvement is a lower risk level, not better selection.")
    print("  Most of the rest is de-risking rather than selection: see VERDICTS.md and")
    print("  evidence/p4_selection_vs_derisking.csv. What selection genuinely buys is skew.\n")

    elapsed = time.time() - t0
    if drift:
        print(f"{'=' * 96}\nFAILED — {len(drift)} published number(s) moved:")
        for d in drift:
            print(f"  {d}")
        print("\nA number moving is either a bug or a deliberate change. If deliberate, it must be")
        print(f"propagated to evidence/, report/ and VERDICTS.md before this passes again.\n{'=' * 96}")
        return 1

    print(f"{'=' * 96}\nREPRODUCED — every published number matches, in {elapsed:.0f}s.")
    print("Next: README.md for the conventions, VERDICTS.md for what was kept and dropped,")
    print(f"report/ for the full write-up.\n{'=' * 96}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
