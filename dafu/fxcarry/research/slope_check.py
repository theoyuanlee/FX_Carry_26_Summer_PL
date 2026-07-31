"""Is the 24-month result real, or is it just a shorter sample?

slope_smooth.py reported net Sharpe 0.431 -> 0.646 at 24-month smoothing, but
the smoothing grid is flat at 1/3/6/12 months and then jumps at 24. A jump like
that is usually an artifact.

The obvious suspect: rolling(24) needs a warm-up, so the smoothed book starts
later than plain carry and skips part of the 2008-09 crisis, which is where
carry takes its worst drawdown. If that is the explanation, the two books are
being scored on different samples and the comparison is meaningless.

This script forces both onto a common index and re-scores.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from fxcarry import api, backtest, costs, evaluation as ev, metrics, signals

DATA, START = "data/raw", "2008-01-01"
UNIVERSE = ["AUD", "CAD", "CHF", "CZK", "DKK", "EUR", "GBP", "HUF",
            "JPY", "NOK", "NZD", "PLN", "SEK", "SGD", "ZAR"]

p1 = api.load_panel(DATA, UNIVERSE).slice(start=START)
p12 = api.load_panel(DATA, UNIVERSE, tenor="12M").slice(start=START)
level = p1.fwd_discount * 12.0
slope = p12.fwd_discount.reindex_like(level) - level
carry = signals.cross_sectional_demean(level)


def run(sig):
    r = backtest.run_signal_backtest(
        sig, p1, dollar_neutral=True,
        spread_model=costs.RollAndTradeCost(p1))
    return (r.gross - r.cost.fillna(0.0)).dropna()


def tilt(months, floor=0.0):
    rank = slope.rank(axis=1, pct=True)
    if months > 1:
        rank = rank.rolling(months, min_periods=max(2, months // 2)).mean()
    return run(signals.cross_sectional_demean(level) * (floor + (1 - floor) * rank))


base = run(carry)

print("=" * 74)
print("SAMPLE START DATES")
print("=" * 74)
print(f"  plain carry starts   {base.index[0].date()}   n = {len(base)}")
for m in (1, 3, 6, 12, 24):
    t = tilt(m)
    print(f"  {m:>2}M smoothing starts  {t.index[0].date()}   n = {len(t)}")

print()
print("=" * 74)
print("SCORED ON EACH BOOK'S OWN SAMPLE vs A COMMON SAMPLE")
print("=" * 74)
print(f"{'smooth':>7} {'own sample':>12} {'common sample':>15} "
      f"{'carry, same window':>20}")
for m in (1, 3, 6, 12, 24):
    t = tilt(m)
    idx = t.index.intersection(base.index)
    own = metrics.sharpe_ratio(t)
    common = metrics.sharpe_ratio(t.loc[idx])
    carry_same = metrics.sharpe_ratio(base.loc[idx])
    print(f"{m:>6}M {own:>12.3f} {common:>15.3f} {carry_same:>20.3f}")

print()
print("  The last column is the test. If plain carry also improves on the")
print("  truncated window, the gain belongs to the sample, not the signal.")

print()
print("=" * 74)
print("WHERE THE DIFFERENCE COMES FROM, YEAR BY YEAR")
print("=" * 74)
t24 = tilt(24)
idx = t24.index.intersection(base.index)
yr = pd.DataFrame({"carry": base.loc[idx], "tilted": t24.loc[idx]})
yr["diff"] = yr["tilted"] - yr["carry"]
ann = yr.groupby(yr.index.year).sum() * 100
print(f"{'year':>6} {'carry':>9} {'tilted':>9} {'diff':>9}")
for y, row in ann.iterrows():
    star = "  <--" if abs(row["diff"]) > 3 else ""
    print(f"{y:>6} {row['carry']:>8.2f}% {row['tilted']:>8.2f}% "
          f"{row['diff']:>8.2f}%{star}")

print()
share = ann["diff"].abs().max() / ann["diff"].abs().sum()
print(f"  Largest single year is {100*share:.0f}% of the total absolute difference.")
print("  A result concentrated in one year is a story about that year.")

print()
print("=" * 74)
print("DOES IT SURVIVE DROPPING ANY ONE YEAR?")
print("=" * 74)
years = sorted(set(idx.year))
diffs = []
for y in years:
    keep = idx[idx.year != y]
    d = metrics.sharpe_ratio(t24.loc[keep]) - metrics.sharpe_ratio(base.loc[keep])
    diffs.append((y, d))
worst = min(diffs, key=lambda kv: kv[1])
best = max(diffs, key=lambda kv: kv[1])
print(f"  full sample difference      {metrics.sharpe_ratio(t24.loc[idx]) - metrics.sharpe_ratio(base.loc[idx]):+.3f}")
print(f"  weakest leave-one-year-out  {worst[1]:+.3f}  (dropping {worst[0]})")
print(f"  strongest                   {best[1]:+.3f}  (dropping {best[0]})")
print(f"  range across all drops      "
      f"[{min(d for _, d in diffs):+.3f}, {max(d for _, d in diffs):+.3f}]")
