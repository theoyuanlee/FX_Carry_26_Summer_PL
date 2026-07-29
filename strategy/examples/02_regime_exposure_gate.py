"""Example 2 — a macro/regime gate on the base book  (Vidhi's pattern).

Run:  python strategy/examples/02_regime_exposure_gate.py

The pattern: your model produces a `pd.Series` of exposure multipliers
(1.0 = fully invested, 0.5 = half risk, 0.0 = flat) and you hand it to the base
via `exposure=`. The base samples it on the rebalance grid, lags it one period,
and scales the *weights* — so the gate pays the transaction costs of the trades
it triggers. That last point is what makes two people's gates comparable.

Anything can produce the series: a percentile rule on VIX (below), an HMM, a
logistic regression on macro features, a hand-drawn crisis calendar. The base
does not care, as long as the value at date t uses only information known at t.
"""

import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from strategy import fx_utils as fx, run

base = run()

# --- Gate A: a trailing-percentile VIX rule (fx_utils.exposure_scalar) ------
# Half exposure when VIX sits in the top 20% of its trailing 3-year range.
vix = fx.load_wide("global_risk")["VIX"]
gate_vix = fx.exposure_scalar(vix, lookback=756, q=0.80, low_mult=0.5)

# --- Gate B: the Stage-6 composite regime (VIX + FX implied vol + EMBI) -----
atm = fx.vol_surface_panel("ATM", "1M").mean(axis=1).rename("FXvol")
indicators = pd.concat([vix, atm, fx.load_em_risk()], axis=1).dropna(how="all")
regimes = fx.regime_classify(indicators)["regime"]
gate_regime = regimes.map({"Low": 1.0, "Moderate": 1.0, "Crisis": 0.5}).dropna()

# --- Gate C: your own model's output ----------------------------------------
# Whatever you build, it just needs to look like this: a dated Series of floats.
gate_custom = pd.Series(1.0, index=base.panels.xret.index).where(
    base.panels.xret.index.year != 2008, 0.25)          # toy: de-risk through 2008

# --- run them all on the SAME base ------------------------------------------
variants = {
    "baseline": base,
    "vix_gate": run(exposure=gate_vix, name="vix_gate"),
    "regime_gate": run(exposure=gate_regime, name="regime_gate"),
    "ex_2008_toy": run(exposure=gate_custom, name="ex_2008_toy"),
}

rows = {}
for label, res in variants.items():
    s = res.summary(benchmark=None)
    net = s.loc[[i for i in s.index if i.endswith("_net")][0]]
    rows[label] = {"net_sharpe": net["sharpe"], "ann_return": net["ann_return"],
                   "max_dd": net["max_drawdown"], "skew": net["skew"],
                   "turnover": res.turnover, "cost_drag": res.cost_drag}

table = pd.DataFrame(rows).T.astype(float).round(4)
print("Exposure gates on the common base (net of costs):\n")
print(table.to_string())

bar = table.loc["baseline", "net_sharpe"]
print(f"\nThe bar to beat is the baseline's {bar:.3f} net Sharpe.")
print("Note every gate also changes turnover and cost drag — that is the point:")
print("de-risking is not free, and a gate applied to a return series would hide it.")

# --- monthly hand-off, if your model decides monthly -------------------------
print(f"\nFor a monthly model: base.monthly() gives {len(base.monthly())} month-end "
      "compounded net returns, and base.signal is the carry panel "
      f"({base.signal.shape}) if you need cross-sectional dispersion as a feature.")
