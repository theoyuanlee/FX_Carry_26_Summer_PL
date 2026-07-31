"""Generate notebooks/tutorial/06_strategy.ipynb."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from _nb import code, md, write

CELLS = []

CELLS.append(md(r"""
# 06: strategy

Everything in `fxcarry.strategy` composes around one interface each. A `Signal` scores the
cross-section, a `Weighting` turns those scores into positions, an `Overlay` optionally puts
options on top of a leg, and a `CostModel` charges for the trading that results. `Book` is where
all four meet: it scores the signal, runs the scores through a weighting, holds the resulting
position for one period, prices the overlay if there is one, and nets out whatever the cost
model charges.

Signals and weightings are indexed by the date their information became knowable, not by the
date anyone acts on it. `Book` performs the module's only shift, pairing a position chosen on
one date with the return realized over the period that follows, so nothing above it has to
remember to lag anything on its own.

This notebook builds one sorted carry book from the ground up: the signal, five different ways
to turn it into positions, two cost models run against the same book, and an option overlay on
top of it. Notebook 04_hedged_leg_from_first_principles rebuilt this same top-five, bottom-five
book by hand for one currency in one month; this notebook runs the whole panel through the
library instead. Reading the vol surface the overlay needs takes on the order of ten seconds to
half a minute on this machine, timed in the setup section below rather than left as a silent
wait. Notebook 07 picks up the book this one builds and asks what can be said about it
statistically.
"""))

CELLS.append(code(r"""
import pathlib
import warnings

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

warnings.filterwarnings("ignore", category=FutureWarning)

# nbconvert runs with this notebook's folder as the working directory, so walk up
# rather than assume how deep the notebook sits.
ROOT = next(p for p in [pathlib.Path.cwd(), *pathlib.Path.cwd().parents]
            if (p / "data" / "raw").is_dir())
DATA = ROOT / "data" / "raw"
TAU = 1.0 / 12.0
"""))

CELLS.append(md(r"""
## Setup: curves, a smile and a funding rate, all before anything else runs

Building `curves` alone would carry the notebook through its first few sections, but two later
ones need more. Section 8 prices `HalfSpreadCost` directly off the two-sided spot quotes, and
section 9's overlay needs a smile and a domestic funding rate before a delta can resolve to a
strike. Building all of it here, once, means no cell further down has to introduce a name it
never defined, and the vol surface only gets read once instead of twice.

The surface load reads `fx_vol_daily.parquet` end to end before it can filter anything, on the
order of sixteen million rows. On this machine that takes on the order of ten seconds to half a
minute, timed below.
"""))

CELLS.append(code(r"""
from fxcarry import Catalog, ParquetSource, SpotForward

catalog = Catalog.default()
source = ParquetSource(DATA / "spot_daily.parquet", DATA / "fwd_points_1m_daily.parquet")
spot = source.quotes(catalog.label_map("spot"), freq="M")
points = source.quotes(catalog.label_map("forward", "1M"), freq="M")
curves = SpotForward.from_quotes(spot, points, catalog, TAU)
print(f"{len(curves.currencies)} currencies, {len(curves.spot.index)} months, "
      f"{curves.spot.index[0]:%Y-%m} to {curves.spot.index[-1]:%Y-%m}")
print(curves.currencies)
"""))

CELLS.append(code(r"""
import time

import pyarrow.parquet as pq

from fxcarry import Performance, VolSurface

# Sections 8 and 9 need a two-sided spot for HalfSpreadCost, a smile and a funding rate for the
# overlay, and Performance for every cost comparison from here on. Building them here, once,
# means neither the surface load nor the overlay's market gets assembled twice.
raw_rows = pq.ParquetFile(DATA / "fx_vol_daily.parquet").metadata.num_rows
t0 = time.time()
surface = VolSurface.from_source(ParquetSource(DATA / "fx_vol_daily.parquet"), catalog,
                                 tenors=["1M"], deltas=[10, 25])
elapsed = time.time() - t0
smile = surface.panel_smile("1M", freq="M").reindex_like(curves.forward.mid)
bill = ParquetSource(DATA / "tbill_daily.parquet").series("GB1M Index", freq="M") / 100.0

print(f"{raw_rows:,} rows read and decoded, then filtered to 1M, 10/25 delta, "
      f"in {elapsed:.1f} seconds")
print(f"smile covers {smile.atm.shape[1]} currencies")
print(f"US 1M bill from {bill.index.min():%Y-%m} to {bill.index.max():%Y-%m}")
"""))

CELLS.append(md(r"""
## Signals: `Carry` and `Momentum`

A `Signal` has one method, `scores`, and does one thing: turn the curves into a cross-section
where a higher number means a currency is worth being more long. `Carry` returns the
`curves.carry` already computed in notebook 03. `Momentum` sums the trailing realized excess
return over a lookback window, a default of one month, three below.
"""))

CELLS.append(code(r"""
from fxcarry import Carry, Momentum

scores = Carry().scores(curves)
mom = Momentum(3).scores(curves)
print("carry scores, latest row")
print(scores.iloc[-1].dropna().sort_values(ascending=False).round(4).head(5))
print("\nmomentum over three months, latest row")
print(mom.iloc[-1].dropna().sort_values(ascending=False).round(4).head(5))
"""))

CELLS.append(md(r"""
## A signal shifts nothing

`Carry.scores` hands back `curves.carry` unchanged, and `Momentum.scores` hands back a rolling
sum of `curves.excess_return`. Both are already indexed by the date the number became knowable,
and neither class shifts anything. The single lag in this module lives in `Book.holdings`, not
in the signal, so a signal can be built, plotted or tested entirely on its own without ever
answering the separate question of when a position built from it would be held.
"""))

CELLS.append(md(r"""
## Five weightings, one row

A `Weighting` turns one row of scores into one row of positions, and every rule normalizes
within that row: a month with fewer scored currencies still ends up holding the same total
size. `TopBottom(k)` goes long the top `k` scores and short the bottom `k`, a dollar on each
side. `Bucket(n, i)` holds one slice of an `n`-way sort, equally weighted and long only.
`SignEqualWeight` holds every scored currency at equal size, in the direction of its sign.
`SpreadWeighted` sizes each position by the score itself. `EqualLong` holds everything scored,
long, regardless of what the score says.

Putting all five on the same row of carry scores is the fastest way to see what each one does
with the same information.
"""))

CELLS.append(code(r"""
from fxcarry import Bucket, EqualLong, SignEqualWeight, SpreadWeighted, TopBottom

row = scores.iloc[[-1]]
rules = {"TopBottom(3)": TopBottom(3), "Bucket(5, 5)": Bucket(5, 5),
         "SignEqualWeight": SignEqualWeight(), "SpreadWeighted": SpreadWeighted(),
         "EqualLong": EqualLong()}
pd.DataFrame({name: rule.weights(row).iloc[0] for name, rule in rules.items()}).round(3)
"""))

CELLS.append(md(r"""
## Gross exposure is not the same number for every rule

`TopBottom` is long-short by construction, a full dollar on each side, so its gross exposure
comes to 2.0. The other four hold one side of the book only, or hold both sides scaled to sum to
one dollar of absolute exposure, so each of those comes to 1.0. Every rule normalizes within the
row; what it normalizes to is a property of the rule itself, and the two groups above do not
share one.
"""))

CELLS.append(code(r"""
pd.Series({name: float(rule.weights(row).abs().sum(axis=1).iloc[0])
           for name, rule in rules.items()}).round(3)
"""))

CELLS.append(md(r"""
## `Book`, and the one shift that matters

`Book.weights` is the position a signal and a weighting call for, dated the day that call could
have been made. `Book.holdings` is `weights().shift(1).fillna(0.0)`: the position actually held
over the period that follows. This is the only shift anywhere in `fxcarry.strategy`, and the
assertion below checks it directly rather than trusting the docstring that says so.
"""))

CELLS.append(code(r"""
from fxcarry import Book

book = Book(curves, Carry(), TopBottom(5))
w, h = book.weights(), book.holdings()
assert h.iloc[1:].equals(w.shift(1).fillna(0.0).iloc[1:]), "holdings is not weights lagged"
print("weights row  ", w.index[-2].date(), "->", w.iloc[-2].abs().sum().round(3), "gross")
print("held over    ", h.index[-1].date())
print("a position chosen on one row can only earn a return that had not happened yet")
"""))

CELLS.append(md(r"""
## Returns, NAV, turnover and the sorted buckets

`Book.returns` sums each held leg's return, weighted by its size, and subtracts whatever the
cost model charges. `book` above was built with no cost model, which defaults to `ZeroCost`, so
this is the gross book. `Book.buckets(n)` reruns the whole book once per slice of an `n`-way
sort, which shows the shape of the carry effect rather than only its long-short spread.
"""))

CELLS.append(code(r"""
gross = book.returns(net=False)
print(f"gross mean {gross.mean():.5f} per month, NAV {book.nav().iloc[-1]:.2f}")
print(f"turnover   {book.turnover().mean():.4f} per month, per currency")

# Book.turnover is holdings().diff().abs().mean(axis=1), a mean across the cross-section, so it
# is a per-currency figure spread over however many columns the panel carries, not a fraction of
# the book. Summing the same absolute changes across each row instead, and dividing by mean
# gross exposure, is what puts turnover on a notional basis. h is the holdings panel from above.
traded = h.diff().abs().sum(axis=1).mean()
held = h.abs().sum(axis=1).mean()
print(f"           {traded:.4f} of notional traded per month across {h.shape[1]} columns, "
      f"against {held:.4f} held")
print(f"           so {traded / held:.1%} of the book turns over, and charging the whole "
      f"notional costs {held / traded:.1f} times charging only what traded")
buckets = book.buckets(5)
(buckets.mean() * 12).round(4)
"""))

CELLS.append(md(r"""
### The bucket sort orders monotonically

The annualized bucket means rise in order from bucket 1, the lowest carry, to bucket 5, the
highest. That ordering holds across the middle three buckets too, not just the two ends
`TopBottom` trades, and it is what makes carry a reasonable variable to sort on in the first
place. `TopBottom`'s own return by itself cannot show it.
"""))

CELLS.append(md(r"""
## What trading costs: two spread models compared

`ZeroCost` charges nothing, which is what `book` above already ran with. `BidAskCost` prices the
gap between the panel's mid return and the return actually available on the side being crossed,
and it charges that on the full notional held every period, with no netting: a position left
unchanged from one month to the next is charged as if it had been closed and reopened.
`HalfSpreadCost` is the model built to separate the two costs a real book pays: a smaller
`roll` charge for keeping a position on, and the full `outright` charge only for the
notional that changes. That distinction is what keeps a book like this one from being charged as
if it traded every leg from scratch every period. Only about 23 percent of its notional turns
over in a month, printed in the turnover cell above, so a charge levied on everything held comes
to roughly four times a charge levied on what actually changed hands.
"""))

CELLS.append(code(r"""
from fxcarry import BidAskCost, HalfSpreadCost, ZeroCost

half = spot.half_spread()
variants = {
    "gross": Book(curves, Carry(), TopBottom(5), costs=ZeroCost()),
    "quoted bid ask": Book(curves, Carry(), TopBottom(5), costs=BidAskCost(curves)),
    "half spread": Book(curves, Carry(), TopBottom(5),
                        costs=HalfSpreadCost(roll=half, outright=half)),
}
summary = pd.DataFrame({name: Performance(b.returns()).summary().iloc[0]
                        for name, b in variants.items()}).T.round(4)
print(summary)

# The brief's version of this cell stops at the annualized summary. The mean it reports is
# scaled by periods_per_year, which is not the per-period figure this notebook's markdown
# compares across variants, so the raw, unannualized mean is printed alongside it.
raw_mean = {name: round(float(b.returns().mean()), 5) for name, b in variants.items()}
print(f"\nraw per-period mean, unannualized: {raw_mean}")

# The forward leg's own two-sided quotes start later than spot's, which is why BidAskCost above
# prices fewer months than the other two variants (see n_obs in the table).
print(f"forward bid/ask coverage starts {curves.forward.bid.dropna(how='all').index.min():%Y-%m}"
      f", spot's own starts {spot.bid.dropna(how='all').index.min():%Y-%m}")
"""))

CELLS.append(md(r"""
## The overlay book: a smile and a funding rate on top

An overlay needs a market carrying both a smile and a rate, which the setup section already
built: `smile` to turn a delta into a strike, and `bill` as the domestic rate a premium paid
today compounds at until settlement. `VerticalSpread(25, 10, "put")` sells the 25-delta option
and buys the 10-delta one further out, on whichever side of the smile the position being
protected is exposed to.

`Book.overlay_kinds` reads that side off the sign of the position itself, not off the currency:
a leg held long loses when its currency falls, so it is protected with puts, and a leg held
short loses when its currency rises, so it takes calls. Both sides of the check below come out of
the same `weights()` call, so what it establishes is that `overlay_kinds` maps that sign the way
its docstring says, on every leg the book has ever held. It is a statement about the mapping, not
about the positions.
"""))

CELLS.append(code(r"""
from fxcarry import VerticalSpread

hedged = Book(curves, Carry(), TopBottom(5), overlay=VerticalSpread(25, 10, "put"),
              smile=smile, domestic_rate=bill)

# The brief's version of this cell rebuilds smile and bill inline. Both are already in scope
# from the setup section, built once there specifically to avoid a second vol surface read
# here, the same read timed above.
kinds = hedged.overlay_kinds()
print("which side each leg's protection sits on, latest row with positions")
print(kinds.iloc[-2].dropna().to_dict())

# pandas' current stack() implementation does not drop NaN by default, unlike its predecessor,
# so an explicit dropna() after stacking is what actually restricts this to the held legs.
hw = hedged.weights()
put_legs = hw.where(kinds == "put").stack().dropna()
call_legs = hw.where(kinds == "call").stack().dropna()
print(f"\nevery put leg held long:   {bool((put_legs > 0).all())}  (n={len(put_legs)})")
print(f"every call leg held short: {bool((call_legs < 0).all())}  (n={len(call_legs)})")

compare = pd.DataFrame({"unhedged": book.returns(), "hedged": hedged.returns()}).dropna()
print(f"\n{len(compare)} months carry both an unhedged and a hedged return")
compare.describe().round(5)
"""))

CELLS.append(md(r"""
## Writing your own `Signal`

`Signal` is an abstract base class with one method, `scores`. Anything that implements it works
with `Weighting`, `Book`, cost models and overlays unchanged, because none of them know or care
where a score came from. `CarryOverVol` below divides carry by trailing realized volatility, so
a wide spread on a currency that has been quiet lately scores higher than the same spread on a
currency that has been moving around.
"""))

CELLS.append(code(r'''
from fxcarry import Signal

class CarryOverVol(Signal):
    """Carry divided by realized volatility, so a wide spread on a quiet currency wins."""

    def __init__(self, window: int = 12):
        self.window = window

    def scores(self, curves):
        vol = curves.excess_return.rolling(self.window).std()
        return curves.carry / vol

scaled = Book(curves, CarryOverVol(), TopBottom(5))
pd.DataFrame({"carry": Performance(book.returns()).summary().iloc[0],
              "carry over vol": Performance(scaled.returns()).summary().iloc[0]}).T.round(4)
'''))

CELLS.append(md(r"""
## Check yourself

**Where is the only shift?** `Book.holdings`, computed as `weights().shift(1).fillna(0.0)`.
Every signal and every weighting above reads and writes the same row it scored, and neither
class moves a number to a different date. The lag that stops a position from earning a return it
could not have known about lives in exactly one place, and the assertion in the `Book` section
above checks it directly rather than assuming it holds.

**Why are book returns simple rather than logarithmic?** `Book.returns` sums
`holdings.abs() * leg_returns` across the row, and that sum is only a portfolio return if
`leg_returns` is already a simple return: a weighted sum of simple returns is a portfolio
return, a weighted sum of log returns is not. The overlay section adds a second reason. An
option payoff and a forward payoff both settle in the same units, dollars per unit of notional,
and a log return could not be added to one directly.

**Which strategy does a cost model with no netting penalize?** A low-turnover one.
`BidAskCost` charges the full round-trip spread on whatever is held, every period, whether or
not that position changed at all. About 23 percent of this book's notional turns over in a
month, so most of what `BidAskCost` charges it for in any given month is capital that was
already on the book the month before. `HalfSpreadCost` separates a maintenance charge from a
trading one, which is why its mean return sits between the other two variants above rather than
matching `BidAskCost`'s lower number.
"""))

write(CELLS, Path(__file__).parents[2] / "notebooks" / "tutorial" / "06_strategy.ipynb")
