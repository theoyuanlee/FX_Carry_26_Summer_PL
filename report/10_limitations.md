# 10. Limitations

*Chapter 10 of the final report. Draft, 2026-08-04.*

---

## 10.0 How to read this chapter

These are the things that would change a conclusion in this report, ordered by how much damage each
could do. Several of them are already visible in earlier chapters as caveats; they are collected here
so a reader can see the full set at once rather than assembling it.

---

## 10.1 Limits that bound what we can claim

### The sample is one sample, and its recent half dominates

Nineteen years of daily data is 5,001 observations of a daily return, but far fewer independent
observations of the thing that actually matters — a crisis. The sample contains roughly four: 2008,
2011–12, 2015–16 and 2020. Every statement in this report about tail behaviour rests on four events,
and no amount of daily data changes that.

Worse for interpretation: **53% of the book's cumulative net P&L comes from the final two and a half
years**, at a Sharpe of 1.99 that appears nowhere else except the pre-crisis period. Whole-sample
statistics are therefore substantially a statement about 2024–26. We cannot distinguish "the strategy
suits the current environment" from "the numbers are carried by a regime that has not yet been
tested", and we do not claim to.

### Nothing is statistically significant

**No result anywhere in this project produced a significant net alpha.** The largest |t| on any
value-adding rung of the combined ladder is 1.16; the largest across all nine failed attempts is 1.7.
This cuts in both directions and should be read symmetrically: the improvements we report are not
statistically established, and neither, strictly, are several of the rejections. With ~230 monthly
observations and effect sizes of one or two percent a year, this project is underpowered to resolve
differences of the size it is measuring. That is a property of the question, not of the execution.

The honest framing is that we can rule out *large* effects and cannot resolve small ones.

### It is a levered version of a known factor

The combined book is β 1.39 on the academic HML_FX carry factor with an R² of 0.69 and an
insignificant alpha. **We did not find a new signal.** The contribution is construction and risk
management — real, and a different claim from discovery.

---

## 10.2 Data limitations, and exactly what each one blocks

### Option data is mids only — the most consequential gap

There is **no bid/ask on any volatility surface** in this repository. Three consequences:

1. **No premium-paying option hedge can be honestly costed.** Buying protection is the most natural
   response to a crash-prone strategy, and we cannot price it. Every option-based result here is
   therefore a *position-trimming proxy*, which is a different instrument with a different payoff.
2. **Chapter 8's volatility premium cannot be converted into a strategy.** It is reported as a
   breakeven statement — the cross-sectional book clears the carry bar only up to a 0.10 vol-point
   round-trip spread — rather than as a Sharpe.
3. **Any result quoting an option strategy's Sharpe as if the premium were free should be
   disbelieved**, including one produced inside this project before the limitation was flagged.

### No investable volatility benchmark

The carry book is validated against DBHVG10U and FXCTEM8 — external, investable series that confirm
it trades the premium it claims to. **There is no equivalent for the volatility premium**, so nothing
independently confirms that chapter 8's construction measures the premium rather than an artifact of
our own implementation. Given that the carry benchmarks are what caught the EM-versus-G10 finding,
this absence is more serious than it sounds.

### Realised volatility is close-to-close

A range-based estimator would be several times more efficient, and needs OHLC spot, which is unbought.
This makes chapter 8's premium estimates noisier than necessary.

### The option universe is 21 names, not 27

Six EM currencies (CLP, COP, IDR, MYR, PEN, PHP) have no option surfaces, so every option-based test
runs on a matched 21-name universe with its own anchor rather than on the tradable 27. Results are
not directly comparable to the ALL-27 baseline and are never quoted as if they were.

### The cross-currency basis is measurable on seven EM names only

Synthetic USD LIBOR was discontinued 2024-09-30, capping every basis result there. More damagingly,
the basis needs onshore fixings, which confines the universe to seven restricted EM currencies with
**no G10 at all** — so the G10 dollar-funding basis the literature actually studies is out of reach.
Chapter 9 reports D3 as a null *and* as a weak test, because on that universe the vanilla carry
anchor is itself negative.

### No macro releases

GDP, PMI, payrolls, inflation, MOVE, the TED spread and financial-conditions indices are not in the
repository. Monthly releases have vintage and revision problems at a daily evaluation frequency, and
handling them properly needs a vintage database. This was a deliberate substitution — the daily
market-based proxy set stands in — but it means the report can describe the book's exposures in
market terms and not in macroeconomic ones.

### No cross-pair quotes

Spot and forward bid/ask exist against USD only. A JPY/TRY cross is mechanically long TRY/USD plus
short JPY/USD, **which the book already holds** — the sort routinely pairs TRY on the long leg with
JPY on the short. The only genuine differences are the saved USD leg's spread and the cross's own
basis, and neither is priceable here. This is recorded as a data request rather than a backtest.

---

## 10.3 Modelling limitations

### This is not a live trading system

Costs are modelled from Bloomberg bid/ask. There is **no market impact, no funding curve, no
settlement calendar, no position limit and no capital charge.** For a book that runs up to 4× leverage
in EM currencies, market impact in a crisis is precisely the state where the model is most optimistic
— and it is also the state the whole report is about. Chapter 9's cost-stress result (the edge dies
between 2× and 3× spreads) is the closest available proxy and is not a substitute.

### Daily, USD-per-FX, single frequency

Monthly-frequency and FCU-per-USD constructions are out of scope by design. One teammate's replication
of a 1984-start academic paper **cannot** be reproduced on this base, and that is stated rather than
patched over: the shared data starts in 2007.

### The tail forecast may be unanswerable, not merely unanswered

Chapter 9 reports the tail-event classifier as a null. Its honest limit is that **7 of 13
cross-validation folds contain no tail month at all**, so out-of-sample AUC is undefined there — with
about 23 tail months in the entire sample, this question may simply not be answerable at monthly
frequency on nineteen years of data. The null is a null about *this test*, not a proof that tails are
unforecastable.

### Four components are re-priced, not rebuilt

Chapter 7's components were reconstructed from teammates' committed outputs rather than ported by
their authors. Each reconstruction's method is recorded, and one (the VIX gate) is exact. But **a
re-price is our reading of someone's signal, not their specification of it**, and replacing them with
real ports is the highest-value remaining work.

---

## 10.4 Process limitations, stated because they affected results

**Guardrails were added after defects, not before them.** Four of the thirteen guardrails in chapter 3
exist because something went wrong: short windows silently unreportable, leaking resample aliases,
roll costs on the wrong grid, and a trimming overlay's gain misattributed to selection. All four are
fixed and all four presented as *plausible numbers* rather than as errors. There is no reason to think
the list is complete.

**Documentation was wrong about its own artifacts five times** — a data pull described as necessary
that was not, two cited output files that had never been written, a cross-validation routine cited as
reused that did not exist, and a docstring asserting a data limitation that was false. The last of
these caused chapter 9's D1 test to run on an approximation for its entire first life. None changed a
published conclusion, but the pattern is worth more than any individual instance: **a claim that
something exists is a testable claim.**

**Teammate adoption of the shared base reached 1 of 5 before the deadline**, which is why chapter 7
rests on reconstructions. The engineering worked; the coordination did not, and routing around it was
the right call but is not the same as the ports existing.

---

## 10.5 What would most change the conclusions

In descending order of value per unit of cost:

1. **Option bid/ask.** Converts chapter 8 from a breakeven statement into a result or a documented
   null, and unblocks the premium-paying hedge that is the natural answer to a crash-prone book.
2. **An investable FX volatility index.** Without it, chapter 8 has no external validation of the kind
   that caught this project's most important finding.
3. **Teammates' own ports.** Replaces four reconstructions with specifications.
4. **G10 cross-currency basis swaps.** Would turn D3 from "null on a weak universe" into a real test
   of the literature's actual claim.
5. **OHLC spot.** A cheaper, more efficient realised-volatility estimator.
6. **Out-of-sample time.** The most valuable and least purchasable. The single most useful thing that
   could happen to this report is the next crisis, evaluated against these frozen windows with these
   pre-registered bars.
