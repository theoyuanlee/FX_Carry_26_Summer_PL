# Final report — structure and status

*Deliverable 3 of 3 (plan §19.5). Structure per plan §14.3, restructured 2026-08-03,
renumbered 2026-08-04.*

> **This is the vendored copy inside the hand-off package.** It is the same eleven chapters, with
> in-package paths rewritten so they resolve from here: `cesare/outputs/` → [`../evidence/`](../evidence/),
> `strategy/tests/` → [`../tests/`](../tests/). References to `strategy/`, `data/raw/` and the
> conventions are unchanged, because [`../strategy/`](../strategy/) and [`../data/raw/`](../data/raw/)
> exist in this package too.
>
> **Three references deliberately point outside the package**, and are kept rather than removed
> because a citation to work that did not ship is still a citation: `cesare/bkm_skew.py` (ch. 9 — the
> D1 rerun's model-free skewness code, research not strategy), the project plan document, and the
> Aug-5 deck. They resolve while `cesare/` exists and become historical citations afterwards.
>
> The one thing this copy adds is [`../VERDICTS.md`](../VERDICTS.md), which closes the evaluation
> this report describes: every extension from all six workstreams, kept or dropped, in one table —
> including the two workstreams with nothing to show.

**Audience:** Bank of America Corporate Treasury / Global Funding.
**Spine:** the desk's four beats — current results · what we did · what we have · what is next.
**Lead with per-window results** (guardrail §6.8, the desk's standing requirement since 2026-07-29).
Whole-sample statistics are supporting evidence only.

## Chapters

| # | Chapter | Status | Primary sources |
|---|---|---|---|
| 1 | [Executive summary](01_executive_summary.md) — what the book earns, where it loses, what integration added | ✅ | `final_comparison.csv`, `p4_combined_ladder.csv` |
| 2 | [Data & conventions](02_data_and_conventions.md) | ✅ | plan §5 |
| 3 | [Methodology & guardrails](03_methodology_and_guardrails.md), incl. the shared base | ✅ | plan §6, §18; `strategy/README.md` |
| 4 | [**Baseline results per stress window**](04_baseline_per_stress_window.md), then the G10-vs-EM finding | ✅ | `p4_stress_table_baseline.csv`, `p4_episode_table_baseline.csv`, `p4_leg_decomposition.csv` |
| 5 | [Return drivers & crash risk](05_return_drivers_and_crash_risk.md) | ✅ | `regression_lrv.csv`, `crash_regressions.csv`, `uip_fama.csv` |
| 6 | [Risk-managed carry · portfolio construction · momentum · regimes](06_risk_managed_carry.md) | ✅ | stage 3–6 CSVs |
| 7 | [**The combined engine**](07_combined_engine.md) — the fold-in ladder, what earned a slot and what did not | ✅ | `p4_combined_ladder.csv`, `p4_component_standalone.csv`, `p4_selection_vs_derisking.csv` |
| 8 | [**The volatility risk premium**](08_volatility_risk_premium.md) — the one qualified positive | ✅ | `p3_d2_*.csv` |
| 9 | [**What did not work**](09_what_did_not_work.md) — the null-results chapter, including the tail-event forecast | ✅ | nine nulls, all with committed CSVs |
| 10 | [Limitations](10_limitations.md) | ✅ | option mids only; no market impact / funding curve; daily USD-per-FX |
| 11 | [Conclusions & recommendations](11_conclusions.md) for a Treasury / Global Funding audience | ✅ | — |

**Two notes on the numbering**, because it changed on 2026-08-04:

- Files are now numbered to match their chapter numbers. Previously the null chapter was filed
  `07_what_did_not_work.md` while being chapter 9, which was a standing source of confusion; it is
  now `09_`.
- **The tail-event forecast (plan §19.3, the desk's central ask) does not have its own chapter.** It
  is a null, and it is written up as **§9.3** alongside the other integration null. An earlier
  version of this table reserved chapter 7 for it and marked that slot "written up inside ch. 7",
  which described a file that did not exist. Chapter 7 is now the combined engine and there is no
  gap in the sequence.

## Rules this report follows

1. **Every number traces to a committed CSV.** No figure appears in prose without a file behind it —
   the plan document's opening promise, and the thing that caught four base defects. Almost all of
   them are in [`../evidence/`](../evidence/); the one documented exception is data provenance,
   where ch. 2 cites [`../data/raw/ticker_manifest.csv`](../data/raw/ticker_manifest.csv). An
   earlier wording of this rule said "in `cesare/outputs/`" and was narrower than the report it
   describes.
2. **Gross and net, always.** A result quoted without its cost drag is not a result.
3. **Per window before whole-sample.** A rule that lifts the full-sample Sharpe while making the
   crisis eras worse is a rule this book does not want, and only the per-window table shows that.
4. **Nulls are stated, not buried.** Chapter 9 is deliberately one of the longest chapters.
5. **Pre-registered bars.** Where a verdict is quoted, the bar it was measured against was written
   down before the run, and the chapter says so.
6. **Re-priced, not rebuilt.** Any teammate's component folded in without their own port is labelled
   as such, with the reconstruction method stated (plan §15 fallback).

## Headline numbers, for cross-checking any draft

| Book | Gross Sharpe | Net Sharpe | MaxDD | CVaR₉₉ | Turnover |
|---|---|---|---|---|---|
| `run()` — ALL, 27 names | 0.6284 | **0.4659** | −29.3% | 0.0292 | 0.6755 |
| `run("G10")` — 9 names | 0.1669 | 0.1191 | −38.2% | — | — |
| `run("COMBINED")` — the Phase-4 engine | 0.6331 | **0.4891** | **−19.1%** | **0.0200** | 0.5902 |
| `run("COMBINED_TAIL")` — *not shipped*, the documented alternative | 0.6808 | 0.5323 | −19.1% | 0.0189 | 0.6051 |

The fourth row is the one contested verdict, made runnable. It is `COMBINED` plus Dafu's VIX
percentile gate — the component the slot rule drops and the tail objective accepts. It is **not the
strategy**; it exists so the cost of the decision (0.043 net Sharpe, 5.4% relative CVaR₉₉) can be
priced rather than asserted. Full reasoning in [`../VERDICTS.md`](../VERDICTS.md).

Test suite, run from inside this package: `tests/test_reconciliation.py` 12/12 ·
`tests/test_episodes.py` 11/11 · `tests/test_overlays.py` 17/17 · `tests/test_combined.py` **12/12**
(8 as shipped in the shared base, plus the `COMBINED_TAIL` assertion) ·
`tests/test_standalone.py` 5/5 · `tests/test_vendor_drift.py` 4/4. Or just
`python reproduce.py`, which runs the books and prints this table.

The 2026-08-05 progress deck built from the same CSVs is `cesare/presentations/deck_2026_08_05.html`,
generated by `python cesare/build_deck.py` — outside this package, in the research folder.
