# DRAFT — not sent. Theo: how to spec the bad-skew filter (§19.1 collision)

*Drafted 2026-08-03. Send with, or just after, the porting note.*
*Owner of the ask: Theo. Owner of the collision: me — I closed the work it overlaps.*

---

**Subject: bad-skew filter — please spec it as marginal over per-currency RR, not vs the baseline**

Theo —

The desk gave you the bad-skew exclusion / sizing filter on Jul 29. Before you run it, one piece of
context that changes what the right test is. This is a coordination problem, not a criticism of the
idea — the moderator question underneath it is genuinely additive and nobody else has done it.

**The collision.** Your ask overlaps two things that are already closed in the repo:

1. **Stage 3, per-currency risk-reversal conditioning** (plan §9). Trim long positions in currencies
   whose crash insurance is expensive, judged on a trailing 3-year percentile. Net Sharpe **0.457**,
   skew −0.65 → −0.60, CVaR₉₉ 2.9% → 2.7%. This is the project's *adopted* tail hedge — the one
   overlay that survived costs. Implementation is already runnable:
   `strategy/examples/03_option_weight_overlay.py::rr_trim_overlay`.
2. **Phase 3 / D1, skew as a cross-sectional signal** (plan §17.1). Five variants on the matched
   21-name option universe. **Null.** And the spanning test ran both ways: carry earns a significant
   alpha over SRP (α +3.77%/yr, t **+2.19**) while SRP earns none over carry (α −0.48%/yr, t −0.38).
   On this sample **carry subsumes skew, not the other way round.**

**Why this matters for the meeting.** If your filter is measured against the *raw* baseline
(net 0.466), it will almost certainly look like it helps — because roughly the same tail improvement
is already sitting in the adopted per-currency RR rule. We would then walk into the same meeting
with two skew answers that appear to contradict each other: yours saying skew adds value, D1 saying
skew is null. Both would be "right" against their own bar, and the desk would rightly ask which one
to believe.

**The fix — one sentence.**

> **Spec the test as marginal over the per-currency RR book (net 0.457), not versus the raw
> baseline (0.466).**

Concretely: the comparison is `run(weight_overlay=rr_trim_overlay)` **with** your bad-skew filter
added, versus `run(weight_overlay=rr_trim_overlay)` **without** it. One change at a time, against
the immediately preceding book, gross and net, with the episode table attached. If your filter beats
that, it is a genuine finding and it goes straight into the combined engine. If it does not, that is
a clean null and it *strengthens* D1 rather than contradicting it — which is a much better outcome
than two irreconcilable slides.

**The part of your ask that is genuinely additive — please keep it and lead with it.** The desk also
asked you to *quantify how carry's predictive power degrades as bad skew rises.* D1 did **not** test
that. D1 tested skew as a **signal**; you would be testing skew as a **moderator of carry**. That is
a different question, it is not covered anywhere in the repo, and it is the more interesting half of
your ask. Suggested shape: bucket currency-months by bad-skew percentile and estimate the
carry → next-month-return relationship within each bucket, with Newey–West errors. If the slope
flattens as skew worsens, you have shown *when* the signal is trustworthy — which is directly usable
as a sizing rule and is a better story than another exclusion filter.

**Practicalities.**
- `fx_utils.vol_surface_panel("RR", "1M", 25)` gives the risk reversal already sign-normalised
  crash-positive; `fx_utils.implied_skew_panel` gives the RR/ATM smile skew.
- Your `theo/data/processed/fx_option_signal_panel.parquet` already carries `bad_skew25_1m`,
  `bad_skew10_1m` and `option_data_quality_flag` at month-end — that is the input, no rebuild needed.
- Coverage caveat: 21 of the 27 names have option surfaces (no CLP/COP/IDR/MYR/PEN/PHP). State the
  matched universe explicitly, as D1 did, so the comparison is like-for-like.
- Honest limit to write down: `data/raw` has option **mids only, no bid/ask**, so a premium-paying
  hedge cannot be costed. A position-trimming proxy is the defensible version. Do not report an
  insurance overlay's Sharpe as if the premium were free.

**Heads-up on timing.** If the Aug 12 gate slips I will reconstruct a bad-skew variant from your
committed signal panel so the combined ladder is not blocked, and it will be labelled *re-priced,
not rebuilt* with the reconstruction stated. That placeholder is strictly worse than your own run —
it is my reading of your signal, not your specification of it — so it is in your interest to get
ahead of it.

— Cesare
