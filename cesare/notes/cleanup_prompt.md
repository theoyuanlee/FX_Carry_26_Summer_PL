# Prompt for the next session — repo cleanup of `strategy/` and `cesare/`

*Paste everything below the line into a new Claude Code session in plan mode.*

---

Plan a cleanup of two folders in this repo: **`strategy/`** and **`cesare/`**. Nothing else.

## Context

UChicago × Bank of America Summer Project Lab on FX carry. Six students, one shared codebase. I own
the shared base (`strategy/`) and the integration track (`cesare/`). The research is **finished** —
the final report is written (`report/`, 11 chapters), the plan document is reconciled, and the
numbers are frozen. What is left is that both my folders have accumulated nineteen weeks of files
and nobody has ever tidied them.

Read `cesare/FX_Carry_Strategy_Project_Plan.md` (the repo's source of truth) and
`strategy/README.md` (the shared base's written contract) before planning.

## What I want

Make both folders legible to someone opening this repo for the first time.

1. **Remove genuinely dead or redundant code** — superseded scripts, duplicated logic, files that
   nothing references and nothing needs.
2. **Group the presentations.** Three HTML decks are scattered across two folders; they should live
   together somewhere sensible.
3. **Reconcile everything that a move or a deletion touches** — the plan document (especially the
   Appendix A output registry), the `report/` chapters, the root `README.md`, `strategy/README.md`,
   `cesare/README.md`. A cleanup that leaves a dead reference behind is not a cleanup.
4. **Leave both folders organised and self-explanatory** — a clear structure, and a short README in
   each that tells a newcomer what is here and where to start.

Optimise for *a stranger understanding the repo*, not for the smallest file count.

## Verified facts — I checked these by execution. Do not rediscover them the hard way.

**Two things look redundant and are load-bearing:**

- **`cesare/fx_utils.py` is a 4 KB re-export shim over `strategy/fx_utils.py`, and it must stay.**
  Eight of Arjun's notebooks plus Dafu's `regime_lab.py` do
  `sys.path.insert(0, "../cesare"); import fx_utils`. Deleting it silently breaks teammates whose
  folders I cannot edit. It exists *precisely* so their code kept working when the engine moved.
- **`strategy/` depends on `cesare/`, deliberately.** `strategy/config.py:252` imports
  `cesare.combined_engine.combined_components`, and `strategy/tests/test_combined.py:117` imports
  `cesare.combined_engine.ADOPTED`. Renaming or moving `cesare/combined_engine.py` breaks
  `run("COMBINED")` and the 8/8 suite. The reasoning is in `combined_preset`'s docstring — read it
  before proposing any change to that seam.

**Other couplings inside `cesare/`:** `final_evaluation.py` imports `d1_bkm_rerun.battery`;
`bkm_skew.py` imports itself in its self-test; `build_deck.py` writes to a hardcoded
`cesare/deck_2026_08_05.html` and reads ~14 CSVs by name.

**A naive orphan scan lies.** Grepping for literal filenames reports
`weights_{equal,erc,inv_vol,mvo}_monthly.csv` as unreferenced. They are not — Appendix A and report
chapter 6 cite them by *pattern* (`weights_{scheme}_monthly.csv`). Check for pattern references
before calling anything an orphan.

**Probably genuinely superseded, but verify rather than assume:**

- `cesare/deck_2026_08_05.md` — the Aug-3 markdown draft of a deck that is now generated as HTML by
  `build_deck.py`. Raw material, not a live artifact.
- `cesare/README.md` (144 lines) and `cesare/requirements.txt` — both now partly duplicated by the
  new repo-wide `README.md` and `requirements.txt` at the root. Decide whether they stay
  folder-scoped or slim to a pointer; do not just delete them.
- `cesare/final_evaluation.ipynb` vs `final_evaluation.py` — the notebook displays what the module
  computes. Check whether it still adds anything.

**In scope for grouping:** `cesare/deck_2026_08_05.html`, `cesare/FX_Carry_Update_Presentation.html`,
`strategy/overview.html`. **Out of scope:** `arjun/outputs/hedge_comparison_onepager.html` — not my
folder.

**The two large notebooks** (`data_visualization.ipynb` 3.7 MB, `strategy_backtest.ipynb` 928 KB)
are large because of embedded figure outputs. Stripping those outputs would shrink the repo a lot
and would also destroy the only committed copy of several rendered charts. Treat that as a decision
to put to me, not one to make quietly.

## Hard constraints

- **No git operations.** Leave everything uncommitted; I commit myself.
- **Never write to `arjun/`, `dafu/`, `theo/`, `vidhi/`, `oleg/`.** Read only. This is why breaking
  the `cesare/fx_utils.py` shim is unfixable rather than merely inconvenient.
- **These must still pass, unchanged:**
  ```bash
  python strategy/tests/test_reconciliation.py   # 12/12
  python strategy/tests/test_episodes.py         # 11/11
  python strategy/tests/test_overlays.py         # 17/17
  python strategy/tests/test_combined.py         #  8/8
  ```
- **These numbers must not move:** `run()` gross **0.6284** / net **0.4659**, G10 **0.1669** /
  **0.1191**, turnover **0.675470**, cost drag **0.018146611**; `run("COMBINED")` gross **0.6331** /
  net **0.4891**, MaxDD **−19.07%**, CVaR₉₉ **0.0200**.
- **These must still run end to end:** `python cesare/build_deck.py`,
  `python cesare/final_evaluation.py`, `python cesare/d2_vrp.py`, `python cesare/d1_bkm_rerun.py`.
- Environment: Python 3.13, and **pyarrow must be the pip build (≥ 24)** — conda's 19.x cannot read
  these parquets.

## How to work

- **Build the reference graph before proposing anything.** For every file in both folders, establish
  what imports it, what cites it by name, and what cites it by pattern — including from `report/`,
  the plan document, the READMEs, the HTML decks, and teammates' folders. Most of the risk here is
  in references, not in code.
- **Give me an explicit disposition for every file** in both folders: keep / move / merge / delete,
  each with a one-line reason. I want to see the whole inventory, including the boring "keep as-is"
  rows, so I can tell that nothing was overlooked.
- **Verify, don't assume.** Claims in the plan document that an artifact or dataset exists have been
  **wrong five times** (Appendix C #12, #18, #26, #28, #30). Check before relying on one. If
  something doesn't reconcile, say so rather than papering over it.
- **Propose deletions, don't perform them speculatively.** Anything you cannot prove is unreferenced
  goes on a "candidates, needs my call" list instead of into the plan as an action.
- Run the four suites before starting and after finishing.

## Definition of done

- Both folders have an obvious structure and a short README explaining it.
- The three HTML decks are grouped together, and `build_deck.py` still writes to the right place.
- No dead cross-references anywhere in the repo — verify by scanning every markdown link and every
  filename cited in the plan document, the report and the READMEs.
- The four suites are green and every acceptance number above is unchanged.
- I get a written list of what was removed and why, and what was left alone despite looking
  removable.
