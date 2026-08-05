# DRAFT — not sent. Porting deadline note (§18.1 gate, 2026-08-12)

*Drafted 2026-08-03. Send after the Aug 5 meeting so it lands with a week to run.*
*Audience: Arjun, Theo, Vidhi, Oleg (Dafu already ported). CC the team channel.*

---

**Subject: base porting — done by Tue Aug 12, and what "done" means**

Team —

The desk made the uniform base a *blocking* item on Jul 22 and asked on Jul 29 that every workstream
migrate and re-run. Dafu is on it; the rest of us are not yet. The combined engine is the Aug
deliverable and it cannot compare things that were measured on different books, so here is a firm
date and an unambiguous definition of done.

**Deadline: the Tue 2026-08-12 BofA meeting.**

**Definition of done — four items, per person:**

1. Your headline result re-derived through `strategy.run()`, so it sits on the same 27-name,
   2007-05 → 2026-06 book everyone else is on.
2. Reported **gross AND net**. A result quoted without its cost drag is not a result.
   `result.summary()` does both by default.
3. The per-window episode table attached — `report_windows(res, STRESS)`. This is the desk's
   standing requirement since Jul 29, not a preference of mine. A rule that lifts the full-sample
   Sharpe while making the crisis eras worse is a rule the book does not want, and only the
   per-window table shows that.
4. `python strategy/tests/test_reconciliation.py` printing **12/12 passed** and
   `python strategy/tests/test_episodes.py` printing **11/11 passed**. If either fails, stop and tell
   me — do not build on a base that is not reconciling.

**You do not need to write documentation for this.** The per-person porting recipe is already in
`strategy/README.md` under "Porting existing work onto the base", including the specific change each
of you needs. The short version:

- **Arjun** — replace the three inline `build_book()` copies with `run(**override)`. Every parameter
  you sweep is already a config field. Your cost and lag stresses map to `cost_from_weights` /
  `returns_from_weights` with no rebuild. *Also: your rebalance heatmap needs re-running on v1.1.0 —
  the roll-leg cost fix moves the QE cell, which was undercharged (drag 0.89% → 1.33%/yr).*
- **Theo** — replace your own panel build with `load_panels()`; your option filter becomes
  `filter_signal` or `weight_overlay`. See `examples/03_option_weight_overlay.py`. Separate note
  coming on how to spec the bad-skew test so it does not collide with completed work.
- **Vidhi** — your overlay already multiplies a return series by a probability scalar, which is
  exactly the `exposure` hook. Three things change and all three matter: your baseline's returns are
  spot-only (the carry accrual is never added, which is why the static track shows −0.71), so
  **expect your headline conclusion to improve**; do **not** pre-lag your probability, the base lags
  it; and your gate will now pay for itself because it moves weights rather than returns.
- **Oleg** — delete the private engine copy in `v1/carry_utils.py` and
  `from strategy import run`. Whatever episodes you study, use the frozen windows in
  `strategy/episodes.py` so your episodes and ours are the same episodes.

**If you slip.** I am not putting the deliverable on four people's schedules, so the fallback is
already running: I will take your **committed outputs** and re-price them on the base myself.
Everything folded in that way gets documented as *re-priced, not rebuilt*, with the reconstruction
method stated — which is honest but strictly worse than your own port, because the construction
differences the base exists to eliminate come back in, and because you lose control of how your work
is represented. Porting is a couple of hours. Please just do it.

Ask me anything — the base is mine and gaps in it are my problem to fix, not yours to work around.

— Cesare
