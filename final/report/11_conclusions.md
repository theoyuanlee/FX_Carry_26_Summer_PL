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

## 11.2 The delivered menu — pick a rung, not a strategy

The project ships **one engine at three points on a risk-appetite ladder**, so the allocation
decision is a mandate choice rather than an acceptance of somebody else's default. All three are
named presets of the same construction and are reproduced by one command.

| Book | When it is the right mandate | Return | Vol | Sharpe | Sortino | Calmar | MaxDD | CVaR₉₉ |
|---|---|---|---|---|---|---|---|---|
| `OFFENSIVE` | calm macro, risk-on, drawdown budget available | **7.64%** | 16.59% | 0.4606 | 0.627 | 0.157 | **−41.24%** | 0.0430 |
| *baseline — reference* | *not a mandate; the comparison line* | *5.21%* | *11.19%* | *0.4659* | *0.634* | *0.160* | *−29.32%* | *0.0292* |
| `CORE` | default / all-weather | 4.33% | 8.85% | 0.4891 | 0.694 | 0.211 | −19.07% | 0.0200 |
| `DEFENSIVE` | the desk judges the regime to be stressed | 4.43% | 8.32% | **0.5323** | **0.760** | **0.219** | −19.07% | **0.0189** |

**Every risk-adjusted ratio improves monotonically down the ladder while return moves monotonically
the other way**, and that ordering holds in all eight frozen stress windows, not just in aggregate.
Through COVID the offensive book loses 28.2% and the defensive book 2.8%; through the 2022 rates
selloff the offensive book makes +40.2% and the defensive book +5.0%. That is the entire trade-off,
and it is visible in both directions rather than only where protection flatters.

Three things this menu does **not** claim, each of which the evidence in this report forbids:

- **`OFFENSIVE` is a leverage dial, not an edge.** Its net Sharpe of 0.4606 is the baseline's 0.4659
  within noise, by construction. The 15% target is the top of a plateau rather than an argmax — across
  targets of 10/12/13/15/18% the Sharpe runs 0.4659 / 0.4656 / 0.4645 / 0.4606 / 0.4430, flat until
  the leverage cap begins truncating the highest-volatility days. What it buys is quantity, and the
  −41% drawdown is what quantity costs.
- **`DEFENSIVE` is not promoted despite having the better ratios.** It is better than `CORE` on
  Sharpe, Sortino, Calmar and CVaR₉₉, and it is still not the default, because the gate it adds failed
  the slot rule fixed before any component was measured. That decision costs 0.043 of net Sharpe and
  it is paid rather than re-argued after the fact (ch. 7, §7.6). It is offered as a named mandate so
  the cost can be priced by whoever disagrees.
- **No rule is offered for switching between the rungs.** Nine timing overlays were tested and none
  paid (ch. 9). A switching signal is precisely the thing this report's own evidence says not to
  claim, so choosing a rung is a judgement the desk makes, not a forecast the book supplies.

### At matched risk

Comparing `CORE` with the baseline on return compares two different risk levels — `CORE` runs at
8.85% volatility against 11.19%. Levered onto matched risk:

| At matched risk | Return | Vol | Sharpe | MaxDD | CVaR₉₉ | Skew |
|---|---|---|---|---|---|---|
| baseline | 5.21% | 11.19% | 0.4659 | −29.32% | 0.0292 | −0.65 |
| **`CORE` levered** | **5.33%** | 11.08% | **0.4813** | **−23.87%** | **0.0253** | **−0.30** |

Same risk, **more return, a 5.4pp shallower drawdown, 13% less CVaR₉₉ and less than half the negative
skew**. This supersedes the concessive reading — *better per unit of risk, worse per dollar deployed* —
carried in earlier material: that was an artifact of comparing at unmatched risk, not a property of
the book. The leverage is a mandate parameter chosen with the whole sample in view, which is
legitimate for a like-for-like comparison and is not offered as a trading rule.

*Source: `../evidence/strategy_menu.csv`, `../evidence/strategy_menu_by_window.csv`,
`../evidence/strategy_menu_matched_risk.csv`, built by `../menu.py`.*

## 11.3 Recommendations

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

## 11.4 What we would want challenged

Stated deliberately, because a report that only lists its strengths is not useful.

- **The VIX gate exclusion.** Our pre-registered rule excluded it when the two ladders disagreed, at a
  cost of 0.043 net Sharpe. We think honouring the rule was right. It is the call we would most like
  argued with.
- **The recent-period concentration.** 53% of cumulative P&L comes from the last two and a half years.
  We cannot tell whether that is a feature of the current environment or a warning about the
  whole-sample numbers.
- ~~**The unmatched risk comparison.**~~ **Closed — see §11.2.** This bullet used to say we had not
  levered `COMBINED` back to a matched risk level and that until we did, it was a risk-reduction
  result rather than a return-improvement one. It has now been run: at matched risk the book returns
  5.33%/yr against the baseline's 5.21% at a −23.87% drawdown against −29.32%. The challenge was
  fair, it was the right thing to have flagged against ourselves, and the answer went the other way
  from the one we conceded.
- **Whether nine nulls means "carry cannot be improved" or "we did not find the improvement."** We
  have argued the former from the risk-premium logic. The latter remains possible, and this project is
  underpowered to distinguish them for small effects.

---

## 11.5 The through-line

The project set out to find a way to improve FX carry through dynamic exposure management. It did not
find one, and it now understands why: **the premium and the crash risk are the same thing, so you
cannot sell one without selling the other.**

What it found instead is more modest and more usable. The premium is real and it is in EM. Its risk is
spot risk on the long leg, in a small number of days. It can be made materially less painful to hold —
a third off the maximum drawdown, 31% off CVaR₉₉ — mostly by taking less risk and partly by dropping
the right names, and the honest accounting separates those two. And in the same option data that
failed to improve the carry sort, there is a *different* premium that behaves unlike anything else we
tested, which we can measure and cannot yet trade.

Six workstreams now report on one baseline, with frozen windows, pre-registered bars and 51 tests. The
next disagreement will be about ideas rather than about conventions, which is the outcome that will
outlast any number in this report.
