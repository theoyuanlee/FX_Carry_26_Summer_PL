# 2. Data and conventions

*Chapter 2 of the final report. Draft, 2026-08-04.*

---

## 2.0 Why this chapter is early and specific

Most of the ways a currency backtest goes wrong are not modelling errors. They are convention errors:
a quote inverted, a forward point scale off by a factor of ten, a pegged currency left in a
volatility-weighted portfolio, a cost model that closes and reopens a position that should have been
rolled. None of these produce an obviously broken result — they produce a *plausible* one.

This chapter records the conventions so a reader can find the error if there is one, and so a
teammate can reproduce a number rather than approximate it.

---

## 2.1 Universe

**Source universe:** 11 G10 and 19 EM currencies against the US dollar, daily, January 2007 to
June 2026.

**Three exclusions, fixed and applied everywhere:**

- **HKD and DKK are dropped** — both are pegged, so their realised volatility is degenerate. In an
  inverse-volatility weighting scheme a near-zero-volatility currency attracts an unboundedly large
  weight, which is a mechanical artifact rather than a position.
- **CNY is dropped in favour of CNH.** CNY has no deliverable forward; CNH is the tradable offshore
  renminbi leg. Trading the untradable onshore rate would be a backtest of an instrument that does
  not exist.

**Result: 9 G10 names** (AUD CAD CHF EUR GBP JPY NOK NZD SEK) and **27 combined names.** These
exclusions are fixed unless a chapter explicitly studies them.

**TRY is kept, and its post-2018 extremes are contained structurally** — by inverse-volatility leg
weights and a 40% cap on any single name's share of its leg — rather than by winsorising the signal.
This is a deliberate choice. Winsorising would suppress exactly the crash behaviour the report claims
to be studying; capping limits the position without editing the data. Chapter 9 notes that TRY drives
one of the negative anchors in the D3 test, and the sensitivity is reported rather than removed.

---

## 2.2 Quoting and the panels built from it

**Quoting is the first thing to get wrong.** EUR, GBP, AUD and NZD are quoted USD-per-FX; everything
else is quoted FX-per-USD. `spots_usd_per_fx` normalises all of them to **USD-per-FX**, so that a
rising number always means the foreign currency appreciating. Every panel downstream assumes this.

**The carry signal is forward-implied carry**, `ln(S/F)` in USD-per-FX terms, annualised — not an
interest-rate ranking. This is a deliberate correction to the original project outline, and it is the
better choice for three reasons: it is *tradable* (it is the rate you actually transact at), it
automatically embeds NDF and convertibility basis for restricted currencies, and it does not depend
on onshore fixing availability. By covered interest parity it equals the CIP-implied rate
differential, and §2.5 shows it does.

**Returns are excess returns**: daily spot log return plus lagged carry accrual divided by 252 — the
standard academic construction. The decomposition into `spot_component` and `carry_component` sums to
the total exactly, which is what makes chapter 4's long-leg/short-leg attribution possible without
re-deriving anything.

**Forward point scales** are per-currency (`FWD_SCALE`) and were validated empirically rather than
taken from documentation; NDF roots are recorded for BRL, CLP, COP, IDR, INR, KRW and PEN.

---

## 2.3 Costs

Every result in this report is reported **gross and net**. The cost model uses actual per-currency
bid/ask half-spreads from the forward data, and it makes one distinction that decides whether the EM
book is viable at all:

- **New notional** pays the **outright** half-spread.
- **Maintained notional** rolls via **FX swap**, paying the **forward points** half-spread.

A cost model that closes and reopens the full position each month charges the outright spread on
notional that never actually traded. On EM names, where the outright spread is wide and the points
spread is not, that difference is the whole margin: it is what makes the combined book's drag
1.81%/yr rather than a multiple of it. **A naive cost model rejects this strategy**, and would be
wrong to.

Realised drag: **0.55%/yr for G10** and **1.81%/yr for the combined book**.

**One defect worth recording**, because it was live for most of the project. The roll leg was
originally billed on the *rebalance* grid rather than the *forward tenor* grid, which is correct only
when the two coincide — i.e. only at the committed baseline of a 1-month tenor rebalanced monthly.
The signature was unmistakable in hindsight: at a 12-month tenor the cost drag *rose* to 4.84%/yr
while turnover *fell* to 0.426, which is backwards. It is fixed, the fix is **bit-identical at the
baseline** (`0.0e+00` across the whole daily cost series), and off-baseline numbers are now
comparable — the 12-month drag falls to 1.87%/yr and the quarterly-rebalance cell, which had been
*under*charged, rises. No published number moved; several previously uninterpretable ones became
interpretable.

---

## 2.4 Data inventory

Thirteen parquet groups in `data/raw/`, each stored wide and long, daily 2007-01 to 2026-06/07:

**Automated pull** (Bloomberg via `src/bloomberg_data.py`; a terminal is required only to *refresh*):
G10 and EM spot and forwards **with bid/ask**, G10 and EM option surfaces (ATM, 10Δ and 25Δ risk
reversals and butterflies), G10 and EM interest rates, global risk (SPX, MXEF, BCOM, DXY, VIX, the
UST curve), and macro market proxies.

**Hand-pulled supplement:** USD risk-free (USGG3M), the carry benchmark indices (DBHVG10U, FXCTEM8,
DBHVBUSI), DKK/HKD rate gaps, EM onshore fixings, and the EMBI Global spread.

**The parquet snapshots are committed**, so every number in this report is reproducible without a
Bloomberg terminal. Provenance is in `ticker_manifest.csv` with coverage and failure CSVs alongside.

**Known gaps, stated because they bound several chapters:**

- **No option surfaces for CLP, COP, IDR, MYR, PEN or PHP.** This is why every option-based test runs
  on a matched 21-name universe rather than the full 27, and why chapters 8 and 9 report U21 anchors
  separately from the ALL-27 baseline.
- **Option data is mids only — there is no bid/ask on any volatility surface.** This is the single
  most consequential gap in the repository. It blocks honest costing of any premium-paying hedge and
  of the entire volatility strategy in chapter 8.
- **Synthetic USD LIBOR was discontinued 2024-09-30**, which caps every cross-currency-basis result
  at that date. The onshore EM fixings themselves run to 2026-07; an earlier version of our own
  documentation attributed the cap to the fixings, which was wrong.
- **CNY forwards are unavailable** (hence CNH), and NIBOR12M, STIB12M and CLSWA are missing.

**A correction worth recording.** Project documentation stated that testing alternative forward
tenors would require a new data pull because "only 1M was pulled". All 27 names carry 1M, 3M, 6M and
12M forwards, and the code already supported all four. The test ran for free and is reported in
chapter 9 as a third null. **A "needs data" claim is a testable claim**, and this one had never been
tested — a pattern that recurred four more times and is discussed in chapter 10.

---

## 2.5 Why the pipeline can be trusted

Four checks, each of which could have failed:

1. **Forward scales.** Median 12-month forward-implied carry per currency against known rate
   differentials → `implied_carry_validation.csv`.
2. **Covered interest parity.** Forward-implied carry ≈ onshore rate differential for deliverable
   currencies, with a persistent basis only where one is expected (NDFs, proxy fixings) →
   `cip_basis_summary.csv`. The identity `cip_basis = carry_panel − interest_diff_vs_usd` holds to
   8e-17.
3. **External benchmarks.** Daily correlation 0.55 with DBHVG10U and 0.39 with FXCTEM8 — the backtest
   trades the same premium the investable indices trade.
4. **The economic licence.** Pooled Fama regression b = 0.733 (t 4.48, n = 6,713) — chapter 5.

**And one external cross-check that is stronger than any of them.** A teammate's independently
written robustness audit reproduces from this base: the same most-damaging jackknife names (JPY, CNH,
MXN), the same finding that ZAR is a drag, the same edge dying between 2× and 3× spreads, and the
same 60-day × month-end parameter cell sitting on a plateau rather than a spike. **Two independent
implementations agreeing is the strongest evidence the construction is right**, and it is worth more
than any internal assertion.

---

## 2.6 Evaluation window and environment

**Common evaluation window: 2007-05-01 → 2026-06-30, 5,001 trading days**, for every comparison in
this report. A variant evaluated on a different window is not comparable to the baseline, and one
defect caught during this project was an overlay that silently extended its own window to 2007-02 by
converting pre-inception missing weights into real zeros — the numbers looked entirely reasonable,
and the error was caught by comparing windows rather than values.

**Environment:** Python 3.13 with numpy, pandas, scipy, statsmodels, matplotlib, and **pyarrow ≥ 24
installed from pip**. The conda build of pyarrow (19.x) cannot read this repository's parquet files
and fails in a way that looks like data corruption rather than a version problem. This is recorded
because it has cost time more than once.
