# `docs/` — superseded design documents

One file, kept as a record of a design that changed.

| File | Status |
|---|---|
| `plans/fxcarry_harness_plan.md` | **Superseded (2026-07-13).** A proposal for a shared backtest harness under `src/fxcarry/` |

**What shipped instead is [`../strategy/`](../strategy/)** — same goal, different layout. The shared
base solved the problem this document was written to solve: an audit had found five materially
different baseline carry books across the repo, one of which never added the carry accrual at all,
which meant no two results were comparable.

This document's internal links point at a `src/fxcarry/` module tree that was never built, so they do
not resolve. They are left broken rather than repaired — they are evidence of a proposal that
changed, and rewriting them would make a superseded plan look like a current one.

For the design that was actually built, read [`../strategy/README.md`](../strategy/README.md).
