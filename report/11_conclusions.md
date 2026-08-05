# 11. Conclusions and recommendations

*Chapter 11 of the final report. Draft, 2026-08-04.*
*Framed for a Corporate Treasury / Global Funding audience.*

---

## 11.1 The four findings

**1. The 2007–2026 FX carry premium is an emerging-market phenomenon, and it is real.**

The 27-currency book earns a net Sharpe of **0.4659** after real bid/ask costs, against **0.1191** for
a G10-only book — and the investable Deutsche Bank G10 carry index was *negative* over the same
period. The construction correlates 0.55 and 0.39 with the two investable indices and beats both on
an information-ratio basis, so it trades the same premium and sizes it better. The economic licence
is the forward-premium puzzle, which holds in sample: pooled b = 0.733 against UIP's prediction of 1
(t 4.48, n = 6,713).

The practical form of this finding: **carry in the majors was not a trade over this period.** Any
mandate framed around G10 carry would have been framed around something that did not pay.

**2. The risk is spot risk on the long leg, concentrated in about 6% of days.**

Carry accrues **+14.31%/yr on the long leg** and spot gives back **−10.43%/yr on that same leg**. Year
by year, carry on the long leg is positive in **all twenty years including all seven losing ones** —
so every losing year is a spot event, never a carry event. Conditionally, the book earns a Sharpe of
0.57 in calm markets, 0.94 in moderate ones, and **exactly zero in crisis at 1.5× the volatility**.

> **The trade is not "earn carry". It is "earn carry and survive spot."**

This is the single most useful sentence in the report for someone sizing the strategy, because it says
where to spend a risk budget and where not to.

**3. Nine attempts to time or improve the premium all failed.**

Crash hedging, portfolio optimisation, momentum, regime timing, option-implied skew, the
cross-currency basis, the forward term structure, a macro probability gate, and a machine-learned tail
forecast. **Not one produced a statistically significant net alpha**; the largest |t| anywhere is 1.7.

This is not nine unlucky results. It is one economic fact observed nine times: **carry is compensation
for bearing a priced risk, so de-risking on elevated risk indicators sells the premium roughly
one-for-one with the risk avoided.** A rule that reliably avoided the bad states while keeping the
premium would be evidence *against* the risk-premium explanation of why carry pays at all.

The clearest single illustration: sixteen features on 230 monthly observations, forecasting next
month's tail under a purged walk-forward scheme, scored an out-of-sample AUC of **0.4685** — worse
than a coin flip — and lost to a single VIX percentile threshold.

**4. Tail management works. Return enhancement does not.**

The integrated book cuts maximum drawdown from **−29.3% to −19.1%** and CVaR₉₉ by **31%**, while
adding no statistically significant return. And **most of even that is not skill**: against a control
holding the identical daily gross exposure spread across all names, **6.8 of the 7.3 points** of
drawdown improvement is simply holding less risk. Only 0.5pp is selection, at t 0.92.

What selection genuinely buys is **skew, −0.63 → −0.31**, which de-risking does not deliver at all.
Holding less of everything makes a book smaller; dropping the right names makes it less asymmetric.
Those are different products, and only the second is a skill claim.

---

## 11.2 Recommendations

**For an allocation decision**

1. **Treat FX carry as an EM risk premium with an equity-like crash profile, not as a diversifier.**
   Net Sharpe ≈ 0.47, maximum drawdown ≈ 29% at a 10% volatility target, negative skew, and its worst
   losses coincide with dollar funding stress (ΔEMBI loading t ≈ −4 on both tracks). It behaves worst
   exactly when a Treasury balance sheet is already under pressure.

2. **Size it for the 6% of days, not the average day.** The premium is earned in calm and moderate
   regimes and nothing at all in crisis, at half again the volatility. A volatility target calibrated
   on full-sample volatility systematically under-reserves for the states that matter.

3. **Do not buy a timing overlay.** We tested nine and none of them paid. If someone presents one that
   does, ask two questions: was it measured on weights or on returns, and was it compared against a
   gross-matched control? Both were decisive in our own results, and an overlay applied to a return
   series is free — which flatters every risk-management rule ever tested.

4. **If the objective is capital preservation, tail overlays are worth having and should be judged on
   the tail.** Under a Sharpe objective this project rejected tail protection four times; under the
   objective the desk actually stated, **five of twelve rules flip to accept**. The clearest example
   is available today with no new modelling: a VIX percentile gate that costs **0.0007 of Sharpe** and
   buys **4.8 points of maximum drawdown**. Nothing about the evidence changed — only which column
   the verdict was read from.

**For the trade itself**

5. **Roll via FX swap, not at the outright.** This is not a detail. Charging the outright spread on
   notional that never traded is what makes a naive cost model reject EM carry; the correct treatment
   is the difference between 1.81%/yr of drag and a multiple of it.

6. **Hold the one-month point.** Testing 1M, 3M, 6M and 12M forwards, the one-month point dominates on
   gross *and* net. Longer-dated carry gives up return without buying anything.

7. **Prefer per-currency conditioning to book-level gates.** The same signal — the risk reversal —
   is rejected at book level and is the preferred tail hedge applied per currency. A book-level gate
   sells the premium indiscriminately, including in the names that were not the problem.

**For the research programme**

8. **Buy option bid/ask.** It is the highest-value item in the project. Without it no premium-paying
   hedge can be honestly costed and the volatility premium in chapter 8 cannot be converted into a
   strategy — it stays a breakeven statement.

9. **Buy an investable FX volatility index.** External validation is what caught this project's most
   important finding (the EM-versus-G10 result); chapter 8 currently has no equivalent.

10. **Investigate the volatility risk premium properly, with the caveats attached.** It is the only
    thing we tested that survives the spanning test against carry (t 4.58, the largest statistic in
    the project) — but two thirds of its cross-sectional Sharpe is a standing short in five managed EM
    currencies whose tail has not occurred in this sample, and it stops clearing the carry bar at a
    0.10 vol-point spread. **It is a measurement, not yet a strategy**, and it is deliberately kept out
    of the executable book.

---

## 11.3 What we would want challenged

Stated deliberately, because a report that only lists its strengths is not useful.

- **The VIX gate exclusion.** Our pre-registered rule excluded it when the two ladders disagreed, at a
  cost of 0.043 net Sharpe. We think honouring the rule was right. It is the call we would most like
  argued with.
- **The recent-period concentration.** 53% of cumulative P&L comes from the last two and a half years.
  We cannot tell whether that is a feature of the current environment or a warning about the
  whole-sample numbers.
- **The unmatched risk comparison.** `COMBINED` runs at 8.8% volatility against the baseline's 11.2%
  and ends at 2.18× against 2.48×. We have not levered it back to a matched risk level. Until we do,
  it is a risk-reduction result, not a return-improvement one.
- **Whether nine nulls means "carry cannot be improved" or "we did not find the improvement."** We
  have argued the former from the risk-premium logic. The latter remains possible, and this project is
  underpowered to distinguish them for small effects.

---

## 11.4 The through-line

The project set out to find a way to improve FX carry through dynamic exposure management. It did not
find one, and it now understands why: **the premium and the crash risk are the same thing, so you
cannot sell one without selling the other.**

What it found instead is more modest and more usable. The premium is real and it is in EM. Its risk is
spot risk on the long leg, in a small number of days. It can be made materially less painful to hold —
a third off the maximum drawdown, 31% off CVaR₉₉ — mostly by taking less risk and partly by dropping
the right names, and the honest accounting separates those two. And in the same option data that
failed to improve the carry sort, there is a *different* premium that behaves unlike anything else we
tested, which we can measure and cannot yet trade.

Six workstreams now report on one baseline, with frozen windows, pre-registered bars and 48 tests. The
next disagreement will be about ideas rather than about conventions, which is the outcome that will
outlast any number in this report.
