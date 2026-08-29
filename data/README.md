# `data/` — the shared Bloomberg snapshots

**This is why nothing in this repository needs a Bloomberg terminal.** All thirteen data groups are
git-tracked, so every number in the report, the decks and the shipped strategy reproduces from a
clean clone with `pip install` and nothing else. A terminal is required only to *refresh* the data,
via [`../src/`](../src/).

Daily, 2007-01 → 2026-06, G10 + EM vs USD.

---

## The thirteen groups

Each is stored twice — `*_wide.parquet` (dates × tickers, what the code reads) and `*_long.parquet`
(tidy, one row per date/ticker/field, useful for auditing).

| Group | What it holds |
|---|---|
| `g10_fx_spot_forward` · `em_fx_spot_forward` | Spot and forward outrights with bid/ask — the source of both the carry signal and the real cost model |
| `g10_interest_rates` · `em_interest_rates` | Deposit / IBOR-style rates by tenor |
| `em_onshore_rates` | Onshore fixings for the restricted EM names, used by the CIP-basis work |
| `g10_rates_gaps` | Fills for the G10 rate curves where the primary tickers are incomplete |
| `g10_fx_options` · `em_fx_options` | Volatility surfaces — ATM, risk reversals, butterflies at 10Δ and 25Δ. **Mids only, no bid/ask** |
| `global_risk` · `em_risk` | VIX, MOVE, EMBI spreads and related risk series |
| `macro_market_proxies` | Macro and market factor proxies used by the regime work |
| `fx_carry_benchmarks` | The investable carry indices the book is benchmarked against (DBHVG10U, FXCTEM8) |
| `usd_riskfree` | USD risk-free / T-bill series |

## The audit trail beside the data

| File | What it is |
|---|---|
| `raw/ticker_manifest.csv` | **Every ticker pulled, with its group and field.** This is what `final/report/02_data_and_conventions.md` cites for ticker-level sourcing, and it is vendored into `final/data/raw/` as provenance |
| `raw/download_coverage_summary.csv` | Coverage achieved per group |
| `raw/missing_tickers_by_group.csv` | What was requested and did not come back |
| `raw/*_failures.csv` · `raw/*_missing_tickers.csv` | Per-group failure detail |
| `raw/FX_extra_data.xlsx` | The hand-pulled supplement (benchmarks, EMBI, onshore fixings), converted by `../src/convert_extra_xlsx.py` |

## ⚠ pyarrow must be the pip build (≥ 24)

Conda's pyarrow 19.x **cannot read these parquet files** and fails in a way that looks like data
corruption rather than a version problem. After any broad conda update:

```bash
/opt/anaconda3/bin/pip install -U pyarrow
```

This is the single most expensive gotcha in the repo. It is repeated in every README for that reason.

## Relationship to `final/data/raw/`

The hand-off package [`../final/`](../final/) vendors its own copy: the **thirteen `*_wide.parquet`
files plus `ticker_manifest.csv`**, and nothing else. That is the subset the shipped strategy
actually reads. The copies are byte-identical and `../final/tests/test_vendor_drift.py` hashes them
against the files here on every run.

The `*_long.parquet` files and the audit CSVs stay here only — they are for understanding the pull,
not for running the strategy.

## Known gaps

No option surfaces for CLP, COP, IDR, MYR, PEN or PHP. No CNY forwards (CNH is the tradable RMB leg).
NIBOR12M, STIB12M and CLSWA are missing. What additional data would unlock what, and roughly what it
costs, is written up in [`../cesare/DATA_SHOPPING_LIST.md`](../cesare/DATA_SHOPPING_LIST.md).
