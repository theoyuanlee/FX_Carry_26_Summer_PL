"""Example 3 — a per-currency option overlay on the base book  (Theo's pattern).

Run:  python strategy/examples/03_option_weight_overlay.py

The pattern: `weight_overlay=f`, where `f(weights, ctx) -> weights` receives the
daily vol-targeted weight panel and returns a modified one. Use it for anything
that acts on *individual currencies* rather than on total exposure: an option
hedge on the long leg, a vol filter, a manual position edit.

Because you return weights (not returns), the base prices your overlay properly:
the trades it triggers pay the bid/ask half-spread, and the hedged position earns
the carry it actually still holds.

The overlay below is the project's Stage-3 "per-currency risk reversal" rule —
trim long positions in currencies whose crash insurance is expensive. That is the
one hedge in the project that survived costs (plan §9), so it's a fair template.

WHAT THIS DOES NOT DO: it does not price an option. Trimming a position is a
proxy for buying a put on it. A real option overlay needs a premium, which needs
option bid/ask that `data/raw` does not currently carry (see
cesare/DATA_SHOPPING_LIST.md §2.2) — so a delta-proxy hedge like this is the
honest version until that data exists. Say so in any write-up.
"""

import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from strategy import fx_utils as fx, run

# 25-delta risk reversal, already sign-normalised crash-positive by the engine:
# positive = FX puts rich = the market is pricing a fat left tail for a long.
RR = fx.vol_surface_panel("RR", "1M")


def rr_trim_overlay(weights: pd.DataFrame, ctx) -> pd.DataFrame:
    """Halve long positions where crash insurance is in its top-quintile expensive.

    Trailing 3-year percentile per currency, so "expensive" is judged against
    that currency's own history and only with data available at the time. Short
    legs are left alone: a rich RR is a warning about being long, not short.
    """
    rr = RR.reindex(weights.index).ffill()
    rank = rr.rolling(756, min_periods=378).rank(pct=True)
    # Month-end sample + one-day lag: same no-lookahead convention as the signal.
    rank_rb = rank.resample(ctx.config.rebal).last().reindex(
        weights.index, method="ffill").shift(1)

    expensive = (rank_rb > 0.80).reindex(
        columns=weights.columns, fill_value=False).astype(bool)
    is_long = weights > 0
    scale = pd.DataFrame(1.0, index=weights.index, columns=weights.columns)
    scale[expensive & is_long] = 0.5
    return weights * scale


def flat_ccy_overlay(weights: pd.DataFrame, ctx) -> pd.DataFrame:
    """Simplest possible overlay: never hold TRY, whatever the sort says."""
    out = weights.copy()
    if "TRY" in out.columns:
        out["TRY"] = 0.0
    return out


base = run()
variants = {
    "baseline": base,
    "rr_trim (option proxy)": run(weight_overlay=rr_trim_overlay, name="rr_trim"),
    "no_TRY": run(weight_overlay=flat_ccy_overlay, name="no_TRY"),
}

rows = {}
for label, res in variants.items():
    s = res.summary(benchmark=None)
    net = s.loc[[i for i in s.index if i.endswith("_net")][0]]
    rows[label] = {"net_sharpe": net["sharpe"], "max_dd": net["max_drawdown"],
                   "skew": net["skew"], "CVaR_99": net["CVaR_99"],
                   "turnover": res.turnover, "cost_drag": res.cost_drag}

print("Per-currency overlays on the common base (net of costs):\n")
print(pd.DataFrame(rows).T.astype(float).round(4).to_string())

print("\nA tail hedge is judged on skew / CVaR / max drawdown, not Sharpe alone —")
print("the project's finding is that these rules buy tail insurance at ~1 Sharpe")
print("point, and none of them adds significant alpha (plan §9).")

# --- what the overlay can see ----------------------------------------------
print("\nInside your overlay, `ctx` gives you:")
print("  ctx.panels.xret / .carry / .spots   the data panels")
print("  ctx.weights_unit                    weights before vol targeting")
print("  ctx.signal                          the panel the sort ran on")
print("  ctx.universe, ctx.config            what was requested")
print("\nReturn a DataFrame with the same index and columns. Positions you zero")
print("stop earning carry AND stop paying to be rolled — both are handled for you.")
