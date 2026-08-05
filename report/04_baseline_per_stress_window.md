# 4. Baseline results, per stress window

*Chapter 4 of the final report. Draft, 2026-08-04.*
*Every number below is reproducible from a committed CSV in `cesare/outputs/`.*

---

## 4.0 Why this chapter comes before the summary statistics

On 29 July 2026 the desk made a standing request: report results **per stress window**, and treat
whole-sample statistics as supporting evidence only. The rationale is a property of the strategy
rather than a reporting preference. Returns compound from carry accrual and spot appreciation, so a
single large loss breaks the compounding path in a way that no sequence of small gains repairs.
Minimising large losses is therefore worth more than adding incremental ones, and a whole-sample
Sharpe is precisely the statistic that averages that distinction away.

This is codified as guardrail §6.8 and enforced in code: `strategy/episodes.py` holds the frozen
windows and `report_windows` refuses to print an annualised ratio for a window shorter than 120
trading days. It is also, as §4.4 shows, the standard that found a real failure in our own tooling.

**Two window sets, and the difference between them is the point.**

- **`ERAS`** partitions the sample contiguously, so shares of P&L across eras sum to exactly 100%.
  That is what makes "this era produced X% of the book's return" an honest statement rather than a
  cherry-pick, and it is the answer to "you chose your windows".
- **`STRESS`** is a set of tight, tail-focused event windows. They overlap and nest inside eras
  because they answer a different question: *did the book preserve capital*.

Both are frozen, and `tests/test_episodes.py::test_windows_are_frozen` asserts the exact keys and
dates. That lock is what stops anyone — including us — re-picking a window after seeing a result.
The windows were chosen from the FX historical record, not from this book's own drawdowns.

---

## 4.1 The stress table

The baseline book, net of costs. Windows under 120 trading days quote cumulative return, drawdown
and worst day only.

| Window | Dates | n | Cum. net | MaxDD | Worst day | What it is |
|---|---|---|---|---|---|---|
| `gfc_2008` | 2008-09 → 2009-06 | 217 | −5.9% | −17.8% | −4.0% | Lehman |
| `euro_2011` | 2011-07 → 2012-12 | 392 | −5.1% | −19.0% | −4.9% | EZ sovereign crisis |
| `taper_2013` | 2013-05 → 2013-09 | 109 | **−12.9%** | **−19.1%** | −4.0% | taper tantrum |
| `china_em_2015` | 2015-06 → 2016-02 | 196 | −5.2% | −9.9% | −2.9% | CNY devaluation |
| `covid_2020` | 2020-02 → 2020-04 | 64 | **−19.6%** | **−24.0%** | −3.8% | worst window in the sample |
| `rates_2022` | 2022-01 → 2022-10 | 216 | **+25.5%** | −6.6% | −2.2% | **control** — carry's best crisis |
| `oil_2026` | 2026-02 → 2026-05 | 85 | **+10.1%** | −1.8% | −1.8% | desk-nominated, 22 Jul |
| `semis_2026` | 2026-04 → 2026-06 | 65 | **+11.7%** | −1.8% | −1.8% | desk-nominated, 22 Jul |

→ `p4_stress_table_baseline.csv` (gross and net; 16 rows)

**`rates_2022` is in this table deliberately.** It is carry's *best* crisis — a risk event in which
the book made 25.5% — and without it the table would read as a list of disasters selected to
motivate a hedge. A stress-window set that contains only losses is a rhetorical device, not an
evaluation standard.

---

## 4.2 The direct answer to the 22 July question

The desk named two 2026 events and asked how the book handled them.

> **Neither 2026 shock was FX-carry stress.**

Both windows are strongly positive with a **−1.8% drawdown**. The oil shock (Feb–May 2026) and the
semiconductor shock (Apr 2026 onward) hit equities and supply chains; they did not reach this book.
That is a clean negative answer to a direct question, and it is worth more than a hedge designed
against an event that never threatened the portfolio.

One honest limit on the framing: the *import/export exposure* channel the question implied would
need trade-balance data that is not in the repository. What is answered here is the return question
— did the book lose money in these windows — not the causal one.

---

## 4.3 Where the P&L actually came from

`ERAS` partitions the sample, so these shares sum to 100% and the comparison is not selective.

| Era | n | Cum. net | Ann. net | Sharpe (net) | MaxDD | Share of net P&L |
|---|---|---|---|---|---|---|
| pre-crisis 2007-08 | 349 | +23.9% | +16.1% | 1.44 | −8.4% | 21.6% |
| GFC 2008-09 | 217 | −5.9% | −6.1% | −0.43 | −17.8% | −5.1% |
| recovery 2009-11 | 522 | +6.4% | +3.5% | 0.35 | −9.3% | 7.0% |
| euro crisis 2011-12 | 392 | −5.1% | −2.7% | −0.22 | −19.0% | −4.0% |
| taper + EM 2013-16 | 1,044 | +11.7% | +3.3% | 0.29 | −23.0% | 13.3% |
| calm 2017-19 | 782 | +5.9% | +2.4% | 0.23 | −16.2% | 7.2% |
| covid 2020 | 262 | −16.3% | −16.3% | −1.26 | −26.9% | −16.4% |
| tightening 2021-23 | 781 | +24.7% | +7.7% | 0.70 | −18.2% | 23.2% |
| recent 2024-26 | 652 | **+70.9%** | **+21.3%** | **1.99** | −11.1% | **53.3%** |

→ `p4_episode_table_baseline.csv` (18 rows, gross and net)

**Read the last row before anything else.** More than half the book's cumulative net P&L comes from
the most recent two and a half years, at a Sharpe of 1.99 that appears nowhere else in the sample
except the pre-crisis period. That concentration is the single most important caveat on every
whole-sample statistic in this report, and it cuts both ways: it is either evidence that the
strategy works well in the current environment, or evidence that the whole-sample numbers are
carried by a recent regime that has not yet been tested by a crisis. **We cannot distinguish these
two readings with the data we have**, and no amount of additional backtesting on this sample will.
It is stated here rather than left for a reader to find.

Three of the nine eras are negative, and they are the three the desk would predict: the GFC, the
euro crisis, and COVID.

---

## 4.4 The standard found a real failure in our own tooling

Two findings fall directly out of building this table, before any modelling.

**The 2013 taper tantrum is the second-worst window in the sample, and it was invisible in every
episode list this repository had.** It sits inside the "taper + EM 2013-16" era, which shows a
*positive* 0.29 Sharpe and +13.3% of total P&L, and it was absent entirely from the previous
hard-coded six-window list. In five months the book lost **12.9% cumulative with a 19.1%
drawdown** — comparable to the GFC and the euro crisis, and completely hidden by the aggregate that
contained it. This is precisely the aggregation failure the desk complained about, found in our own
reporting rather than argued in the abstract.

**Until this cycle, four of the eight stress windows could not be reported at all.**
`StrategyResult.summary()` returned an empty frame for any window shorter than 120 trading days,
because `summary_stats(min_obs=120)` silently skipped it and there was no passthrough. That silently
voided `covid_2020` (64 days), `oil_2026` (85), `semis_2026` (65) **and `taper_2013` (109)** — both
windows the desk named personally, the worst window in the sample, and the window we now use to make
the argument for per-window reporting. A second surface of the same defect raised `IndexError` when
a short window was merely echoed in a notebook.

Both are fixed, and both fixes are **bit-identical at the committed baseline** — the whole daily
cost series matches the pre-fix series to `0.0e+00` — so no published number moved. Regression tests
guard them.

The lesson is not about the bug. It is that **a reporting standard nobody exercises is not a
standard**, and the defect survived undiscovered only because nothing had ever asked this system for
a short window.

---

## 4.5 Where the risk sits and where the gains come from

The 15 July ask was to decompose the rate differential month by month, splitting the long leg from
the short leg. Annualised contributions over 2007-05 → 2026-06, reconciling to the book's gross
return at **3.9e-17**:

| Leg | Annualised contribution |
|---|---|
| **carry, long leg** | **+14.31%** |
| carry, short leg | +2.47% |
| **spot, long leg** | **−10.43%** |
| spot, short leg | +0.67% |
| **total = gross** | **+7.03%** |

→ `p4_leg_decomposition.csv` (328 rows: monthly, quarterly, annual, and the annualised full sample)

**Carry accrual is roughly 2.4× the realised P&L, and spot gives back over half of it — essentially
all of that on the long leg.** Year by year the pattern is stark: **carry on the long leg is
positive in all twenty years, including all seven losing years.** Every losing year is a spot event
on the long leg. Never a carry event.

> **The trade is not "earn carry". It is "earn carry and survive spot."**

That reframes what risk management is *for* in this book. The carry leg has never been the problem,
so a rule that reduces carry exposure to control risk is attacking the wrong side of the trade —
which is consistent with chapter 9's finding that every exposure-timing rule sells premium roughly
one-for-one with the risk it avoids. It is also the clearest argument for the desk's tail objective
being the right objective.

**One trap worth recording**, because anyone repeating this decomposition will hit it: a currency can
have a spot return on a day its carry is missing. On such a day `xret` is NaN and the portfolio
drops the name from `gross` entirely, while an unmasked spot leg happily keeps counting it. Unmasked,
the daily residual reaches 8e-3, which is exactly the shape of the 0.3pp gap an earlier provisional
version of this table showed. Masking the components to where `xret` is present takes the
reconciliation to 3.9e-17. The qualitative conclusion survived; the numbers moved.

---

## 4.6 The whole-sample view, and the G10-versus-EM finding

Now the supporting evidence. All tracks vol-targeted to 10% annualised, common window
2007-05 → 2026-06, ~5,000 trading days.

| Track | Ann. return | Ann. vol | Sharpe | MaxDD | IR vs benchmark |
|---|---|---|---|---|---|
| G10 gross | 1.9% | 11.5% | 0.17 | −36.5% | 0.27 |
| G10 net | 1.4% | 11.5% | 0.12 | −38.2% | 0.21 |
| **Combined gross** | **7.0%** | 11.2% | **0.63** | −26.8% | 0.50 |
| **Combined net** | **5.2%** | 11.2% | **0.47** | −29.3% | 0.34 |
| DBHVG10U (DB G10 carry index) | −0.7% | 9.0% | −0.08 | −39.1% | — |
| FXCTEM8 (DB EM carry index) | 1.5% | 8.9% | 0.16 | −32.1% | — |

→ `strategy_summary_stats.csv`

**The 2007–2026 carry premium lives in EM, not G10.** The combined 27-currency book earns 7.0%/yr
gross at a Sharpe of 0.63; a G10-only book earns 1.9% at 0.17. This is not an artifact of our
construction — the investable Deutsche Bank G10 carry index was *negative* over the same period. A
report that presented carry as a majors strategy would be describing a trade that did not work.

**The construction is validated externally.** Daily correlation is 0.55 with DBHVG10U and 0.39 with
FXCTEM8 — the same trade — and both tracks beat their benchmark on an information-ratio basis (0.27
and 0.50), so the sizing adds value over the index construction rather than merely replicating it.

**Costs matter but do not kill it.** Actual bid/ask drag is 0.55%/yr for G10 and 1.81%/yr for the
combined book. Rolling positions via FX swap at the points spread, rather than closing and reopening
at the outright, is what keeps EM viable; a naive cost model would reject this strategy.

---

## 4.7 What this chapter establishes

1. The premium is EM, it is externally validated, and it survives realistic costs.
2. It is a **calm-market** phenomenon that loses money in the GFC, the euro crisis and COVID, and
   more than half its cumulative P&L comes from the last two and a half years.
3. Its losses are **spot events on the long leg**, never carry events.
4. The two events the desk named in 2026 were not stress for this book at all.
5. The reporting standard that produced all of the above found a defect that had been hiding the
   sample's second-worst window.

Everything after this chapter is an attempt to improve on point 2. Chapter 9 records that nine such
attempts failed.
