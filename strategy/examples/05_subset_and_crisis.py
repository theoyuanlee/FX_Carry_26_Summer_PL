"""Example 5 — editing the universe and studying one episode.

Run:  python strategy/examples/05_subset_and_crisis.py

Covers the two most common "I just want to look at X" requests:
  * change who is in the book (drop a name, hand-pick a basket, G10 vs EM);
  * zoom in on a period (2008, COVID) without re-estimating anything.

Important distinction:
  `run(start=..., end=...)`   builds the book, then reports on that window.
  `result.reslice(...)`       re-slices an already-built book — cheaper, and
                              identical, because trailing windows still use the
                              data before the start date. That is what you want
                              for a subperiod study: the strategy did not know
                              in 2008 that you would only look at 2008.
"""

import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from strategy import run


def stats(res, label):
    s = res.summary(benchmark=None)
    net = s.loc[[i for i in s.index if i.endswith("_net")][0]]
    return {"label": label, "n_ccy": len(res.universe), "n_days": int(net["n_days"]),
            "net_sharpe": net["sharpe"], "ann_return": net["ann_return"],
            "max_dd": net["max_drawdown"], "skew": net["skew"]}


base = run()
all_names = base.universe

# --- 1. who is in the book --------------------------------------------------
books = [
    stats(base, "ALL (27)"),
    stats(run("G10"), "G10 only (9)"),
    stats(run("EM"), "EM only (18)"),
    stats(run(universe=[c for c in all_names if c != "TRY"]), "ALL ex-TRY"),
    stats(run(universe=[c for c in all_names if c not in ("TRY", "BRL", "ZAR")]),
          "ALL ex high-carry EM"),
    stats(run(universe=["AUD", "NZD", "NOK", "SEK", "JPY", "CHF"]),
          "hand-picked G6 basket"),
    # exclude=() keeps the pegs the project normally drops — a deliberate study,
    # not the default, and the reason `exclude` is a knob rather than hardcoded.
    stats(run(universe="ALL", exclude=("CNY",)), "ALL + pegged HKD/DKK"),
]
print("Universe variations (net of costs, full window):\n")
print(pd.DataFrame(books).set_index("label").astype(float).round(4).to_string())
print("\nRead these carefully before quoting one. Adding the pegs 'improves' the")
print("Sharpe only because a pegged currency has near-zero vol, so inverse-vol")
print("weighting hands it a huge, un-tradable position — which is exactly why")
print("HKD/DKK are excluded by default (plan §5.1). Dropping TRY or the high-carry")
print("EM names likewise flatters the book by removing realised crash risk after")
print("the fact. A universe edit needs an economic reason, not a better number.")

# --- 2. one episode at a time ----------------------------------------------
episodes = {
    "GFC 2008-09": ("2008-01-01", "2009-06-30"),
    "Euro crisis 2011-12": ("2011-06-01", "2012-12-31"),
    "China/EM 2015-16": ("2015-06-01", "2016-06-30"),
    "COVID 2020": ("2020-01-01", "2020-12-31"),
    "Rates shock 2022": ("2022-01-01", "2022-12-31"),
    "Recent 2023-26": ("2023-01-01", "2026-06-30"),
}
print("\nThe same book, by episode (reslice — no rebuild, no re-estimation):\n")
rows = [stats(base.reslice(lo, hi), name) for name, (lo, hi) in episodes.items()]
print(pd.DataFrame(rows).set_index("label").astype(float).round(4).to_string())

# --- 3. what drove one episode ---------------------------------------------
gfc = base.reslice("2008-01-01", "2009-06-30")
contrib = gfc.contrib.sum().sort_values()
print("\nGFC P&L by currency (worst 5 / best 5):")
print("  worst:", ", ".join(f"{c} {v:.1%}" for c, v in contrib.head(5).items()))
print("  best: ", ", ".join(f"{c} {v:.1%}" for c, v in contrib.tail(5).items()))

split = pd.DataFrame({
    "spot": (gfc.weights.reindex_like(gfc.spot_component) * gfc.spot_component
             ).sum(axis=1).sum(),
    "carry accrual": (gfc.weights.reindex_like(gfc.carry_component) *
                      gfc.carry_component).sum(axis=1).sum(),
}, index=["GFC total"])
print("\nSpot vs carry split of the GFC P&L (log units):")
print(split.round(4).to_string())
print("\nCarry kept accruing while spot collapsed — the crash-risk premium the")
print("whole project is about. `spot_component` and `carry_component` always")
print("sum to `xret` exactly, so this split is exact rather than approximate.")
