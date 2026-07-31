"""Carry executed at each currency's own optimal tenor.

The tenor study found that the best forward tenor is a cost decision and that it
differs by bloc: G10 prefers 1M until spreads get expensive, EM prefers 6M at
every cost level tested. Every book in the literature, and every book in our
repo, forces ONE tenor on the whole panel.

So don't. Run the wide-spread currencies at a long tenor and the narrow-spread
ones at a short tenor, in a single carry book.

This is not a new signal. The sort is the same demeaned forward discount every
carry study uses, and the tenor result already showed the exposure is nearly
identical across tenors. What changes is the execution: each sleeve trades where
its own spread says it should. The claim is therefore a cost claim, and it is
falsifiable -- if the mixed book does not beat every uniform-tenor book net of
costs, the idea is worthless.

Reported either way, and scored on a common sample.
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
MONTHS = {"1M": 1, "3M": 3, "6M": 6, "12M": 12}


def sleeve(tenor, ccys, mult, level_all):
    """One sleeve of the book: these currencies, at this tenor.

    The signal is demeaned across the FULL panel, not within the sleeve, so
    splitting the book by execution tenor does not quietly change what is being
    traded. Only the instrument differs.
    """
    p = api.load_panel(DATA, ccys, tenor=None if tenor == "1M" else tenor)
    p = p.slice(start=START)
    m = MONTHS[tenor]
    sig = level_all[ccys].reindex(p.fwd_discount.index)
    return backtest.run_horizon_backtest(
        sig, p, horizon=m, dollar_neutral=False,
        spread_model=costs.RollAndTradeCost(p, multiple=mult))


def monthly_stream(res):
    """Spread a held-to-maturity return evenly over the months it spans, so
    sleeves on different tenors can be added to one monthly series."""
    m = int(round(12 / res.periods_per_year))
    s = res.net.dropna()
    if m == 1:
        return s
    rows = {}
    for date, v in s.items():
        # The return is earned over the whole holding period; attribute it
        # evenly rather than crediting it all to the settlement month.
        span = pd.date_range(date, periods=m, freq="ME")
        for d in span:
            rows[d] = rows.get(d, 0.0) + v / m
    return pd.Series(rows).sort_index()


def build(assignment, mult, level_all):
    """assignment: {tenor: [currencies]}. Returns a monthly net series."""
    parts = []
    for tenor, ccys in assignment.items():
        if not ccys:
            continue
        parts.append(monthly_stream(sleeve(tenor, ccys, mult, level_all)))
    df = pd.concat(parts, axis=1).dropna(how="all")
    return df.sum(axis=1, min_count=1).dropna()


def score(s):
    return {"n": int(len(s)),
            "sharpe": float(metrics.sharpe_ratio(s)),
            "vol": float(s.std(ddof=1) * np.sqrt(12)),
            "mean": float(s.mean() * 12),
            "skew": float(s.skew()),
            "dd": float(metrics.max_drawdown(np.exp(s.cumsum())))}


def main() -> None:
    # One signal for the whole panel, demeaned once, reused by every sleeve.
    p1 = api.load_panel(DATA, UNIVERSE).slice(start=START)
    level_all = signals.cross_sectional_demean(p1.fwd_discount * 12.0)

    # Split by median quoted spread rather than by the G10/EM label, so the
    # rule is mechanical and does not smuggle in a judgement about which
    # currencies are "emerging".
    spread = p1.fwd_half_spread.mean().sort_values()
    cheap = list(spread.index[: len(spread) // 2])
    dear = list(spread.index[len(spread) // 2:])
    print("=" * 78)
    print("SPLIT BY QUOTED SPREAD (median), not by bloc label")
    print("=" * 78)
    print(f"  narrow, trade short tenor: {', '.join(cheap)}")
    print(f"  wide,   trade long  tenor: {', '.join(dear)}")
    print(f"  median half-spread: {1e4*spread.median():.1f} bp")

    results = {}
    print()
    print("=" * 78)
    print("MIXED vs UNIFORM, net Sharpe on a common sample")
    print("=" * 78)
    header = f"{'cost':>6} " + " ".join(f"{c:>10}" for c in
                                        ("all 1M", "all 3M", "all 6M",
                                         "mixed 1/6", "mixed 1/3"))
    print(header)

    for mult in (0.5, 1.0, 2.0, 4.0, 8.0):
        books = {
            "all 1M": build({"1M": UNIVERSE}, mult, level_all),
            "all 3M": build({"3M": UNIVERSE}, mult, level_all),
            "all 6M": build({"6M": UNIVERSE}, mult, level_all),
            "mixed 1/6": build({"1M": cheap, "6M": dear}, mult, level_all),
            "mixed 1/3": build({"1M": cheap, "3M": dear}, mult, level_all),
        }
        # Common sample across all five so the comparison is honest.
        idx = None
        for s in books.values():
            idx = s.index if idx is None else idx.intersection(s.index)
        row = {k: metrics.sharpe_ratio(v.loc[idx]) for k, v in books.items()}
        results[str(mult)] = row
        best = max(row, key=row.get)
        print(f"{mult:>5.1f}x " + " ".join(f"{row[c]:>10.3f}" for c in
                                           ("all 1M", "all 3M", "all 6M",
                                            "mixed 1/6", "mixed 1/3"))
              + f"   best: {best}")
        if mult == 1.0:
            keep_books, keep_idx = books, idx

    print()
    print("=" * 78)
    print("FULL PROFILE AT 1x QUOTED SPREAD, common sample")
    print("=" * 78)
    prof = pd.DataFrame({k: score(v.loc[keep_idx]) for k, v in keep_books.items()}).T
    print(prof.to_string(float_format=lambda v: f"{v:,.4f}"))

    b = keep_books["all 1M"].loc[keep_idx]
    for name in ("mixed 1/6", "mixed 1/3"):
        a = keep_books[name].loc[keep_idx]
        rho = float(np.corrcoef(a, b)[0, 1])
        d = metrics.sharpe_ratio(a) - metrics.sharpe_ratio(b)
        mds = ev.min_detectable_sharpe(b, correlation=rho)
        print(f"\n  {name} vs all 1M:")
        print(f"    correlation                   {rho:+.3f}")
        print(f"    Sharpe difference             {d:+.3f}")
        print(f"    minimum detectable difference {mds:.3f}")
        print(f"    verdict                       "
              f"{'DETECTABLE' if abs(d) > mds else 'inside the noise'}")

    (OUT / "mixed_tenor.json").write_text(json.dumps(results, indent=2),
                                          encoding="utf-8")
    print(f"\nwrote {OUT / 'mixed_tenor.json'}")


if __name__ == "__main__":
    main()
