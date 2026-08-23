"""The delivered menu — one engine, three books, with the pros and cons of each.

    python final/menu.py          # print the menu, write both CSVs

The desk's condition on 2026-08-12 was that every strategy presented comes with
its pros and cons clearly explained, and that the count stays small. This module
is that menu, made reproducible: it emits `evidence/strategy_menu.csv` (the
whole-sample battery) and `evidence/strategy_menu_by_window.csv` (the same books
across the eight frozen stress windows).

**These are not three strategies.** They are one book at three points on a single
risk-appetite ladder, each strictly more protected than the one above it, and the
ladder is the argument. Presenting three unrelated strategies would invite the
question the project cannot answer — which one is right — where a ladder invites
the question it can: how much protection do you want to pay for.

**There is deliberately no rule for switching between them.** Every
exposure-timing rule this project tested came back null (plan §9, §12, §19.3), so
a switching signal is precisely the thing the evidence says not to claim. The
ladder is a mandate choice the desk makes; it is not a signal we trade.

**Numbers are computed, prose is authored.** Every figure in the CSVs comes from
a live `run()` through the shipped engine, so the menu cannot drift from the
strategy. The pros and cons are written by hand and signed, because they are
editorial judgements — deriving them from a formula would dress an opinion up as
a measurement, which is the one thing this project has consistently refused to do.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

PACKAGE_ROOT = Path(__file__).resolve().parent
if str(PACKAGE_ROOT) not in sys.path:
    sys.path.insert(0, str(PACKAGE_ROOT))

from strategy import run                                         # noqa: E402
from strategy.config import PRESETS                              # noqa: E402
from strategy.episodes import STRESS, report_windows             # noqa: E402

EVIDENCE = PACKAGE_ROOT / "evidence"
OUT = EVIDENCE / "strategy_menu.csv"
OUT_WINDOWS = EVIDENCE / "strategy_menu_by_window.csv"
OUT_MATCHED = EVIDENCE / "strategy_menu_matched_risk.csv"

#: Vol target that brings CORE onto the baseline's realised risk. Solved once
#: by bisection and pinned, so this module stays a report rather than a search;
#: `matched_risk()` asserts the realised vols actually land together.
MATCHED_TARGET = 0.1264

#: The menu, in ladder order — most risk first. The baseline sits in the middle
#: as the REFERENCE line rather than as a fourth choice: it is what the desk is
#: already implicitly comparing against, and leaving it out would make the
#: offensive book's drawdown look like a property of the menu rather than of
#: leverage.
BOOKS = [
    ("OFFENSIVE", "OFFENSIVE", "mandate"),
    ("ALL", "BASELINE (reference)", "reference"),
    ("CORE", "CORE", "mandate"),
    ("DEFENSIVE", "DEFENSIVE", "mandate"),
]

#: Authored, not computed. Each entry states the case for the book and the case
#: against it, and the case against is written first where it is the more
#: important one — the Aug 5 decision was to lead with the caveat rather than let
#: the desk find it.
PROS: dict[str, str] = {
    "OFFENSIVE":
        "Highest return of the three (7.6%/yr net) and by far the best "
        "participation in good states — +40.2% through the 2022 rates selloff "
        "against CORE's +9.2%. Simplest book to explain and to run: no overlays, "
        "no teammate inputs, no option data. Cheapest to build.",
    "BASELINE (reference)":
        "The team's shared baseline and the number every extension in the project "
        "was measured against. Fully costed, fully reproducible, no dependencies.",
    "CORE":
        "Best Calmar of the three (0.211) and the shallowest drawdown (-19.1%, "
        "against the baseline's -29.3%). Halves the negative skew, -0.65 to -0.28. "
        "The only book whose every component cleared the slot rule fixed before "
        "any of them were measured. Levered to the baseline's risk it delivers "
        "MORE return (5.33% vs 5.21%) at a 5.4pp shallower drawdown.",
    "DEFENSIVE":
        "Best on every risk-adjusted ratio in the project: Sharpe 0.5323, Sortino "
        "0.760, Calmar 0.219, CVaR99 0.0189. Shallowest COVID drawdown of the four "
        "books (-8.1% against the baseline's -24.0%) and the smallest loss in the "
        "worst window in the sample.",
}

CONS: dict[str, str] = {
    "OFFENSIVE":
        "The drawdown is the price and it is large: -41.2% whole-sample, -34.0% "
        "through COVID alone. Highest turnover (0.98) and cost drag (2.67%/yr) of "
        "the four. Earns NO risk-adjusted improvement — its Sharpe of 0.4606 is "
        "the baseline's 0.4659 within noise, by construction. This is a leverage "
        "dial, and anyone reading it as an edge has misread it.",
    "BASELINE (reference)":
        "Deepest drawdown of any unlevered book here (-29.3%) and the worst skew "
        "(-0.65). Loses 19.6% through COVID with nothing to cushion it.",
    "CORE":
        "Lowest return per dollar deployed of the three (4.33%/yr) because it runs "
        "at 8.9% vol, not 10%. Adds no statistically significant alpha — the "
        "largest |t| on any rung of the integration ladder is 1.16. And 6.8 of its "
        "7.3pp of drawdown improvement is simply holding less notional, not "
        "selection; the selection alpha is t 0.92. Depends on two teammate inputs "
        "that were re-priced, not rebuilt.",
    "DEFENSIVE":
        "Its extra component FAILED the pre-registered slot rule — the VIX gate "
        "improves only 3 of 6 stress windows measured add-one-in, where the rule "
        "requires 4. It is presented because that decision cost 0.043 of Sharpe "
        "and the desk should be able to price it, NOT because the evidence "
        "promotes it. Gives back the most upside of the three: +5.0% in the 2022 "
        "rates selloff against the baseline's +25.5%. Its whole-sample MaxDD is "
        "identical to CORE's — the gate is fully invested through the drawdown "
        "episode, so only CVaR99 actually moves.",
}

#: When each book is the right mandate. Authored for the same reason.
WHEN: dict[str, str] = {
    "OFFENSIVE": "calm macro, risk-on, drawdown tolerance available",
    "BASELINE (reference)": "not a mandate — the comparison line",
    "CORE": "default / all-weather; the book that ships",
    "DEFENSIVE": "desk judges the macro environment to be stressed",
}

_STATS = ("ann_return", "ann_vol", "sharpe", "sortino", "calmar",
          "max_drawdown", "CVaR_99", "skew", "hit_rate")


def build() -> tuple[pd.DataFrame, pd.DataFrame]:
    """Run every book on the shipped engine and assemble both tables."""
    rows, windows = [], []
    for preset, label, kind in BOOKS:
        r = run(preset)
        s = r.summary(benchmark=None)
        net = s.loc[f"{r.config.name}_net"]
        gross = s.loc[f"{r.config.name}_gross"]

        row = {"book": label, "preset": preset, "kind": kind,
               "when": WHEN[label], "gross_sharpe": float(gross["sharpe"])}
        row.update({k: float(net[k]) for k in _STATS})
        row.update({"turnover": float(r.turnover), "cost_drag": float(r.cost_drag),
                    "n_days": int(net["n_days"]),
                    "pros": PROS[label], "cons": CONS[label]})
        rows.append(row)

        w = report_windows(r, windows=STRESS, which="net")
        w.insert(0, "book", label)
        windows.append(w)

    return pd.DataFrame(rows), pd.concat(windows, ignore_index=True)


def matched_risk() -> pd.DataFrame:
    """CORE levered to the baseline's risk — the desk's 2026-08-05 question.

    The ask was: *lever COMBINED back to the baseline's risk level so it can be
    compared on return rather than on risk-adjusted return.* Until now it was
    never run, and the team's own answer on 2026-08-05 was the concessive one —
    "better per unit of risk, worse per dollar deployed". That framing turns out
    to be an artifact of comparing two books at different risk levels.

    Levered to a matched 11.1% volatility CORE delivers MORE return than the
    baseline (5.33% vs 5.21%) at a 5.4pp shallower drawdown, 13% less CVaR99 and
    less than half the negative skew. Same risk, more return, smaller tail.

    **The leverage is a mandate parameter, not a signal**, and the target was
    chosen with the whole sample in view. That is legitimate for a like-for-like
    comparison — the question is explicitly "at the same risk, which is better" —
    but it would not be legitimate as a trading rule, and it is not offered as one.
    """
    rows = []
    for label, preset, vt in (("ALL baseline", "ALL", None),
                              ("CORE levered to matched risk", "CORE", MATCHED_TARGET)):
        cfg = run(preset).config if vt is None else None
        r = run(preset) if vt is None else run(PRESETS[preset]().with_(vol_target=vt))
        s = r.summary(benchmark=None)
        net = s.loc[f"{r.config.name}_net"]
        rows.append({"book": label, "vol_target": vt or 0.10,
                     **{k: float(net[k]) for k in _STATS},
                     "turnover": float(r.turnover), "cost_drag": float(r.cost_drag)})
    out = pd.DataFrame(rows)

    gap = abs(out.loc[0, "ann_vol"] - out.loc[1, "ann_vol"])
    assert gap < 2e-3, (
        f"the two books are no longer at matched risk ({gap:.4f} apart) — "
        f"re-solve MATCHED_TARGET before quoting this table as like-for-like")
    return out


def main() -> None:
    menu, by_window = build()
    menu.to_csv(OUT, index=False)
    by_window.to_csv(OUT_WINDOWS, index=False)

    show = ["book", "ann_return", "ann_vol", "sharpe", "sortino", "calmar",
            "max_drawdown", "CVaR_99"]
    print(f"\nTHE MENU — one engine, {sum(k == 'mandate' for _, _, k in BOOKS)} books")
    print("=" * 100)
    print(menu[show].to_string(index=False,
                               formatters={c: "{:.4f}".format for c in show[1:]}))
    print("=" * 100)

    # The ladder claim, checked rather than asserted in prose. If this ever stops
    # printing OK the deck's central slide is wrong and needs to be redrawn.
    vols = menu["ann_vol"].tolist()
    cal = menu["calmar"].tolist()
    ladder = vols == sorted(vols, reverse=True) and cal == sorted(cal)
    print(f"  monotone ladder: {'OK' if ladder else 'BROKEN'} — "
          f"vol {' > '.join(f'{v:.3f}' for v in vols)}")
    print(f"  Calmar rises the other way: {' < '.join(f'{c:.3f}' for c in cal)}")

    matched = matched_risk()
    matched.to_csv(OUT_MATCHED, index=False)
    print("\n  AT MATCHED RISK — the 2026-08-05 desk question, answered")
    print("  " + "-" * 96)
    mshow = ["book", "ann_return", "ann_vol", "sharpe", "max_drawdown", "CVaR_99", "skew"]
    print("  " + matched[mshow].to_string(index=False).replace("\n", "\n  "))

    print(f"\n  wrote {OUT.relative_to(PACKAGE_ROOT.parent)}")
    print(f"  wrote {OUT_WINDOWS.relative_to(PACKAGE_ROOT.parent)} "
          f"({len(by_window)} rows, {len(STRESS)} windows x {len(BOOKS)} books)")
    print(f"  wrote {OUT_MATCHED.relative_to(PACKAGE_ROOT.parent)}")
    print("  No switching rule is provided, and that is deliberate: every "
          "exposure-timing rule\n  tested in this project came back null. The "
          "ladder is a mandate choice, not a signal.\n")


if __name__ == "__main__":
    main()
