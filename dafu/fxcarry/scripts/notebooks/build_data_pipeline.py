"""Generate notebooks/00_data_pipeline.ipynb."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from _nb import code, md, write

CELLS = []

CELLS.append(md(r"""
# 00: the data pipeline, end to end

How market data gets from a Bloomberg Terminal onto this laptop, and what to run at each
stage. This is the operational half of the data story: the commands, the mechanics, and the
checks. It is written to be followed rather than admired, and to be enough on its own the
next time a pull is needed.

It deliberately does not cover what is *in* the files. `notebooks/data_dictionary/` does
that: notebook 00 there holds the inventory and the long format, 01 the spot, forward and
rate files, 02 the option surfaces. Nor does it teach the reading API, which
`notebooks/tutorial/02_quotes.ipynb` works through class by class. Read this one for the
plumbing.

**What runs here.** Everything that touches Bloomberg or DVC is in a fenced block rather
than a code cell, because neither works without a Terminal session or a running bridge. The
cells that do execute inspect the state already on disk: which tickers a pull would ask for,
what DVC has recorded, whether the local files match that record, and one read straight
through to a panel. So the notebook runs top to bottom on any machine with the data pulled,
and the parts you cannot run are still written out in full.
"""))

CELLS.append(md(r"""
## The trip in one picture

Four stages, four different tools, and only the last one runs anywhere.

```
  Bloomberg Terminal                     you need a Terminal session for this
        |
        |  1. PULL          xbbg -> blp.bdh(tickers, flds, start, end)
        |                   tickers built by Catalog, never typed by hand
        v
  data/raw/*.parquet                     long format: ticker, date, field, value
        |
        |  2. TRACK         dvc add  ->  writes a .dvc pointer, git-ignores the parquet
        |                   dvc push ->  uploads the content to Box
        v
  UChicago Box                           the parquets live here, not in git
        |
        |  3. RETRIEVE      rclone serve webdav  ->  local bridge on :8080
        |                   dvc pull             ->  fetches by hash through the bridge
        v
  data/raw/*.parquet again               same bytes, different laptop
        |
        |  4. READ          ParquetSource + Catalog.label_map -> Quotes
        v
  a panel you can compute on
```

Stages 1 to 3 each need something this machine may not have. Stage 4 is the only one that is
always available, which is why the rest of the repo starts there.
"""))

CELLS.append(code(r"""
import hashlib
import pathlib

import pandas as pd

# nbconvert runs with this notebook's folder as the working directory, so walk up
# rather than assume how deep the notebook sits.
ROOT = next(p for p in [pathlib.Path.cwd(), *pathlib.Path.cwd().parents]
            if (p / "data" / "raw").is_dir())
DATA = ROOT / "data" / "raw"
print(f"repo root: {ROOT.name}")
print(f"data dir : {DATA.relative_to(ROOT)}")
"""))

CELLS.append(md(r"""
## Stage 1: the pull

`xbbg` is a thin wrapper over Bloomberg's own BLPAPI. One function does almost all the work
here:

```python
from xbbg import blp

frame = blp.bdh(
    tickers=["EURUSD Curncy", "USDJPY Curncy"],
    flds=["PX_LAST", "PX_BID", "PX_ASK"],
    start_date="1983-11-01",
    end_date="2026-07-30",
    Per="D",                 # daily; "M" for monthly macro series
    backend="pandas",
)
```

`bdh` is "Bloomberg data history": a time series per ticker per field. It returns a long
frame, one row per ticker, date and field, which is exactly the shape `data/raw` stores and
the shape `ParquetSource` expects. Nothing reshapes it on the way in.

Two other calls come up occasionally. `blp.bdp` fetches a single current value per ticker,
which is how you check a ticker resolves at all before asking for forty years of it, and
`blp.bds` fetches bulk reference data such as the members of an index. Neither is used by
the pulls in this repo.

The pull notebooks are `01_bloomberg_pull_fx.ipynb` for the FX prices and
`02_bloomberg_pull_macro.ipynb` for the country macro series. Both are stored without
output, since neither can run without a Terminal.
"""))

CELLS.append(md(r"""
### Tickers come from the catalog, not from a keyboard

This is the part worth internalising, because it is where a pull silently goes wrong. A
Bloomberg FX ticker encodes the pair, the instrument, the tenor and the wing delta, and the
conventions differ per currency: seven currencies trade forwards as non-deliverables under a
root that is not their ISO code, and the yen family quotes forward points on a different
scale. Typing those by hand is how you pull forty years of the wrong series.

`Catalog` builds them instead. The cell below prints what each dataset would request,
without contacting Bloomberg, so you can inspect the request before spending a Terminal
session on it.
"""))

CELLS.append(code(r"""
from fxcarry import Catalog, reference

catalog = Catalog.with_legacy()      # traded currencies plus the ones the euro replaced
vol_catalog = catalog.subset([c for c in reference.VOL_CURRENCIES if c in catalog])

requests = {
    "spot": catalog.tickers("spot"),
    "1M forward points": [c.fwd_ticker("1M") for c in catalog],
    "forward curve": catalog.tickers("forward", reference.FWD_TENORS),
    "at-the-money vol": vol_catalog.tickers("atm", reference.VOL_TENORS),
    "risk reversals": vol_catalog.tickers("rr", reference.SMILE_TENORS,
                                          reference.VOL_DELTAS),
    "butterflies": vol_catalog.tickers("bf", reference.SMILE_TENORS,
                                       reference.VOL_DELTAS),
    "short rates": catalog.tickers("rate"),
    "dollar indices": list(reference.DOLLAR_INDEX_TICKERS.values()),
}
for name, tickers in requests.items():
    print(f"{name:19s} {len(tickers):5d}  e.g. {tickers[0]}")
print(f"\n{sum(len(t) for t in requests.values()):,} tickers in total, "
      f"{len(catalog)} currencies")
"""))

CELLS.append(code(r"""
# The conventions that make hand-typing a bad idea, shown on the currencies that break it.
odd = [c for c in catalog if c.fwd_root != c.iso]
print("forwards quoted under a root that is not the ISO code:")
for c in odd:
    print(f"  {c.iso}  pair {c.pair:7s}  forward {c.fwd_ticker('1M'):16s}  "
          f"(ISO would give {c.iso}1M Curncy)")

scales = sorted({c.point_scale for c in catalog})
print(f"\nforward-point scales in use: {scales}")
print("a wrong scale does not raise, it just misprices the forward by that factor")
"""))

CELLS.append(md(r"""
### The limits, and why the pull is batched

Bloomberg meters data by request. A desk licence carries a daily cap on unique securities and
a monthly cap on the total, and a single `bdh` asking for two thousand tickers of forty-year
daily history is both slow and easy to trip.

Both pull notebooks therefore batch, roughly like this:

```python
def bdh_batched(tickers, flds, start, end, batch=150):
    tickers = list(dict.fromkeys(tickers))          # dedupe, keep order
    frames = []
    for i in range(0, len(tickers), batch):
        chunk = tickers[i : i + batch]
        frames.append(blp.bdh(tickers=chunk, flds=flds, start_date=start,
                              end_date=end, Per="D", backend="pandas"))
        print(f"  {i + len(chunk):4d}/{len(tickers)} pulled")
    return pd.concat(frames, ignore_index=True)
```

Three reasons, in order of how much they matter. A tripped limit costs you the whole request
rather than the batch, so smaller requests lose less. The progress print tells you where a
long pull stopped, so you can resume rather than restart. And deduplicating first matters
more than it looks: several currencies share a rate ticker, so a naive list asks for the same
series more than once and pays for it twice.

Validate before you pull. Both notebooks open with a probe cell that asks for a handful of
tickers over a short window and prints which resolved, which came back empty and which
failed. An empty result usually means the ticker is wrong rather than the history is missing,
and finding that out on eight tickers is cheaper than on two thousand.
""".rstrip()))

CELLS.append(md(r"""
## Stage 2: tracking with DVC

The parquets are too large for git and they are not source. DVC handles them: it records a
hash of each file in a small text pointer that *is* committed, and stores the bytes
themselves on a remote.

```bash
dvc add data/raw/spot_daily.parquet     # writes spot_daily.parquet.dvc, git-ignores the data
git add data/raw/spot_daily.parquet.dvc data/raw/.gitignore
git commit -m "data: refresh the spot pull"
dvc push                                 # sends the content to Box
```

A pointer is four lines. That is the whole mechanism: the hash is the name the content is
stored under, so `dvc pull` on another machine asks for that hash and gets identical bytes,
and git history records which hash the repo expected at each commit.
"""))

CELLS.append(code(r"""
pointers = sorted(DATA.glob("*.parquet.dvc"))
print(f"{len(pointers)} tracked files under {DATA.relative_to(ROOT)}\n")
print("one pointer, in full:")
print((DATA / "spot_daily.parquet.dvc").read_text().strip())
print("\nthe remote it pulls from:")
print((ROOT / ".dvc" / "config").read_text().strip())
"""))

CELLS.append(md(r"""
## Stage 3: getting the data onto a laptop

The remote is UChicago Box, and here the setup has one wrinkle worth knowing about. DVC has
no native Box or rclone remote type. `rclone` does speak Box, so it runs as a local WebDAV
server and DVC talks to that instead. The bridge is a translation layer, nothing more.

One-time, per machine:

```bash
rclone config
#   -> new remote, name: uchicago-box, type: box
#   -> auto config: yes, then log in with CNetID@uchicago.edu
dvc remote add -d box-remote webdav://127.0.0.1:8080
```

Every session, in its own terminal, left running:

```bash
rclone serve webdav uchicago-box:fxcarry-data --addr 127.0.0.1:8080 --vfs-cache-mode writes
```

Then, in the repo:

```bash
dvc pull        # or dvc push, after a fresh pull from the Terminal
```

The bridge is only needed for `dvc pull` and `dvc push`. Analysis never touches it, so once
the files are local you can forget it exists until the next refresh. If `dvc pull` reports
`Unsupported URL type rclone://`, a missing `dvc-webdav` module, or an `AttributeError`
mentioning `GEN_EMAIL`, all three are diagnosed with fixes in
`docs/plans/setup_plan.md` under Phase 0.2.
"""))

CELLS.append(md(r"""
### Checking what actually landed

Two questions after a pull: is every tracked file present, and does its content match what
DVC recorded. The second is the one worth running, because a truncated or half-written
download is the failure that looks like a data problem later.
"""))

CELLS.append(code(r'''
def recorded(pointer):
    """The md5 and size a .dvc pointer claims for its file."""
    fields = {}
    for line in pointer.read_text().splitlines():
        line = line.strip().lstrip("- ")
        if ":" in line:
            key, _, value = line.partition(":")
            fields[key.strip()] = value.strip()
    return fields.get("md5"), int(fields.get("size", 0))


rows = {}
for pointer in pointers:
    target = pointer.with_suffix("")            # drop the .dvc
    md5, size = recorded(pointer)
    rows[target.name] = {
        "present": target.exists(),
        "MB recorded": round(size / 1e6, 1),
        "MB on disk": round(target.stat().st_size / 1e6, 1) if target.exists() else 0.0,
        "size matches": target.exists() and target.stat().st_size == size,
    }
state = pd.DataFrame(rows).T
print(state.to_string())
print(f"\npresent: {int(state['present'].sum())}/{len(state)}   "
      f"size matches: {int(state['size matches'].sum())}/{len(state)}")
'''))

CELLS.append(code(r"""
# Size is a cheap proxy. The hash is the real check, so verify one file properly.
target = DATA / "spot_daily.parquet"
md5, size = recorded(DATA / "spot_daily.parquet.dvc")

digest = hashlib.md5()
with target.open("rb") as handle:
    for chunk in iter(lambda: handle.read(1 << 20), b""):
        digest.update(chunk)

print(f"{target.name}")
print(f"  recorded md5 {md5}")
print(f"  computed md5 {digest.hexdigest()}")
print(f"  match: {digest.hexdigest() == md5}")
print("\n`dvc status` checks all of them at once; this is what it is doing underneath.")
"""))

CELLS.append(md(r"""
## Stage 4: reading it

The only stage that needs nothing but the repo. One source, one label map off the catalog,
one pivot, and the three quoted sides come back aligned on a single index.

`notebooks/tutorial/02_quotes.ipynb` covers what `Quotes` guarantees and why the sides are
never combined across, and `notebooks/data_dictionary/00_architecture_and_inventory.ipynb`
covers the long format and what each file holds. This is just the shortest path from a file
to something you can compute on.

One difference from the pull worth being deliberate about. Stage 1 above used
`Catalog.with_legacy()`, because a pull should take everything the terminal will give,
including the currencies the euro replaced in 1999. Analysis uses `Catalog.default()`, which
leaves those out, because a defunct currency is not something a strategy can hold. So the
pull is wider than the panel on purpose, and the cell below prints both counts rather than
leaving the gap to be discovered later.
"""))

CELLS.append(code(r"""
from fxcarry import ParquetSource, SpotForward

analysis = Catalog.default()          # what a strategy trades; no legacy currencies
source = ParquetSource(DATA / "spot_daily.parquet", DATA / "fwd_points_1m_daily.parquet")
spot = source.quotes(analysis.label_map("spot"), freq="M")
points = source.quotes(analysis.label_map("forward", "1M"), freq="M")
curves = SpotForward.from_quotes(spot, points, analysis, 1 / 12)

print(f"pulled   {len(catalog)} currencies (with legacy)")
print(f"analysed {len(analysis)} currencies (traded only)")
print()
print(f"spot      {spot.mid.shape}  three sides on one index")
print(f"forwards  {points.mid.shape}")
print(f"panel     {len(curves.currencies)} currencies survive the join, "
      f"{curves.spot.index[0]:%Y-%m} to {curves.spot.index[-1]:%Y-%m}")
print("\nannualized carry, latest row, five widest:")
print((curves.carry.iloc[-1].dropna().sort_values(ascending=False).head(5) * 100).round(2))
"""))

CELLS.append(md(r"""
## Refreshing the data

The order matters, and stage 2 is the one people forget.

1. On a machine with a Terminal, run `01_bloomberg_pull_fx.ipynb`, and
   `02_bloomberg_pull_macro.ipynb` if you want the macro series. Check the probe cell's
   output before letting the pull run.
2. `dvc add` the changed parquets, commit the pointers, `dvc push`. A pull that is not
   pushed exists on one laptop only, and the committed pointer will then reference content
   nobody else can fetch.
3. Elsewhere, `git pull` then `dvc pull`.
4. Re-run the checks above, then re-execute `notebooks/data_dictionary/`, which prints row
   counts, ticker counts and date ranges per file. Those numbers are the record of what the
   pull produced, so a surprise there is a finding rather than a nuisance.

Two things that will look like breakage and are not. The universe grows: a fresh pull covers
more currencies than the last one, so ticker counts and row counts move up and any number
written down in prose goes stale. And the right edge is ragged: a month-end resample takes
the last print inside the month, so the final row of a fresh pull carries a mid-month quote
until the month closes. `notebooks/04_hedged_leg_from_first_principles.ipynb` shows what that
does to the last leg in a sample.
"""))

CELLS.append(md(r"""
## Where to go next

| To learn | Read |
| --- | --- |
| What is in each file, and which currencies it really covers | `notebooks/data_dictionary/` |
| How to read a pull into panels, class by class | `notebooks/tutorial/02_quotes.ipynb` |
| Why a ticker is built rather than typed | `notebooks/tutorial/01_catalog.ipynb` |
| The tables the tickers come from | `notebooks/tutorial/08_reference.ipynb` |
| DVC setup troubleshooting, with the three known failures | `docs/plans/setup_plan.md` |
| What the data is eventually for | `notebooks/03_crash_hedged_carry.ipynb` |
"""))

write(CELLS, Path(__file__).parents[2] / "notebooks" / "00_data_pipeline.ipynb")
