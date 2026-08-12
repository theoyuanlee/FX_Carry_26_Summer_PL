# `final/inputs/` — vendored teammate outputs

Three files. They are the reason `final/` runs at all.

**The problem they solve.** In the multi-person repo, `run("COMBINED")` reached at runtime into
`arjun/outputs/`, `theo/data/processed/` and `vidhi/outputs/` and raised `FileNotFoundError` if any
was absent. That is fine in a shared repo where all six folders exist, and fatal for a hand-off
package: the moment the teammate folders are retired the strategy stops running. These are
byte-identical copies, so the strategy's inputs live inside the package that ships it.

**Every one is a *committed output*, re-priced rather than rebuilt** (plan §15 fallback). That
matters and is not a technicality: a re-price is *our* reading of a teammate's signal, not their
specification of it. Base adoption reached 1 of 5 — only Dafu ported his work onto the shared base —
so four of the five components were folded in this way, and every one carries its reconstruction
method in `../evidence/p4_component_standalone.csv` and in `../evidence/component_verdicts.csv`.
That column is part of the deliverable. Preserve it.

## The files

| File | Source | Size | SHA-256 (first 16) | Added by | Owner |
|---|---|---|---|---|---|
| `duration_hedge_series.csv` | `arjun/outputs/duration_hedge_series.csv` | 459.8 KB | `6958b52a91999d88…` | `6716b57` 2026-07-29 | Arjun |
| `fx_option_signal_panel.parquet` | `theo/data/processed/fx_option_signal_panel.parquet` | 152.3 KB | `27eefb03bfebf9e5…` | `9d2ec5e` 2026-07-18 | Theo |
| `adaptive_strategy_returns_monthly.csv` | `vidhi/outputs/adaptive_strategy_returns_monthly.csv` | 11.5 KB | `eb0506a883eca6f0…` | `6bc2906` 2026-07-21 | Vidhi |

`../tests/test_vendor_drift.py` re-hashes each against its source and fails on any difference, and
reports them as unverifiable rather than failing once the source folders are gone.

---

### `duration_hedge_series.csv` — Arjun, **ADOPTED**

4,994 rows, 2007-05-01 → 2026-06-30. Columns `book`, `TLT`, `h_expanding`, `hedged_net`.

Read by `combined_engine.arjun_duration_inputs()`, which takes two things from it: the **TLT daily
return series**, and the **half-spread implied by Arjun's own cost model**. The half-spread is
*backed out* rather than re-parsed from a Bloomberg workbook only he has — he charges
`HALF · |Δh|`, and both the gross and net hedged tracks are committed, so

    HALF = median((gross − net) / |Δh|)  over the days the ratio moves

recovers **0.678 bp** and reproduces his committed net series to **1.1e-15**. An exact
reconstruction from committed data, with no dependency on a file that was never shared.

The hedge ratio is then **re-estimated on this base's own net book** with his estimator (expanding
504-day, lagged) rather than reused — so the leg is measured on the book it is actually hedging, and
it pays its own transaction costs through `ExternalLeg`. Priced honestly it costs 0.02 bp/yr
(0.41 bp total). `h_expanding` is NaN early, before the expanding window arms, which is correct
no-lookahead behaviour: the hedge is simply not on yet.

Two corrections worth knowing, both verified by execution: his `book` column **is** `run().net`
bit-identical (max |Δ| 1.0e-16 across all 4,994 shared days), so his comparison was always on the
shared base; and his −33.2% drawdown is a **cumsum** figure, not the wealth-curve convention this
project uses — his convention applied to the base's own net series reproduces −0.3322331117648022
exactly. The two numbers were never in conflict; they were in different units.

### `fx_option_signal_panel.parquet` — Theo, **ADOPTED**

4,865 × 16, `month_end` 2007-01-31 → 2026-06-30, long panel over G10 + EM. Columns include
`atm_vol_1m`, `rr25_raw_1m`, `bf25_1m`, `rr10_raw_1m`, `bf10_1m` and the signal actually used,
**`bad_skew25_1m`**.

Read by `combined_engine._theo_bad_skew()`, which applies his cross-sectional p80 rule as a
post-sizing trim. Committed 2026-07-18 and unchanged since — in particular it is **not** affected by
his 2026-08-05 commit, which added notebooks and no data (see `../VERDICTS.md`).

Worth recording because it converts a vague coordination warning into a checkable fact: his
`bad_skew25_1m` is **bit-identical** to `fx_utils.vol_surface_panel("RR", "1M")` resampled to
month-end — max absolute difference **0.0** across all 21 shared currencies. So his signal and the
base's risk-reversal are the *same number*; what differs is the axis it is conditioned on (his
cross-sectional p80 vs the adopted per-currency trailing p80) and the action taken (exclude vs
halve). Two readings of one signal, not two signals.

### `adaptive_strategy_returns_monthly.csv` — Vidhi, **REJECTED**

234 rows, month-end 2007-01-31 → 2026-06-30. Columns `date`, `static`, `binary_filter`,
`probability_scaled`. The two filter columns are NaN for the first ~61 months (expanding-window
burn-in), leaving 173 live months from 2012-02.

Read by `combined_engine.regime_gate()`, which recovers the gate as `probability_scaled / static`
(values in [0, 1]) — **only the gate transfers**, because her book's returns use `log_return(spot)`
and never add the carry accrual, so it sorts on carry and harvests none of it. That is why her
static track shows Sharpe −0.71 and −72% drawdown while the same trade on this base is +0.47.

**This file is vendored even though the component is rejected**, and that is the point: the rejection
is reproducible from inside `final/` rather than being something a reader has to take on trust. It
is the single most destructive component tested (0.4659 → 0.0964 standalone), and the diagnostic
matters more than the number — the gate's correlation with VIX is ≈0 at every lead and lag, and it
fails under **both** possible lag conventions, so the verdict does not rest on a judgement call
about a convention her outputs do not record.

---

## Who is not here

- **Dafu** needs no file. His VIX percentile gate is one `fx_utils.exposure_scalar` call on
  `../data/raw/global_risk_wide.parquet` (`VIX`, 756-day lookback, 80th percentile, halve exposure),
  so it reconstructs **exactly** — it reproduces his committed headline to 5 decimal places. He is
  also the only teammate who actually ported onto the shared base, and his is the component the
  slot rule drops. Runnable as `run("COMBINED_TAIL")`.
- **Oleg** has no committed output of any kind — no `outputs/` directory, no CSV, no parquet, and
  zero `to_csv`/`to_parquet` calls anywhere in his notebook. There is nothing to vendor and nothing
  was tested. Recorded as a named gap in `../VERDICTS.md`, not as silence.
