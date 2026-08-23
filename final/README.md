# FX Carry — the strategy, and the evidence behind it

**UChicago Summer Project Lab × Bank of America** · Corporate Treasury / Global Funding
Daily Bloomberg data, 2007-01 → 2026-06, G10 + EM vs USD.

This folder is the whole deliverable: the strategy, every input it reads, the evidence every number
traces to, the tests that prove the numbers, and the written report. It runs on its own. Nothing
here reads a file outside this folder, and there is a test that checks that by tracing every file
the code opens.

```bash
pip install -r final/requirements.txt
python final/reproduce.py
```

That takes a few minutes and prints the table below, checks every number against the published
value, prints the per-window results and the component verdicts, and **exits non-zero if anything
has moved**.

---

## The headline

| Book | Gross Sharpe | Net Sharpe | Ann. return | Ann. vol | MaxDD | CVaR₉₉ | Skew | Turnover |
|---|---|---|---|---|---|---|---|---|
| `run()` — baseline, 27 currencies | 0.6284 | **0.4659** | 5.21% | 11.19% | −29.32% | 0.0292 | −0.65 | 0.6755 |
| `run("G10")` — 9 currencies | 0.1669 | 0.1191 | 1.38% | 11.55% | −38.23% | 0.0316 | −0.95 | 0.3769 |
| **`run("COMBINED")` — the strategy** | **0.6331** | **0.4891** | 4.33% | 8.85% | **−19.07%** | **0.0200** | **−0.28** | 0.5902 |
| `run("COMBINED_TAIL")` — *not shipped* | 0.6808 | 0.5323 | 4.43% | 8.32% | −19.07% | 0.0189 | −0.26 | 0.6051 |

Common window 2007-05-01 → 2026-06-30, 5,001 trading days, vol-targeted to 10% annualised, net of
real per-currency bid/ask half-spreads.

**Read that table the right way round.** The strategy adds **0.023** of net Sharpe over the
baseline, which is not statistically significant and is not what it is for. What it buys is the
tail: **10.25 points of maximum drawdown, 31% of CVaR₉₉, and skew from −0.65 to −0.28.** That is
what the desk asked for — one large loss breaks the compounding path, so minimising large losses is
worth more than adding incremental gains.

The fourth row is not the strategy. It is the one contested verdict made runnable — see
[Where the honest reader should push back](#where-the-honest-reader-should-push-back).

### The delivered menu — one engine, three books

The same construction at three points on a single **risk-appetite ladder**, so the desk can pick a
mandate rather than accept a default. Each is a named preset; `CORE` and `DEFENSIVE` are aliases onto
the two books above, asserted bit-identical in the tests, so there is exactly one definition of the
strategy.

| Book | When | Return | Vol | Sharpe | Sortino | Calmar | MaxDD | CVaR₉₉ |
|---|---|---|---|---|---|---|---|---|
| `run("OFFENSIVE")` | calm macro, risk-on | **7.64%** | 16.59% | 0.4606 | 0.627 | 0.157 | **−41.24%** | 0.0430 |
| *`run()` — reference* | *not a mandate* | *5.21%* | *11.19%* | *0.4659* | *0.634* | *0.160* | *−29.32%* | *0.0292* |
| `run("CORE")` | default / all-weather | 4.33% | 8.85% | 0.4891 | 0.694 | 0.211 | −19.07% | 0.0200 |
| `run("DEFENSIVE")` | desk judges the regime stressed | 4.43% | 8.32% | **0.5323** | **0.760** | **0.219** | −19.07% | **0.0189** |

**Every risk-adjusted ratio improves monotonically down the ladder while return moves monotonically
the other way.** That is the trade-off, with no story on top of it.

Two things this menu is careful not to claim. `OFFENSIVE` is the baseline levered to a 15% vol
target — a **risk dial, not an edge**: its Sharpe is the baseline's within noise, by construction,
and the −41% drawdown is the price. And **no rule is provided for switching between the three**,
because every exposure-timing rule this project tested came back null; choosing a rung is a mandate
decision, not a signal we trade.

Built by [`menu.py`](menu.py) into [`evidence/strategy_menu.csv`](evidence/strategy_menu.csv), with
the pros and cons of each book as authored columns and the per-window table in
[`evidence/strategy_menu_by_window.csv`](evidence/strategy_menu_by_window.csv).

### At matched risk

The combined book runs at 8.85% volatility against the baseline's 11.19%, so comparing them on
return is comparing two risk levels. Levered onto the baseline's risk
([`evidence/strategy_menu_matched_risk.csv`](evidence/strategy_menu_matched_risk.csv)):

| At matched risk | Return | Vol | Sharpe | MaxDD | CVaR₉₉ | Skew |
|---|---|---|---|---|---|---|
| baseline | 5.21% | 11.19% | 0.4659 | −29.32% | 0.0292 | −0.65 |
| **CORE levered** | **5.33%** | 11.08% | **0.4813** | **−23.87%** | **0.0253** | **−0.30** |

Same risk, **more return, a 5.4pp shallower drawdown, 13% less CVaR₉₉ and less than half the negative
skew**. This retires the "better per unit of risk, worse per dollar deployed" reading — that was an
artifact of comparing at unmatched risk. The leverage is a mandate parameter chosen with the whole
sample in view: legitimate for a like-for-like comparison, and not offered as a trading rule.

---

## What the strategy is

**A vol-targeted, inverse-vol-weighted FX carry book across 27 currencies, plus a long-duration
hedge and a bad-skew exclusion overlay.**

Rank every currency by **forward-implied carry**, `ln(S/F)` — the rate differential the forward
market will actually transact at, which is the tradable version of the signal and includes the
NDF/convertibility basis that an interest-rate ranking misses. Go long the top bucket, short the
bottom, weight within each leg by inverse volatility with a 40% cap on any single name, and scale
the whole book to a 10% annualised volatility target on a 60-day trailing window. Rebalance monthly.
Then two additions that earned their place: a **long-TLT leg** sized by an expanding-window hedge
ratio, and an overlay that **excludes currencies whose option-implied skew sits in the top quintile
of the cross-section** — the ones the option market is charging most for crash protection.

**Why it should earn anything.** Uncovered interest parity says a high-yielding currency should
depreciate by exactly its rate advantage, leaving nothing. It does not. The pooled Fama regression
on this panel gives **b = 0.73** against UIP's prediction of 1 (Newey–West t = 4.5, n = 6,713
currency-months): high-carry currencies depreciate, but not enough. The gap is the premium.

**And why it is a premium rather than free money.** Both tracks load negatively on changes in FX
implied volatility and the EMBI spread with t-statistics of −4 to −6. Carry is compensated crash
risk: it pays steadily and then loses a great deal at once, in exactly the states where an investor
least wants it. That is not a flaw in the trade, it is the trade. It is also why nine attempts to
*time* the premium all failed — de-risking on risk indicators sells the premium roughly one-for-one
— and why the two components that survived manage the tail rather than predict the return.

The sharpest way to see the risk: on the long leg, carry accrues **+14.31%/yr** and spot gives back
**−10.43%/yr**. Carry on the long leg is positive in all twenty years, *including all seven losing
ones*. **Every losing year is a spot event, never a carry event.**

---

## How to run it

**Requirements:** Python 3.13 and the five packages in [`requirements.txt`](requirements.txt).

**One caveat that will cost you an afternoon if you skip it:** `pyarrow` must be the **pip** build
(≥ 24). Conda's 19.x cannot read this project's parquet files and fails in a way that looks like
data corruption rather than a version problem. If you use Anaconda:

```bash
/opt/anaconda3/bin/pip install -U pyarrow
```

**No Bloomberg terminal is needed.** [`data/raw/`](data/raw/) is committed. A terminal is only
required to *refresh* the data, which reproducing nothing here requires.

```python
import sys; sys.path.insert(0, "/path/to/final")
from strategy import run

base = run()                 # the baseline
strat = run("COMBINED")      # the strategy
print(strat.summary())       # gross and net, side by side, always

from strategy.episodes import STRESS, report_windows
print(report_windows(strat, STRESS))    # and per window, before you quote anything
```

Change one thing at a time; every knob is a field on `StrategyConfig`:

```python
run(vol_target=0.15)                     # a different risk level
run(universe=["AUD", "JPY", "MXN"])      # a different universe
run().reslice("2008-01-01", "2009-06-30")   # a sub-period, without rebuilding
```

### Reproducing the headline table

```bash
python final/reproduce.py
```

### The tests

```bash
python final/tests/test_reconciliation.py   # 12/12  the numbers reconcile to the committed CSVs
python final/tests/test_episodes.py         # 11/11  frozen windows, per-leg split, the short-window rule
python final/tests/test_overlays.py         # 17/17  composition, the gross-non-increasing contract
python final/tests/test_combined.py         # 12/12  the COMBINED preset, COMBINED_TAIL, and the menu
python final/tests/test_standalone.py       #   5/5  does this package still run with nothing else?
python final/tests/test_vendor_drift.py     #   4/4  has any vendored copy drifted from its source?
```

`test_standalone.py` is the one that matters for trusting this folder. It traces every file opened
during a full run and asserts each resolves inside `final/`, runs the strategy in a subprocess with
`final/` as the only path entry, and runs it again from a working directory outside the repository.
A green strategy suite proves the numbers are right; only that one proves the package is whole.

---

## Conventions you must know before trusting any number here

These are not style preferences. Each one changes what a number means.

**1 · No lookahead, enforced structurally.** Signals are sampled at the rebalance date and lagged one
trading day; every trailing window uses only past data. Overlays are lagged by the engine, so an
extension passes an *unlagged* signal and lets the base lag it — double-lagging silently weakens a
rule and looks like a bad result.

Two specific traps, both found by execution here rather than by reasoning: `rebal` accepts only
**right-labelled** pandas aliases (`D`, `W-FRI`, `2W`, `ME`, `QE`). Left-labelled ones (`MS`, `SMS`,
`QS`) **leak** — `.resample("MS").last()` stamps the January-31 value onto the January-1 label, so
the single `shift(1)` removes one day of what can be a thirty-day lookahead. And `.mask()` on a
weight panel turns a pre-inception `NaN` into a real `0.0`, which starts the book two months early
and quietly makes a variant non-comparable to the baseline it is measured against.

**2 · Gross and net, always — and net is the only result.** Costs are real per-currency Bloomberg
bid/ask half-spreads. New notional pays the outright half-spread; maintained notional rolls via FX
swap at the *points* spread rather than the outright, which is what keeps EM viable at all. The
baseline's drag is 1.81%/yr and the strategy's 1.27%/yr. Overlays modify **weights**, not returns,
so a de-risking rule pays for the trades it triggers. An overlay applied to a return series is free,
which flatters every risk-management rule ever tested — and was the single most common defect in the
five baselines this project started from.

**3 · Per window before whole-sample.** A rule that lifts the full-sample Sharpe while making the
crisis eras worse is a rule this book does not want, and only the per-window table shows that.
Windows are frozen in [`strategy/episodes.py`](strategy/episodes.py) and asserted by the tests: nine
`ERAS` that **partition** the sample (so their shares of P&L sum to 100% — that is the answer to "you
picked your windows") and eight `STRESS` windows that may overlap.

**Below ~120 trading days, annualised ratios are blank on purpose.** Annualising a Sharpe off 64 days
of COVID is noise wearing a decimal point. Short windows report cumulative return, MaxDD, worst day
and `n_days`, and the code refuses to do otherwise.

**4 · Every number traces to a committed CSV.** All of them are in [`evidence/`](evidence/), with one
documented exception: data provenance, which cites
[`data/raw/ticker_manifest.csv`](data/raw/ticker_manifest.csv). Nothing appears in prose without a
file behind it. That rule is what caught four defects in the engine itself.

**5 · Two metric conventions coexist and must never be compared across.** `daily_net` for the
tradable book; `monthly_uncosted` for D2, the volatility-risk-premium study. The convention is a
column in `evidence/final_comparison.csv`, not an assumption.

**6 · Re-priced, not rebuilt.** Four of the five teammate components were folded in from committed
outputs rather than ported by their authors — base adoption reached 1 of 5. Every one carries its
reconstruction method. A re-price is *our* reading of someone's signal, not their specification of
it, and the distinction is preserved per row rather than smoothed away.

---

## What is in this folder

| Path | What it is |
|---|---|
| [`README.md`](README.md) | This file |
| [`VERDICTS.md`](VERDICTS.md) | **Every extension from all six workstreams, kept or dropped** — the evaluation, itemised |
| [`reproduce.py`](reproduce.py) | One command: runs the books, asserts every published number, prints the tables |
| [`verdicts.py`](verdicts.py) | Builds `evidence/component_verdicts.csv` by reading the CSVs — no number is typed in |
| [`combined_engine.py`](combined_engine.py) | **The strategy definition.** `ADOPTED`, the components, and the ladder that decided them |
| [`requirements.txt`](requirements.txt) | Five packages, with the pyarrow caveat |
| [`strategy/`](strategy/) | The engine: config, the run pipeline, ~45 pure functions, frozen windows, overlay composition |
| [`inputs/`](inputs/) | The three teammate outputs the strategy reads, with [`PROVENANCE.md`](inputs/PROVENANCE.md) |
| [`data/raw/`](data/raw/) | 13 parquets + the ticker manifest, 35 MB, with [`PROVENANCE.md`](data/raw/PROVENANCE.md) |
| [`evidence/`](evidence/) | 60 committed CSVs — every number in the project — with an index and per-file descriptions |
| [`tests/`](tests/) | Six suites: four on the numbers, one on standalone-ness, one on vendor drift |
| [`report/`](report/) | The eleven-chapter written report |

**Start here:** this README → [`VERDICTS.md`](VERDICTS.md) → [`report/01_executive_summary.md`](report/01_executive_summary.md).
For a specific number, [`evidence/README.md`](evidence/README.md) says which file holds it and what
produced it.

### Where this package came from

It was assembled from a six-person research repository in which the strategy's definition lived in
one student's personal folder and its inputs in three others'. `run("COMBINED")` used to raise
`FileNotFoundError` the moment any of those folders went away. Everything it needs is now vendored
here, byte-for-byte, with provenance per file; the only edits to the copied code are six path
constants and one import, all declared in `tests/test_vendor_drift.py`, which fails on any
undeclared difference. The research folders remain in the repository for now and nothing about them
changed.

---

## What was evaluated, and what came of it

Six workstreams, sixteen components, one common book, bars written down before each run.
**Two adoptions.** Full detail, including the reconstruction method and the caveats, in
[`VERDICTS.md`](VERDICTS.md).

| Workstream | Verdicts |
|---|---|
| Arjun | Duration hedge (long TLT) → **ADOPTED** |
| Theo | Bad-skew exclusion → **ADOPTED** · option-conditioned carry (Aug 5) → **not evaluable**, input never committed |
| Dafu | VIX percentile gate → **REJECTED**, contested · option insurance → **blocked**, option data is mids-only |
| Vidhi | Macro/regime probability gate → **REJECTED**, the most destructive component tested |
| Oleg | **Never tested** — no committed output of any kind |
| Cesare | Tail-event forecast → **null** · D1 skew, D3 basis, D6 term structure → **null** · D2 vol risk premium → **positive, excluded** · Stages 3–6 → **rejected** |

**The rejections are the substance.** Nine attempts failed to beat the simple book and no result
anywhere in this project has a statistically significant net alpha — the largest |t| on any rung of
the integration ladder is 1.16. Every null was measured against a bar fixed in advance, on this
book, with the CSV still in the repo. That is what makes the two adoptions worth anything.

### Where the honest reader should push back

Four things, and they are here rather than in a footnote because a reader who finds them unaided
will rightly distrust everything else.

**The adopted overlay is mostly de-risking, not selection.** Of the bad-skew filter's 7.3 pp
drawdown improvement, **6.8 pp is simply holding less notional and 0.5 pp is the signal** — measured
against a control reproducing the overlay's exact daily gross spread across every name. The
selection alpha is +1.25%/yr at **t = 0.92**. What selection genuinely buys is skew, −0.63 → −0.31,
which de-risking does not deliver at all. Relatedly, **the strategy runs at 8.85% volatility, not the
10% target**, so part of its shallower drawdown is a lower risk level rather than a better book.

**One verdict is genuinely contested.** Dafu's VIX gate is accepted by the tail objective and
rejected by the slot rule. It is rejected here on the pre-registered rule, and that decision costs
**0.043 net Sharpe and 5.4% of relative CVaR₉₉**. The alternative book is built, tested and runnable
as `run("COMBINED_TAIL")` so the cost can be priced rather than asserted. The reasoning, and the
counter-argument at full strength, are in [`VERDICTS.md`](VERDICTS.md).

**One workstream was never tested and one result was never evaluable.** Oleg committed no output, so
nothing of his was measured. Theo's August notebook is committed unexecuted with its input missing,
so it could not be folded in. Both are rows in the verdict table with the blocker named, because a
gap stated in the artifact is a gap and a gap omitted is a claim.

**The best number in the project is not in the strategy.** D2, the FX volatility risk premium,
scores Sharpe 1.69 — and it is monthly, on a 21-name option universe, and gross of option bid/ask.
On its own breakeven grid it dies inside G10 interbank spreads, on the very names that are its
standing shorts. It is written up in full and deliberately kept away from the costed daily books.

---

## Honest limits

- **Not a live trading system.** Costs are modelled from Bloomberg bid/ask; there is no market
  impact, no funding curve, no settlement calendar, no borrow. Real execution would be worse.
- **Option data is mids only.** No bid/ask on any volatility surface, so a premium-paying hedge
  cannot be honestly costed anywhere in this project. Every option-based result is either a
  position-trimming proxy or explicitly uncosted.
- **Daily, USD-per-FX, 252-day annualisation**, forward-implied carry. Monthly and FCU-per-USD
  constructions are out of scope by design.
- **Base adoption reached 1 of 5.** Four of five teammate components are re-priced from committed
  outputs rather than ported by their authors.
- **In-sample in the sense that matters.** Nineteen years is one macro regime cycle, not many. Every
  component was chosen on this sample, and nothing here has been tested on data nobody looked at.
- **Known data gaps:** no option surfaces for CLP/COP/IDR/MYR/PEN/PHP; no CNY forwards (CNH is the
  tradable RMB leg); NIBOR12M, STIB12M and CLSWA missing.
