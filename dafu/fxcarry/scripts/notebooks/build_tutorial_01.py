"""Generate notebooks/tutorial/01_catalog.ipynb."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from _nb import code, md, write

CELLS = []

CELLS.append(md(r"""
# 01: the catalog

`fxcarry.catalog` is where the library starts: identity and convention, not data. A
`Currency` knows what a currency is called, which pair it trades against the dollar, how its
forward points scale, and what its tickers look like. It never opens a parquet file and never
sees a number that moves from one day to the next. That is `fxcarry.quotes`, the subject of
the next notebook.

This notebook works through the three names the module exports. `Currency` is one currency's
identity. `Catalog` is a set of them, plus the parsing that inverts what those currencies
build. `TickerId` is the shape a ticker string decodes into.
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
## One currency, opened up

`Currency` is a frozen dataclass with five fields: `iso`, `pair`, `point_scale`,
`spot_ticker`, `fwd_root`. Everything else on the class is a method that reads one of these
five rather than storing anything new. Two currencies, side by side, show the whole shape at
once.
"""))

CELLS.append(code(r"""
from fxcarry import Catalog

catalog = Catalog.default()
jpy, aud = catalog["JPY"], catalog["AUD"]
pd.DataFrame([vars(jpy), vars(aud)], index=["JPY", "AUD"])
"""))

CELLS.append(md(r"""
## Quote direction, read off the pair

The market does not quote every currency the same way round. `AUDUSD` is already dollars per
Australian dollar. `USDJPY` is yen per dollar, the other way up. `Currency` does not store
which convention applies; the `quoted_usd_per_fcu` property reads it straight off the pair
string, `True` whenever the pair ends in `USD`. `to_usd_per_fcu` uses that property to invert
a quote only when the market itself has not already done so. The code cell below also lists
every currency already quoted that way across the whole catalog, not just the two examples.
"""))

CELLS.append(code(r"""
print(f"{jpy.pair}  quoted_usd_per_fcu = {jpy.quoted_usd_per_fcu}")
print(f"{aud.pair}  quoted_usd_per_fcu = {aud.quoted_usd_per_fcu}")
print(f"157.20 yen per dollar is {jpy.to_usd_per_fcu(157.20):.8f} dollars per yen")
print(f"0.6540 already points the right way: {aud.to_usd_per_fcu(0.6540):.8f}")

usd_quoted = [c.iso for c in catalog if c.quoted_usd_per_fcu]
print(f"\nquoted dollars per foreign currency unit already, {len(usd_quoted)} of "
      f"{len(catalog)}: {usd_quoted}")
"""))

CELLS.append(md(r"""
## Point scales: a difference in pips, not a level

A forward-points quote is not the forward rate. It is a difference from spot, expressed in
pips, and the size of a pip is a per-currency convention rather than something universal:

$$F^{\text{nat}} = S^{\text{nat}} + \frac{\text{points}}{\text{scale}}$$

For most pairs a pip is one ten-thousandth of the quote, `point_scale = 10000`. The yen quotes
in whole units to two decimal places instead, so its scale is 100: a print of $-40.85$ points
means $-0.4085$ yen. Using the wrong scale here does not throw an error, and it does not put the
forward on the wrong side of spot either. Both divisors leave this outright below spot, as the
cell shows; the default one just leaves it a hundredth as far below. That is what makes the
mistake dangerous. Carry computed off the wrong outright is off by the same factor as the scale
error and still looks like an ordinary small number, so nothing about the arithmetic itself
signals it. `notebooks/tutorial/08_reference.ipynb` carries these same numbers through to the
annualized carry, and `notebooks/tutorial/03_curves.ipynb` shows what a currency pinned near
zero does to a sorted book. `Currency.outright` applies the formula above; `point_scale` is
public so anything that needs to display raw points, rather than convert them, can do so
honestly.
"""))

CELLS.append(code(r"""
print(f"JPY scale {jpy.point_scale:>8,.0f}   -40.85 points = {-40.85 / jpy.point_scale:+.4f} yen")
print(f"AUD scale {aud.point_scale:>8,.0f}    12.30 points = {12.30 / aud.point_scale:+.6f}")

# The same points print through both divisors. AUD's 10,000 is the default that any pair
# without its own POINT_SCALE entry takes, so it is also what JPY would get if its entry were
# missing, which is the realistic way this goes wrong.
spot_native = 157.20
right = jpy.outright(spot_native, -40.85)
wrong = spot_native + -40.85 / aud.point_scale
print(f"\nspot     {spot_native:>9.4f} yen per dollar")
print(f"outright {right:>9.4f} with JPY's scale of {jpy.point_scale:,.0f}, "
      f"{spot_native - right:.6f} below spot")
print(f"outright {wrong:>9.4f} with the default {aud.point_scale:,.0f}, "
      f"{spot_native - wrong:.6f} below spot")
print("both below spot; the default divisor just puts it a hundredth as far below")
"""))

CELLS.append(md(r"""
## Building tickers

Every quote in the catalog resolves to a Bloomberg-style ticker, and `Currency` builds all of
them. `spot_ticker` is stored directly. `fwd_ticker(tenor)` appends a tenor to the forward
root. `vol_ticker(kind, tenor, delta)` covers the three pieces of a quoted smile: `"atm"` for
the at-the-money level, which takes no delta, and `"rr"` or `"bf"` for a risk reversal or
butterfly at a wing delta such as 25 or 10.
"""))

CELLS.append(code(r"""
print(jpy.spot_ticker, "|", jpy.fwd_ticker("3M"))
print(catalog["BRL"].fwd_ticker("1M"), " <- NDF root, not BRL1M")
for kind, delta in [("atm", None), ("rr", 25), ("bf", 10)]:
    print(f"{kind:>4} {delta}  ->  {jpy.vol_ticker(kind, '1M', delta)}")
"""))

CELLS.append(md(r"""
## NDF roots, the concrete reason `fwd_root` exists

`fwd_root` is a separate field from `iso` because the two disagree for a handful of
currencies. Their spot still trades under the ISO pair, but the forward is a non-deliverable
forward quoted under its own Bloomberg root: `BRL1M` returns nothing, `BCN1M` is the ticker
that actually loads. Building the table below by filtering the catalog for `fwd_root != iso`
is also the fastest way to find every currency this affects, rather than trusting a comment
somewhere to have listed them all.
"""))

CELLS.append(code(r"""
pd.DataFrame([(c.iso, c.pair, c.fwd_root, c.fwd_ticker("1M"))
              for c in catalog if c.fwd_root != c.iso],
             columns=["iso", "pair", "fwd_root", "1M forward ticker"])
"""))

CELLS.append(md(r"""
## The catalog as a collection

`Catalog` supports `len`, `in` and iteration, and adds `isos` for the currency codes in
catalog order and `subset` for picking a smaller catalog out of a larger one, order preserved.
`Catalog.with_legacy()` adds the currencies the euro replaced, printed below as a direct
count rather than something to work out from the two catalog sizes: they stopped trading on
31 December 1998, which is a fact about the world rather than a modeling choice, so it belongs
in the library. Any other subset, such as the G10 built below, is a choice a particular piece
of research makes, so it belongs at the call site and not baked into `Catalog` itself.
"""))

CELLS.append(code(r"""
print(len(catalog), "currencies;", "JPY" in catalog, "|", "XXX" in catalog)
g10 = catalog.subset(["AUD", "CAD", "CHF", "EUR", "GBP", "JPY", "NOK", "NZD", "SEK"])
print("subset keeps order:", g10.isos)

legacy = Catalog.with_legacy()
print(f"with legacy: {len(legacy)} currencies, {len(legacy) - len(catalog)} more than default")
"""))

CELLS.append(md(r"""
## `tickers` and `label_map`

`tickers(kind, tenors, deltas)` builds every ticker of one kind across the whole catalog, in
catalog order and deduplicated. `label_map(kind, tenor, delta)` builds the same set but keyed
the other way round, ticker to ISO code. That is the only thing a quote loader needs from a
catalog: which column each ticker pivots into once the long parquet file is read. Everything
else `Catalog` offers exists to help a human read the tickers; `label_map` is what a machine
reads.
"""))

CELLS.append(code(r"""
print(catalog.tickers("forward", ["1M"])[:4])
print(catalog.tickers("rr", ["1M"], [25])[:2])
print(dict(list(catalog.label_map("forward", "1M").items())[:4]))
"""))

CELLS.append(md(r"""
## The check: a builder and a parser are inverses

`vol_ticker` turns a currency, a kind, a tenor and a delta into a string. `Catalog.parse` does
the opposite: given a string, it recovers those same four pieces as a `TickerId`, or returns
`None` if the string is not a ticker this catalog covers. If the two are really inverses,
every option ticker the catalog can build should parse back to exactly the fields it was built
from, on all 35 currencies at once rather than on one hand-picked example.
"""))

CELLS.append(code(r"""
built = catalog.tickers("rr", ["1M", "3M"], [10, 25]) + catalog.tickers("atm", ["1M"])
decoded = [catalog.parse(t) for t in built]
assert all(d is not None for d in decoded), "a built ticker failed to parse"
assert all(catalog[d.iso].vol_ticker(d.kind, d.tenor, d.delta) == d.symbol
           for d in decoded), "round trip changed the ticker"
print(f"{len(built)} tickers built and parsed back with no change")
print(catalog.parse("USDJPY25R1M BGN Curncy"))
print(catalog.parse("SOMETHING ELSE Curncy"), "<- not ours, so None")
"""))

CELLS.append(md(r"""
## Check yourself

**Why is `fwd_root` not always the ISO code?** Because the forward market and the spot market
are not always the same market. A handful of countries restrict their currency from trading
offshore, so international banks quote a non-deliverable forward instead: a cash-settled
contract on the exchange rate, booked under its own Bloomberg root rather than the currency's
own. `BRL`, `CLP`, `COP`, `IDR`, `INR`, `PEN` and `TWD` all work this way in the default
catalog. Their spot ticker is the ordinary ISO pair; their forward is not.

**What does `quoted_usd_per_fcu` decide downstream?** Which way a panel of many currencies
gets flipped before anything is compared across them. Raw quotes point in whatever direction
the market happens to trade in: the "quote direction" section above lists the four currencies
already quoted dollars per foreign currency unit, and the rest are quoted the other way round.
Every downstream calculation, carry, excess return, a cross-sectional rank, needs a rise in
the number to mean the same thing for every currency in the panel: the foreign currency
getting stronger. That alignment happens once, off this one property, rather than being
re-derived pair by pair.

**Why does `parse` return `None` rather than raise?** Because failing to match is the expected
outcome most of the time it is called. `parse` exists to sort tickers, tell which ones belong
to this catalog and which do not, out of a file that was pulled by ticker prefix and inevitably
contains names the catalog has no opinion about. Raising would turn that sort into a
try/except around every call; returning `None` lets the caller filter with a plain
comprehension instead.
"""))

write(CELLS, Path(__file__).parents[2] / "notebooks" / "tutorial" / "01_catalog.ipynb")
