# `final/data/raw/` — provenance

Every file here is a **byte-identical copy** of the same filename in the repo-root `data/raw/`,
verified by SHA-256 at the time of vendoring. Nothing here was regenerated, resampled or converted.

**Why a copy and not a reference.** `strategy/fx_utils.py:21` resolves the data directory as
`Path(__file__).resolve().parent.parent / "data" / "raw"` — i.e. always a sibling of the `strategy`
package. Since `final/` carries its own copy of that package at `final/strategy/`, the data has to
sit at `final/data/raw/` for the package to find it. The alternatives were a symlink (fragile on
Windows, and it makes the standalone claim true only by a trick) or patching that line in the
vendored engine (which would stop the engine being a byte-identical copy, and the byte-identity is
what makes drift detectable). A copy costs 35 MB and no cleverness. That was the trade.

**Source:** daily Bloomberg, pulled via `src/bloomberg_data.py` (xbbg/blpapi). A Bloomberg terminal
is needed only to *refresh* this data — never to reproduce anything in `final/`, because these
snapshots are committed.

## What is here — 14 files, 35.2 MB

| File | Size | Shape | Index range | SHA-256 (first 16) | Added by |
|---|---|---|---|---|---|
| `em_fx_options_wide.parquet` | 11.93 MB | 5087 × 975 | 2007-01-01 → 2026-06-30 | `749e1cf866f81c51…` | `834472c` 2026-06-30 |
| `em_fx_spot_forward_wide.parquet` | 6.11 MB | 5094 × 285 | 2007-01-01 → 2026-06-30 | `e59d93152647fdf2…` | `834472c` 2026-06-30 |
| `em_interest_rates_wide.parquet` | 0.33 MB | 5087 × 34 | 2007-01-01 → 2026-06-30 | `0c1c912d73a05218…` | `834472c` 2026-06-30 |
| `em_onshore_rates_wide.parquet` | 0.30 MB | 7127 × 16 | 2007-01-01 → 2026-07-06 | `d4a4613f5160f53e…` | `a363eb0` 2026-07-06 |
| `em_risk_wide.parquet` | 0.07 MB | 5091 × 1 | 2007-01-01 → 2026-07-06 | `5c143945d8d7851e…` | `a363eb0` 2026-07-06 |
| `fx_carry_benchmarks_wide.parquet` | 0.12 MB | 5091 × 3 | 2007-01-01 → 2026-07-06 | `13a0cbbc8da2c537…` | `a363eb0` 2026-07-06 |
| `g10_fx_options_wide.parquet` | 9.30 MB | 5087 × 825 | 2007-01-01 → 2026-06-30 | `0f97db30e879bd93…` | `834472c` 2026-06-30 |
| `g10_fx_spot_forward_wide.parquet` | 4.64 MB | 5087 × 198 | 2007-01-01 → 2026-06-30 | `99de1fa9a17a640a…` | `834472c` 2026-06-30 |
| `g10_interest_rates_wide.parquet` | 1.24 MB | 5087 × 81 | 2007-01-01 → 2026-06-30 | `7f91edf8ce91c117…` | `834472c` 2026-06-30 |
| `g10_rates_gaps_wide.parquet` | 0.13 MB | 5091 × 4 | 2007-01-01 → 2026-07-06 | `661864a14aced653…` | `a363eb0` 2026-07-06 |
| `global_risk_wide.parquet` | 0.54 MB | 5087 × 19 | 2007-01-01 → 2026-06-30 | `dcde2a6337f579bc…` | `834472c` 2026-06-30 |
| `macro_market_proxies_wide.parquet` | 0.45 MB | 5155 × 24 | 2007-01-01 → 2026-06-30 | `97b7fde679ff83c5…` | `834472c` 2026-06-30 |
| `usd_riskfree_wide.parquet` | 0.07 MB | 5091 × 1 | 2007-01-01 → 2026-07-06 | `60570d3f94084f36…` | `a363eb0` 2026-07-06 |
| `ticker_manifest.csv` | 0.05 MB | 930 × 3 | — | `cf75e18dd87700c4…` | `834472c` 2026-06-30 |

## Who reads what

The 13 parquets are reached through exactly one function, `fx_utils.load_wide(group)`, which opens
`RAW_DIR / f"{group}_wide.parquet"`. Nothing else in `final/` opens a data file.

| File | Read by |
|---|---|
| `g10_fx_spot_forward_wide` · `em_fx_spot_forward_wide` | `core.load_panels` (spot, forwards) and `fx_utils.forward_halfspreads` (`PX_BID`/`PX_ASK`/`PX_LAST`) — the book and its costs |
| `g10_fx_options_wide` · `em_fx_options_wide` | `fx_utils.vol_surface_panel` — the ATM/RR/BF surfaces behind the bad-skew overlay |
| `global_risk_wide` | `combined_engine.vix_gate` (`VIX`) — the rejected gate and `COMBINED_TAIL` |
| `fx_carry_benchmarks_wide` | `fx_utils.load_benchmarks` — DBHVG10U / FXCTEM8, the information ratios |
| `em_risk_wide` | `fx_utils.load_em_risk` (`JPEIGLSP`, the EMBI spread) |
| `g10_interest_rates_wide` · `em_interest_rates_wide` · `em_onshore_rates_wide` · `g10_rates_gaps_wide` · `usd_riskfree_wide` | `fx_utils.load_rates_panel` / `onshore_rate` — the CIP validation path, not the traded signal |
| `macro_market_proxies_wide` | `fx_utils` macro regressions |
| `ticker_manifest.csv` | Nothing at runtime. Vendored as **provenance** — it is what `report/02_data_and_conventions.md` cites for ticker-level sourcing |

## What was deliberately left behind, and why

The repo-root `data/raw/` holds 36 files / 82 MB. 22 of them are not here:

| Excluded | Size | Why |
|---|---|---|
| 13 × `*_long.parquet` | 45.3 MB | The long-format twin of each wide file. **Nothing in the runtime path opens one** — every read goes through `load_wide`. Carrying them would have more than doubled this folder for no reproduction value |
| `FX_extra_data.xlsx` | 1.5 MB | The hand-pulled supplement. It is an *input to* `src/convert_extra_xlsx.py`, which produced `usd_riskfree`, `fx_carry_benchmarks`, `g10_rates_gaps`, `em_onshore_rates` and `em_risk` — all of which are here as parquet. The xlsx is never read at runtime |
| 8 × coverage/failure/manifest CSVs | 0.05 MB | `download_coverage_summary.csv`, `missing_tickers_by_group.csv` and the six per-group `*_failures.csv` / `*_missing_tickers.csv`. Pull diagnostics for a refresh that `final/` does not perform. The one manifest a reader needs — `ticker_manifest.csv` — **is** here |

Known data gaps, unchanged from the source and worth knowing before you trust a per-currency number:
no option surfaces for CLP/COP/IDR/MYR/PEN/PHP; no CNY forwards (CNH is the tradable RMB leg);
NIBOR12M, STIB12M and CLSWA missing.

## Verifying this folder

`final/tests/test_vendor_drift.py` re-hashes every file here against the repo-root original and
fails on any difference. Once the sibling folders are retired the source is gone, and that test
reports the files as unverifiable rather than failing — the check is a guard against silent drift
while both copies exist, not a permanent dependency.

**Environment note:** pyarrow must be the pip build (≥ 24). Conda's 19.x cannot read these files and
fails in a way that looks like data corruption rather than a version problem. Fix with
`/opt/anaconda3/bin/pip install -U pyarrow`.
