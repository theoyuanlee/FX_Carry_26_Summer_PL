# FX Carry — UChicago Summer Project Lab × Bank of America

**Can a traditional FX carry strategy be improved by dynamically adjusting exposure using
macroeconomic conditions, volatility and momentum?**

Nineteen years of daily data, 27 currencies, real bid/ask costs, benchmarked against investable
carry indices. The short answer is **no, not in any way that survives costs and significance
testing** — and the detail of that failure, plus the two things that did work, is the deliverable.

*Corporate Treasury / Global Funding. Data: daily Bloomberg, 2007-01 → 2026-06, G10 + EM vs USD.*

---

## Start here → [`final/`](final/)

**[`final/`](final/) is the hand-off package and the thing to read first.** It is self-contained: the
strategy, every input it reads, the evidence every number traces to, the tests that prove the
numbers, and the eleven-chapter report. Nothing in it reads a file outside it, and a test enforces
that by tracing every file the code opens.

```bash
pip install -r final/requirements.txt
python final/reproduce.py
```

That takes a few minutes, runs the books, **checks every published number against its committed
value, and exits non-zero if anything has moved.**

| If you have | Read |
|---|---|
| **5 minutes** | [`final/README.md`](final/README.md) → [`final/VERDICTS.md`](final/VERDICTS.md) — what shipped, and what was dropped |
| **1 hour** | [`final/report/`](final/report/), eleven chapters. Ch. 1 is the executive summary; **ch. 9, what did not work, is deliberately one of the longest** |
| **A day, and scepticism** | The six research folders below, and the "where the honest reader should push back" section of [`final/README.md`](final/README.md) |

---

## The delivered strategy — one engine, three books

The same construction at three points on a single **risk-appetite ladder**, so the desk picks a
mandate rather than accepting a default.

| Book | When | Return | Vol | Sharpe | Sortino | Calmar | MaxDD | CVaR₉₉ |
|---|---|---|---|---|---|---|---|---|
| `run("OFFENSIVE")` | calm macro, risk-on | **7.64%** | 16.59% | 0.4606 | 0.627 | 0.157 | **−41.24%** | 0.0430 |
| *`run()` — reference* | *not a mandate* | *5.21%* | *11.19%* | *0.4659* | *0.634* | *0.160* | *−29.32%* | *0.0292* |
| `run("CORE")` | default / all-weather | 4.33% | 8.85% | 0.4891 | 0.694 | 0.211 | −19.07% | 0.0200 |
| `run("DEFENSIVE")` | desk judges the regime stressed | 4.43% | 8.32% | **0.5323** | **0.760** | **0.219** | −19.07% | **0.0189** |

**Every risk-adjusted ratio improves monotonically down the ladder while return moves monotonically
the other way.** That is the trade-off, with no story on top of it. Common window
2007-05-01 → 2026-06-30, 5,001 trading days, net of real per-currency bid/ask half-spreads.

Two things this menu is careful not to claim. `OFFENSIVE` is the baseline levered to a 15% vol
target — a **risk dial, not an edge**. And **no rule is provided for switching between the three**,
because every exposure-timing rule this project tested came back null.

**Four findings**, each developed in the report:

1. **The 2007–2026 carry premium is an EM phenomenon.** A G10-only book earns a net Sharpe of 0.12,
   and the investable DB G10 carry index was *negative* over the sample.
2. **The risk is spot risk on the long leg.** Carry accrues +14.31%/yr on the long leg and spot gives
   back −10.43%/yr on the same leg. Carry on the long leg is positive in all twenty years, including
   all seven losing ones — *every losing year is a spot event, never a carry event.*
3. **Nine attempts to time or improve the premium all failed**, none with significant net alpha.
   Carry compensates a priced risk, so de-risking on risk indicators sells the premium roughly
   one-for-one.
4. **Tail management works; return enhancement does not.** The shipped book cuts maximum drawdown
   by a third and CVaR₉₉ by 31%, adds no significant return — and most of even that is holding less
   risk rather than choosing better.

**A null is a valid deliverable here**, and most of this project's results are nulls. Eighteen
components were evaluated across six workstreams against bars written down before each run;
**two were adopted.** The itemised table is [`final/VERDICTS.md`](final/VERDICTS.md).

---

## Where everything is

### The deliverable

| Path | What it is |
|---|---|
| **[`final/`](final/)** | **The hand-off package.** Self-contained: strategy, inputs, evidence, tests, report. Start at [`final/README.md`](final/README.md) |
| [`final/VERDICTS.md`](final/VERDICTS.md) | Every component from all six workstreams, kept or dropped — the evaluation, itemised |
| [`final/report/`](final/report/) | The eleven-chapter written report |
| [`final/evidence/`](final/evidence/) | 63 committed CSVs — every number in the project — with an index and per-file descriptions |

### Shared infrastructure

| Path | What it is |
|---|---|
| [`strategy/`](strategy/) | **The shared base** every workstream builds on. One book, one set of conventions, one set of numbers. [`strategy/README.md`](strategy/README.md) is the written contract |
| [`data/`](data/) | 13 git-tracked Bloomberg groups, daily 2007→2026. **No terminal needed** to reproduce anything — only to refresh. See [`data/README.md`](data/README.md) |
| [`src/`](src/) | The Bloomberg pull and the hand-pulled-supplement converter. The only thing here that needs a terminal |

### The six research workstreams

Each folder is its owner's source of truth for method, and each README opens with how that work
landed in the final evaluation.

| Folder | Workstream | How it landed |
|---|---|---|
| [`arjun/`](arjun/) | Robustness, attribution, hedging | **Duration hedge → ADOPTED** · EM deleveraging → not evaluable as quoted |
| [`theo/`](theo/) | FX options, skew and vol filters | **Bad-skew exclusion → ADOPTED** · two later components not evaluable as committed |
| [`dafu/`](dafu/) | Regime switching, the `fxcarry` library | VIX gate → **REJECTED, contested** · option insurance → blocked on data |
| [`vidhi/`](vidhi/) | Macro/regime-aware adaptive carry | Regime probability gate → **REJECTED** |
| [`cesare/`](cesare/) | Research stages 0–6, Phase-3 signals, Phase-4 integration | Nine components, all **rejected or null**; D2 positive but excluded |
| [`oleg/`](oleg/) | Exploration | **NEVER TESTED** — no committed output |

### Supporting material

| Path | What it is |
|---|---|
| [`cesare/FX_Carry_Strategy_Project_Plan.md`](cesare/FX_Carry_Strategy_Project_Plan.md) | The project's working record — methodology, every stage verdict, the guardrails, and a 44-entry defect ledger |
| [`cesare/presentations/`](cesare/presentations/) | The five HTML decks. See [its README](cesare/presentations/README.md) for which are generated and which numbers are dated |
| [`proposal/`](proposal/) | The original Project Lab mandate |
| [`papers/`](papers/) | The reference literature held locally |
| [`docs/`](docs/) | A superseded July design document, kept as a record |
| [`notebooks/`](notebooks/) | Legacy first-week scratch, kept deliberately |

---

## Why some things appear twice

`final/` **vendors** what it needs — the engine, the evidence CSVs, the report, the three teammate
inputs, and the thirteen wide parquets. So [`strategy/`](strategy/) and [`final/strategy/`](final/strategy/)
are near-identical copies, and so are [`cesare/outputs/`](cesare/outputs/) and
[`final/evidence/`](final/evidence/).

**This is deliberate and it is guarded.** Before it was assembled, `run("COMBINED")` raised
`FileNotFoundError` the moment any personal folder went away — the strategy's definition lived in one
student's folder and its inputs in three others'. `final/tests/test_vendor_drift.py` hashes every
copy against its source, declares the six intentional path patches, and **fails on any undeclared
difference**; `final/tests/test_standalone.py` proves the package runs with nothing else present.

The research folders remain because the working record is part of the hand-off. Where the two differ,
**`final/` is authoritative.**

---

## Setup

**Python 3.13.** For the deliverable alone, `final/requirements.txt` (five packages) is enough. For
the whole repository including the research notebooks:

```bash
pip install -r requirements.txt
```

> **⚠ pyarrow must be the pip build (≥ 24).** Conda's pyarrow 19.x **cannot read this repository's
> parquet files** and fails in a way that looks like data corruption rather than a version problem.
> After any broad conda update, re-fix with:
> ```bash
> /opt/anaconda3/bin/pip install -U pyarrow
> ```

Refreshing the data from Bloomberg additionally needs `pip install -r requirements-bbg.txt` and a
terminal. **Nothing else in the repository requires one.**

## Verifying it yourself

The hand-off package, six suites:

```bash
python final/tests/test_reconciliation.py   # 12/12  the numbers reconcile to the committed CSVs
python final/tests/test_episodes.py         # 11/11  frozen windows, per-leg split, short-window rule
python final/tests/test_overlays.py         # 17/17  composition, the gross-non-increasing contract
python final/tests/test_combined.py         # 12/12  the COMBINED preset, COMBINED_TAIL, and the menu
python final/tests/test_standalone.py       #   5/5  does this package still run with nothing else?
python final/tests/test_vendor_drift.py     #   4/4  has any vendored copy drifted from its source?
```

The shared base, four suites:

```bash
python strategy/tests/test_reconciliation.py   # 12/12
python strategy/tests/test_episodes.py         # 11/11
python strategy/tests/test_overlays.py         # 17/17
python strategy/tests/test_combined.py         # 11/11
```

Then, from the repository root:

```python
from strategy import run
from strategy.episodes import STRESS, report_windows

base = run()                      # the team baseline
print(base.summary())             # gross AND net, with an IR vs the matching index
print(report_windows(base, STRESS, which="net"))   # per stress window — read this first
```

---

## Four conventions to know before reading any number here

- **Gross and net, always.** A result quoted without its cost drag is not a result.
- **Per window before whole-sample.** Every variant reports the frozen episode table next to its
  whole-sample statistics. Below ~120 trading days, annualised ratios are suppressed *by the code* —
  annualising a Sharpe off 64 days of COVID is noise wearing a decimal point.
- **Overlays move weights, not returns**, so a de-risking rule pays for the trades it triggers. An
  overlay applied to a return series is free, which flatters every risk-management rule ever tested.
- **Bars are pre-registered.** Where a verdict is quoted, the bar was written down before the run.
  Honouring one of them cost 0.043 of net Sharpe, and we took the cost.

The full set, and the traps that motivated each, is in
[`final/README.md`](final/README.md#conventions-you-must-know-before-trusting-any-number-here).

## Data and confidentiality

The parquet files in [`data/raw/`](data/raw/) and [`final/data/raw/`](final/data/raw/) are derived
from Bloomberg and are committed so that this academic deliverable reproduces without a terminal or
an entitlement. They are provided for review of this project's results and remain subject to
Bloomberg's licensing terms; they are not redistributable as a data product.
