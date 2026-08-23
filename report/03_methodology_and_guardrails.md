# 3. Methodology and guardrails

*Chapter 3 of the final report. Draft, 2026-08-04.*

---

## 3.0 The argument of this chapter

A backtest is a claim about a counterfactual, and the ways it can be wrong are well known and easy to
commit accidentally. This project's response was to write the rules down *before* they were needed,
put as many of them as possible into code so they are enforced rather than remembered, and record
every one that was violated.

That last part is the point of this chapter. **Four of the guardrails below exist because something
went wrong**, and they are more informative than the ones adopted on principle.

---

## 3.1 The guardrails

**1. No lookahead.** Signals are sampled at the rebalance date and lagged one trading day. Every
trailing window uses only past data. Any new conditioning variable — VIX, implied volatility,
regimes, a machine-learning forecast — is sampled the same way. Overlays pass their signal
*unlagged*; the base applies the lag, so double-lagging cannot happen silently.

**2. Newey–West inference everywhere**, 5 lags daily and 3 monthly. Daily overlapping returns have
serial correlation, and an OLS t-statistic on them overstates significance.

**3. Gross and net, always.** Every variant reports both. A result quoted without its cost drag is
not a result.

**4. Benchmarks.** Every table reports an information ratio against the investable index matching the
universe — DBHVG10U for G10, FXCTEM8 otherwise.

**5. Fixed universe.** The peg and CNY exclusions and the 40% leg cap are fixed unless a chapter
explicitly studies them.

**6. One sizing standard.** 10% annualised volatility target, 60-day window, 4× leverage cap, scaled
by the unit book's own trailing realised volatility.

**7. One evaluation window.** 2007-05 → 2026-06 for every comparison.

**8. Per-window reporting is mandatory.** Every variant reports the frozen episode table next to its
whole-sample statistics. A whole-sample-only result is incomplete, not a result. Below ~120 trading
days, report cumulative return, drawdown, worst day and the observation count — **never an annualised
Sharpe**. `episodes.report_windows` forces the annualised columns to NaN under that threshold, so the
rule is enforced by code rather than by memory.

**9. Incremental honesty.** Components are tested **one change at a time** against the immediately
preceding book — not against a number from another notebook, window or universe — gross and net, with
the adopt/reject rule written down *before* the run. Build order is fixed in advance and every ladder
is reported both add-one-in and leave-one-out, so the outcome is an assembly rather than a search.

**10. Rebalance-grid safety.** Only **right-labelled** pandas resample aliases are permitted: `D`,
`W-*`, `2W`, `ME`, `QE`. Left-labelled aliases leak — `.resample("MS").last()` stamps the *January
31st* value onto the label *January 1st*, so the single one-day lag removes one day of what can be a
thirty-day lookahead. This matters directly for the desk's "test different rebalancing dates" request:
**the naive way to do it is the wrong way.**

**11. Cost-model validity.** The roll leg is billed on the forward-tenor grid, not the rebalance
grid. See chapter 2 §2.3.

**12. A trimming overlay must be reported against a gross-matched de-risking control.** An overlay
that zeroes or trims positions does two things at once — it drops particular names (selection) and it
leaves the book holding less notional (de-risking) — and a shallower drawdown follows mechanically
from the second whatever the first is worth. Chapter 7 shows this changing the reading of the
project's strongest Phase-4 number.

**13. A component's slot verdict must be re-measured on the stack actually proposed.** A
leave-one-out run on a stack containing a component that is later rejected measures every survivor
against a book nobody will build.

---

## 3.2 The four that exist because something went wrong

Guardrails 8, 10, 11 and 12 were not adopted on principle. Each was written after a defect was found
by execution, and each defect had the same shape: **the output looked entirely reasonable.**

| # | What went wrong | How it presented | How it was caught |
|---|---|---|---|
| 8 | `summary()` returned an empty frame for any window under 120 trading days | Four of eight stress windows silently unreportable — including both the desk named and the sample's second-worst window | Asking for a short window for the first time |
| 10 | Left-labelled resample aliases stamp a month-end value on a month-start label | A 30-day lookahead that the one-day lag reduces to 29 | Testing the alias directly on a monotone series |
| 11 | Roll costs billed on the rebalance grid, correct only at the baseline | Drag *rising* to 4.84%/yr while turnover *fell* — backwards | Noticing the sign of the relationship, not the size |
| 12 | A trimming overlay's drawdown gain attributed to selection | 7.3pp improvement, of which 6.8pp was holding less risk | Building the control before believing the number |

**None of these produced an obviously wrong answer.** That is the argument for guardrails that are
executed rather than remembered: the failure mode of a quantitative project is not a crash, it is a
plausible number.

A fifth pattern is not a guardrail but recurs often enough to name. **A claim that an artifact or
dataset exists is a testable claim**, and in this project it was wrong five times: a data pull
described as necessary that was not (chapter 2 §2.4), two output files cited in documentation that
had never been written, a cross-validation routine cited as "reused verbatim" that existed nowhere,
and a docstring asserting a data limitation that did not exist — which is why chapter 9's D1 test
originally ran on an approximation. The rule earned by that: **check before relying on your own
documentation.**

---

## 3.3 The shared base

An audit on 28 July found **five different baseline carry strategies in five folders**, differing in
frequency, quoting convention, universe, cost model, data source — and in one case in whether the
strategy collected the carry accrual at all. Extensions measured against different baselines are not
comparable to each other, which meant the team's central deliverable was not constructible.

The response was `strategy/` — a thin, config-driven package over the validated engine. It adds **no
financial mathematics of its own**; it fixes the order of operations and exposes every parameter plus
two extension hooks.

**The design decision that matters: overlays modify weights, not returns, and are applied before the
cost model.** An overlay applied to a return series is free, which flatters every risk-management rule
ever tested — and that was precisely the defect in one of the surveyed baselines. Because these move
weights, a de-risking rule pays the transaction costs of the trades it triggers and its turnover is
reported.

**Acceptance is asserted on every run.** `run()` reproduces the committed headline exactly: ALL gross
**0.6284** / net **0.4659**, G10 **0.1669** / **0.1191**, turnover 0.675470, cost drag 1.8146611%/yr.
Internal identities hold to `0.0e+00`: per-currency contributions sum to gross, spot plus carry
components equal excess returns, and net equals gross minus cost. Both hooks are exact no-ops at
neutral settings, so an extension measures only its own effect.

**51 tests** across four suites guard this, and they are run before and after any change:

```
python strategy/tests/test_reconciliation.py    # 12/12 — reconciliation, identities, hook no-ops
python strategy/tests/test_episodes.py          # 11/11 — frozen windows, leg split, the two v1.1.0 fixes
python strategy/tests/test_overlays.py          # 17/17 — composition, gross-non-increasing, ExternalLeg
python strategy/tests/test_combined.py          #  11/11 — the COMBINED preset and the menu
```

---

## 3.4 Frozen evaluation windows

Two sets, both frozen, with a test asserting the exact keys and dates:

- **`ERAS`** — a contiguous partition of the sample, so per-era shares of P&L sum to 100%. That is
  what makes "this era produced X% of the return" honest rather than selective, and it is the answer
  to "you chose your windows".
- **`STRESS`** — tight, tail-focused event windows, allowed to overlap and to nest inside eras,
  answering the different question of whether the book preserved capital.

**The freeze is the point.** Adding a window later is allowed; silently changing one is not, because
every cross-workstream comparison depends on everybody using the same windows. The lock is what stops
anyone re-picking a window after seeing a result. The windows were chosen from the FX historical
record rather than from this book's own drawdowns, and the set deliberately includes `rates_2022` —
carry's *best* crisis — so it cannot be read as a list of disasters selected to motivate a hedge.

---

## 3.5 Pre-registration, and what it cost

Where a verdict is quoted in this report, the bar it was measured against was written down before the
run. Three instances where that had teeth:

**The tail-forecast bars** (chapter 9) were fixed in advance, including the requirement to beat a
"dumb incumbent" — a single VIX percentile threshold. The model lost, and **it was not iterated**: one
regularisation strength, one pre-registered mapping, and the alternative mapping reported beside it as
the spread rather than as a second attempt.

**The slot criterion** for the combined engine (chapter 7) was fixed before any component was tested,
including what to do when the two ladders disagree. They did disagree, about the VIX gate, and
honouring the rule **cost 0.043 of net Sharpe**. Taking that cost rather than re-reading the rule
after seeing the answer is the entire purpose of writing it first.

**The tail re-verdict rule** (chapter 6) was fixed before the numbers were computed, and it was
applied mechanically — including to a row where the mechanical answer was awkward. That row is kept
and labelled rather than dropped.

**Pre-registration is only meaningful when it costs something.** In this project it cost 0.043 of
Sharpe and one uncomfortable table, and both are reported.

---

## 3.6 What this chapter establishes

The methodology is not novel and is not meant to be. What it is, is *enforced*: 51 tests, frozen
windows, guardrails in code rather than in memory, and a written record of the four occasions on
which a plausible-looking number turned out to be wrong. Every result in chapters 4 through 9 was
produced under these constraints, and the ones that are nulls are nulls under them too.
