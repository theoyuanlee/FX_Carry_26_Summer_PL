# BUSN 41902 + Hayashi, bound to `fxcarry`

Weeks 2-4 of the [month plan](month_plan.md).

The authored plans in `D:\GitHub\summer-26\learning\busn41902\` (`STUDY-GUIDE.md` and
`HAYASHI-GUIDE.md`) are the source of truth and are not modified. This document combines
them into one running order and binds that order to code in this repo.

## Reading order: textbook first, lecture note second

Hayashi is the course's parent text, and lectures 1-7 follow its chapters in order. The
lecture notes are dense and compressed, good for revision and bad for first contact. So each
topic runs:

1. Hayashi sprint: read the sections, attempt the flagged exercises blank-page, grade
   against Hayashi's own answers. This is the why.
2. busn41902 sprint: lecture note, MATLAB reference, port the helper into `src/busn41902`,
   do the problem-set questions. This is the how.
3. The `fxcarry` audit: thirty minutes, on the six topics that have one.

ESL is deferred. It's machine-learning oriented and belongs with advanced methods later
rather than with this month's econometrics review. Two consequences, both real. The bootstrap
(busn sprint 12) and PCA/factors (sprint 14) have no Hayashi twin, as Hayashi's guide says
explicitly, so those two run lecture-note-only. And `stats.Shrinkage` loses the anchor ESL E1
would have given it, so it stays unowned this month unless you choose otherwise.

## The combined blocks

| # | Topic | Hayashi | busn41902 | Binds to |
|---|---|---|---|---|
| A | OLS foundations | H1 (1.1-1.3), H3 (2.1-2.3 sandwich) | 1, 2 (PS1) | foundational, nothing directly |
| B | White SE and HAC | H4 (2.4-2.6, 2.9), H6 (6.1-6.4), H7 (6.5-6.7) | 3 | `stats.HAC.mean_se:47`, `stats.py:57`, `constants.DEFAULT_NW_LAGS`, `nw_t` in `crash_hedged/analysis.py:47` and `strategy.py:47` |
| C | Testing, ML, GLS | H2 (1.4-1.6) | 4, 5 (PS2), 6 | nothing |
| D | Serial correlation | H5 (2.10-2.12) | 7, 8 (PS3) | Overlapping monthly returns are serially correlated by construction |
| E | IV | H8 (3.1-3.3) | 9 | nothing |
| F | GMM | H9 (3.4-3.6, 3.8) | 10, 11 (Midterm Q3) | `stats.LinearSDF.fit:99`, Hansen's J at `:180` |
| G | Bootstrap | none, lecture note only | 12 | Carry Sharpe significance is currently asymptotic-only |
| H | PCA and factors | none, lecture note only | 14 | `stats.FactorModel.fit:40`, the DOL/HML_FX/VOL work in nb 02 |
| I | MLE, probit, trinity | H10 (7, 8.1) | 13 | nothing |
| J | Midterm and repair | none | 15, 16 | nothing |

Block B is the one to take seriously. H7 gives you the long-run variance as $\gamma_0$ plus
twice the sum of autocovariances, why the truncated kernel can fail to be positive
semidefinite while Bartlett cannot, and the bandwidth off-by-one: $q(n)=3$ weights
autocovariances at lags 0, 1, 2 by 1, 2/3, 1/3. `constants.DEFAULT_NW_LAGS = 6` sits under
every significance claim in your deck, and after H7 you can finally say whether 6 is
defensible or a number someone typed.

## The arithmetic

Ten Hayashi sprints plus sixteen busn41902 sprints is 52 hours. Weeks 2-4 are 21 days, so
that is 2.5 hrs/day for this track alone, on top of 3-4 hrs of library work and an hour of
C++. A 7-hour day with no slack, every day, for three weeks.

It does not all fit. Choose deliberately rather than discovering it in week 4.

### Recommended core, 32 hours

Blocks A, B, F, D, G, H, in that order. Foundational first, then the four topics with a code
payoff:

| Order | Block | Hours | Why this one |
|---|---|---|---|
| 1 | A: OLS foundations | 8 | Everything rests on the sandwich; skipping it makes the rest recitation |
| 2 | B: White and HAC | 8 | Every t-statistic you have published |
| 3 | F: GMM | 6 | `LinearSDF.fit` and the J-test |
| 4 | D: Serial correlation | 6 | The defect your monthly returns have by construction |
| 5 | G: Bootstrap | 2 | The tool you don't yet use and should |
| 6 | H: PCA and factors | 2 | `FactorModel.fit` |

Roughly 10.7 hrs/week, which fits.

### What slips, and the cost

Blocks C (PS2), E (IV), I (MLE/probit), J (midterm Q1-Q2 and the closed-book redo), plus PS3
Q1 in sprint 6.

This cuts against your own rule that "the homework and midterm are the main practice": the
core keeps PS1, most of PS3 and Midterm Q3, but drops PS2 and Midterm Q1-Q2. If the
exercises matter more to you than the code bindings, invert the priority: run blocks A, C, D
in the authored order and let the GMM and factor audits wait until after the project ends.
That is a legitimate choice. It just needs to be a choice.

## Week allocation

| Week | Blocks | fxcarry audit landing |
|---|---|---|
| 2 | A (H1, H3 → busn 1, 2), start B (H4, H6) | none |
| 3 | finish B (H7 → busn 3), F (H9 → busn 10, 11) | `stats.py`, `nw_t`, `DEFAULT_NW_LAGS`; then `LinearSDF.fit` |
| 4 | D (H5 → busn 7, 8), G (busn 12), H (busn 14) | Overlapping-return correction; Sharpe significance; `FactorModel.fit` |

## How to run a bound block

Keep both sprints exactly as their guides specify. Then add one step, thirty minutes:

> Open the `fxcarry` function in the binding column. Does it do what you just derived? Check
> the lag choice, the degrees-of-freedom correction, the small-sample behaviour, and whether
> the test fixture resembles real data. Write one sentence: what would break, and when.

That is the whole binding: no new plan, no reordering, one extra step on six topics.

## Why bind at all

Your working rule is that generated code you haven't read isn't yours, and no generated
number gets presented until it's been re-derived. `stats.py` (530 lines) is exactly that:
`HAC` standard errors, `LinearSDF`'s iterated GMM and Hansen's J statistic, `FactorModel`'s
time-series betas. The rebuild folded the old `metrics.py` and `asset_pricing.py` into that
one module, so what was two files to own is now one. Every t-statistic in the crash-hedged
carry deck came out of it.

BUSN 41902 is the course that teaches you to check them, and Hayashi is the book that tells
you why the check is the right one.

## Related

- [Month plan](month_plan.md), the master schedule
- [C++ and QuantLib track](cpp_quantlib_track.md), QuantNet Levels 1-5, ending in reading the
  QuantLib FX source
