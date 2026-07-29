"""Example 1 — the baseline, and how to check you are on it.

Run:  python strategy/examples/01_baseline.py

Start every piece of work here. If these numbers don't match the committed ones,
something in your environment is wrong and nothing downstream can be trusted.
"""

import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from strategy import run

# --- the whole thing --------------------------------------------------------
base = run()                    # ALL 27 names, quintile sort, inverse-vol, 10% vol target

print(base)
print("\nPerformance (gross and net of real bid/ask costs):")
cols = ["ann_return", "ann_vol", "sharpe", "max_drawdown", "skew", "info_ratio"]
print(base.summary()[cols].astype(float).round(4).to_string())

print(f"\nTurnover {base.turnover:.3f} one-sided per rebalance | "
      f"cost drag {base.cost_drag:.2%}/yr | {len(base.universe)} currencies")

# --- the reconciliation check ----------------------------------------------
committed = pd.read_csv(
    Path(__file__).resolve().parents[2] / "cesare/outputs/strategy_summary_stats.csv",
    index_col=0)
got_net = float(base.summary(benchmark=None).loc["ALL_net", "sharpe"])
want_net = float(committed.loc["ALL_net", "sharpe"])
print(f"\nReconciliation: net Sharpe {got_net:.4f} vs committed {want_net:.4f} "
      f"-> {'OK' if abs(got_net - want_net) < 5e-4 else 'MISMATCH'}")

# --- what you get back ------------------------------------------------------
print("\nResult contents:")
print(f"  weights        {base.weights.shape}   what is actually held, daily and signed")
print(f"  weights_unit   {base.weights_unit.shape}   before vol targeting (gross 2)")
print(f"  contrib        {base.contrib.shape}   per-currency P&L; rows sum to `gross`")
print(f"  xret           {base.xret.shape}   = spot_component + carry_component")
print(f"  gross/cost/net  {len(base.net)} days each")

top = base.contrib.sum().sort_values(ascending=False)
print("\nTop 5 P&L contributors:", ", ".join(
    f"{c} {v:.1%}" for c, v in top.head(5).items()))
print("Bottom 5:              ", ", ".join(
    f"{c} {v:.1%}" for c, v in top.tail(5).items()))
