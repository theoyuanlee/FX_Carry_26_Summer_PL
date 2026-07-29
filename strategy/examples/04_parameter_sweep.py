"""Example 4 — robustness sweeps on the base book  (Arjun's pattern).

Run:  python strategy/examples/04_parameter_sweep.py

Two techniques:

1. REBUILD sweeps — vary a construction knob and re-run. Panels are cached, so
   ~80 rebuilds is a coffee break, not an afternoon.

2. POST-HOC re-pricing — for cost and implementation-lag stresses you do NOT
   need to rebuild at all. `result.cost_from_weights(w, multiple)` and
   `result.returns_from_weights(w.shift(lag))` re-price the stored weight panel,
   and are asserted to agree with a full rebuild in the test suite.
"""

import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from strategy import run


def net_sharpe(res) -> float:
    s = res.summary(benchmark=None)
    return float(s.loc[[i for i in s.index if i.endswith("_net")][0], "sharpe"])


base = run()
bar = net_sharpe(base)
print(f"Baseline net Sharpe {bar:.4f} — every cell below is measured against it.\n")

# --- 1. one-knob-at-a-time sweeps ------------------------------------------
sweeps = {
    "n_buckets": [3, 4, 5, 6],
    "vol_window": [20, 40, 60, 90, 120],
    "max_leg_share": [0.25, 0.33, 0.40, 0.50, 1.00],
    "rebal": ["W", "2W", "ME", "QE"],
    "vol_target": [0.06, 0.08, 0.10, 0.12, 0.15],
    "weighting": ["equal", "inv_vol", "erc"],
}
for knob, values in sweeps.items():
    cells = {v: net_sharpe(run(**{knob: v})) for v in values}
    line = "  ".join(f"{v}: {s:.3f}" for v, s in cells.items())
    spread = max(cells.values()) - min(cells.values())
    print(f"{knob:>14} | {line}   (spread {spread:.3f})")

# --- 2. jackknife: how much does the result depend on one name? -------------
print("\nJackknife — net Sharpe with each currency removed (5 most damaging):")
jk = {c: net_sharpe(run(universe=[x for x in base.universe if x != c]))
      for c in base.universe}
jk_s = pd.Series(jk).sort_values()
for c, s in jk_s.head(5).items():
    print(f"  drop {c}: {s:.3f}  ({s - bar:+.3f})")
print(f"  most helpful to drop: {jk_s.index[-1]} -> {jk_s.iloc[-1]:.3f} "
      f"({jk_s.iloc[-1] - bar:+.3f})")

# --- 3. cost stress, WITHOUT rebuilding ------------------------------------
print("\nCost stress (post-hoc re-pricing of the same weights):")
for m in (1.0, 1.5, 2.0, 3.0, 5.0):
    net = base.gross - base.cost_from_weights(base.weights, multiple=m)
    sh = net.mean() / net.std() * (252 ** 0.5)
    print(f"  {m:>3}x spreads: net Sharpe {sh:.3f}")

# --- 4. implementation-lag stress, WITHOUT rebuilding ----------------------
print("\nImplementation-lag stress (extra days between signal and execution):")
for lag in (0, 1, 2, 3, 5):
    w = base.weights.shift(lag) if lag else base.weights
    net = base.returns_from_weights(w) - base.cost_from_weights(w)
    sh = net.mean() / net.std() * (252 ** 0.5)
    print(f"  +{lag}d lag: net Sharpe {sh:.3f}")

# --- 5. two-dimensional grid ------------------------------------------------
print("\nvol_window x rebal grid (net Sharpe):")
grid = pd.DataFrame(
    {rb: {vw: net_sharpe(run(vol_window=vw, rebal=rb))
          for vw in (20, 40, 60, 90, 120)}
     for rb in ("W", "2W", "ME", "QE")})
print(grid.round(3).to_string())
print("\nRead the grid for plateaus, not peaks: an isolated maximum is a warning,")
print("not a setting. Report the spread alongside the headline number.")
