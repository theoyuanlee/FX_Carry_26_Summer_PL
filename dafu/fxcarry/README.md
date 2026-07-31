# fxcarry

A modular, generic FX cross-sectional strategy research library.

## Learning the theory

A four-week program running to the end of the project:

- [Month plan](docs/plans/month_plan.md) is the master schedule and the place to start.
  Week 1 is the FINM 37301 sprint, cut into six phases rather than days, so a day can hold
  two or three of the light ones: phase 0 reads the library as it now stands, module by
  module against its tutorial notebook, and phases 1 to 5 work through the lecture notes
  alongside Shamah's *A Foreign Exchange Primer* and Castagna's *FX Options and Smile
  Risk*, scoped to what the lectures cover and weighted toward options and the smile. Each
  phase pairs reading with hand derivations, checks against this repo's data, one module
  owned at the depth the theory now supports, and one addition to `fxcarry`: the four delta
  conventions, the market-strangle butterfly, vanna-volga interpolation, the Greeks,
  Breeden-Litzenberger density extraction. Verification comes from identities, limiting
  cases and hand computation, never a reference library. Weeks 2-4 run three tracks in
  parallel.
- [C++ and QuantLib track](docs/plans/cpp_quantlib_track.md): about an hour a day through
  QuantNet Levels 1-5, stopping there, so QuantLib's FX source is readable by the end of
  the project. Reading only. Nothing is ported or reused, and `fxcarry` stays pure Python.
  The C++ pays off later, in `research/bayesian-smc-sv`.
- [BUSN 41902 binding](docs/plans/busn41902_binding.md) is a map rather than a plan. Six
  sprints of the course explain econometrics already running here (Newey-West standard
  errors, iterated GMM, factor betas, shrinkage), so each doubles as an audit of code that
  was generated and never re-derived.

## Environment setup

Requires Python ≥ 3.11. We use [uv](https://docs.astral.sh/uv/) for environment management.

```bash
# 1. Create virtual environment (Python 3.12)
uv venv --python 3.12 .venv

# 2. Activate
#    Windows (PowerShell):
.venv\Scripts\activate
#    macOS / Linux:
source .venv/bin/activate

# Windows: if you get "running scripts is disabled on this system", run once:
#   Set-ExecutionPolicy -Scope CurrentUser -ExecutionPolicy RemoteSigned

# 3. Install fxcarry + all dependencies (editable, with dev tools)
uv pip install -e ".[dev]"
```

### What gets installed

| Package | Purpose |
|---------|---------|
| pandas, numpy, pyarrow | Data handling |
| statsmodels | Newey-West regressions, factor loadings |
| matplotlib | Plotting |
| xbbg | Bloomberg data pulls (requires active Terminal session) |
| dvc[webdav] | Data version control. Pulls shared datasets from UChicago Box via the rclone bridge below |
| pyOpenSSL, cryptography | Version floors pinned to avoid a `dvc`-transitive OAuth-stack conflict (`AttributeError: ... GEN_EMAIL`) |
| pytest, ruff | Testing and linting (dev extra) |

`rclone` is a separate system tool rather than a Python package. Install it with
`winget install Rclone.Rclone` (Windows) or `brew install rclone` (macOS) before setting up
data access below.

### Data access (DVC)

Data files are git-ignored and tracked by DVC with UChicago Box as remote storage. DVC has
no native `rclone://` remote type, so rclone runs only as a local WebDAV bridge to Box, and
DVC talks to that bridge through a real `webdav://` remote. After installing, set up the
remote once:

```bash
# One-time: configure rclone for UChicago Box (interactive OAuth)
rclone config
#   → new remote, name: uchicago-box, type: box
#   → auto config: yes → log in with CNetID@uchicago.edu

# Every session: start the local bridge (keep this running in its own terminal)
rclone serve webdav uchicago-box:fxcarry-data --addr 127.0.0.1:8080 --vfs-cache-mode writes

# One-time: point DVC at the bridge
dvc remote add -d box-remote webdav://127.0.0.1:8080

# Pull data
dvc pull
```

If you hit `Unsupported URL type rclone://`, a missing `dvc-webdav` module, or an
`AttributeError` mentioning `GEN_EMAIL`/`X509_V_FLAG_*`, see the troubleshooting table in
`docs/plans/setup_plan.md` (Phase 0.2). All three are diagnosed and fixed there.

See `docs/plans/setup_plan.md` for the full DVC setup walkthrough.

## Pipeline usage

`notebooks/00_data_pipeline.ipynb` walks the whole chain end to end, from the terminal
through DVC and Box to a panel, with the commands for each stage and checks on what landed.
The short version:

1. On a machine with an active Bloomberg Terminal session, run
   `notebooks/01_bloomberg_pull_fx.ipynb` for the full FX pull: full-universe spot and
   forwards, the forward curve, the option vol surface, short-rate curves and dollar
   indices, all into `data/raw/*.parquet`. Then track with DVC.
   `notebooks/02_bloomberg_pull_macro.ipynb` pulls the country macro series, though its
   ticker catalogue has never been checked against a terminal.
2. One-time, non-Bloomberg reference data (Fama-French factors and 25 portfolios from the
   Ken French Data Library, consumption from FRED). Free and permanent, committed to git
   under `data/external`:

   ```bash
   python scripts/fetch_external_data.py
   ```

3. Build a panel and run a book:

   ```python
   from fxcarry import Book, Carry, Catalog, ParquetSource, SpotForward, TopBottom

   catalog = Catalog.default()
   source = ParquetSource("data/raw/spot_daily.parquet")
   points = ParquetSource("data/raw/fwd_points_1m_daily.parquet")

   curves = SpotForward.from_quotes(
       source.quotes(catalog.label_map("spot"), freq="M"),
       points.quotes(catalog.label_map("forward", "1M"), freq="M"),
       catalog,
       tenor=1 / 12,
   )
   book = Book(curves, Carry(), TopBottom(k=5))
   ```

   Put options on top by passing an overlay and a smile:

   ```python
   from fxcarry import VerticalSpread, VolSurface

   surface = VolSurface.from_source(ParquetSource("data/raw/fx_vol_daily.parquet"), catalog)
   hedged = Book(curves, Carry(), TopBottom(k=5),
                 overlay=VerticalSpread(sell_delta=25, buy_delta=10, kind="put"),
                 smile=surface.panel_smile("1M", freq="M"))
   ```

   Reversing the two deltas reverses the trade. Any other pair of quoted deltas, either sign,
   or a ratio through `quantities`, is the same call with different arguments.

4. `notebooks/03_crash_hedged_carry.ipynb` is the worked baseline: a carry book that sells
   the near crash rung and buys the far one back, built step by step and cross-checked
   against the validated pipeline in `research/crash_hedged/`. That pipeline runs: after
   `dvc pull`, `validate.py` prints ALL CHECKS PASS and `strategy.py` prints REGRESSION
   ANCHORS OK against the committed outputs. See `research/README.md` for the order to run
   them in.

5. `notebooks/05_regime_switching_carry.ipynb` puts five regime models on the team project's
   shared carry book and asks what each is worth once it may only use data available at the
   time. It is the one notebook here that needs a second checkout: the estimators come from
   this library, the book and the raw panels from `FX_Carry_26_Summer_PL`. Keep the two
   repositories side by side, or set `FX_CARRY_PL_ROOT`. Rebuild it with
   `python scripts/notebooks/build_regime_switching.py`, which writes the same notebook here
   and into that project's `dafu/` folder so the two copies cannot drift.

### Library layout

| module | what it is for |
| --- | --- |
| `reference.py` | literal tables: tickers, point scales, tenor and delta grids |
| `catalog.py` | `Currency`, `Catalog`: what an instrument is called and which conventions it follows |
| `quotes.py` | `Quotes`, `QuoteSource`: reading the pulls, holding two-sided data |
| `curves.py` | `SpotForward`: spot and forward levels, and the returns they imply |
| `vol.py` | `Smile`, `VolSurface`: the quoted smile, and volatility at a delta |
| `options.py` | `PricingModel`, `Instrument`, `Overlay`: pricing, positions and hedges |
| `strategy.py` | `Signal`, `Weighting`, `CostModel`, `Book`: a view turned into returns |
| `stats.py` | `Performance`, `HAC`, `FactorModel`, `LinearSDF`, and friends |
| `regimes.py` | `MarkovSwitching`, `TrailingPercentile`, `LogisticRegime`: which state the world is in, and the gates that turn that into exposure |
| `compare.py` | `Comparison`: several books on one window, scored together and saved as one file |

Everything is in dollars per foreign currency unit, so a rise in a rate means the foreign
currency gained. Volatilities cross the library boundary as decimals. `Book` performs the one
shift that pairs a position with the return realized after it was chosen; nothing else in the
library shifts anything.

All hard-coded values (ticker universe, forward-point scale factors, tenors, deltas,
defaults) live in `src/fxcarry/reference.py`. Extend the currency universe or change a
convention there, not in the library code.

Run the test suite (synthetic data only, no Bloomberg needed) with:

```bash
pytest
```

### Executing the notebooks

Notebook execution needs the `notebooks` extra (`uv pip install -e ".[dev,notebooks]"`).
Bake a notebook's outputs with, e.g.:

```bash
python -m nbconvert --to notebook --execute --inplace \
    --ExecutePreprocessor.kernel_name=fxcarry notebooks/00_data_pipeline.ipynb
```

Register the named kernel once with `python -m ipykernel install --user --name fxcarry`. The
notebooks under `tutorial/` and `data_dictionary/` are generated by the builder scripts in
`scripts/notebooks/`, so edit the builder and re-run it rather than editing the `.ipynb`.

The two `00*` pull notebooks are the exception to all of this: they need a live Terminal, so
they are stored without output and cannot be executed here.

`notebooks/tutorial/` is a module-by-module walkthrough of the library, one notebook per file
under `src/fxcarry`, starting from `00_start_here.ipynb`. `notebooks/data_dictionary/` checks
what the pulled parquet files under `data/raw` actually contain against what the catalog
assumes, rather than taking it on faith.
