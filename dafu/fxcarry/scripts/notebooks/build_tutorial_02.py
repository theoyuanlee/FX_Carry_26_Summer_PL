"""Generate notebooks/tutorial/02_quotes.ipynb."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from _nb import code, md, write

CELLS = []

CELLS.append(md(r"""
# 02: quotes

Pulls arrive long, one row per ticker, date and field, and there is exactly one pipeline
through them: read long, map each ticker to a column label, pivot by field. Only the map
changes between one instrument and the next; the reshaping never does.

`QuoteSource` is where that pipeline lives. `ParquetSource` reads it off disk, `FrameSource`
takes a frame already sitting in memory, and both share the pipeline through the same base
class. Files that carry all three quoted sides come back as a `Quotes` object, holding aligned
mid, bid and ask panels. Single-field data such as a rate curve has no sides, so it comes back
as a plain frame or series instead.
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
## The long frame, before any pivoting

`ParquetSource` reads one or more parquet files and concatenates them; `long_frame()` returns
the result exactly as validated, four columns, `ticker`, `date`, `field` and `value`, one row
per observation. Nothing is pivoted yet. This is the shape every pull is stored in, and the
shape `quotes`, `panel` and `series` all start from below.
"""))

CELLS.append(code(r"""
from fxcarry import Catalog, FrameSource, ParquetSource

catalog = Catalog.default()
source = ParquetSource(DATA / "spot_daily.parquet")
long = source.long_frame()
print(long.shape)
long.head()
"""))

CELLS.append(md(r"""
## `label_map` meets `quotes`

`quotes(label_of, freq)` pivots the long frame once, on a `(field, label)` column index, and
slices the result into three panels, one per quoted field. Passing `catalog.label_map("spot")`
maps every spot ticker in the catalog to its ISO code, so the columns come back named by
currency rather than by ticker. All three sides come from that one pivot, so they always share
the same dates and the same columns; that shared origin is what lets `apply` and `invert`
below trust the alignment rather than re-checking it on every call.
"""))

CELLS.append(code(r"""
spot = source.quotes(catalog.label_map("spot"), freq="M")
print("mid", spot.mid.shape, "| bid", spot.bid.shape, "| ask", spot.ask.shape)
print("same index:", spot.mid.index.equals(spot.bid.index))
print("same columns:", list(spot.mid.columns) == list(spot.ask.columns))
spot.mid.iloc[-3:, :6].round(4)
"""))

CELLS.append(md(r"""
## Combining quotes: `apply` pairs sides, not objects

Turning forward points into an outright rate takes both the spot panel and the points panel,
cell by cell, one side at a time. `Quotes.apply` calls its function once per side: mid meets
mid, bid meets bid, ask meets ask, across every `Quotes` object involved. A function that took
two whole `Quotes` objects instead could still typecheck while grabbing bid off one argument
and ask off the other, and nothing would catch it until the resulting price looked wrong.
Pairing sides positionally removes that mistake from the space of things a caller can even
write. The cell below builds the outright quote's mid, bid and ask in one call, and the
function it passes to `apply` never sees a mixed pair.
"""))

CELLS.append(code(r"""
points = ParquetSource(DATA / "fwd_points_1m_daily.parquet").quotes(
    catalog.label_map("forward", "1M"), freq="M")
common = [c for c in spot.columns if c in points.columns]
outright = spot.select(common).apply(
    lambda s, p: pd.DataFrame({c: catalog[c].outright(s[c], p[c]) for c in common},
                              index=s.index),
    points.select(common))
outright.mid.iloc[-2:, :5].round(4)
"""))

CELLS.append(md(r"""
## `invert`, and why the sides swap

Some pairs are quoted the wrong way round for what a calculation needs, dollars per yen rather
than yen per dollar, and inverting them is more than replacing $x$ with $1/x$: the sides have
to swap as well. For $a \ge b > 0$, $1/a \le 1/b$, so the larger of two positive numbers has
the smaller reciprocal. A bid is the lower of a pair's two native quotes and an ask is the
higher one, so once both are reciprocated the old ask becomes the new bid and the old bid
becomes the new ask. `Quotes.invert` performs that swap. Skipping it would leave the wider
reciprocal labelled bid and the narrower one labelled ask, a spread that reads negative,
which is another way of saying the quote would be paying a counterparty for trading against
it instead of the other way round.
"""))

CELLS.append(code(r"""
jpy = spot.select(["JPY"])
flipped = jpy.invert()
row = -1
print(f"native  bid {jpy.bid.iloc[row, 0]:.4f}  ask {jpy.ask.iloc[row, 0]:.4f}")
print(f"flipped bid {flipped.bid.iloc[row, 0]:.8f}  ask {flipped.ask.iloc[row, 0]:.8f}")
print(f"1/ask = {1 / jpy.ask.iloc[row, 0]:.8f}  is the new bid")
"""))

CELLS.append(md(r"""
## The check: inverting a well-formed quote cannot cross it

$1/a \le 1/b$ for $a \ge b > 0$ is not just an algebra fact about two numbers, it is a property
`invert` had better preserve on every column of a live panel: reciprocating a bid-ask pair
that starts non-crossed should never produce one that is crossed. The panel this notebook has
been using is not spotless, though. Seven cells in the monthly spot pull already have bid
above ask before anything is inverted, so the invariant below is asserted only where the
source itself is well formed, and `crossed()` is the separate check that reports the rest,
cells where `bid <= mid <= ask` fails outright rather than just `bid <= ask`.
"""))

CELLS.append(code(r"""
well_formed = spot.bid <= spot.ask
gap = (spot.invert().ask - spot.invert().bid).where(well_formed)
assert float(gap.min().min()) >= 0.0, "inverting crossed a well formed quote"

# NaN comparisons are always False, so a strict bid > ask isolates the real violations
# from the missing quotes that "not well_formed" alone would also catch.
crossed_bid_ask = spot.bid > spot.ask
print(f"cells where the pull has bid > ask: {int(crossed_bid_ask.sum().sum())} "
      f"of {well_formed.size}")
print(f"cells failing bid <= mid <= ask:    {int(spot.crossed().sum().sum())}")
print(f"inverted spread, minimum over well formed cells: {float(gap.min().min()):.1f}")
"""))

CELLS.append(md(r"""
## `spread`, `half_spread` and `coverage`

`spread()` is `ask - bid`, in the quote's native units. `half_spread(relative=True)` is half
of that as a fraction of mid, which is what actually compares across currencies quoted at very
different levels: a yen quote sits in the hundreds, a Kuwaiti dinar quote is a fraction of one,
and only a relative number puts the two on the same footing. `coverage()` reads the first
valid date, the last valid date and the observation count off mid, one row per column, which
is the fastest way to spot a currency whose history starts later than the rest of the panel.
"""))

CELLS.append(code(r"""
print("median half spread, basis points")
print((spot.half_spread().median() * 1e4).round(2).sort_values().head(8))
spot.coverage().head(6)
"""))

CELLS.append(md(r"""
## Single-field data: `panel` and `series`

A T-bill yield or a short-rate benchmark has one number a day, not three, so there is no bid
or ask to align and `quotes` has nothing to build. `series` reads one ticker's one field as a
plain series; `panel` does the same for a whole label map at once, still a date-by-label
frame, but with a single value per cell rather than three.
"""))

CELLS.append(code(r"""
bill = ParquetSource(DATA / "tbill_daily.parquet").series("GB1M Index", freq="M") / 100.0
rates = ParquetSource(DATA / "fx_short_rate_daily.parquet").panel(
    catalog.label_map("rate", "3M"), freq="M")
print(f"US 1M bill, {bill.index[-1]:%Y-%m-%d}: {bill.iloc[-1]:.4%}")
print("3M benchmarks:", list(rates.columns))
"""))

CELLS.append(md(r"""
## What happens when the sides are not there

Calling `quotes` on data that never carried a bid or an ask is a request `QuoteSource` cannot
fill, and it says so rather than returning a `Quotes` object with two panels silently full of
NaN.
"""))

CELLS.append(code(r"""
try:
    ParquetSource(DATA / "tbill_daily.parquet").quotes({"GB1M Index": "USD"})
except ValueError as err:
    print(err)
"""))

CELLS.append(md(r"""
## `FrameSource`, for a hand-built example and for testing

`ParquetSource` reads from disk; `FrameSource` wraps a long frame that is already sitting in
memory, and shares everything downstream of `long_frame()` with it, `quotes`, `panel` and
`series` all work the same way on both. That makes it the natural way to build a small worked
example by hand, or to test a downstream calculation against numbers whose right answer is
known in advance, without going anywhere near a parquet file.
"""))

CELLS.append(code(r"""
hand = pd.DataFrame({
    "ticker": ["AUDUSD Curncy"] * 6,
    "date": pd.to_datetime(["2026-01-30"] * 3 + ["2026-02-27"] * 3),
    "field": ["PX_LAST", "PX_BID", "PX_ASK"] * 2,
    "value": [0.6540, 0.6539, 0.6541, 0.6602, 0.6601, 0.6603],
})
FrameSource(hand).quotes({"AUDUSD Curncy": "AUD"}).mid
"""))

CELLS.append(md(r"""
## Several files, one source

`ParquetSource` accepts more than one path, concatenates everything it reads, and then
deduplicates on `(ticker, date, field)`, keeping the last row it sees for each combination.
That is what lets a refreshed pull sit alongside an older one without editing either file:
list the new pull after the old one, and the newer value wins wherever a ticker, date and
field repeat, while everything neither file shares still comes through untouched.
`notebooks/04_hedged_leg_from_first_principles.ipynb` uses exactly this to combine
`spot_daily.parquet` with the broader and emerging-market pulls that extend its coverage.
"""))

CELLS.append(md(r"""
## Check yourself

**Why does `apply` pair sides rather than objects?** Because a function written to combine two
`Quotes` objects wholesale would still run even if it read bid off one argument and ask off
the other by mistake, and nothing would flag it until the resulting price looked wrong. Pairing
sides positionally, mid with mid, bid with bid, ask with ask, removes that mistake from what a
caller can even write; the function passed to `apply` above only ever sees matched sides.

**What breaks if `invert` does not swap the sides?** For $a \ge b > 0$, the reciprocal of the
old bid, $1/b$, is the larger of the two new numbers, and the reciprocal of the old ask, $1/a$,
is the smaller one. Reciprocating in place without relabelling would leave the panel called
bid holding the larger number and the panel called ask holding the smaller one, so every
inverted spread would come out negative. `spread` and `half_spread` reading those mislabeled
panels would report a negative transaction cost on a quote whose native form has a perfectly
ordinary positive one, and the assertion in the check above would fail on the very first
well-formed cell it touched.

**Why is `crossed` a warning rather than an error?** Because it inspects data pulled from a
real terminal across four decades, and some cells will fail the ordering no matter how careful
the pull is, a bad print, a stale quote crossed against a moving market, whatever produced the
194 cells `crossed()` reports above. Seven of those are the narrower failure, bid above ask
outright; the rest keep their sides in order but put mid outside them. Raising on the first
crossed cell would stop every calculation the moment the pull touched one bad tick. Returning a
boolean frame instead lets the caller count the damage, decide whether to filter it out, and
move on.
"""))

write(CELLS, Path(__file__).parents[2] / "notebooks" / "tutorial" / "02_quotes.ipynb")
