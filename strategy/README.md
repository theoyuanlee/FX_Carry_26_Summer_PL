# `strategy/` — the team's base FX carry strategy

**One book. One set of conventions. One set of numbers.** Every extension in this project —
a macro/regime gate, an FX-option hedge, a robustness audit, a crisis study, an ML overlay —
plugs into the strategy defined here. That is the whole point: if your gate is measured on your
baseline and mine on mine, neither of us learns whether the gate works. Build on this and the
comparison is apples to apples.

```python
import sys; sys.path.insert(0, "/path/to/FX_Carry_26_Summer_PL")
from strategy import run

base = run()                      # the team baseline
mine = run(exposure=my_signal)    # my extension, same book underneath
print(base.summary(), mine.summary(), sep="\n")
```

The baseline is the project's validated construction (see
[`cesare/FX_Carry_Strategy_Project_Plan.md`](../cesare/FX_Carry_Strategy_Project_Plan.md)):
**net Sharpe 0.4659**, gross 0.628, 27 currencies, 2007-05 → 2026-06, net of real bid/ask costs
and benchmarked against investable carry indices. `strategy/tests/test_reconciliation.py` asserts
those numbers on every run, so drift gets caught immediately.

---

## Contents

| File | What it is |
|---|---|
| [`config.py`](config.py) | `StrategyConfig` — every knob, with the baseline as defaults. Presets `ALL_BASELINE` / `G10_BASELINE` / `EM_BASELINE`, plus `COMBINED` (see [The `COMBINED` preset](#the-combined-preset)). |
| [`core.py`](core.py) | `run(config) -> StrategyResult`. Orchestration only — no financial maths of its own. |
| [`fx_utils.py`](fx_utils.py) | The engine: ~45 pure functions (data → panels → sorts → costs → stats → regressions). This is where the maths lives. |
| [`episodes.py`](episodes.py) | The frozen evaluation windows (`ERAS`, `STRESS`) and the per-window reports built on them. See rule 11. |
| [`overlays.py`](overlays.py) | Stacking several extensions in one book: `compose_exposure`, `compose_overlays`, and `ExternalLeg` for non-FX instruments. |
| [`examples/`](examples/) | Five runnable scripts, one per extension pattern. Start with `01_baseline.py`. |
| [`tests/test_reconciliation.py`](tests/test_reconciliation.py) | 12 acceptance tests: reconciliation to committed outputs, internal identities, and no-op guards on the hooks. |
| [`tests/test_episodes.py`](tests/test_episodes.py) | 11 tests on the frozen windows, the per-leg decomposition, and the two v1.1.0 base fixes. |
| [`tests/test_overlays.py`](tests/test_overlays.py) | 17 tests on composition, the gross-non-increasing contract, and `ExternalLeg` P&L / costs / lag. |
| [`tests/test_combined.py`](tests/test_combined.py) | 8 tests freezing the `COMBINED` preset: it reproduces the ladder's final row, runs the baseline's window, and stays a superset of the base. |

That is the whole package: five modules, five examples, four test suites. There is nothing else in
here — the visual overview of this base now lives with the project's other decks at
[`../cesare/presentations/overview.html`](../cesare/presentations/overview.html).

## Setup

- **Python 3.13**, `numpy pandas scipy statsmodels pyarrow matplotlib`.
- **pyarrow must be the pip build (≥ 24)** — conda's 19.x cannot read this repo's parquet files.
  Fix with `/opt/anaconda3/bin/pip install -U pyarrow` after any broad conda update.
- **Data:** reads the shared, git-tracked `data/raw/*.parquet` at the repo root. No Bloomberg
  terminal needed — a terminal is only required to *refresh* the data via `src/`.
- **Import:** put the repo root on `sys.path` (see the snippet above). Notebooks in a personal
  folder use `sys.path.insert(0, "..")`.

Verify your environment in one command:

```bash
python strategy/tests/test_reconciliation.py     # expect "12/12 passed"
python strategy/tests/test_episodes.py           # expect "11/11 passed"
python strategy/tests/test_overlays.py           # expect "17/17 passed"
python strategy/tests/test_combined.py           # expect "11/11 passed"
```

---

## What the base gives you for free

These are the guardrails (plan §6) that make results comparable. You do not have to implement
any of them, and you should not work around them:

1. **No lookahead.** Signals are sampled at the rebalance date and lagged one trading day; every
   trailing window uses only past data. Your overlay is lagged the same way — pass an *unlagged*
   signal and let the base lag it.
2. **Gross AND net.** Real per-currency bid/ask half-spreads, with maintained notional rolled via
   FX swap at the points spread rather than the outright. `summary()` always reports both.
3. **A common evaluation window** (2007-05 → 2026-06) so every book covers the same days.
4. **Benchmarking.** `summary()` adds an information ratio vs the investable index that matches
   your universe — DBHVG10U for G10, FXCTEM8 otherwise.
5. **Overlays cost money.** Hooks modify *weights*, not returns, so the cost model prices the
   trades your rule triggers and turnover reflects them. An overlay applied to a return series is
   free, which makes every risk-management rule look better than it is.

---

## `StrategyConfig` reference

Defaults reproduce the committed baseline. Change one thing; leave the rest alone.

### Universe

| Field | Default | Meaning |
|---|---|---|
| `universe` | `"ALL"` | `"ALL"` (27) · `"G10"` (9) · `"EM"` (18) · or an explicit list like `["AUD","JPY","MXN"]` |
| `exclude` | `("HKD","DKK","CNY")` | Dropped from `ALL`/`EM`: HKD/DKK are pegged (degenerate vol), CNY has no deliverable forward. Ignored when `universe` is an explicit list. |
| `tenor` | `"1M"` | Forward tenor for the carry signal and the cost model (`1M`/`3M`/`6M`/`12M`). |

### Signal

| Field | Default | Meaning |
|---|---|---|
| `signal` | `"carry"` | `"carry"` · `"momentum"` · a daily DataFrame panel · a callable `f(panels) -> DataFrame` |
| `momentum_lookback` | `63` | Days, when `signal="momentum"`. |
| `filter_signal` | `None` | Same-shaped panel for a directional double sort (keep longs ≥ 0, shorts ≤ 0). |

### Sort and within-leg weighting

| Field | Default | Meaning |
|---|---|---|
| `n_buckets` | `None` | Sort buckets. `None` → 3 for a single-region book, 5 for the full cross-section. |
| `weighting` | `"inv_vol"` | `"equal"` · `"inv_vol"` · `"erc"` · `"mvo"` |
| `max_leg_share` | `0.40` | Cap on any one name's share of its leg. |
| `min_per_leg` | `2` | Thinner rebalance dates keep the previous weights. |
| `vol_window` | `60` | Trailing window for inverse-vol leg weights. |
| `cov_window` | `250` | Covariance window for `erc`/`mvo`. |
| `rebal` | `"ME"` | `"ME"` · `"QE"` · `"W"` · `"2W"` … |

### Sizing

| Field | Default | Meaning |
|---|---|---|
| `vol_target` | `0.10` | Annualised vol target. `None` = no targeting (unit gross-2 book). |
| `vol_target_window` | `60` · `lev_cap` `4.0` · `vol_floor` `0.01` | Sizing guards. |

### Overlay hooks — where extensions attach

| Field | Default | Meaning |
|---|---|---|
| `exposure` | `None` | `pd.Series` of multipliers (1.0 = fully invested). Scales total risk. Sampled on the rebalance grid, **lagged one period by the base**. Dates before the series starts are fully invested. |
| `weight_overlay` | `None` | `f(weights, ctx) -> weights`. Per-currency changes: hedges, filters, manual edits. |
| `external_legs` | `()` | Tuple of `ExternalLeg` — non-FX instruments held alongside the book (a bond hedge, a futures overlay). Each earns `Σ w·r` and pays `Σ\|Δw\|·cost_bps/1e4`. |
| `extra_lag` | `0` | Extra days of execution lag on top of the base's own one-day lag. |

Stacking more than one of anything: see [Composing extensions](#composing-extensions) below.

### Costs and window

| Field | Default | Meaning |
|---|---|---|
| `costs` | `True` | Charge bid/ask half-spreads + roll. |
| `cost_multiple` | `1.0` | Scale all spreads — cost-stress sensitivity. |
| `start`, `end` | `None` | Evaluation window; `None` = the book's natural common window. |
| `name` | `""` | Label used in output tables. |

Derive configs with `.with_()`:

```python
from strategy import ALL_BASELINE, run
cfg = ALL_BASELINE.with_(weighting="erc", vol_target=0.15, name="erc_15")
res = run(cfg)
```

---

## `StrategyResult` reference

| Attribute | Type | What it is |
|---|---|---|
| `gross`, `cost`, `net` | `Series` | Daily returns. `net == gross - cost`, exactly. |
| `weights` | `DataFrame` | What is actually held — daily, signed, post-sizing, post-overlay. |
| `weights_unit` | `DataFrame` | After the sort, before vol targeting (gross 2). |
| `contrib` | `DataFrame` | Per-currency P&L. **Rows sum to `gross` exactly** — attribution adds up. |
| `xret` | `DataFrame` | Currency excess returns. |
| `spot_component`, `carry_component` | `DataFrame` | **Sum to `xret` exactly** — the spot-vs-carry split, no re-derivation needed. |
| `signal` | `DataFrame` | The panel the sort ran on. |
| `panels` | `Panels` | Shared data: `spots`, `carry`, `xret`, half-spreads. |
| `universe`, `config`, `window` | | What was actually run. |
| `turnover` / `turnover_daily` | `float` / `Series` | One-sided per rebalance / daily Σ\|Δw\|. |
| `cost_drag` | `float` | Annualised cost in return units. |

| Method | What it does |
|---|---|
| `summary(benchmark="auto", min_obs=120)` | Gross + net stats table (Sharpe, Sortino, Calmar, MaxDD, VaR/CVaR, skew, hit rate, IR). Columns with fewer than `min_obs` observations are dropped, so a window under 120 trading days returns an **empty** frame unless you lower it — `episodes.report_windows` does. |
| `monthly(which="net")` | Month-end compounded returns, for monthly overlays. |
| `reslice(start, end)` | Same book, narrower window — no rebuild, no re-estimation. |
| `returns_from_weights(w)` | Re-price an arbitrary weight panel (e.g. `weights.shift(2)`). |
| `cost_from_weights(w, multiple)` | Re-price its costs at scaled spreads. |

---

## The four extension patterns

Each has a runnable script in [`examples/`](examples/).

### 1. Total-exposure gate — regimes, macro, timing → [`02_regime_exposure_gate.py`](examples/02_regime_exposure_gate.py)

Your model emits a dated `Series` of multipliers; the base lags it and scales the weights.

```python
gate = my_model_probability.clip(0, 1)          # unlagged — the base lags it
res  = run(exposure=gate, name="my_gate")
print(res.summary())
```

Works with anything: an HMM, a logistic regression on macro features, a VIX percentile rule, a
hand-drawn crisis calendar. Values > 1.0 lever *up* if that is what you want to test.

### 2. Per-currency overlay — option hedges, filters, manual edits → [`03_option_weight_overlay.py`](examples/03_option_weight_overlay.py)

```python
def my_overlay(weights, ctx):
    rr = ctx.panels.xret.copy()                 # ctx gives you every panel
    out = weights.copy()
    out.loc[some_condition, "TRY"] = 0.0        # return a same-shaped frame
    return out

res = run(weight_overlay=my_overlay, name="hedged")
```

`ctx` carries `panels`, `weights_unit`, `signal`, `universe`, `config`. Whatever you return is what
gets traded, costed and reported.

### 3. Robustness sweep → [`04_parameter_sweep.py`](examples/04_parameter_sweep.py)

```python
for w in (20, 40, 60, 90, 120):
    print(w, run(vol_window=w).summary().loc["ALL_net", "sharpe"])
```

Panels are cached, so ~80 rebuilds take under a minute. For **cost and lag stress you do not need
to rebuild at all**:

```python
base = run()
net_2x = base.gross - base.cost_from_weights(base.weights, multiple=2.0)
lagged = base.returns_from_weights(base.weights.shift(2))
```

### 4. Universe edits and episode studies → [`05_subset_and_crisis.py`](examples/05_subset_and_crisis.py)

```python
ex_try = run(universe=[c for c in run().universe if c != "TRY"])
gfc    = run().reslice("2008-01-01", "2009-06-30")
```

`reslice` re-slices an existing book rather than rebuilding it — trailing windows still use the data
before the start date, which is what a subperiod study should do.

---

## Composing extensions

`StrategyConfig` carries **one** `exposure` and **one** `weight_overlay`. When several of us stack
components in the same book ([`overlays.py`](overlays.py)):

```python
from strategy import run, compose_exposure, compose_overlays, ExternalLeg

res = run(
    exposure=compose_exposure(vix_gate, regime_gate),          # gates multiply
    weight_overlay=compose_overlays(skew_filter, option_trim), # overlays chain
)
```

Three things about this are contract, not convenience:

1. **Gates multiply, so order cannot matter.** Two gates each halving risk give 0.25, not 0.5 —
   they are independent risk vetoes, and a book that ignored the second one would be claiming
   diversification between two signals that fire together. A gate's missing dates count as 1.0
   (fully invested), so a model that only starts in 2015 leaves 2007–2014 untouched rather than
   being handed a free "avoided 2008".
2. **Overlays may scale positions down, never re-normalise back up.** This is asserted at runtime
   and raises if violated. The failure mode is silent and serious: an overlay that re-normalises to
   a target gross undoes whatever gate ran before it, then inherits credit for that gate's drawdown
   improvement. Every step also receives the *same* `ctx`, so an overlay keys off the base book
   rather than off what the previous overlay did.
3. **`ExternalLeg` is for a new instrument, not a reweighting.** A bond hedge cannot go through
   `weight_overlay`: `portfolio_returns` intersects columns and would silently drop it, and
   `roundtrip_cost` raises on a name with no half-spread series. Pass it as an external leg and it
   earns its return *and pays its own transaction costs*:

```python
leg = ExternalLeg(returns=tlt_daily_return,   # one unit of the instrument
                  weight=-hedge_ratio,         # signed units, unlagged — the base lags it
                  cost_bps=1.5, name="TLT")
res = run(external_legs=(leg,))
print(res.external_coverage)     # days the leg held but had no quote
```

The leg appears as a column of `contrib`, so `contrib.sum(axis=1) == gross` still holds.
All three are exact no-ops at their neutral settings (`compose_exposure()`, `compose_overlays()`,
`external_legs=()`), so adding the machinery cannot move your numbers.

**Honest limit `ExternalLeg` does not remove:** it prices a *linear* instrument. A premium-paying
option hedge needs an option price, and `data/raw` carries option **mids only**.

---

## The `COMBINED` preset

`run("COMBINED")` is the frozen Phase-4 integrated book (plan §19.4) — the baseline plus the two
teammate components that earned a slot under a criterion fixed *before* any of them was measured:
improve MaxDD or CVaR₉₉ in at least 4 of the 6 pre-2026 stress windows, cost under 0.05 whole-sample
net Sharpe, and survive leave-one-out. Two of four components qualified.

```python
run("COMBINED")          # gross 0.6331 · net 0.4891 · MaxDD -19.07% · CVaR99 0.0200
```

Two things about it are worth knowing before you use it:

- **It is a callable, not a constant.** `PRESETS["COMBINED"]` resolves through
  `config.combined_preset()`, which builds data-derived objects and therefore does file IO. Making
  it a constant would mean `import strategy` reads files on every teammate's machine whether or not
  they use the preset.
- **It is the one place the base reaches into `cesare/`.** `combined_preset` imports
  `cesare.combined_engine.combined_components` lazily, at the moment the preset is requested. Its
  inputs are teammates' *committed outputs*, re-priced rather than rebuilt (plan §15 fallback), so
  the assembly logic belongs in `cesare/`, not here. The dependency is one-directional everywhere
  else: `cesare` imports `strategy`, never the reverse. Read the `combined_preset` docstring in
  [`config.py`](config.py) before changing anything on that seam — moving or renaming
  `cesare/combined_engine.py` breaks `run("COMBINED")` and `tests/test_combined.py`.

Every component folded in is labelled **re-priced, not rebuilt**, with its reconstruction method
recorded per row in `cesare/outputs/p4_component_standalone.csv`.

---

## Rules for AI agents working in this repo

If you are an agent helping a teammate with an extension, follow these. They exist because the
comparison across teammates is the deliverable.

1. **Import the base. Do not rebuild it.** `from strategy import run`. Do not write your own carry
   sort, vol target, or cost model, and do not copy `fx_utils.py` into a personal folder. If the
   base cannot express what is needed, say so explicitly rather than forking.
2. **Never edit files in `strategy/`** to make an extension work. The base is shared; changing it
   silently invalidates everyone else's numbers. Extensions live in the teammate's own folder and
   reach the base through `StrategyConfig` fields and the two hooks. Genuine gaps in the base go to
   Cesare as a request.
3. **Run `python strategy/tests/test_reconciliation.py` before and after your work.** Expect
   `12/12 passed`, plus `11/11` from `tests/test_episodes.py`, `17/17` from
   `tests/test_overlays.py` and `11/11` from `tests/test_combined.py` — 51 in total. If any fails,
   stop and report — do not build on a base that is not reconciling.
4. **Always report gross AND net**, on the same window, next to the baseline. A result quoted
   without its cost drag is not a result. Use `summary()`, which does both by default.
5. **State the config.** Any table, CSV or chart must record what produced it —
   `result.config.describe()` returns a flat dict for exactly this.
6. **Compare against the right bar.** The relevant comparison is `run()` with your one change,
   versus `run()` without it — not against a number from another notebook, another window, or
   another universe.
7. **Do not tune on the full sample and report the peak.** Sweeps are for finding plateaus. If you
   report a best cell, report the spread across the sweep next to it.
8. **A null result is a valid deliverable.** Most overlays in this project have failed to beat the
   simple book, and saying so clearly is worth more than a mined win. Do not search for a
   configuration that finally looks good.
9. **Write outputs to your own folder** (`<you>/outputs/`), never to `cesare/outputs/` or
   `strategy/`.
10. **No git operations** unless explicitly asked — leave changes uncommitted.
11. **Report per window, not just whole-sample.** Every result table carries a `window` column, and
    you print `report_windows(res)` before quoting any whole-sample number. A rule that lifts the
    full-sample Sharpe while making the crisis eras worse is a rule this book does not want, and
    only the per-window table shows that. Below ~120 trading days quote cumulative return, MaxDD,
    worst day and `n_days` — never an annualised Sharpe. `episodes.py` enforces both for you.

```python
from strategy import run
from strategy.episodes import ERAS, STRESS, report_windows, compare_windows

res = run(exposure=my_gate)
print(report_windows(res, STRESS, which="both"))     # did it preserve capital?
print(report_windows(res, ERAS))                     # where did the P&L come from?
print(compare_windows({"base": run(), "mine": res}, STRESS, metric="max_drawdown"))
```

`ERAS` partitions the sample, so its shares of P&L sum to 100% — that is the answer to "you picked
your windows". `STRESS` is the tail-event set and is allowed to overlap. **Both are frozen**: adding
a window is fine, silently changing one is not, and `tests/test_episodes.py` asserts the exact dates.

---

## Porting existing work onto the base

The audit that motivated this package (2026-07-28) found each extension needs only a small change.

### Vidhi — macro/regime gate

Your overlay already consumes a single return series and multiplies it by a probability-derived
scalar, which is exactly the `exposure` hook:

```python
base = run()
features = build_monthly_state_features(base.monthly(), market, base.signal.std(axis=1))
prob     = expanding_logistic_predictions(...).probability
res      = run(exposure=probability_exposure(prob), name="regime_gate")
```

Three things change when you migrate, and all three matter:

- **Your baseline's returns are spot-only** — `safe_log_return(spot)` never adds the carry accrual,
  so your book harvests none of the interest differential it is sorting on. That is why the static
  track shows Sharpe −0.71 and −72% drawdown while the same trade on this base is +0.47. Your
  headline conclusion will need re-deriving; it is likely to improve.
- **Do not pre-lag your probability** — pass it unlagged; the base lags it. Double-lagging silently
  weakens the gate.
- **Your gate will now pay for itself** (it moves weights, not returns), so expect a slightly lower
  Sharpe than the free version — that is the honest number.

Also worth fixing while migrating: the feature screen (`coverage >= 0.60`, `iloc[:, :80]`) currently
runs on the full sample before the expanding-window fit, which leaks. Screen inside the fold.

### Arjun — robustness audit and attribution

Replace all three copies of `build_book()` with `run(**override)`. Every parameter you sweep is a
config field: `universe`, `n_buckets`, `weighting`, `vol_window`, `cov_window`, `max_leg_share`,
`min_per_leg`, `rebal`, `vol_target`, `lev_cap`, `vol_floor`, `tenor`, `extra_lag`, `cost_multiple`.
Your cost and lag stresses map to `cost_from_weights` / `returns_from_weights` (no rebuild), and
your two hard assertions are now guarantees the base tests on every run:
`contrib.sum(1) == gross` and `xret == spot_component + carry_component`.
`04_parameter_sweep.py` reproduces your published jackknife and cost-stress findings.

### Theo — FX options, skew and vol filters

Your work is the `weight_overlay` hook — see `03_option_weight_overlay.py`, which implements the
project's per-currency risk-reversal rule as a template. `fx_utils.vol_surface_panel(kind, tenor,
delta)` gives ATM / RR / BF surfaces, sign-normalised crash-positive, and
`fx_utils.implied_skew_panel` the smile skew. Note the honest limit: `data/raw` has option **mids
only, no bid/ask**, so a premium-paying hedge cannot be costed yet — a position-trimming proxy is
the defensible version until that data is bought (`cesare/DATA_SHOPPING_LIST.md` §2.2).

### Dafu — `src/fxcarry/` and the BER replication

`src/fxcarry/` stays where it is; it is a separate, working thing with different conventions
(monthly, FCU-per-USD, `f_t − s_{t+1}`, 1984-start, your own `dafu/data/raw/` snapshot) and it is
the right tool for a BER paper replication. Two notes: (1) the BER sample starts in 1984 and the
shared `data/raw/` starts in 2007, so that replication **cannot** be reproduced on the team base —
keep it separate and say so; (2) for anything meant to be compared with teammates' extensions, use
this base instead. If you want a BER-style construction here, `run(vol_target=None, weighting="equal")`
is the closest expressible book, on the 2007+ sample.

---

## Reconciliation targets

| Book | Gross Sharpe | Net Sharpe | Source |
|---|---|---|---|
| `run()` — ALL, 27 names | 0.6284 | **0.4659** | `cesare/outputs/strategy_summary_stats.csv` |
| `run("G10")` — 9 names | 0.1669 | 0.1191 | same |
| `run("EM")` — 18 names | 0.606 | 0.376 | this build (no committed reference — the plan reports ALL and G10 only) |
| `run("COMBINED")` — the Phase-4 book | 0.6331 | **0.4891** | `cesare/outputs/p4_combined_ladder.csv`, final row |

Also fixed: turnover **0.675470** and cost drag **0.018146611** on `run()`; MaxDD **−19.07%** and
CVaR₉₉ **0.0200** on `run("COMBINED")`.

If your build does not produce these, fix that before anything else.

---

## Scope and honest limits

- **Daily, USD-per-FX, 252-day annualisation**, forward-implied carry `ln(S/F)`. Monthly-frequency
  and FCU-per-USD constructions are out of scope for v1 by design — see the Dafu note above.
- **Not a live trading system.** Costs are modelled from Bloomberg bid/ask; there is no market
  impact, no funding curve, no settlement calendar.
- **The engine is shared, not frozen.** New helpers belong in `fx_utils.py` as pure functions on
  wide panels, with docstrings that record the parameter rationale. Extension-specific logic does
  not belong there.
- Details of every design choice — why forward-implied carry rather than rate ranking, why the pegs
  are dropped, why costs roll via FX swap, why inverse-vol beat ERC/MVO/equal — are in
  [`cesare/FX_Carry_Strategy_Project_Plan.md`](../cesare/FX_Carry_Strategy_Project_Plan.md), the
  project's source of truth.
