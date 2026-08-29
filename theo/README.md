# `theo/` — the FX options track: skew, vol filters, and option-conditioned carry

**Theo** · UChicago Summer Project Lab with Bank of America (Corporate Treasury / Global Funding).

> ### How this work landed
> **Bad-skew exclusion → ADOPTED.** It is one of the two components in the shipped strategy: the
> overlay that excludes currencies whose option-implied skew sits in the top quintile of the
> cross-section. Two later components are **not evaluable as committed** — their declared inputs
> were never committed. Full reasoning, including the caveat that most of the overlay's tail gain is
> de-risking rather than selection, in [`../final/VERDICTS.md`](../final/VERDICTS.md).
> The shipped strategy is [`../final/`](../final/).

---

## The notebooks, in order

| Notebook | What it does |
|---|---|
| `01_build_core_carry_panel.ipynb` | Builds the core G10 1M carry panel from the shared `data/raw/` parquets |
| `02_g10_carry_baseline.ipynb` | The G10 long/short carry baseline |
| `03_transaction_costs_and_turnover.ipynb` | Cost model and turnover accounting |
| `04_em_carry_extension.ipynb` | Extends the book to EM |
| `05_em_carry_robustness_and_attribution.ipynb` | Robustness battery and per-currency attribution |
| `06_options_skew_and_vol_filters.ipynb` | **The adopted work.** Skew and vol filters on the carry book |
| `06_options_filter_regression(9).ipynb` | Regression study of the option filters — a separate line of work that shares the `06_` prefix |
| `07_option_conditioned_carry_strategy.ipynb` | Option-conditioned carry (Aug 5). **Not evaluable** — see below |
| `08_comprehensive_carry_strategy_optimization(6).ipynb` | Macro/option optimisation layer (Aug 14). **Not evaluable** — see below |
| `data_preview.ipynb` | Early look at the raw pulls |
| `slides/` | `week1`, `week2` notebooks; `week5/build/main.pdf`; `week6/` the macro-option research document |

### About the filenames

`(9)` and `(6)` are browser download-revision markers, and there are two different notebooks with a
`06_` prefix. **They are left as they are on purpose:** `07_option_conditioned_carry_strategy.ipynb`
cites `theo/06_options_filter_regression(9).ipynb` **by name inside its own cells and stored
outputs**, so renaming the file would silently break a provenance citation in an executed notebook.
The names are ugly; a dangling citation in the evidence chain would be worse.

## What the shipped strategy actually uses

One file: **`data/processed/fx_option_signal_panel.parquet`** — committed 2026-07-18 and unchanged
since. It is vendored byte-for-byte into [`../final/inputs/`](../final/inputs/) and hashed against
this copy by `../final/tests/test_vendor_drift.py`. Nothing else in this folder is read at runtime by
the shipped book.

The other eleven parquets in `data/processed/` are the July work's outputs, kept as the record behind
the notebooks above.

## The two gaps, stated

Notebooks `07` and `08` arrived after the 2026-08-07 scope freeze. Both are committed **executed,
with stored outputs** — but their declared input `option_filter_regression_panel_primary_v9.parquet`
exists nowhere on disk or in git, and neither do the eleven parquets notebook 07 writes. So the
results can be read but not reproduced or re-priced on the common book.

This matters for how their numbers are quoted: **notebook 07's best variants reach Sharpe 0.49
against Theo's own baseline of 0.44** — 20 currencies, monthly, a flat 5 bp cost. That is *not*
comparable to the shared base's 0.4659 on 27 currencies daily with real per-currency bid/ask. A +0.05
improvement measured on a different book is a different measurement, which is the whole reason
[`../strategy/`](../strategy/) exists.

**To close it:** commit the `_v9` panel, and notebook 07 re-prices through the same `weight_overlay`
path as every other component.

## Running these

Python 3.13, `pip install -r ../requirements.txt` from the repo root (see the pyarrow caveat there).
The notebooks read the shared, git-tracked `../data/raw/*.parquet` — **no Bloomberg terminal needed.**
