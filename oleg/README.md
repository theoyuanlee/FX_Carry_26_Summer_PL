# `oleg/` — exploration only; never evaluated

**Oleg** · UChicago Summer Project Lab with Bank of America (Corporate Treasury / Global Funding).

> ### How this work landed
> **NEVER TESTED.** No output of any kind was committed, so nothing from this workstream could be
> measured on the common book. It has a row in [`../final/VERDICTS.md`](../final/VERDICTS.md) with
> the blocker named — because a gap stated in the artifact is a gap, and a gap omitted from it is a
> claim.

---

## What is here

Four files, ~140 KB:

| File | What it is |
|---|---|
| `v1/carry_backtest.ipynb` | A G10 carry backtest. Runs, and has executed cell output |
| `v1/carry_utils.py` | A private mini-copy of the carry engine, predating the shared [`../strategy/`](../strategy/) base |
| `v2/utils.py` | **0 bytes.** A second pass that was started and not written |
| `requirements.txt` | Unpinned; superseded by the repo-root [`../requirements.txt`](../requirements.txt), which is authoritative |

## Why nothing could be evaluated

There is no `outputs/` directory, and **no `to_csv` or `to_parquet` call anywhere in the notebook.** A
G10 carry book does exist as executed cell output — 2007-02-01 → 2026-06-30, gross Sharpe 0.2109,
MaxDD −31.4% — but it was never persisted to a file. On top of that, `carry_utils.RAW_DIR` resolves
to `oleg/data/raw`, which does not exist, so the notebook cannot be re-run here as committed.

Every other component in the project was folded onto the common book from a **committed artifact**.
This workstream produced none, so no measurement of it appears anywhere — not because it was skipped,
but because it was not possible.

**To close it:** one committed daily net return series on the common window
(2007-05-01 → 2026-06-30) makes it re-priceable through the same path every other component went
through.

## A note on the folder name

This directory was named `" v1"`, with a leading space, until the 2026-08-27 hand-off cleanup. The
space broke shell globbing and path handling. It was renamed to `v1/` and the three places that
quote the path — [`../final/VERDICTS.md`](../final/VERDICTS.md), `../final/verdicts.py`, and the
generated `../final/evidence/component_verdicts.csv` — were updated in lockstep, with the CSV
regenerated and diffed to confirm that path string was the only cell that moved.

**The 0-byte `v2/utils.py` and the unpinned `requirements.txt` are deliberately kept.** They are the
evidence behind the "never tested" verdict, which counts and names them. Tidying them away would
falsify a committed verdict row to save 84 bytes.
