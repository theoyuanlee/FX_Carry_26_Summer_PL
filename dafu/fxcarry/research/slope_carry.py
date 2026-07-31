"""Carry, conditioned on whether the market expects it to last.

Standard carry sorts on the LEVEL of the forward discount and is indifferent
to whether that discount is expected to persist or to disappear. But each
currency's own forward curve quotes exactly that. Define

    level_i  = d^1M_i  * 12                  (the usual carry signal)
    slope_i  = d^12M_i * 1  -  d^1M_i * 12   (annualised long minus short)

A negative slope means the long end pays less than the short end: the market is
pricing the rate differential to narrow, so today's carry is expected to decay.
A flat or positive slope means it is priced to persist.

The claim under test: carry that is priced to persist is worth more than carry
that is priced to decay, so tilting toward flat-curve currencies should improve
the book.

Why this is not the shrinkage idea that failed. Shrinkage tries to repair a
NOISY ESTIMATE of expected returns, and FX has no such estimate to repair --
the discount is quoted. The slope is also quoted. This adds a second price to
the signal, not a statistical correction to it.

Runs the honest checks: does slope add anything beyond level, or is it a
repackaging of it?
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


def curve(currencies=UNIVERSE):
    """The 1M panel plus the annualised level and slope signals."""
    p1 = api.load_panel(DATA, currencies).slice(start=START)
    p12 = api.load_panel(DATA, currencies, tenor="12M").slice(start=START)
    level = p1.fwd_discount * 12.0
    slope = p12.fwd_discount.reindex_like(level) - level
    return p1, level, slope


def unit(sig):
    """Scale a signal to unit gross exposure so blends are comparable."""
    g = sig.abs().sum(axis=1)
    return sig.div(g.where(g > 0), axis=0)


def run(sig, panel, mult=1.0):
    return backtest.run_signal_backtest(
        sig, panel, dollar_neutral=True,
        spread_model=costs.RollAndTradeCost(panel, multiple=mult))


def stats(res, label):
    n = (res.gross - res.cost.fillna(0.0)).dropna()
    g = res.gross.dropna()
    return {
        "strategy": label,
        "n": int(len(n)),
        "sharpe_gross": float(metrics.sharpe_ratio(g)),
        "sharpe_net": float(metrics.sharpe_ratio(n)),
        "se": float(ev.sharpe_standard_error(n)),
        "mean": float(n.mean() * 12),
        "vol": float(n.std(ddof=1) * np.sqrt(12)),
        "skew": float(n.skew()),
        "kurt": float(n.kurtosis()),
        "max_dd": float(metrics.max_drawdown(np.exp(n.cumsum()))),
        "turnover": float(res.weights.diff().abs().sum(axis=1).dropna().mean() * 12),
    }


def main() -> None:
    out = {}
    p, level, slope = curve()

    # ---- 0. is the slope even distinct from the level? --------------------
    print("=" * 74)
    print("IS THE SLOPE A REPACKAGING OF THE LEVEL?")
    print("=" * 74)
    both = pd.concat([level.stack(), slope.stack()], axis=1).dropna()
    both.columns = ["level", "slope"]
    print(f"  pooled correlation(level, slope) = {both.corr().iloc[0,1]:+.3f}")
    xs = level.apply(lambda r: r.corr(slope.loc[r.name]), axis=1).dropna()
    print(f"  mean cross-sectional correlation = {xs.mean():+.3f}"
          f"   (sd across months {xs.std():.3f})")
    print()
    print("  Mean annualised slope, by currency (negative = carry priced to decay):")
    ms = slope.mean().sort_values()
    for c, v in ms.items():
        print(f"    {c:>4} {100*v:+7.2f}%   (mean level {100*level[c].mean():+6.2f}%)")
    out["slope_level_corr"] = float(both.corr().iloc[0, 1])
    out["xs_corr_mean"] = float(xs.mean())

    # ---- 1. the strategies -------------------------------------------------
    carry = signals.cross_sectional_demean(level)
    slope_only = signals.cross_sectional_demean(slope)

    print()
    print("=" * 74)
    print("BLENDING CARRY WITH THE SLOPE TILT")
    print("=" * 74)
    print(f"{'weight on slope':>16} {'SR gross':>9} {'SR net':>8} {'vol':>7} "
          f"{'skew':>7} {'maxDD':>8} {'turn':>7}")
    rows = []
    for w in [0.0, 0.1, 0.2, 0.3, 0.4, 0.5, 0.75, 1.0]:
        sig = ((1 - w) * unit(carry)).fillna(0.0) + (w * unit(slope_only)).fillna(0.0)
        sig = sig.replace(0.0, np.nan)
        s = stats(run(sig, p), f"w={w}")
        rows.append({**s, "w": w})
        print(f"{w:>16.2f} {s['sharpe_gross']:>9.3f} {s['sharpe_net']:>8.3f} "
              f"{100*s['vol']:>6.2f}% {s['skew']:>7.2f} {100*s['max_dd']:>7.1f}% "
              f"{s['turnover']:>7.2f}")
    out["blend"] = rows

    # ---- 2. the conditional version: only trade persistent carry ----------
    print()
    print("=" * 74)
    print("CONDITIONAL VERSION: DOWN-WEIGHT CARRY THE CURVE SAYS WILL DECAY")
    print("=" * 74)
    # Rank slope cross-sectionally into [0,1]; scale the carry signal by it.
    rank = slope.rank(axis=1, pct=True)
    print(f"{'floor':>8} {'SR gross':>9} {'SR net':>8} {'vol':>7} {'skew':>7} "
          f"{'maxDD':>8} {'turn':>7}")
    cond_rows = []
    for floor in [0.0, 0.25, 0.5]:
        mult = floor + (1 - floor) * rank
        sig = signals.cross_sectional_demean(level) * mult
        s = stats(run(sig, p), f"cond floor={floor}")
        cond_rows.append({**s, "floor": floor})
        print(f"{floor:>8.2f} {s['sharpe_gross']:>9.3f} {s['sharpe_net']:>8.3f} "
              f"{100*s['vol']:>6.2f}% {s['skew']:>7.2f} {100*s['max_dd']:>7.1f}% "
              f"{s['turnover']:>7.2f}")
    out["conditional"] = cond_rows

    # ---- 3. baseline and the honest comparison ----------------------------
    print()
    print("=" * 74)
    print("HEAD TO HEAD vs PLAIN CARRY")
    print("=" * 74)
    base = run(carry, p)
    base_s = stats(base, "carry")
    best_w = max(rows, key=lambda r: r["sharpe_net"])
    best_c = max(cond_rows, key=lambda r: r["sharpe_net"])
    for s in (base_s, best_w, best_c):
        print(f"  {s['strategy']:>16}  SRnet {s['sharpe_net']:+.3f}  "
              f"vol {100*s['vol']:.2f}%  skew {s['skew']:+.2f}  "
              f"DD {100*s['max_dd']:.1f}%  turn {s['turnover']:.2f}")
    print(f"\n  SE(Sharpe) on this sample = {base_s['se']:.3f}")
    print(f"  Minimum detectable Sharpe gain = "
          f"{ev.min_detectable_sharpe(base_s['n']):.3f}")

    # ---- 4. spanning: is the tilt anything beyond carry? ------------------
    print()
    print("=" * 74)
    print("SPANNING: does plain carry explain the tilted book?")
    print("=" * 74)
    w = best_w["w"]
    tilt_sig = ((1 - w) * unit(carry)).fillna(0.0) + (w * unit(slope_only)).fillna(0.0)
    tilt = run(tilt_sig.replace(0.0, np.nan), p)
    y = (tilt.gross - tilt.cost.fillna(0.0)).dropna()
    xcar = (base.gross - base.cost.fillna(0.0)).dropna()
    idx = y.index.intersection(xcar.index)
    sp = ev.spanning_regression(y.loc[idx], pd.DataFrame({"carry": xcar.loc[idx]}))
    print(f"  best blend weight on slope = {w}")
    print(f"  alpha (annual)  {sp.alpha_annual:+.4f}   t = {sp.alpha_t:+.2f}")
    print(f"  beta on carry   {sp.betas['carry']:+.3f}")
    print(f"  R^2             {sp.r_squared:.3f}")
    out["spanning"] = {"w": w, "alpha_annual": float(sp.alpha_annual),
                       "alpha_t": float(sp.alpha_t),
                       "beta": float(sp.betas["carry"]),
                       "r_squared": float(sp.r_squared)}

    # ---- 5. does it hold in both blocs? -----------------------------------
    print()
    print("=" * 74)
    print("BY BLOC")
    print("=" * 74)
    for name, ccys in (("G10", G10), ("EM", EM)):
        pb, lv, sl = curve(ccys)
        cb = signals.cross_sectional_demean(lv)
        sb = signals.cross_sectional_demean(sl)
        b = stats(run(cb, pb), "carry")
        sig = ((1 - w) * unit(cb)).fillna(0.0) + (w * unit(sb)).fillna(0.0)
        t = stats(run(sig.replace(0.0, np.nan), pb), "tilted")
        print(f"  {name:>4}  carry {b['sharpe_net']:+.3f} -> tilted "
              f"{t['sharpe_net']:+.3f}   "
              f"(vol {100*b['vol']:.2f}% -> {100*t['vol']:.2f}%, "
              f"DD {100*b['max_dd']:.1f}% -> {100*t['max_dd']:.1f}%)")
        out[f"bloc_{name}"] = {"carry": b, "tilted": t}

    (OUT / "slope_carry.json").write_text(json.dumps(out, indent=2), encoding="utf-8")
    print(f"\nwrote {OUT / 'slope_carry.json'}")


if __name__ == "__main__":
    main()
