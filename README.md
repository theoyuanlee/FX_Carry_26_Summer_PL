# FX Carry — UChicago Summer Project Lab × Bank of America

**Can a traditional FX carry strategy be improved by dynamically adjusting exposure using
macroeconomic conditions, volatility and momentum?**

Nineteen years of daily data, 27 currencies, real bid/ask costs, benchmarked against investable
carry indices. The short answer is **no, not in any way that survives costs and significance
testing** — and the detail of that failure, plus the one thing that did work, is the deliverable.

*Corporate Treasury / Global Funding. Data: daily Bloomberg, 2007-01 → 2026-06, G10 + EM vs USD.*

---

## The headline numbers

| Book | Gross Sharpe | Net Sharpe | MaxDD | CVaR₉₉ | Turnover |
|---|---|---|---|---|---|
| `run()` — ALL, 27 currencies | 0.6284 | **0.4659** | −29.3% | 0.0292 | 0.6755 |
| `run("G10")` — 9 currencies | 0.1669 | 0.1191 | −38.2% | — | — |
| `run("COMBINED")` — the integrated book | 0.6331 | **0.4891** | **−19.1%** | **0.0200** | 0.5902 |

Common window 2007-05-01 → 2026-06-30, 5,001 trading days, vol-targeted to 10% annualised, net of
real per-currency bid/ask half-spreads.

**Four findings**, each developed in the report:

1. **The 2007–2026 carry premium is an EM phenomenon.** A G10-only book earns a net Sharpe of 0.12,
   and the investable DB G10 carry index was *negative* over the sample.
2. **The risk is spot risk on the long leg.** Carry accrues +14.31%/yr on the long leg and spot gives
   back −10.43%/yr on the same leg. Carry on the long leg is positive in all twenty years, including
   all seven losing ones — *every losing year is a spot event, never a carry event.*
3. **Nine attempts to time or improve the premium all failed**, none with significant net alpha.
   Carry compensates a priced risk, so de-risking on risk indicators sells the premium roughly
   one-for-one.
4. **Tail management works; return enhancement does not.** The integrated book cuts maximum drawdown
   by a third and CVaR₉₉ by 31%, adds no significant return — and most of even that is holding less
   risk rather than choosing better.

---

## Reproduce the headline in one command

```bash
python strategy/tests/test_reconciliation.py     # expect 12/12 passed
```

That asserts the numbers above against the committed outputs on every run. Three more suites cover
the frozen evaluation windows, the overlay composition contract, and the integrated preset:

```bash
python strategy/tests/test_episodes.py           # 11/11
python strategy/tests/test_overlays.py           # 17/17
python strategy/tests/test_combined.py           #  8/8
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

## Where everything is

| Path | What it is |
|---|---|
| **[`strategy/`](strategy/)** | **The shared base.** One book, one set of conventions, one set of numbers. Start at [`strategy/README.md`](strategy/README.md) — it is the written contract, including the rules for AI agents working in this repo. |
| **[`report/`](report/)** | **The final report**, eleven chapters. Start at [`report/README.md`](report/README.md). Chapter 9 (what did not work) is deliberately one of the longest. |
| [`cesare/`](cesare/) | Research track and integration: the [project plan](cesare/FX_Carry_Strategy_Project_Plan.md) (**the repo's source of truth**), the stage notebooks, and the Phase-3/Phase-4 modules. All committed outputs live in `cesare/outputs/`. |
| [`data/raw/`](data/) | 13 git-tracked parquet groups, daily 2007→2026. **No Bloomberg terminal needed** to reproduce anything — a terminal is only required to *refresh*. |
| [`src/`](src/) | The Bloomberg pull (`bloomberg_data.py`) and the hand-pulled-supplement converter. |
| `arjun/` `dafu/` `theo/` `vidhi/` `oleg/` | Per-teammate workstreams. Each folder is its owner's source of truth for method. |
| [`papers/`](papers/) | The reference literature cited in the report. |

**The single source of truth for any claim** is
[`cesare/FX_Carry_Strategy_Project_Plan.md`](cesare/FX_Carry_Strategy_Project_Plan.md). Every number
in the report and the decks is reproducible from a CSV in `cesare/outputs/`.

---

## Setup

**Python 3.13.** Install from the root requirements file:

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
terminal. Nothing else in the repository requires one.

---

## How this project works

Six people, one strategy, and — until August 2026 — five different baselines. An audit found five
materially different baseline carry books across the repo, one of which never added the carry accrual
at all, which meant no two results were comparable. `strategy/` was built to fix that: it adds no
financial mathematics of its own, it fixes the order of operations, and it exposes every parameter
plus two extension hooks.

Four conventions are worth knowing before reading any number here:

- **Gross and net, always.** A result quoted without its cost drag is not a result.
- **Per window before whole-sample.** Every variant reports the frozen episode table next to its
  whole-sample statistics. Below ~120 trading days, annualised ratios are suppressed *by the code*.
- **Overlays move weights, not returns**, so a de-risking rule pays for the trades it triggers. An
  overlay applied to a return series is free, which flatters every risk-management rule ever tested.
- **Bars are pre-registered.** Where a verdict is quoted, the bar was written down before the run.
  Honouring one of them cost 0.043 of net Sharpe, and we took the cost.

**A null is a valid deliverable here**, and most of this project's results are nulls.

---

## Presentations

| File | What |
|---|---|
| [`cesare/deck_2026_08_05.html`](cesare/deck_2026_08_05.html) | Aug 5 progress deck — generated by `python cesare/build_deck.py`, self-contained, opens offline |
| [`strategy/overview.html`](strategy/overview.html) | Visual overview of the shared base |
| [`cesare/FX_Carry_Update_Presentation.html`](cesare/FX_Carry_Update_Presentation.html) | Jul 19 update |
