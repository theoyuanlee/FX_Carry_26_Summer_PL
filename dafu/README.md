# `dafu/` — regime-switching carry, and the `fxcarry` research library

**Dafu** · UChicago Summer Project Lab with Bank of America (Corporate Treasury / Global Funding).

> ### How this work landed
> **VIX percentile gate → REJECTED, and it is the one contested verdict in the project.** It is
> accepted by the desk's tail objective and rejected by the pre-registered slot rule; it was decided
> on the slot rule, and that decision **costs 0.043 net Sharpe and 5.4% of relative CVaR₉₉**. The
> alternative book is built, tested and runnable as `run("COMBINED_TAIL")` so the cost can be priced
> rather than asserted. A second component, the option-insurance overlay, is **blocked on data** —
> the repo's option surfaces are mids-only, so a premium-paying hedge cannot be honestly costed.
>
> This is also **the only workstream that actually ported onto the shared base.** The component
> dropped belongs to the one person who did the integration work properly. That is uncomfortable and
> it is not a reason to decide it differently. The argument at full strength is in
> [`../final/VERDICTS.md`](../final/VERDICTS.md) — it is the longest section in that document.

---

## What is here

| Path | What it is |
|---|---|
| `regime_switching_carry.ipynb` | The research notebook: regime-switching models applied to the carry book |
| `regime_lab.py` | Plumbing between the team's shared panels and `fxcarry`'s regime estimators. Deliberately decides nothing — it loads, grids to month-end, and hands off |
| `fxcarry/` | A modular FX cross-sectional strategy research library (12 modules, below) |
| `outputs/` | 20 committed result files — the gate sweep, the regime probabilities, the episode Sharpes, the option overlay and drag |

### The `fxcarry` package

| Module | Concern |
|---|---|
| `catalog.py` | Instrument identity: what a currency is called, which conventions it follows |
| `quotes.py` | Two-sided market data, and the one pipeline that reads it |
| `curves.py` | Spot and forward levels at one tenor, and the returns they imply |
| `vol.py` | The quoted volatility smile, and volatility at a delta |
| `options.py` | Option pricing, positions, and the hedges built out of them |
| `regimes.py` | Saying which state the world is in, and how much of that answer is hindsight |
| `strategy.py` | Turning a view into weights, and weights into returns |
| `stats.py` | Estimating things from return series |
| `compare.py` | Putting several books side by side without re-running any of them |
| `registry.py` | What each pull contains, and whether the file on disk still agrees |
| `reference.py` | Reference tables: ticker catalogs, market conventions, analytics defaults |

## ⚠ The data in this folder is DVC-tracked, not committed

`data/raw/*.dvc` are **pointer files, not data.** The parquets themselves live on a public,
read-only remote declared in `.dvc/config`. Two ways forward:

```bash
# either: pull this folder's own copies (needs `pip install dvc`)
cd dafu && dvc pull

# or, simpler: use the repo-root data, which IS committed
ls ../data/raw/*.parquet
```

**For reproducing anything in the report or the shipped strategy you want the second one.** The
repo-root `../data/raw/` is git-tracked precisely so that no external fetch, credential or terminal
is ever required. This folder's DVC setup is Dafu's own workflow and is kept as part of the record.

## Running these

Python 3.13, `pip install -r ../requirements.txt` from the repo root (see the pyarrow caveat there).
`dvc` is **not** in that file — it is needed only for `dvc pull` above, which is optional.
