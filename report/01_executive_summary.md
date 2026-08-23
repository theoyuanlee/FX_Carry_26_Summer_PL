# 1. Executive summary

*Chapter 1 of the final report. Draft, 2026-08-04.*
*Every number below is reproducible from a committed CSV in `cesare/outputs/`.*

---

## 1.1 What we set out to answer

**Can a traditional FX carry strategy be improved by dynamically adjusting exposure using
macroeconomic conditions, volatility and momentum?**

Nineteen years of daily data, 27 currencies, real bid/ask costs, benchmarked against investable carry
indices. The short answer is **no, not in any way that survives costs and significance testing** —
and the useful answer is what that failure looks like in detail, and what turned out to work instead.

---

## 1.2 What the book earns

Common window 2007-05 → 2026-06, 5,001 trading days, vol-targeted to 10% annualised.

| Track | Ann. return | Ann. vol | Sharpe | MaxDD | IR vs benchmark |
|---|---|---|---|---|---|
| G10 net | 1.4% | 11.5% | 0.12 | −38.2% | 0.21 |
| **Combined (27 names) gross** | **7.0%** | 11.2% | **0.63** | −26.8% | 0.50 |
| **Combined net** | **5.2%** | 11.2% | **0.47** | −29.3% | 0.34 |
| DBHVG10U (DB G10 carry index) | −0.7% | 9.0% | −0.08 | −39.1% | — |

**The 2007–2026 carry premium lives in EM, not G10.** The combined book earns a net Sharpe of 0.47;
a G10-only book earns 0.12, and the investable DB G10 carry index was *negative* over the same
period. A report presenting carry as a majors strategy would be describing a trade that did not work.

The construction is externally validated (daily correlation 0.55 and 0.39 with the two investable
indices) and it beats both on an information-ratio basis, so the sizing adds value over the index
construction. Costs matter but do not kill it: 1.81%/yr of drag on the combined book, and rolling
positions via FX swap rather than at the outright is what keeps EM viable.

---

## 1.3 Where it loses, and why

**It is a calm-market strategy.** Conditional on a lagged three-state regime classifier, the book
earns a Sharpe of 0.57 in Low, 0.94 in Moderate, and **exactly zero in Crisis at 1.5× the
volatility** — about 6% of days carrying the crash risk and contributing none of the return.

**Its losses are spot events, never carry events.** Decomposing annualised contribution by leg, and
reconciling to the book's gross return at 3.9e-17:

| Leg | Annualised contribution |
|---|---|
| carry, long leg | **+14.31%** |
| carry, short leg | +2.47% |
| spot, long leg | **−10.43%** |
| spot, short leg | +0.67% |
| **total = gross** | **+7.03%** |

Carry accrual is ~2.4× the realised P&L, and spot gives back over half of it, essentially all on the
long leg. Year by year, **carry on the long leg is positive in all twenty years including all seven
losing years.**

> **The trade is not "earn carry". It is "earn carry and survive spot."**

**Two caveats that belong in the summary rather than an appendix.** First, more than half the book's
cumulative net P&L — **53%** — comes from the most recent two and a half years, at a Sharpe of 1.99
that appears nowhere else in the sample. That is either evidence the strategy suits the current
environment or evidence the whole-sample numbers are carried by an untested regime, and **we cannot
distinguish those readings with this data.** Second, the strategy is a levered version of the known
academic carry factor (β 1.39, R² 0.69) with an alpha of 2.2%/yr that is not significant (t 1.56).
We did not discover a new signal.

---

## 1.4 What did not work — nine times

Nine distinct attempts to improve on the simple book failed against a bar written down before each
was run. Four were standard, three were deliberately non-standard, two came out of the integration
work.

| | Attempt | Outcome |
|---|---|---|
| 1 | Crash hedging / exposure timing | No rule has significant alpha — all \|t\| < 1.7 |
| 2 | Portfolio optimisation (ERC, equal, mean-variance) | None beats inverse volatility net of costs |
| 3 | Momentum overlay | Dominated — less Sharpe *and* worse drawdown |
| 4 | Regime-aware allocation | Max \|t\| 0.59 against the simplest hedge |
| 5 | Option-implied skew (D1) | Null; the published spanning claim *reverses* |
| 6 | Cross-currency basis (D3) | Null, on a universe too weak to test it properly |
| 7 | Forward term structure (D6) | Null — the 1-month point dominates on gross *and* net |
| 8 | Macro/regime probability gate | Destructive: 0.4659 → 0.0964 |
| 9 | Tail-event forecast | Out-of-sample AUC **0.4685** — loses to one VIX threshold |

**Nothing anywhere in this project produced a statistically significant net alpha.** That is not nine
unlucky results; it is one economic fact observed nine times. Carry is compensation for bearing a
priced risk, so de-risking on elevated risk indicators sells the premium roughly one-for-one with the
risk avoided. A rule that reliably avoided the bad states without giving up the premium would be
evidence *against* the risk-premium explanation of why carry pays at all.

**This accumulated negative evidence is the most defensible thing the project has produced**, and
chapter 9 is deliberately its longest chapter. A desk deciding whether to allocate to FX carry is
better served by knowing which nine improvements do not work than by a tenth backtest that does.

---

## 1.5 What integration added

Until August, six people measured six ideas against six different baselines — an audit found five
materially different baseline strategies, one of which never collected the carry accrual at all. A
shared base was built, and every component was re-priced on it.

| | Gross Sharpe | Net Sharpe | Ann. vol | MaxDD | CVaR₉₉ |
|---|---|---|---|---|---|
| baseline | 0.6284 | 0.4659 | 11.2% | −29.3% | 0.0292 |
| **`COMBINED`** | 0.6331 | **0.4891** | **8.8%** | **−19.1%** | **0.0200** |

`COMBINED` is the baseline plus a duration hedge and a bad-skew exclusion. It is shallower in **all
six pre-2026 stress windows** — most dramatically COVID (−24.0% → −10.3%) and the GFC
(−17.8% → −5.6%).

**Three qualifications belong in the same breath as that table:**

1. **No improvement is statistically significant.** The largest t-statistic on any value-adding rung
   is 1.16. The book buys drawdown and skew, not return.
2. **Most of the drawdown improvement is not skill.** Against a control holding the identical daily
   gross exposure spread across every name, **6.8 of the 7.3 points** of drawdown improvement is
   simply holding less risk. Only 0.5pp is selection, at t 0.92. What selection genuinely buys is
   **skew, −0.63 → −0.31**, which de-risking does not deliver at all.
3. **It runs at lower risk — and once that is corrected for, it wins on return too.** `COMBINED`
   carries 8.8% volatility against 11.2%, and at its own risk level it compounds to 2.18× against the
   baseline's 2.48×: better per unit of risk, worse per dollar. **Levered to matched risk (11.08%) it
   returns 5.33%/yr against the baseline's 5.21%, at a drawdown of −23.87% against −29.32%, CVaR₉₉ of
   0.0253 against 0.0292 and skew of −0.30 against −0.65.** Same risk, more return, smaller tail. This
   supersedes the reading carried in earlier versions of this report, which described the result as
   risk-reduction only; that was an artifact of comparing two books at different risk levels rather
   than a property of the book. The leverage is a mandate parameter, not a signal.

**The most valuable output is not the book.** It is that six workstreams now produce numbers on one
baseline, so the next disagreement between two of us is about ideas rather than conventions.

---

## 1.6 The one qualified positive

Every failed attempt above asked the same question: *can some signal improve the carry sort?* One
line of work asked a different one — *is there a second, distinct premium in the same data?* — and
the answer appears to be yes.

Selling one-month at-the-money implied volatility and paying realised earns a positive premium in
**20 of 21 currencies**, 13 of them individually significant. Crucially it **survives the spanning
test against carry** (α +3.33%/yr, **t 4.58**) — the exact test that killed the two novel signals,
where carry subsumed the candidate rather than the reverse. That is the largest t-statistic anywhere
in the project.

**It is not a recommendation, for three reasons that travel with it:**

1. **Two thirds of the cross-sectional Sharpe is a standing tilt, not timing.** Removing the
   per-currency mean takes it from 1.69 to 0.55, the skew inverts from +1.66 to −1.84, and the
   drawdown doubles to −48.7%. The standing shorts are TRY, MXN, THB, KRW and INR — managed
   currencies whose tail has not occurred inside 2007–2026. The raw book's zero drawdown through the
   GFC is a property of that position, not evidence of its safety.
2. **It cannot be costed.** Option data is mids only. Rather than publish a zero-cost Sharpe we solve
   for the breakeven spread: the cross-sectional book stops clearing the carry bar at **0.10 vol
   points** round-trip, which is *inside* G10 interbank — and its largest positions are in EM, where
   spreads are several times wider.
3. **The evidence is weaker by construction** than the two nulls it outperforms: close-to-close
   realised volatility, and no investable index to validate against.

It is reported as the project's most interesting finding and its clearest data request, and it is
deliberately **kept out of the executable book**, because `COMBINED` is costed and this is not.

---

## 1.7 What we would tell a Treasury desk

1. **FX carry over this sample is an EM trade**, it is real, and it survives realistic costs at a net
   Sharpe of about 0.47.
2. **Its risk is spot risk on the long leg, concentrated in about 6% of days.** Size for that, and do
   not expect a timing rule to remove it — we tested nine and none did.
3. **Tail management works; return enhancement does not.** The integrated book cuts maximum drawdown
   by a third and CVaR₉₉ by 31%, and adds no significant return. If the objective is capital
   preservation, that is a good trade. If it is return, this is not where to find it.
4. **Be careful what you attribute to skill.** Most of our own best-looking risk improvement was
   holding less risk. The control that showed this is cheap, and we would not trust a comparable
   number from anyone who had not run it.
5. **Two data purchases would change what we can say**: option bid/ask, and an investable FX
   volatility index. Both are cheap relative to the questions they close out.

---

## 1.8 How to verify any of this

Every number in this report traces to a committed CSV in `cesare/outputs/`, and the headline books
are reproducible in one command each:

```bash
python strategy/tests/test_reconciliation.py   # 12/12 — asserts 0.6284 / 0.4659 on every run
python strategy/tests/test_episodes.py         # 11/11
python strategy/tests/test_overlays.py         # 17/17
python strategy/tests/test_combined.py         # 11/11
```
