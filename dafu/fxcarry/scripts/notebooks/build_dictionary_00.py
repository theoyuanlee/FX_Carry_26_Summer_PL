"""Generate notebooks/data_dictionary/00_architecture_and_inventory.ipynb."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from _nb import code, md, write

CELLS = []

CELLS.append(md(r"""
# 00: architecture and inventory

This is the first of three notebooks in `data_dictionary/`. The nine tutorial notebooks in
`notebooks/tutorial/` teach `fxcarry` module by module, working from a `Catalog` and a handful
of illustrative numbers. None of them stop to look at the files those numbers come from. This
folder does that instead: notebook 01 works through spot, forwards and rates, notebook 02
through the option surfaces, and this one draws the map that the other two assume. Where the
files come from, what shape they arrive in, what each one holds, and how one read path turns a
parquet file on disk into the panels the rest of the library operates on.
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

CELLS.append(code(r"""
import pyarrow.parquet as pq
"""))

CELLS.append(md(r"""
## Where the files come from

A Bloomberg terminal session runs the pull notebooks under `notebooks/`
(`01_bloomberg_pull_fx` for the prices, `02_bloomberg_pull_macro` for the country macro
series), which write one long parquet per instrument group straight into `data/raw`. That
machine is the only place any of this is fetched fresh; everywhere else reads whatever the
terminal already produced. `notebooks/00_data_pipeline.ipynb` walks that chain stage by
stage, including the DVC and Box hop this notebook only mentions in passing.

DVC tracks each parquet by content hash rather than by the file itself. Box holds the actual
bytes, and `dvc pull`, run over an rclone WebDAV bridge, is what lands them on a machine that
has never touched the terminal. Git carries the `.dvc` pointer files, one per parquet, and
nothing else from `data/raw`: the parquets themselves are excluded by `.gitignore`, so a clone
of this repository has the code and the pointers but not the data until `dvc pull` runs.
"""))

CELLS.append(code(r"""
config = (ROOT / ".dvc" / "config").read_text()
print(config)

parquet_files = sorted(DATA.glob("*.parquet"))
dvc_files = sorted(DATA.glob("*.dvc"))
print(f"{len(parquet_files)} parquet files in data/raw, {len(dvc_files)} .dvc pointer files")

pointer = (DATA / "spot_daily.parquet.dvc").read_text()
print(f"\none pointer, spot_daily.parquet.dvc:\n{pointer}")
"""))

CELLS.append(md(r"""
## Long, not wide

Every one of those thirteen files shares one shape: four columns, `ticker`, `date`, `field`
and `value`, one row per observation. A pull that adds a new currency adds rows to this shape
rather than a new column, so nothing about the file format changes to widen the universe it
covers, only the list of tickers requested from the terminal.

`fxcarry.quotes.QuoteSource` is built on that regularity. `long_frame` returns the four columns
validated, and everything the class does afterwards, `quotes`, `panel`, `series`, is the same
pivot to a date index against whichever column the caller asks for. One reshaping pipeline
serves spot, forwards, vols and rates alike, because the long shape they arrive in never
differs between them.

## One file, opened

`tbill_daily.parquet` is the smallest file in the pull, which makes it a cheap first look at
the shape every other file shares.
"""))

CELLS.append(code(r"""
table = pq.read_table(DATA / "tbill_daily.parquet")
frame = table.to_pandas(date_as_object=False)
print(frame.dtypes.to_dict())
frame.head()
"""))

CELLS.append(md(r"""
## The inventory, kept cheap on purpose

One row per file needs a row count, a byte size, a distinct-ticker count and a date range.
Parquet keeps a row count and a byte size in its file metadata already, so those cost nothing
to read. It also keeps a per-row-group minimum and maximum for every column, so a date range
comes from that same metadata rather than from opening the column at all.

The one thing metadata cannot answer is how many distinct tickers a column holds: a minimum and
a maximum say nothing about what falls in between. `tickers.nunique()` needs the `ticker`
column actually read off disk. For twelve of the thirteen files that is a small read.
`fx_vol_daily.parquet` is the exception, at 16.0 million rows, and it is what the total below
is mostly spent on. Reading `date` the same way, as the brief for this notebook first drafted
it, would double that cost for no extra information, since the metadata already gives the exact
same range for free.
"""))

CELLS.append(code(r"""
import time


def date_range(handle, path):
    # Row-group statistics can be present but empty, has_min_max False, which happens when a
    # row group's date column is entirely null. min()/max() over a run of Nones then succeeds
    # silently and turns into NaT further down, no exception raised. Guarding on has_min_max
    # for every row group before trusting the metadata is what stops that from happening quietly;
    # falling back to an actual column read costs exactly what the brief's version always paid,
    # so a file that cannot answer from metadata is no worse off than before this optimization.
    col_idx = handle.schema_arrow.get_field_index("date")
    stats = [handle.metadata.row_group(g).column(col_idx).statistics
             for g in range(handle.metadata.num_row_groups)]
    if all(s is not None and s.has_min_max for s in stats):
        lo, hi = min(s.min for s in stats), max(s.max for s in stats)
        return pd.Timestamp(lo).date(), pd.Timestamp(hi).date()
    dates = pq.read_table(path, columns=["date"])["date"].to_pandas()
    return pd.Timestamp(dates.min()).date(), pd.Timestamp(dates.max()).date()


def summarize(path):
    # The brief's version also read a full "date" column to get the same first/last range.
    # Row-group statistics in parquet metadata already carry an exact min and max for every
    # column, so date_range() above gets it for free when every row group has one; only the
    # ticker count still costs anything on the common path, because nunique() has no metadata
    # shortcut.
    handle = pq.ParquetFile(path)
    tickers = pq.read_table(path, columns=["ticker"])["ticker"].to_pandas()
    first, last = date_range(handle, path)
    return {"rows": handle.metadata.num_rows,
            "MB": round(path.stat().st_size / 1e6, 1),
            "tickers": tickers.nunique(),
            "first": first, "last": last}


t0 = time.time()
inventory = pd.DataFrame({p.name: summarize(p) for p in sorted(DATA.glob("*.parquet"))}).T
elapsed = time.time() - t0

print(f"{len(inventory)} files, {inventory['rows'].astype(int).sum():,} rows, "
      f"{inventory['MB'].astype(float).sum():.0f} MB on disk, "
      f"inventoried in {elapsed:.1f} seconds")
inventory
"""))

CELLS.append(md(r"""
## What each file is for

The file names group into three families: spot and forward-points quotes, option-vol surfaces,
and rate or index benchmarks. Within a family, several files exist because the currency
universe grew in stages rather than because the shape changed; the next cell pulls out the
counts each paragraph below refers to.
"""))

CELLS.append(code(r"""
from fxcarry import Catalog, ParquetSource, reference


def pair_isos(path):
    "Distinct six-character market pairs on a file, reduced to the non-USD currency code."
    tickers = pq.read_table(path, columns=["ticker"])["ticker"].to_pandas().unique()
    pairs = sorted({t[:6] for t in tickers})
    return pairs, {(p[3:] if p.startswith("USD") else p[:3]) for p in pairs}

catalog = Catalog.default()

original_pairs, original_isos = pair_isos(DATA / "fx_vol_daily.parquet")
em_pairs, em_isos = pair_isos(DATA / "fx_vol_em_daily.parquet")
broad_pairs, broad_isos = pair_isos(DATA / "fx_vol_broad_daily.parquet")
all_vol_isos = original_isos | em_isos | broad_isos

print(f"fx_vol_daily.parquet:       {len(original_pairs)} pairs {original_pairs}")
print(f"fx_vol_em_daily.parquet:    {len(em_pairs)} pairs {em_pairs}")
print(f"fx_vol_broad_daily.parquet: {len(broad_pairs)} pairs {broad_pairs}")
print(f"\n{len(all_vol_isos)} currencies across the three files, matching "
      f"reference.VOL_CURRENCIES exactly: {all_vol_isos == set(reference.VOL_CURRENCIES)}")

spot_tickers = set(pq.read_table(DATA / "spot_daily.parquet",
                                 columns=["ticker"])["ticker"].to_pandas().unique())
current_spot = {c.iso: c.spot_ticker for c in catalog}
legacy_spot = {tk for tk, _ in reference.LEGACY_EURO_TICKERS.values()}
missing_spot = {iso: tk for iso, tk in current_spot.items() if tk not in spot_tickers}

print(f"\nspot_daily.parquet: {len(spot_tickers)} tickers, "
      f"{len(current_spot) - len(missing_spot)} of {len(current_spot)} currently traded "
      f"currencies, {len(legacy_spot & spot_tickers)} currencies the euro replaced")
print(f"{len(missing_spot)} currently traded currencies are not in spot_daily.parquet: "
      f"{sorted(missing_spot)}")

broad_file_tickers = set(pq.read_table(DATA / "spot_fwd_broad_daily.parquet",
                                       columns=["ticker"])["ticker"].to_pandas().unique())
broad_spot_isos = {iso for iso, tk in current_spot.items() if tk in broad_file_tickers}
has_spot_in_broad = sorted(broad_isos & broad_spot_isos)
already_has_spot = sorted(broad_isos - broad_spot_isos)
print(f"\nof the {len(broad_isos)} broad-extension vol pairs, {len(has_spot_in_broad)} have a "
      f"spot ticker in spot_fwd_broad_daily.parquet itself: {has_spot_in_broad}")
print(f"the other {len(already_has_spot)} already had one in spot_daily.parquet: "
      f"{already_has_spot}")
"""))

CELLS.append(code(r"""
import re


def fwd_roots(path):
    "Distinct forward-ticker roots: the letters before the first digit."
    tickers = pq.read_table(path, columns=["ticker"])["ticker"].to_pandas().unique()
    return sorted({re.match(r"^[A-Z]+", t).group() for t in tickers})


multi_roots = fwd_roots(DATA / "fwd_points_multi_daily.parquet")
grid_roots = fwd_roots(DATA / "fwd_points_grid_daily.parquet")
print(f"fwd_points_multi_daily.parquet: {len(multi_roots)} forward roots, full tenor curve")
print(f"fwd_points_grid_daily.parquet:  {len(grid_roots)} roots, none shared with the file "
      f"above: {set(grid_roots) & set(multi_roots)}")
print("these are exactly the NDF and EM/broad roots whose 1M and 3M points live in "
      "spot_fwd_em_daily.parquet and spot_fwd_broad_daily.parquet instead")

print(f"\nreference.SHORT_RATE_TICKERS covers {len(reference.SHORT_RATE_TICKERS)} currencies, "
      f"pulled as {int(inventory.loc['fx_short_rate_daily.parquet', 'tickers'])} tickers "
      f"across up to {len(reference.RATE_TENORS)} tenors each")
"""))

CELLS.append(code(r"""
# The tenor and delta grids the two paragraphs below describe in words, read straight off
# reference.py rather than typed out separately: FWD_TENORS is the forward curve grid,
# VOL_TENORS the vol term structure, VOL_DELTAS the wing deltas each surface quotes at.
print(f"reference.FWD_TENORS ({len(reference.FWD_TENORS)}): {reference.FWD_TENORS}")
print(f"reference.VOL_TENORS ({len(reference.VOL_TENORS)}): {reference.VOL_TENORS}")
print(f"reference.VOL_DELTAS: {reference.VOL_DELTAS}")
print(f"\nlegacy euro currencies, {len(reference.LEGACY_EURO_TICKERS)} of them: "
      f"{sorted(reference.LEGACY_EURO_TICKERS)}")
"""))

CELLS.append(md(r"""
**Spot and forwards.** `spot_daily.parquet` is the original spot pull: 37 tickers, 26 of the
currently traded currencies plus the 11 legacy currencies printed above, each one fixed into
the euro on 1 January 1999. That date is not something read off these files, it is the
historical fact the `LEGACY_EURO_TICKERS` grouping is built on; `reference.py` gives the same
date in its own comment. `spot_daily.parquet` does not cover every currently traded currency:
the nine printed above are missing entirely, and their spot ticker only appears in the two
files below instead. `spot_fwd_em_daily.parquet` and `spot_fwd_broad_daily.parquet` each bundle
a currency's spot ticker together with its forward points in one file. The EM file carries all
five pairs its vol extension covers; the broad file's vol extension covers nine pairs, but only
five of those have a spot ticker in `spot_fwd_broad_daily.parquet` itself, since the other four
already had one in `spot_daily.parquet`. Bundling spot and forward together in the same file is
what lets the five currencies that actually need it reach `catalog.label_map("spot")` at all.
`fwd_points_1m_daily.parquet` and `fwd_points_multi_daily.parquet` hold the 1-month forward
points and the same universe's full tenor curve, `reference.FWD_TENORS` printed above, `1W` out
to `2Y`, for the original 34-root universe; section 7 below has the exact relationship between
them. `fwd_points_grid_daily.parquet` fills in the tenors beyond 1M and 3M for the twelve NDF
and EM/broad roots, the same grid completion the original 34-root universe already had.

**Volatility.** `fx_vol_daily.parquet` is the original 19-pair vol pull, at the full tenor and
delta grid printed above: `reference.VOL_TENORS` runs `1W` to `2Y`, and `reference.VOL_DELTAS`
is `[5, 10, 25]`, each with a risk reversal and a butterfly. At 16.0 million rows it is the
largest file in the pull by a wide margin.
`fx_vol_em_daily.parquet` and `fx_vol_broad_daily.parquet` are the five-pair and nine-pair
extensions, each quoted at 1M and 3M with the 10 and 25-delta wings only when first pulled.
`fx_vol_grid_daily.parquet` is the same grid completion as the forward-points file above,
filling in the missing tenors and the 5-delta wing for those fourteen currencies. Put together,
the four vol files give every currency in `reference.VOL_CURRENCIES` a surface, which the cell
above checks rather than assumes.

**Rates and indices.** `fx_short_rate_daily.parquet` holds money-market benchmarks, one ticker
per currency and tenor, `PX_LAST` only, covering the LIBOR family plus CDOR, BBSW, WIBOR and
the rest of `reference.SHORT_RATE_TICKERS`. This is the direct alternative to the parity
inversion notebook 03 of the tutorial set works through, and it reaches fewer currencies than
that inversion can.
`tbill_daily.parquet` holds one ticker, the US 1-month bill `GB1M Index`, also `PX_LAST` only:
every leg in the book prices its domestic rate off this one series. `fx_dollar_index_daily.parquet`
holds two broad dollar indices, `BBDXY Index` and `DXY Curncy`, quoted two sided. Neither feeds
a currency-level calculation directly; they are a market-wide dollar gauge to compare a
currency's move against, not a leg of anything the library prices.
"""))

CELLS.append(md(r"""
## Which fields each file carries

Not every file is two sided. The pull for a rate benchmark or a bill only ever asked for
`PX_LAST`, since money-market benchmarks are not quoted with a bid and an ask the way a
tradable spot or option is.
"""))

CELLS.append(code(r"""
def fields(path):
    return sorted(pq.read_table(path, columns=["field"])["field"].to_pandas().unique())

fields_table = pd.Series({p.name: ", ".join(fields(p))
                          for p in sorted(DATA.glob("*.parquet"))}).to_frame("fields")
fields_table
"""))

CELLS.append(md(r"""
A file carrying only `PX_LAST` cannot produce a `Quotes`, since `Quotes` is three sides sharing
one index and there is only one side to give it. `QuoteSource.quotes` checks for exactly that
and raises rather than returning something with two sides silently filled with nothing; `panel`
exists for precisely this case, one field pulled straight through with no attempt at three
sides. `fx_short_rate_daily.parquet` demonstrates both halves of that in one cell.
"""))

CELLS.append(code(r"""
source = ParquetSource(DATA / "fx_short_rate_daily.parquet")
rate_labels = catalog.label_map("rate", tenor="1M")

try:
    source.quotes(rate_labels, freq="M")
except ValueError as exc:
    print(f"quotes() on a PX_LAST-only file raises:\n  {exc}")

one_month = source.panel(rate_labels, freq="M")
print(f"\npanel() instead: {one_month.shape}, last row of 1M rates:")
print(one_month.iloc[-1].dropna().round(3))
"""))

CELLS.append(md(r"""
## Where two files overlap

`fwd_points_1m_daily.parquet` and `fwd_points_multi_daily.parquet` both carry 1-month forward
points for the same 34 roots. `ParquetSource` concatenates every file it is given and drops
duplicate `(ticker, date, field)` rows, keeping whichever copy came from the file listed last.
So when the two overlap, the order they are passed in decides which value survives.
"""))

CELLS.append(code(r"""
def keys(path):
    return set(pq.read_table(path, columns=["ticker"])["ticker"].to_pandas().unique())

a, b = keys(DATA / "fwd_points_1m_daily.parquet"), keys(DATA / "fwd_points_multi_daily.parquet")
print(f"1M file {len(a)} tickers, multi-tenor file {len(b)} tickers, shared {len(a & b)}")
print("every 1M-file ticker is also in the multi-tenor file, at the same tenor")
"""))

CELLS.append(md(r"""
That overlap is not always the same number twice over. One print, `AUD1M Curncy` on
2026-07-15, differs by 0.01 points between the two files, which is enough to show which copy a
`ParquetSource` actually keeps rather than assuming it from the docstring.
"""))

CELLS.append(code(r"""
both = ParquetSource(DATA / "fwd_points_1m_daily.parquet", DATA / "fwd_points_multi_daily.parquet")
lf = both.long_frame()
row = lf[(lf["ticker"] == "AUD1M Curncy") & (lf["field"] == "PX_LAST")
        & (lf["date"] == "2026-07-15")]

only_1m = pq.read_table(DATA / "fwd_points_1m_daily.parquet",
                        filters=[("ticker", "==", "AUD1M Curncy"), ("field", "==", "PX_LAST"),
                                ("date", "==", pd.Timestamp("2026-07-15"))]).to_pandas()
only_multi = pq.read_table(DATA / "fwd_points_multi_daily.parquet",
                           filters=[("ticker", "==", "AUD1M Curncy"), ("field", "==", "PX_LAST"),
                                   ("date", "==", pd.Timestamp("2026-07-15"))]).to_pandas()

print(f"fwd_points_1m_daily.parquet alone:    {only_1m['value'].iloc[0]:+.2f}")
print(f"fwd_points_multi_daily.parquet alone: {only_multi['value'].iloc[0]:+.2f}")
print(f"ParquetSource, 1M file listed first:  {row['value'].iloc[0]:+.2f}")
print("the file listed last, fwd_points_multi_daily.parquet, is the one that survives")
print("so a refreshed pull goes after the one it supersedes, not before it")
"""))

CELLS.append(md(r"""
## `data/external`: not from the terminal at all

Three files sit in `data/external` rather than `data/raw`. They are not part of the Bloomberg
pull and never go through DVC: `scripts/fetch_external_data.py` fetches them once from the
Ken French Data Library and FRED, both free and public, and the result is small enough to
commit straight to git. They carry US equity factors and a consumption series, not FX.
"""))

CELLS.append(code(r"""
ext = ROOT / "data" / "external"
for path in sorted(ext.glob("*.parquet")):
    frame = pd.read_parquet(path)
    print(f"{path.name:18s} {str(frame.shape):>12s}  {list(frame.columns)[:6]}")
"""))

CELLS.append(md(r"""
## From file to panel, step by step

Everything above stops at what a file holds. `ParquetSource` is where a file turns into
something the rest of the library can price against, and it always does it in the same three
steps: read the long frame, map each ticker in it to a column label, and pivot by field into
mid, bid and ask sharing one index. `spot_daily.parquet` is the file already opened above, this
time carried all the way through.
"""))

CELLS.append(code(r"""
source = ParquetSource(DATA / "spot_daily.parquet")
labels = catalog.label_map("spot")
print(f"1. long frame        {source.long_frame().shape}")
print(f"2. label map         {len(labels)} tickers to currency codes")
quotes = source.quotes(labels, freq="M")
print(f"3. pivoted, monthly  {quotes.mid.shape}, three sides on one index")
print(f"\n{len(labels)} tickers in the catalog's spot map, only {quotes.mid.shape[1]} of them "
      f"found in this file: the missing {len(labels) - quotes.mid.shape[1]} are the currencies "
      f"printed earlier as absent from spot_daily.parquet, reached through the em and broad "
      f"files instead.")
"""))

CELLS.append(md(r"""
## What is not here

Everything read in this notebook, and everything the two notebooks after it read, is a market
price: a spot rate, a forward point, an implied volatility, a money-market rate, a dollar
index. There is no CPI release in this pull, no payrolls print, no central bank decision,
nothing that would let a question be asked about a currency's fundamentals rather than its
price. A macro question needs a separate pull; the tables in `fxcarry.reference` that name
macro indicators and tickers are typed out for that future pull, and notebook 08 of the
tutorial set says plainly that none of them has ever been checked against a terminal.
"""))

write(CELLS, Path(__file__).parents[2] / "notebooks" / "data_dictionary"
      / "00_architecture_and_inventory.ipynb")
