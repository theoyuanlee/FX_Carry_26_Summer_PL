# `cesare/presentations/` — the project's HTML decks

Four self-contained HTML pages, newest first. Each opens from a `file://` path with no network:
no CDN, no external stylesheet, no remote image. Open them in a browser; there is nothing to build.

| Deck | Date | What it is | Made by |
|---|---|---|---|
| [`deck_2026_08_12.html`](deck_2026_08_12.html) | 2026-08-12 | BofA progress deck. The evaluation closed: all 16 components across all six workstreams with a verdict, the two named gaps, and the one contested call | **Generated** — `python cesare/build_deck_aug12.py` |
| [`deck_2026_08_05.html`](deck_2026_08_05.html) | 2026-08-05 | BofA progress deck. Six workstreams folded into one engine, the tail re-verdict, per-stress-window results, and what is new since the Jul 29 meeting | **Generated** — `python cesare/build_deck.py` |
| [`overview.html`](overview.html) | 2026-08-03 | Visual overview of the shared base [`../../strategy/`](../../strategy/) — what `run()` is, the guardrails, and the headline books | Hand-made |
| [`FX_Carry_Update_Presentation.html`](FX_Carry_Update_Presentation.html) | 2026-07-19 | Mid-project update to the desk | Hand-made |

## Three things to know before quoting from these

**The two generated decks are generated, so do not edit them.** Every number in the prose is pulled
from a CSV cell rather than typed — that is what keeps the repo's standing promise (plan §1,
`report/README.md` rule 1) that every number traces to a committed file. Both assert their headline
against a live `run()` before the page is written, and fail rather than publish a stale slide. To
change one, change its generator and re-run it.

**Only the Aug 12 deck rebuilds byte-identically.** `build_deck.py` renders seven matplotlib
figures, and matplotlib assigns random SVG element ids per run — so regenerating
`deck_2026_08_05.html` produces a ~900-line diff in which *every* line is an id, the file length is
unchanged to the byte and all 13,871 numeric tokens match (plan Appendix C #41). A dirty Aug 5 deck
is therefore not evidence of anything until the ids are normalised; a clean one would be the
surprise. `build_deck_aug12.py` has no figures and is deterministic — run it twice and the hashes
match, which is why it is safe to regenerate before a meeting.

**`overview.html` is a July snapshot and its episode buckets are superseded.** Its baseline numbers
are still correct (gross 0.6284 / net 0.4659, G10 0.1669 / 0.1191), but it predates the `COMBINED`
book and it groups the sample into ad-hoc buckets like "Recent 2023-26". Those are superseded by the
frozen `ERAS` and `STRESS` windows in
[`../../strategy/episodes.py`](../../strategy/episodes.py) — plan:1328 records the supersession, and
plan §19.2 explains why it mattered: the 2013 taper tantrum, the second-worst window in the sample,
was invisible inside `overview.html`'s aggregation. **For any per-window claim, use
`p4_stress_table_baseline.csv` / `p4_episode_table_baseline.csv`, not this page.**

## Not here

`arjun/outputs/hedge_comparison_onepager.html` is Arjun's, and lives in his folder.
