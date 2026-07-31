"""Generate notebooks/tutorial/08_reference.ipynb."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from _nb import code, md, write

CELLS = []

CELLS.append(md(r"""
# 08: reference

`fxcarry.reference` is where the library keeps what a human read off a terminal once: which
ticker a currency's spot and forward quote under, how many pips make one price unit, how a
year gets counted, and where an economic release lives. Every value here is a literal, so
nothing in this module computes. `fxcarry.catalog`, covered in notebook 01, is where these
tables get behaviour: a `Currency` builds tickers and converts points using what `reference`
stores, but `reference` itself never builds or converts anything.

This notebook works through the module's tables in the order a reader would reach for them:
quoted fields, the ticker catalog, point scales, the two constants that get conflated most
often, the option surface grid, the rate benchmarks, and the macro release tables, closing
with a checklist for adding a currency and a short self-test.
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
## Quoted fields

Every quote pulled from the terminal comes tagged with one of three fields. `FIELDS` lists
them; `FIELD_TO_KEY` says which attribute each one lands on once a quote gets split into
sides. `PX_LAST` becomes `mid`, and the two touch prices become `bid` and `ask`.
"""))

CELLS.append(code(r"""
from fxcarry import reference

print(reference.FIELDS)
print(reference.FIELD_TO_KEY)
"""))

CELLS.append(md(r"""
## The ticker catalog

`SPOT_FWD_TICKERS` is the map every other table in the module, and every `Currency` in
`fxcarry.catalog`, is built from: ISO code to a `(spot ticker, 1M forward-points ticker)` pair.
`LEGACY_EURO_TICKERS` holds the currencies the euro replaced on 31 December 1998, kept
separate because they stopped trading rather than because anyone chose to drop them.
"""))

CELLS.append(code(r"""
print(f"{len(reference.SPOT_FWD_TICKERS)} currently traded, "
      f"{len(reference.LEGACY_EURO_TICKERS)} replaced by the euro in 1999")
pd.DataFrame(reference.SPOT_FWD_TICKERS, index=["spot", "1M forward"]).T.head(8)
"""))

CELLS.append(md(r"""
For most currencies the forward ticker's root is just the ISO code with `1M` appended. A
handful of markets restrict the currency from trading offshore, so the forward quotes as a
non-deliverable forward under its own Bloomberg root instead. Filtering the catalog for a
forward root that does not match its ISO code finds every one of them directly, rather than
trusting a comment to have listed them all. `notebooks/tutorial/01_catalog.ipynb` already builds
this same list off `Currency.fwd_root`; the table below rebuilds it from the raw
`SPOT_FWD_TICKERS` literal instead, without going through `Currency` at all.
"""))

CELLS.append(code(r"""
ndf = [(iso, spot, fwd) for iso, (spot, fwd) in reference.SPOT_FWD_TICKERS.items()
       if fwd.split("1M")[0] != iso]
print(f"{len(ndf)} currencies quote their forward under a different root:")
pd.DataFrame(ndf, columns=["iso", "spot ticker", "1M forward ticker"])
"""))

CELLS.append(md(r"""
## Point scales, and the check that a scale is not decorative

A forward-points quote is a difference from spot in pips, not a level, and the size of a pip is
a per-currency convention: `POINT_SCALE` is the divisor that turns a points print into price
units. Most pairs quote in ten-thousandths, so `"default"` is 10,000. The yen and a handful of
others quote coarser, and `POINT_SCALE` states each one explicitly rather than deriving it from
anything.

Each non-default scale in the table was pinned down the same way: ask which divisor puts the
implied one-month carry within range of a plausible interest-rate differential. A scale wrong by
a factor of 100 does not raise an error. It leaves the outright forward on the correct side of
spot but two orders of magnitude too close to it, and the carry that comes out the other end
still looks like a number, just the wrong one, off by the same factor as the scale error. The
cell below states that factor rather than leaving it implicit, comparing JPY's carry under its
correct scale of 100 against the same arithmetic run with the default scale of 10,000.

Both branches invert to dollars per yen before taking the log, because that is the panel
`SpotForward.carry` is defined on. USDJPY is quoted yen per dollar, so running the carry formula
on the native quote returns the right magnitude with the sign reversed, which is the one mistake
this section cannot afford to make. `notebooks/tutorial/03_curves.ipynb` sorts the whole panel's
carry and prints JPY in the negative tail; the cell below gets the same sign on these
illustrative numbers. `notebooks/tutorial/01_catalog.ipynb` already runs this same JPY pair
through `Currency.outright` under both divisors and stops at the two resulting rates; the
comparison below carries the same numbers one step further, into the annualized carry a wrong
scale would produce.
"""))

CELLS.append(code(r"""
from fxcarry import Catalog

jpy = Catalog.default()["JPY"]
spot_native = 157.20  # yen per dollar, the direction USDJPY is quoted in
points = -40.85

# carry is minus the log discount on the dollars-per-foreign-unit panel, so the reciprocals go
# in, not the native quotes. Feeding the native quotes straight in flips the sign.
def carry(fwd_native):
    return -np.log((1 / fwd_native) / (1 / spot_native)) * 12

right_fwd = jpy.outright(spot_native, points)
# reference.POINT_SCALE["default"] rather than a bare 10000.0, so the wrong-scale branch
# points at the same table the right-scale branch reads its own divisor from.
wrong_fwd = spot_native + points / reference.POINT_SCALE["default"]

print(f"spot {spot_native:.2f} yen per dollar is {1 / spot_native:.8f} dollars per yen")
print(f"right scale {jpy.point_scale:,.0f}:   outright {right_fwd:.4f} native, "
      f"{1 / right_fwd:.8f} usd per jpy, carry {carry(right_fwd):+.4%} per year")
print(f"default scale {reference.POINT_SCALE['default']:,.0f}: outright {wrong_fwd:.4f} native, "
      f"{1 / wrong_fwd:.8f} usd per jpy, carry {carry(wrong_fwd):+.4%} per year")
print(f"off by a factor of {carry(right_fwd) / carry(wrong_fwd):.0f}, which is the scale ratio")
print("the forward is above spot in dollars per yen, so the yen is dear forward and yields "
      "less than the dollar, so its carry is negative")
"""))

CELLS.append(md(r"""
## Two annualization constants, easy to conflate

`PERIODS_PER_YEAR` and `DAY_COUNT` answer different questions and share no formula.
`PERIODS_PER_YEAR` counts how many return observations make a year, so a per-period mean or
volatility can be scaled up to a yearly rate: multiply a mean by 12, or a monthly volatility by
$\sqrt{12}$. It never looks at a calendar; a 28-day February and a 31-day March both count as
one twelfth of a year. `DAY_COUNT` is a money-market day-count denominator: it turns an
annualized quoted yield into the interest actually accrued over a stated number of elapsed
days, and it does look at the calendar, because accrued interest depends on how many days
actually passed. Using one where the other belongs is not a rounding error; it changes what the
resulting number means.
"""))

CELLS.append(code(r"""
print("PERIODS_PER_YEAR", reference.PERIODS_PER_YEAR)
print("DAY_COUNT       ", dict(list(reference.DAY_COUNT.items())[:5]))
print("RESAMPLE_ALIAS  ", reference.RESAMPLE_ALIAS)
print("DEFAULT_NW_LAGS ", reference.DEFAULT_NW_LAGS)
"""))

CELLS.append(md(r"""
The difference shows up as soon as the calendar is not exactly one twelfth of a year, which it
never is. Accrue the same illustrative 5%/yr quoted USD deposit rate over a 28-day February and
a 31-day March using `DAY_COUNT["USD"]`, then annualize an illustrative monthly mean return
using `PERIODS_PER_YEAR["M"]`, which does not care which month the return came from.
"""))

CELLS.append(code(r"""
quoted_rate = 0.05  # illustrative 5%/yr quoted USD deposit rate, not pulled from anywhere
feb_days, mar_days = 28, 31
accrued_feb = quoted_rate * feb_days / reference.DAY_COUNT["USD"]
accrued_mar = quoted_rate * mar_days / reference.DAY_COUNT["USD"]
print(f"interest accrued, {feb_days}-day February: {accrued_feb:.4%}")
print(f"interest accrued, {mar_days}-day March:    {accrued_mar:.4%}")

monthly_mean = 0.002  # illustrative mean monthly return, not pulled from anywhere
annualized = monthly_mean * reference.PERIODS_PER_YEAR["M"]
print(f"\na {monthly_mean:.2%} monthly mean annualizes to {annualized:.2%} through "
      f"PERIODS_PER_YEAR['M'] = {reference.PERIODS_PER_YEAR['M']:.0f}, the same multiplier "
      f"whether the month behind it held {feb_days} days or {mar_days}")
"""))

CELLS.append(md(r"""
## The option surface grid

`FWD_TENORS` is the full forward curve grid. `VOL_TENORS` and `SMILE_TENORS` are the same set
of tenors the vol surface quotes at, since the wings are quoted at every tenor the at-the-money
level is. `VOL_DELTAS` are the wing deltas, down to the thin 5-delta tail. `VOL_SOURCE` is the
generic Bloomberg quote-source suffix every option ticker carries. `VOL_CURRENCIES` is narrower
than the spot and forward catalog: not every currency in `SPOT_FWD_TICKERS` has a quoted option
surface.
"""))

CELLS.append(code(r"""
print("forward tenors", reference.FWD_TENORS)
print("vol tenors    ", reference.VOL_TENORS)
print("wing deltas   ", reference.VOL_DELTAS, "| source suffix", reference.VOL_SOURCE)
print(f"{len(reference.VOL_CURRENCIES)} currencies with a quoted surface, of "
      f"{len(reference.SPOT_FWD_TICKERS)} in the spot and forward catalog")
"""))

CELLS.append(md(r"""
## Rate benchmarks: an explicit map, because there is no pattern to derive

Money-market benchmarks do not share a naming convention the way forward tickers do. The LIBOR
family follows a four-character prefix plus a zero-padded tenor, but CDOR, BBSW, WIBOR and the
rest each use their own local root, so `SHORT_RATE_TICKERS` writes every one out rather than
generating them from a rule. It also covers far fewer currencies than `SPOT_FWD_TICKERS`, which
is why the library inverts covered interest parity to get an implied foreign rate for most
currencies instead of pulling one directly; `notebooks/04_hedged_leg_from_first_principles.ipynb`
works through that inversion on one leg.

`RATE_TICKER_TO_KEY` is the reverse of `SHORT_RATE_TICKERS`, ticker to `(iso, tenor)`, and it is
built with a dict comprehension in `reference.py` rather than written out a second time. Two
copies of the same map can drift apart; one map and a derived inverse cannot.
"""))

CELLS.append(code(r"""
pd.DataFrame(reference.SHORT_RATE_TICKERS).T.head(10)
"""))

CELLS.append(code(r"""
print(reference.RATE_TICKER_TO_KEY["US0003M Index"])
# SHORT_RATE_TICKERS also keys USD, the domestic leg every pair already prices against, and USD
# has no pair of its own so it never appears in SPOT_FWD_TICKERS. Comparing the two lengths
# directly would overstate the overlap by one; intersecting them is what answers how many
# catalog currencies carry a benchmark. notebooks/data_dictionary/01 uses the same intersection.
with_benchmark = sorted(set(reference.SHORT_RATE_TICKERS) & set(reference.SPOT_FWD_TICKERS))
print(f"{len(reference.SHORT_RATE_TICKERS)} keys in SHORT_RATE_TICKERS, of which "
      f"{len(with_benchmark)} are currencies in the spot and forward catalog's "
      f"{len(reference.SPOT_FWD_TICKERS)}; the extra key is USD, the domestic leg")
"""))

CELLS.append(md(r"""
## Macro release tables, unverified

`MACRO_INDICATORS` names a set of economic releases: what each one measures, how often it
prints, what unit it is in, and how many periods it typically lags the period it describes.
`MACRO_TICKERS` maps a subset of those indicators to a Bloomberg ticker, country by country.

Neither table has been checked against a terminal. The tickers below were written from a
general sense of Bloomberg's naming conventions, not read off a screen, and no macro series of
any kind exists anywhere in `data/raw`: every pull the rest of this library reads from is FX
spot, forwards, vols and short rates. Treat every entry in `MACRO_TICKERS` as a starting point
for a terminal session, not as a table this library has ever actually pulled.
"""))

CELLS.append(code(r"""
print(f"{len(reference.MACRO_INDICATORS)} indicators defined, "
      f"{len(reference.MACRO_TICKERS)} countries mapped")
pd.DataFrame(reference.MACRO_INDICATORS,
             index=["description", "frequency", "unit", "lag"]).T.head(6)
"""))

CELLS.append(md(r"""
## How to add a currency

Every edit lives in one file, `reference.py`, and touches at most three of its tables.

- Add one entry to `SPOT_FWD_TICKERS`: the ISO code, its spot ticker, and its 1M forward-points
  ticker. If the forward trades as a non-deliverable forward, the ticker's root will not match
  the ISO code, the same way it does not for BRL, CLP, COP, IDR, INR, PEN and TWD above.
- Add an entry to `POINT_SCALE` only if the pair is not a plain four-decimal quote. Pin the
  scale down by checking which divisor puts the implied one-month carry within range of a
  plausible rate differential, the check section 3 above walked through for JPY.
- Optionally add an entry to `SHORT_RATE_TICKERS` if a local money-market benchmark exists and
  is worth pulling directly, rather than relying on the parity inversion.
- Nothing else. `Catalog.default()` rebuilds itself from `SPOT_FWD_TICKERS` and `POINT_SCALE`
  on every call, `RATE_TICKER_TO_KEY` rebuilds itself from `SHORT_RATE_TICKERS`, and every
  ticker-building method on `Currency` reads the fields the new entry supplied. No other module
  holds a currency's ticker string, so there is nowhere else to add one.
"""))

CELLS.append(md(r"""
## Check yourself

**What does a wrong point scale look like in a backtest?** Not an error. Section 3's JPY
example used the correct scale of 100 to get a carry of -3.1224% per year; running the same
points through the default scale of 10,000 instead gives -0.0312%, a hundredth of the true size
and still a perfectly plausible-looking small carry number. A backtest built on the wrong scale
would run to completion and report results, just results off by the scale ratio on every
currency the wrong scale touches. Catching it takes an independent estimate of the rate
differential to compare against; nothing about the arithmetic itself signals the mistake.

**Why is `RATE_TICKER_TO_KEY` derived rather than written out?** Because `SHORT_RATE_TICKERS`
is already the source of truth for which ticker each currency and tenor uses, and writing the
reverse map out by hand would give the module two places that could disagree about the same
ticker. `reference.py` builds it with one dict comprehension over `SHORT_RATE_TICKERS.items()`,
so adding, removing or renaming a rate ticker in the forward map changes the reverse map for
free, the same way notebook 01's `Catalog.parse` stayed correct without a second copy of
anything `Currency` already builds.

**Why does no other module hold a ticker string?** So that adding or fixing a ticker is a
one-line change in one file. `fxcarry.catalog` builds every ticker string it needs from the
data `reference` supplies rather than writing any of them out again; its own `Curncy` literals
are regex patterns and docstring examples describing the generic Bloomberg suffix shape, not
any specific currency's identity. If a second module hard-coded even one currency's ticker,
correcting that ticker would mean finding every place it had been copied, which is exactly the
kind of drift the checklist in section 8 exists to prevent.
"""))

write(CELLS, Path(__file__).parents[2] / "notebooks" / "tutorial" / "08_reference.ipynb")
