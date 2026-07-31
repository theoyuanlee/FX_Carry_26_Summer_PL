"""The slope tilt works gross and dies on turnover. Can smoothing rescue it?

research/slope_carry.py established two things. Conditioning carry on the slope
of each currency's own forward curve RAISES gross Sharpe from 0.485 to 0.558 and
cuts volatility from 4.46% to 3.85%, so the conditioner carries information. But
turnover goes from 1.20 to 5.38 a year and the cost wipes the gain out.

That is a specific failure, not a vague one. The slope RANK is jumpy month to
month while the economics it proxies -- where a central bank is in its cycle --
moves over quarters. So the signal is re-sorting on noise.

The fix that follows from the diagnosis: smooth the CONDITIONER, leave the carry
signal alone. If the information is real and slow, an average over a few months
keeps it while collapsing the trading. If smoothing kills the gross improvement
too, the improvement was noise and the idea is dead.

Reported either way.
"""

from __future__ import annotations

import json
import pathlib

import numpy as np
import pandas as pd

from fxcarry import api, backtest, costs, evaluation as ev, metrics, signals

DATA, START = "data/raw", "2008-01-01"
OUT = pathlib.Path("research/out"); OUT.mkdir(parents=True, exist_ok=True)

UNIVERSE = ["AUD", "CAD", "CHF", "CZK", "DKK", "EUR", "GBP", "HUF",
            "JPY", "NOK", "NZD", "PLN", "SEK", "SGD", "ZAR"]
G10 = ["AUD", "CAD", "CHF", "EUR", "GBP", "JPY", "NOK", "NZD", "SEK"]
EM = ["CZK", "HUF", "PLN", "ZAR"]


def curve(ccys=UNIVERSE):
    p1 = api.load_panel(DATA, ccys).slice(start=START)
    p12 = api.load_panel(DATA, ccys, tenor="12M").slice(start=START)
    level = p1.fwd_discount * 12.0
    slope = p12.fwd_discount.reindex_like(level) - level
    return p1, level, slope


def tilted_signal(level, slope, months, floor):
    """Carry, scaled by a smoothed cross-sectional rank of the curve slope.

    ``floor`` is how much weight a currency keeps when its curve says the carry
    will decay fastest. floor=1 recovers plain carry; floor=0 zeroes it out.
    """
    rank = slope.rank(axis=1, pct=True)
    if months > 1:
        rank = rank.rolling(months, min_periods=max(2, months // 2)).mean()
    return signals.cross_sectional_demean(level) * (floor + (1 - floor) * rank)


def run(sig, panel, mult=1.0):
    return backtest.run_signal_backtest(
        sig, panel, dollar_neutral=True,
        spread_model=costs.RollAndTradeCost(panel, multiple=mult))


def stats(res):
    n = (res.gross - res.cost.fillna(0.0)).dropna()
    g = res.gross.dropna()
    return {"n": int(len(n)),
            "gross": float(metrics.sharpe_ratio(g)),
            "net": float(metrics.sharpe_ratio(n)),
            "vol": float(n.std(ddof=1) * np.sqrt(12)),
            "skew": float(n.skew()),
            "kurt": float(n.kurtosis()),
            "dd": float(metrics.max_drawdown(np.exp(n.cumsum()))),
            "turn": float(res.weights.diff().abs().sum(axis=1).dropna().mean() * 12),
            "cost": float(res.cost.dropna().mean() * 12),
            "series": n}


def main() -> None:
    p, level, slope = curve()
    carry = signals.cross_sectional_demean(level)
    base = stats(run(carry, p))
    print("=" * 78)
    print("BASELINE: plain carry")
    print(f"  gross {base['gross']:.3f}  net {base['net']:.3f}  "
          f"vol {100*base['vol']:.2f}%  skew {base['skew']:+.2f}  "
          f"DD {100*base['dd']:.1f}%  turn {base['turn']:.2f}  "
          f"cost {100*base['cost']:.2f}%")

    print()
    print("=" * 78)
    print("SMOOTHING THE CONDITIONER  (floor = 0.25)")
    print("=" * 78)
    print(f"{'smooth':>8} {'gross':>7} {'net':>7} {'vol':>7} {'skew':>7} "
          f"{'DD':>8} {'turn':>7} {'cost':>7}")
    grid = {}
    for m in (1, 3, 6, 12, 24):
        s = stats(run(tilted_signal(level, slope, m, 0.25), p))
        grid[m] = s
        print(f"{m:>6}M  {s['gross']:>7.3f} {s['net']:>7.3f} {100*s['vol']:>6.2f}% "
              f"{s['skew']:>7.2f} {100*s['dd']:>7.1f}% {s['turn']:>7.2f} "
              f"{100*s['cost']:>6.2f}%")

    print()
    print("=" * 78)
    print("THE FLOOR, AT THE BEST SMOOTHING")
    print("=" * 78)
    best_m = max(grid, key=lambda k: grid[k]["net"])
    print(f"  (smoothing fixed at {best_m}M)")
    print(f"{'floor':>8} {'gross':>7} {'net':>7} {'vol':>7} {'skew':>7} "
          f"{'DD':>8} {'turn':>7}")
    floors = {}
    for f in (0.0, 0.25, 0.5, 0.75, 1.0):
        s = stats(run(tilted_signal(level, slope, best_m, f), p))
        floors[f] = s
        print(f"{f:>8.2f} {s['gross']:>7.3f} {s['net']:>7.3f} {100*s['vol']:>6.2f}% "
              f"{s['skew']:>7.2f} {100*s['dd']:>7.1f}% {s['turn']:>7.2f}")

    best_f = max(floors, key=lambda k: floors[k]["net"])
    win = floors[best_f]
    print()
    print("=" * 78)
    print(f"HEAD TO HEAD   (smooth {best_m}M, floor {best_f})")
    print("=" * 78)
    for lab, s in (("plain carry", base), ("slope-conditioned", win)):
        print(f"  {lab:>18}  net {s['net']:+.3f}  vol {100*s['vol']:.2f}%  "
              f"skew {s['skew']:+.2f}  kurt {s['kurt']:.2f}  "
              f"DD {100*s['dd']:.1f}%  turn {s['turn']:.2f}")

    idx = base["series"].index.intersection(win["series"].index)
    rho = float(np.corrcoef(base["series"].loc[idx], win["series"].loc[idx])[0, 1])
    mds = ev.min_detectable_sharpe(base["series"], correlation=rho)
    print(f"\n  correlation with plain carry      {rho:+.3f}")
    print(f"  Sharpe difference                 {win['net'] - base['net']:+.3f}")
    print(f"  minimum detectable difference     {mds:.3f}")
    verdict = "DETECTABLE" if abs(win["net"] - base["net"]) > mds else "INSIDE THE NOISE"
    print(f"  verdict on the Sharpe claim       {verdict}")

    # Volatility is estimated far more precisely than a mean, so test it too.
    boot = ev.bootstrap_difference(win["series"].loc[idx], base["series"].loc[idx],
                                   n_boot=4000, seed=11)
    print()
    print("  Stationary block bootstrap, conditioned minus plain:")
    for k, v in boot.items():
        if isinstance(v, dict):
            print(f"    {k:>12}: diff {v.get('difference', float('nan')):+.4f}  "
                  f"CI [{v.get('lower', float('nan')):+.4f}, "
                  f"{v.get('upper', float('nan')):+.4f}]  "
                  f"P(better) {v.get('prob_better', float('nan')):.0%}")

    # Spanning.
    sp = ev.spanning_regression(win["series"].loc[idx],
                                pd.DataFrame({"carry": base["series"].loc[idx]}))
    print()
    print(f"  Spanning on plain carry: alpha {sp.alpha_annual:+.4f} "
          f"(t = {sp.alpha_t:+.2f}), beta {sp.betas['carry']:+.3f}, "
          f"R^2 {sp.r_squared:.3f}")

    print()
    print("=" * 78)
    print("BY BLOC")
    print("=" * 78)
    bloc = {}
    for name, ccys in (("G10", G10), ("EM", EM)):
        pb, lv, sl = curve(ccys)
        b = stats(run(signals.cross_sectional_demean(lv), pb))
        t = stats(run(tilted_signal(lv, sl, best_m, best_f), pb))
        bloc[name] = {"carry_net": b["net"], "tilt_net": t["net"],
                      "carry_vol": b["vol"], "tilt_vol": t["vol"],
                      "carry_dd": b["dd"], "tilt_dd": t["dd"]}
        print(f"  {name:>4}  net {b['net']:+.3f} -> {t['net']:+.3f}   "
              f"vol {100*b['vol']:.2f}% -> {100*t['vol']:.2f}%   "
              f"DD {100*b['dd']:.1f}% -> {100*t['dd']:.1f}%")

    payload = {"best_smooth": best_m, "best_floor": best_f,
               "rho": rho, "mds": float(mds), "verdict": verdict,
               "base": {k: v for k, v in base.items() if k != "series"},
               "tilt": {k: v for k, v in win.items() if k != "series"},
               "smooth_grid": {str(k): {kk: vv for kk, vv in v.items()
                                        if kk != "series"}
                               for k, v in grid.items()},
               "floor_grid": {str(k): {kk: vv for kk, vv in v.items()
                                       if kk != "series"}
                              for k, v in floors.items()},
               "bloc": bloc}
    (OUT / "slope_smooth.json").write_text(json.dumps(payload, indent=2),
                                           encoding="utf-8")
    print(f"\nwrote {OUT / 'slope_smooth.json'}")


if __name__ == "__main__":
    main()
