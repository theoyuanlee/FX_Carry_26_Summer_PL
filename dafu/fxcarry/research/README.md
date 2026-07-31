# research

Work that uses `fxcarry` rather than being part of it. Rougher than `src/` by design, and
allowed to change shape as a question changes. Two separate things live here, in different
states.

## `crash_hedged/`, the live pipeline

The crash-hedged carry study: a carry book that sells the near crash rung on each leg and
buys the far one back. It runs on the class API and its own gates pass.

Run in this order, from the repository root, after `dvc pull`:

| Step | Script | What it does | Gate |
| --- | --- | --- | --- |
| 1 | `build_panel.py` | reshapes the raw parquets into one monthly panel, one row per currency-month | writes `out/monthly_panel.parquet` |
| 2 | `hedged_carry.py` | prices every leg across every arm | writes `out/leg_returns.parquet` |
| 3 | `validate.py` | six structural checks on the two files above | must print `ALL CHECKS PASS` |
| 4 | `analysis.py` | inference, per-currency tables, the peso arithmetic | writes `out/per_currency.csv` and friends |
| 5 | `strategy.py` | the sorted book, forward costs, the regression anchors | must print `REGRESSION ANCHORS OK` |

`make_deck_figures.py` and `make_strategy_figures.py` redraw the charts and are optional.

Nothing needs regenerating to read the study. `notebooks/03_crash_hedged_carry.ipynb` walks
it end to end from the committed outputs, and cross-checks itself against them twice.

The two gates are worth taking seriously rather than treating as ceremony. Check 2 in
`validate.py` is an identity that must hold to machine precision on every in-the-money
leg-month, and check 6 bounds the overlay between what it collected and what it could lose.
Both are properties of the contract rather than statistics, so a failure means the
arithmetic broke, not that the market moved.

## `slope_carry.py`, `slope_check.py`, `slope_smooth.py`, `mixed_tenor.py`

These do not run on this branch, and porting them is not the fix.

They import `fxcarry.api` and `fxcarry.evaluation`, two modules that exist only on the
unmerged branch `feature/shrinkage-carry-v2`. They were committed to `main` on 2026-07-21
in a bulk commit while their dependency stayed on the other branch, so they have never
imported here. This is unrelated to the class rebuild: the modules they want predate it and
were never on `main` at any point.

They are kept rather than deleted because `main` holds the only copy of the scripts and the
other branch holds the only copy of what they import, so deleting either side loses work
that the other cannot reconstruct. Resolving it properly means deciding what to do with
`feature/shrinkage-carry-v2`, which is thirty commits ahead of `main` and fifty-five behind.
That is a merge decision, not a rename.

## Conventions

`out/` is committed. The files are small, they are what the notebooks and the write-ups
read, and having them under version control is what makes a change in a number visible in a
diff rather than a surprise months later.

Everything in here reads `data/raw`, which is DVC-tracked.
`notebooks/00_data_pipeline.ipynb` covers how that gets onto a machine.
