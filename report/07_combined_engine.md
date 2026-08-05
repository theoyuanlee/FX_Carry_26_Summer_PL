# 7. The combined engine

*Chapter 7 of the final report. Draft, 2026-08-04.*
*Every number below is reproducible from a committed CSV in `cesare/outputs/`.*

---

## 7.0 What this chapter is for

Six people spent a summer on this strategy. Until August, each of us measured our idea against our
own baseline, which meant a difference between two results measured the two baselines rather than
the two ideas. An audit on 28 July found **five different baseline carry strategies in five folders**,
differing in frequency, quoting convention, universe, cost model, data source — and in one case in
whether the strategy collected the carry accrual at all.

This chapter is what happened when they were all put on the same book. It answers three questions:
which components help, which do not, and how much of the apparent improvement is real.

The honest headline is stated before the tables: **the combined book has a materially better
drawdown profile and no statistically significant improvement in return.** Most of the drawdown
improvement is a lower risk level rather than better selection. That is a smaller claim than the
headline Sharpe suggests, and it is the claim we defend.

---

## 7.1 The interface problem, and the contract that solves it

`StrategyConfig` carries exactly **one** `exposure` series and **one** `weight_overlay` callable.
Four teammates each wanted one. There was also a subtler problem: an overlay that re-normalises gross
exposure silently undoes any gate that ran before it, and then inherits credit for that gate's
drawdown improvement.

`strategy/overlays.py` fixes both, and three of its properties are contract rather than convenience:

1. **Gates multiply, so order cannot matter.** Two gates each halving risk give 0.25, not 0.5. They
   are independent risk vetoes, and a book that ignored the second would be claiming diversification
   between two signals that fire together. A gate's missing dates count as fully invested, so a model
   that only starts in 2015 leaves 2007–2014 untouched rather than being handed a free "avoided 2008".
2. **Overlays may scale positions down, never re-normalise back up.** This is asserted at runtime and
   raises if violated.
3. **`ExternalLeg` is for a new instrument, not a reweighting.** A bond hedge cannot go through
   `weight_overlay`: the portfolio function intersects columns and would silently drop it, and the
   cost model raises on a name with no half-spread series. As an external leg it earns its return
   *and pays its own transaction costs*.

All three are exact no-ops at their neutral settings (`0.0e+00`), so adding the machinery could not
move anybody's numbers, and 17 tests assert exactly that.

---

## 7.2 Re-priced, not rebuilt — and what that costs

The plan made teammate adoption of the shared base the gate for this work, with a deadline of the
12 August meeting. With nine days to go adoption stood at **1 of 5**. Waiting would have consumed
both remaining weeks and still left this chapter unwritten, so the fallback ran instead: every
component was **reconstructed from its owner's committed outputs and re-priced on the shared base**.

**This label travels with every number in this chapter.** A re-price is our reading of a teammate's
signal, not their specification of it. Where a reconstruction could be verified exactly it was, and
where it could not, the method is recorded in the CSV's own `reconstruction` column.

| Component | Owner | Attachment | How it was reconstructed |
|---|---|---|---|
| Duration hedge | Arjun | `ExternalLeg` | TLT return from his committed series; hedge ratio re-estimated on *this* base with his estimator (expanding 504d, lagged); `cost_bps` backed out of his own gross-vs-net series (0.678bp, reproduces his net to 1.1e-15) |
| VIX percentile gate | Dafu | `exposure` | **Exact** — his rule is one `exposure_scalar` call on shared `data/raw`, so no file is needed; reproduces his headline to 5dp |
| Macro/regime gate | Vidhi | `exposure` | Gate recovered as `probability_scaled / static` from her committed monthly tracks (173 months, values in [0,1]). Only the gate transfers — her book omits the carry accrual |
| Bad-skew exclusion | Theo | `weight_overlay` | His committed `bad_skew25_1m` panel with his cross-sectional p80 rule, applied as a post-sizing trim |

**Three things we learned by doing this that we would not have learned by waiting.**

**Arjun's baseline *is* the shared base, bit-identical.** His `book` column matches `run().net` to
**1.0e-16** across all 4,994 shared days. Both apparent discrepancies decompose exactly: his 0.4673
versus our 0.4659 is **7 US market holidays** dropped by his TLT inner join, and his −33.2% versus
our −29.3% is a **cumsum drawdown convention**, not a different book — his convention applied to our
own net series gives −0.33223, matching his figure to every digit. His MaxDD is therefore not
comparable to any other number in this report, and his measured improvement was already on the
shared base. *"Their numbers differ from ours" has at least three explanations — different book,
different sample, different convention — and only the first is worth a week of anyone's time.*

**Theo's "bad skew" and the base's risk reversal are the same number.** His committed
`bad_skew25_1m` is bit-identical to `vol_surface_panel("RR", "1M")` resampled to month-end: maximum
absolute difference **0.0** across all 21 shared currencies. The apparent overlap between his
workstream and the project's existing per-currency risk-reversal rule is not an overlap of related
ideas — it is the same signal, conditioned on a different axis (cross-sectional p80 versus
per-currency trailing p80) with a different action (exclude versus halve).

**The duration hedge was never "essentially unpriced".** Its published gross-versus-net gap of 3.8e-5
looked like a missing cost model. It is not: an expanding-window beta moves very little
(Σ|Δh| = 0.94 over eighteen years), so a near-zero charge is arithmetically correct for what it
bills. Priced honestly through `ExternalLeg` the leg costs **0.02bp/yr**, and the rebalance-drift
charge nobody bills adds 0.074bp/yr. **The headline does not move.** *A suspiciously small number
deserves the same diagnosis as a suspiciously large one — "unpriced" and "barely trades" look
identical in the output.*

---

## 7.3 Every component on one book

Each row is the shared baseline with exactly one thing changed. For the first time these are
comparable to each other rather than merely collected together.

| Component | Owner | Net Sharpe | vs its bar | MaxDD | CVaR₉₉ | Skew | Turnover |
|---|---|---|---|---|---|---|---|
| *(bar)* baseline | — | **0.4659** | — | −29.3% | 0.0292 | −0.65 | 0.675 |
| *(bar)* per-currency RR | — | 0.4559 | −0.010 | −27.6% | 0.0272 | −0.60 | 0.693 |
| **Duration hedge** | Arjun | **0.5145** | **+0.049** | −28.4% | 0.0282 | −0.60 | 0.675 |
| VIX percentile gate | Dafu | 0.4653 | −0.001 | **−24.5%** | 0.0283 | −0.73 | 0.706 |
| Bad-skew exclusion | Theo | 0.4360 | −0.020 | **−22.0%** | **0.0206** | **−0.31** | 0.590 |
| Macro/regime gate | Vidhi | **0.0964** | **−0.370** | −33.6% | 0.0262 | −0.89 | 0.941 |

→ `p4_component_standalone.csv` (7 rows, with each row's full config stamped)

**Note that Sharpe is not the ordering that matters.** The bad-skew exclusion is *below* the baseline
on Sharpe and is in the shipped book; the VIX gate is *at* the baseline on Sharpe and is not. The
slot criterion, fixed before any of this ran, is a tail criterion.

**Vidhi's gate is the single most destructive component tested**, taking the book from 0.4659 to
0.0964. The diagnostic matters more than the number: its correlation with VIX is approximately zero
at every lead and lag, and it fails under **both** possible lag conventions — so the verdict does not
rest on a judgement call about a convention her committed outputs do not record. Her original result
was not wrong on its own terms; it was measured on a book whose returns omit the carry accrual
entirely, so the gate was reducing losses on a book that should not have been losing.

---

## 7.4 The ladder, and the slot criterion

The criterion was fixed in advance. A component earns its slot if, net of costs, it (i) improves
MaxDD **or** CVaR₉₉ in **at least 4 of the 6 pre-2026 stress windows**, **and** (ii) costs less than
0.05 whole-sample net Sharpe, **and** (iii) survives leave-one-out.

Two ladders are reported, always. Add-one-in is order-dependent by construction and flatters whoever
goes first; **leave-one-out is the real test** — a component that does not hurt when removed has not
earned its slot.

| Rung (add-one-in) | Net Sharpe | MaxDD | CVaR₉₉ | α vs previous rung (t) | Windows | Slot |
|---|---|---|---|---|---|---|
| baseline | 0.4659 | −29.3% | 0.0292 | — | — | — |
| **+ duration hedge** | 0.5145 | −28.4% | 0.0282 | +0.74%/yr (1.16) | 4/6 | ✅ |
| + VIX percentile gate | 0.5127 | −24.1% | 0.0275 | +0.08%/yr (0.18) | 3/6 | ❌ |
| **+ bad-skew exclusion** | **0.5323** | **−19.1%** | **0.0189** | +1.40%/yr (1.10) | 6/6 | ✅ |

→ `p4_combined_ladder.csv` (16 rows: `add`, `loo`, `final`, `final_loo`)

**The two ladders disagree about the VIX gate**, and that disagreement decided it. Add-one-in says
it improves only 3 of 6 windows, which fails criterion (i). Leave-one-out says removing it costs
0.043 of net Sharpe, which passes. The protocol written before the run says a component the two
ladders disagree about is **not robust** and is excluded on the strict reading of criterion (i).

**That decision costs 0.043 of net Sharpe, and we took the cost.** Taking it rather than re-reading
the rule after seeing the answer is the entire purpose of fixing the rule in advance. Both numbers
are in the CSV so a reader can disagree with us on the evidence rather than on assertion. It is also
the call we would most like challenged.

**The shipped book is therefore `COMBINED` = baseline + duration leg + bad-skew exclusion:**

| | Gross Sharpe | Net Sharpe | Ann. vol | MaxDD | CVaR₉₉ | Turnover | Cost drag |
|---|---|---|---|---|---|---|---|
| baseline | 0.6284 | 0.4659 | 11.2% | −29.3% | 0.0292 | 0.675 | 1.81%/yr |
| **`COMBINED`** | 0.6331 | **0.4891** | **8.8%** | **−19.1%** | **0.0200** | 0.590 | 1.27%/yr |

`run("COMBINED")` reproduces the ladder row at `0.0e+00`; `test_combined.py` passes 8/8.

---

## 7.5 Four things that must be reported with that table

**1. No alpha anywhere is statistically significant.** The largest t-statistic on any rung that adds
value is **1.16**. The book buys drawdown and skew, not return. The pre-registered prior — that the
combination would be worth less than the sum of its parts — turns out to be **half right**: the
parts do stack on the tail, and not at all on alpha.

The only large t-statistics in the exercise belong to the component that hurt: adding the
macro/regime gate costs −2.14%/yr at **t −1.76**, and removing it gains +3.14%/yr at **t +2.69**.
Quoting 2.69 as "the largest t-statistic on the ladder" would be true and deeply misleading, since
it is evidence about taking something *out*.

**2. Most of the tail gain is de-risking, not selection.** This is guardrail §6.12 and it is the most
important table in the chapter. An overlay that trims positions does two things at once: it drops
*particular* names (selection) and it leaves the book holding *less notional* (de-risking). A
shallower drawdown follows mechanically from the second whatever the first is worth.

The control holds the overlay's **exact daily gross exposure** — matched to 8.9e-16 — but spreads the
reduction across every name, so any remaining difference is selection and nothing else.

| Book | Net Sharpe | Ann. vol | MaxDD | CVaR₉₉ | Skew |
|---|---|---|---|---|---|
| baseline | 0.4659 | 11.2% | −29.3% | 0.0292 | −0.65 |
| gross-matched de-risk *(control)* | 0.4062 | 8.5% | −22.5% | 0.0222 | −0.63 |
| bad-skew exclusion *(the overlay)* | 0.4360 | 9.0% | −22.0% | 0.0206 | **−0.31** |

→ `p4_selection_vs_derisking.csv`

**Of the 7.3 points of drawdown improvement, 6.8 is holding less risk and 0.5 is selection**, and
the selection alpha is +1.25%/yr at **t 0.92** — indistinguishable from zero. Without this control
the project's strongest-looking number would have been its most misleading.

The exception is real and worth keeping: **selection buys skew, −0.63 → −0.31, which de-risking does
not deliver at all.** Holding less of everything makes a book smaller; dropping the right names makes
it less asymmetric. Those are different products and only the second is a skill claim.

**3. The combined book runs at a lower risk level.** 8.8% annualised volatility against the
baseline's 11.2%. Part of the drawdown improvement is therefore simply less risk, and the comparison
is stated that way rather than presented as a free lunch. The consequence is visible in raw wealth:
over the full sample the baseline compounds to **2.48×** and `COMBINED` to **2.18×**. It is better
per unit of risk and worse per dollar deployed. **We have not levered it back to a matched risk
level**, and until we do, the fair reading is that this is a risk-reduction result rather than a
return-improvement one.

**4. It gives up upside, and it is worse in the two 2026 windows.** Per stress window, net:

| Window | Baseline MaxDD | `COMBINED` MaxDD | Baseline cum. | `COMBINED` cum. |
|---|---|---|---|---|
| `gfc_2008` | −17.8% | **−5.6%** | −5.9% | −2.5% |
| `euro_2011` | −19.0% | **−8.2%** | −5.1% | **+4.0%** |
| `taper_2013` | −19.1% | −17.2% | −12.9% | −12.4% |
| `china_em_2015` | −9.9% | **−6.2%** | −5.2% | +0.3% |
| `covid_2020` | −24.0% | **−10.3%** | −19.6% | **−4.5%** |
| `rates_2022` | −6.6% | −5.1% | **+25.5%** | **+9.2%** |
| `oil_2026` | −1.8% | *−5.3%* | +10.1% | +1.4% |
| `semis_2026` | −1.8% | *−4.7%* | +11.7% | +5.4% |

→ `p4_combined_by_episode.csv` (544 rows: 16 variants × 17 windows × gross/net)

The six pre-2026 windows are the ones the slot criterion was written against, and the combined book
is shallower in all six — dramatically so in COVID (−24.0% → −10.3%) and the GFC (−17.8% → −5.6%).

But it converts less of the good states: in the 2022 rates selloff, carry's best crisis, the baseline
made +25.5% and the combined book +9.2%. And in both 2026 windows it is **worse** than the baseline.
That last point is consistent rather than alarming — chapter 4 established that neither 2026 shock
was carry stress, so there was nothing to protect against and the protection only cost money. It is
also a fair characterisation of what this book is: **insurance that is paid for in the good states.**

---

## 7.6 Verdict

`COMBINED` is adopted as the project's integrated book, with these qualifications attached rather
than footnoted:

- It improves the drawdown profile substantially and the return not significantly.
- Most of the drawdown improvement is a lower risk level; only 0.5pp of 7.3pp is selection, and that
  part is not statistically significant.
- What selection genuinely buys is skew, and that is a real if smaller result.
- Two of four teammate components earned a slot; one was excluded by a rule we chose to honour at a
  cost of 0.043 Sharpe; one was destructive.
- Every component is **re-priced, not rebuilt**, and replacing those reconstructions with the
  owners' own ports is the highest-value remaining work on this chapter.

The single most useful output is not the book. It is that six workstreams now produce numbers on one
baseline, so the next disagreement between two of us will be about ideas rather than about
conventions.
