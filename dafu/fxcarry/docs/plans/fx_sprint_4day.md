# FX options sprint: the 4.5-day cut of Week 1

> **Merged with FINM 33000 on 2026-07-31.** The prerequisite phase below and FINM 33000's own plan were about to cover the same four lectures and the same homework a week apart, at two different depths. They now run once, at the deeper one, inside a single burst block: `learning/STUDY-GUIDE.md`, block 1. Phases 2 through 5 and the finm37301 remainder are unchanged and keep the Aug 4 deadline; the prerequisite phase is superseded by [the note below](#prerequisite-phase-the-finm-33000-slice).
>
> The merge buys 6h45 back — the duplicated core — and the rate rises from ~6h/day to burst. Parts 1a and 1b come to 36h30, which lands on Aug 3 from a half-day Friday, leaving Aug 4 as thin buffer rather than as the finish. Thin, not comfortable: if Friday gives less than about 7h, Aug 4 gets used.

FX options study is due before Tuesday 2026-08-04. From Thursday 2026-07-30 that leaves 4.5 days at roughly 6h each, 27h of capacity. The sprint below needs 27.5h. There is no slack, and the [cut order](#cut-order-if-a-day-is-lost) says what goes first if a day is lost.

This is not a replacement for [the month plan](month_plan.md)'s Week 1. It is the slice of it that fits before Tuesday: the prerequisite phase below, then phases 2 through 5, Read/Derive/Verify only. Phase 0, Phase 1's Derive/Verify/Own/Build, and every Own and Build block in phases 2-5 move to week 2. [Why that's safe](#deferred-to-week-2-and-why-its-safe) is its own section, because none of it is what Tuesday's deadline is actually asking for.

## The hour budget

| Block | Hours |
|---|---|
| Prerequisite phase: FINM 33000 slice (L1, L5, L6, L7 notes, HW2 written) | 6 |
| finm37301 lec02, the remainder | 1.5 |
| Phase 2: the option contract, Garman-Kohlhagen, delta | 4 |
| Phase 3: delta conventions and the ATM strike | 6 |
| Phase 4: structures and the smile | 6 |
| Phase 5: Greeks and Breeden-Litzenberger | 4 |
| **Total** | **27.5** |

## Prerequisite phase: the FINM 33000 slice

> **Superseded 2026-07-31 — read this first.** This phase is now part 1a of `learning/STUDY-GUIDE.md`'s block 1, and it runs at FINM 33000's Write depth rather than the 6h review pass below: the complete L1–L7 lecture pass closed-book, HW2 written in full, plus a new written item on forward prices. 15h rather than 6h, and it covers strictly more.
>
> It is the whole pass, not the four lectures this phase names, because those four do not stand alone: `lec05.tex:34` opens by naming L4's Itô apparatus and says L3's definitions "carry over almost word for word", and `lec06.tex:415` derives martingale pricing by generalising L2 and L3's discrete FTAP. The scoping below sidestepped that by cutting the Itô-dependent material; running L6 and L7 whole means L2–L4 come first. If Aug 4 tightens, L2 and L3 are the first 3h to slide out — they are the only pass items with no consumer in phases 2–5.
>
> Two of the scoping decisions in this section are now obsolete. **L6 is no longer cut at slide 6.7** and **L7 is no longer cut to its forward and tradeable-asset sections**; both were scoped that way to avoid Itô's rule, and L4 is now being written anyway. Black-76 gets the martingale machinery underneath it instead of the statement of it. Everything else here — why the phase exists, what feeds what, the done-when — still holds, and the reading scopes below remain the right fallback if a day is lost.
>
> The cut order at the bottom of this file also changes: HW2 P1 and P2(b) are no longer cuttable, since HW2 in full is FINM 33000's highest-value set on its own terms and no longer only a means to Phase 5.

The blocker this phase fixes: the FX notes assume option theory rather than build it. Lec03's Black-76 is a forward-measure statement with no derivation of the measure; lec04's Greeks and Breeden-Litzenberger are used, not derived. FINM 33000 is where they're derived, but the course is seven lectures and five homeworks. The slice that actually feeds this sprint is four lectures and one homework, against FINM 33000's own lecture spine (`learning/finm33000/README.md`) and homework tiering (`learning/finm33000/STUDY-GUIDE.md`).

| Item | Topic | Feeds |
|---|---|---|
| L1 | Arbitrage-free pricing, forwards, options, put-call parity, static replication | Phase 2's "put-call parity from contract definitions alone" |
| L5 | The Black-Scholes model, replication, the Greeks | $d_1$/$d_2$ and spot delta in Phase 2; the analytic vega/vanna/volga in Phase 5 |
| L6 | Martingale pricing, Girsanov, the Black-Scholes formula | The risk-neutral $Q$ behind $V = P\cdot E^Q[\text{payoff}]$ and $F = E^Q[S_T]$, which lec03 uses without re-deriving |
| L7 | Joint $\sigma\sqrt{T}$ effects, $N(d)$ interpretations, Bachelier, forward prices, tradeable assets | Forward prices as tradeable assets, which is what makes Black-76 a forward-measure statement in the first place, and what Garman-Kohlhagen relies on via CIP |
| HW2 P2(a) | The Carr-Madan / Breeden-Litzenberger identity | Phase 5's central derivation, $P(T) f^Q(K) = \partial^2 V/\partial K^2$, verbatim |

Not needed: L2 and L3 are the one-period and multi-period FTAP, discrete machinery this sprint doesn't touch. L4 is Itô's rule, needed to derive Black-Scholes from a stochastic model, not to use the closed-form result the FX notes hand you. HW3 through HW5 are martingale-measure completeness, the self-financing trap, optional stopping and the OU solution: real content, but none of it is load-bearing for FX options, and it stays on the FINM 33000 homework plan for its own reasons.

L6 and L7 need scoping within themselves, because both keep going well past what this sprint needs, and both continuations lean on Itô's rule, which the slice deliberately excludes. **L6:** read through Slide L6.7 ("Option pricing," `lec06.tex` line 504) and stop. That slide is where the martingale-pricing conclusion is applied to get $C_t = B_t E_t[Y_T/B_T]$, which is the $V = P\cdot E^Q[\text{payoff}]$ statement this slice needs; the same general conclusion applied to $S$ itself gives $F = E^Q[S_T]$, so nothing past L6.7 is required for either. Slides L6.3 through L6.6 are the FTAP proof sketch, and the notes flag them as reference only in their own words ("the result is needed; the proof details are not," `lec06.tex` line 431): read them for the conclusion, not for the argument. Slide L6.8 onward is Girsanov's theorem and the Itô-product-rule recomputation of the risk-neutral drift, through L6.31; both depend on Itô's rule (`lec06.tex` lines 468 and 657, "the calculation is the Itô product rule" and "by Itô's rule, $X/B$ has dynamics"), so both stay out with L4. **L7:** skip the vega/convexity, joint-$\sigma\sqrt T$, Jensen, replication-vs-expectation, $N(d)$-interpretation, general-payoff and Bachelier sections (`lec07.tex` lines 58-517, labels `sec:L7-vega-rule` through `sec:L7-bachelier`): all of it consolidates Black-Scholes material L5 and the scoped L6 already cover. Start at `sec:L7-forward` (line 518) and read through `sec:L7-tradeable` (line 771): forward prices as risk-neutral martingales, and what counts as a tradeable asset, which is exactly what Garman-Kohlhagen needs via CIP. The dividends section after it (`sec:L7-dividends-lookahead`, lines 772-892) is optional; the notes' own header comment says dividends "are not on the final exam."

Scoped this way the four reads come to 32,851 words across 2,596 lines: 11,783 for L1 (unscoped, `lec01.tex`), 11,247 for L5 (unscoped, `lec05.tex`), 6,098 for the L6 slice, 3,723 for the L7 slice. Unscoped, the same four files run 47,738 words across 3,867 lines. That's still a substantial amount of derivation-heavy material sitting inside a 6h budget that also has to cover writing all of HW2 (about 2h, per the STUDY-GUIDE's own estimate), a closed-book derivation pass, and checking against `solutions/`. So 6h assumes review pace on lectures already sat through in Fall 2025, not a first read. If a first read of any one lecture runs past about 90 minutes, stop and fall back to the named sections above rather than let it eat into Phase 2's time.

**Read.** L1 and L5 in full; L6 through Slide L6.7; L7 from `sec:L7-forward` through `sec:L7-tradeable` (`learning/finm33000/notes/src/lec01.tex`, `lec05.tex`, `lec06.tex`, `lec07.tex`, or the built `notes/finm33000.pdf`). Closed-book after, per the course's own working rule.

**Write.** HW2 in full, per the STUDY-GUIDE's own verdict ("the highest-value set in the course"): P1's static bounds, P2(a) the identity itself, P2(b) its discretization onto listed strikes.

*Done when* put-call parity, $d_1$/$d_2$, the risk-neutral pricing statement, and the Breeden-Litzenberger identity all reproduce closed-book, and HW2 is checked against `learning/finm33000/solutions/`.

## finm37301 lec02, the remainder

Lec01 and part of lec02 are already read. Finishing lec02 (implied yields, the FX swap, the basis) is background, not option theory: Phase 2's Black-76 sits on the forward from lec01 (already learned) and CIP, not on lec02's account of why CIP isn't exact in practice. The remainder is cheap to close out and worth doing for continuity, but it is the first thing to give up if the week runs short.

## Phase 2 through Phase 5

Same Read, Derive, Verify and Checkpoint blocks as `month_plan.md`'s Phase 2 through Phase 5; that content doesn't change, only the Own and Build blocks are cut this week. What follows is the reduced done-when for each, since the month plan's original done-when criteria assume the Own/Build work that isn't happening until week 2.

### Phase 2: the option contract and Black-Scholes for FX (4h)

Read Shamah Ch. 14-15, Castagna §1.3 and §2.1-2.2.2, lec03. Derive put-call parity, then Garman-Kohlhagen from Black-76 plus CIP, naming the step that uses CIP. Verify against `VolSurface.atm_panel`, parity to 1e-12.

*Done when* Garman-Kohlhagen is derived from Black-76 plus CIP with the CIP step named, put-call parity holds on paper and against real ATM quotes to 1e-12, and the four premium conventions are written from memory as a conversion table.

### Phase 3: delta conventions and the ATM strike (6h)

The hard phase, and the one the deck most depends on. Read Castagna §2.2.3-2.2.4, §4.1-4.1.1, §5.2.1-5.2.2, lec04's delta section. Derive spot versus forward delta, premium-adjusted delta and why it changes the hedge, the delta-neutral straddle strike in both conventions and the sign flip between them. Verify the spot-delta 25-delta strike round trip against real quotes across G10 and tenors, then measure the pips-versus-premium-adjusted gap the same way, and again at 10 delta where the crash hedge lives.

*Done when* the premium-adjusted delta formula and its sign flip are derived on paper, the spot-delta 25-delta strike round-trips to 0.25 across G10 and tenors (the convention `Black76.strike_from_delta` already implements), and you can state by hand how far a premium-adjusted strike would move from its spot-delta counterpart, without the root-find that implements it existing yet.

### Phase 4: structures and the smile (6h)

Read Castagna §1.4, §3.6-3.8, §4.4, §4.9, lec04's structures section. Derive how straddle, risk reversal and butterfly isolate the second through fourth moments, the RR and BF formulas, the smile-butterfly inversion, and vanna-volga as a three-option replication. Verify the five-point smile for one calm and one crisis date, and measure the market-strangle-versus-smile-butterfly gap in vol points at 25 and 10 delta, per currency.

*Done when* the five-point smile is built by hand for both a calm and a crisis date, RR and BF are derived and inverted to per-strike vols, and you can state the market-strangle-versus-smile-butterfly gap in vol points at both deltas without yet having coded the §4.9 solve.

### Phase 5: Greeks and the implied distribution (4h)

Read Castagna §2.2.2, §3.6 again, §4.5.2-4.5.3, §4.10, lec04's Greeks and Breeden-Litzenberger sections. Derive vega, vanna and volga from the Black-Scholes formula, and Breeden-Litzenberger: this is HW2 P2(a) again, in the FX notation. Verify by extracting the implied density for one currency, checking non-negativity, unit mass and call monotonicity.

*Done when* vega/vanna/volga are derived from the Black-Scholes formula, Breeden-Litzenberger is derived in three lines matching HW2 P2(a), and the implied density for one currency is checked by hand for non-negativity, unit mass and call monotonicity.

## Deferred to week 2, and why it's safe

- **Phase 0.** 2,723 lines of library orientation. Reading eight modules against their notebooks is not FX options study, and nothing downstream of it in this sprint requires it: the theory in phases 2-5 is being derived on paper and checked against raw quotes, not against `fxcarry`'s internals.
- **Phase 1's Derive, Verify, Own and Build.** The basis and FX swaps aren't options. Only the lec02 reading carries over, because it's already half done and costs little; the CIP-in-practice derivation, the basis verification against 2008/2020 data, and `curves.py` ownership wait for week 2 alongside Phase 0.
- **Own, every phase.** Owning a module means judging whether the rebuilt library's code does what it claims, at the depth the month plan sets per phase. That judgment presupposes Phase 0's map of the eight modules, which isn't happening this week, so an Own block done now would be reading code without the context to tell keep from fix from delete.
- **Build, every phase.** Extending `strike_from_delta` to all four conventions, the market-strangle convention on `Smile`, the Greeks and density in a notebook: all of it changes `fxcarry`, and none of it is required to derive or verify the theory by hand. The month plan already treats Own and Build as library work bundled into study, so this is where the theory being solid and the library being finished separate cleanly.
- **C++.** Runs in the evenings regardless, off the [C++ track](cpp_quantlib_track.md); parked explicitly this week so the daytime 6h budget stays about FX options.

## Cut order if a day is lost

In order, first cut to last:

1. **finm37301 lec02, the remainder (1.5h).** Already flagged as background; push it to week 2 with the rest of Phase 1.
2. **HW2 P1 and P2(b).** Keep P2(a), the Breeden-Litzenberger identity itself: it's Phase 5's derivation verbatim. The static-bounds workout (P1) and the discretization onto listed strikes (P2(b)) can be read from `learning/finm33000/solutions/` instead of written.
3. **Narrow the Verify blocks' breadth**, not their existence. Phase 3's "across G10 and tenors" becomes EUR at one tenor; Phase 4's "one calm and one crisis date, per currency" becomes one calm date, one currency. The rule that nothing counts as understood without reproducing it on real data still holds. The sample shrinks; the check doesn't disappear.
4. **Protected, cut last:** Phase 2's Garman-Kohlhagen derivation (the CIP bridge every later phase leans on), Phase 3 in full (the hard phase, the one the deck most depends on), Phase 4's Derive block (straddle, risk reversal, butterfly, vanna-volga replication), and Phase 5's Breeden-Litzenberger derivation. Phase 4's Derive block stays even if a full day is lost, because the smile-butterfly-versus-market-strangle distinction it derives is what `research/crash_hedged/` already leans on; only Phase 4's Verify narrows further, per item 3 above.

## Recall notes

Same template as the month plan, one file per phase in `docs/notes/theory/`, written with the books shut. The prerequisite phase gets one too, since HW2 P2(a) is a derivation that has to survive being asked cold.
