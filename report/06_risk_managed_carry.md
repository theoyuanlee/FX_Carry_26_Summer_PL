# 6. Risk-managed carry: hedging, construction, momentum and regimes

*Chapter 6 of the final report. Draft, 2026-08-04.*
*Every number below is reproducible from a committed CSV in `cesare/outputs/`.*

---

## 6.0 Scope, and where the verdicts live

Chapter 5 ended on an opportunity: the carry premium earns nothing in crisis, at 1.5× the
volatility. This chapter covers the four standard responses a desk would reach for —

- **Stage 3** — dynamic exposure management and crash hedging
- **Stage 4** — portfolio construction and optimisation
- **Stage 5** — a momentum overlay
- **Stage 6** — regime-aware allocation

— and reports what each buys. The **verdicts** are in chapter 9, because all four failed the
pre-registered bar and that chapter exists so nulls are collected rather than scattered. This chapter
covers what was built, what the surviving refinements are, and the one structural finding that
determines whether any of it is worth having.

**The bar, throughout.** Any variant must beat, net of costs with Newey–West significance, *both* the
simple vol-targeted book (net Sharpe **0.4659**) and the per-currency risk-reversal-hedged book
(**0.4559**) — **or** clear the desk's alternative route: a material MaxDD or CVaR₉₉ improvement at
≤ 0.02 net Sharpe cost, demonstrated per stress window.

---

## 6.1 The finding that governs the rest of the chapter

Stated first because it explains every result below.

**Where a hedge is applied decides whether it is worth having.** The same conditioning variable — the
25Δ risk reversal, i.e. what the option market charges for crash protection — produces opposite
verdicts depending on whether it is applied at the book level or per currency:

| Rule | Net Sharpe | MaxDD | CVaR₉₉ | Skew | Verdict |
|---|---|---|---|---|---|
| baseline (vol-targeted) | **0.4659** | −29.3% | 2.92% | −0.65 | — |
| IV/RR binary, **book level** | 0.3690 | −31.3% | 2.78% | — | **reject** — worse on both |
| Per-currency RR conditioning | 0.4559 | −27.6% | 2.72% | −0.60 | tail insurance, ~1 Sharpe point |

→ `stage3_dynamic_comparison.csv`

A book-level gate turns the entire portfolio off when aggregate risk indicators are elevated. It
therefore sells the premium in exactly the states where the premium is highest, and it does so
indiscriminately — including in the names that were not the problem. Per-currency conditioning halves
exposure only in the names whose *own* crash insurance has become expensive, which keeps the rest of
the book working.

The per-currency rule breaks dollar-neutrality by design: mean net FX exposure is −0.10, reaching
about −1.1 in the 2008 stress. **The long-USD tilt in crises is the hedge**, and it is reported as an
exposure rather than hidden as a side effect.

---

## 6.2 Stage 3 — no exposure-timing rule adds significant alpha

Six variants, gross and net, on both universes, each tested against the same-cost-basis baseline:

| Rule | G10 | Combined | Verdict |
|---|---|---|---|
| Vol targeting (vs static) | t −0.29 | t +0.51 | adopt as the sizing standard — no alpha claim |
| VIX threshold | t −1.15; CVaR₉₉ 3.2→2.7% | t −0.27; MaxDD −29→−25% | tail insurance only |
| IV/RR binary, book level | t −0.56; MaxDD −38→−31% | **t −1.69; Sharpe 0.47→0.37** | G10 tail only; **combined reject** |
| IV/RR linear ramp | t −0.24, mild tail gain | t −0.41, no tail gain | dominated |
| Per-currency RR | t +0.01; MaxDD −38→−34% | t −0.04; skew −0.65→−0.60 | tail insurance — **preferred** |

**Every |t| is below 1.7.** This is not a failure of implementation, it is what chapter 5 predicts:
carry compensates priced crash risk, so de-risking on elevated risk indicators sells the premium
roughly one-for-one with the risk avoided. A rule that reliably avoided the bad states without giving
up the premium would be evidence *against* the risk-premium explanation of why carry pays at all.

**Why these hedges are honestly costed, and why that matters.** Every hedge here scales **weights**,
not returns, so the cost model prices the reduced notional *and the trades the toggle triggers*. An
overlay applied to a return series is free, which flatters every risk-management rule ever tested —
and it was precisely the defect found in one of the five surveyed baselines. The book-level binary
hedge's rejection is largely a cost result: it trades a lot to buy a tail improvement it does not
reliably deliver.

---

## 6.3 Stage 4 — optimisation does not beat inverse volatility

Four within-leg weighting schemes, everything else held fixed and every variant re-vol-targeted to
10% so the comparison is scale-free:

| Scheme | Gross Sharpe | Net Sharpe | Turnover | MaxDD | Skew | α vs inv_vol (t) |
|---|---|---|---|---|---|---|
| **Inverse vol** (incumbent) | 0.63 | **0.47** | 0.68 | −29% | −0.65 | — |
| ERC | 0.59 | 0.44 | 0.63 | −32% | −0.56 | −0.2%/yr (−0.5) |
| Equal weight | 0.46 | 0.34 | 0.47 | −32% | −0.52 | −1.2%/yr (−1.8) |
| Mean-variance (μ = carry) | 0.46 | 0.32 | 0.70 | **−52%** | **−1.15** | −1.1%/yr (−0.8) |

→ `stage4_weighting_comparison.csv`, `weights_{scheme}_monthly.csv`

**Inverse volatility is the best net-of-cost scheme, and mean-variance is the worst track in the
project.** ERC is a near-tie — it shares inverse-vol's diagonal limit and only re-weights for
correlation — but its edge does not survive costs. Equal weight gives up Sharpe by ignoring the
volatility structure.

Mean-variance is instructive rather than merely bad. With μ set to noisy monthly carry it churns
(highest turnover), concentrates into the 40% position cap, and inherits a much fatter left tail
(−52% drawdown, −1.15 skew). It is a clean demonstration of optimising on estimation error: the
optimiser treats a signal with an R² of 0.01 as a return forecast and sizes accordingly.

Every scheme's alpha versus inverse-vol is ≤ 0 and insignificant. There is no net outperformance to
capture, and the incumbent choice is vindicated on evidence rather than assumed.

---

## 6.4 Stage 5 — momentum is dominated

Three combination methods across three lookbacks (21/63/252 days), both universes, gross and net:

| Family | Best ALL net Sharpe | MaxDD | vs pure carry (0.47 / −29%) |
|---|---|---|---|
| pure carry (baseline) | 0.47 | −29% | — |
| pure momentum | −0.02 to −0.33 | −52 to −73% | net money loser |
| double-sort filter | 0.37 (63d) | −51% | **dominated** — less Sharpe *and* worse tail |
| 50/50 z-blend | 0.16 (252d) | −49% | dominated |

→ `stage5_momentum_comparison.csv`, `stage5_track_correlation.csv`

Momentum does not reduce drawdown or CVaR₉₉ at less Sharpe cost than the Stage-3 hedges — it gives up
0.1 to 0.5 Sharpe **and worsens** the drawdown. The mechanism is mechanical: filtering thins each leg,
and vol targeting then levers up the more concentrated book.

Standalone momentum genuinely diversifies — near-zero correlation with carry, positive skew, lower
CVaR₉₉ — but loses money net, so it is not investable on its own here. It is retained as a regression
factor (chapter 5) and not as an allocation.

**The one apparent win is reported as mining rather than adopted.** The G10 blend at a 252-day
lookback beats its baseline. It is a single cell: only that lookback, only that universe, and gone in
the combined book. Reporting the peak of a sweep without the spread across the sweep is how a
backtest becomes a story, and the sweep is reported.

---

## 6.5 Stage 6 — regimes are a diagnostic, not a rule

Chapter 5 gave the descriptive payoff: carry is a calm-market phenomenon that earns nothing in
crisis. The allocation question is whether that can be traded.

| Variant | ALL net Sharpe |
|---|---|
| Moderate → 0.5, Crisis → 0.0 | **0.4830** |
| Crisis → 0.5 | 0.4697 |
| Crisis → 0.0 | 0.4660 |
| vol-targeted baseline | 0.4659 |
| per-currency RR | 0.4567 |
| VIX threshold | 0.4412 |

→ `stage6_regime_stats.csv`, `stage3_dynamic_comparison.csv`

*(Two figures for the per-currency RR book appear in this report and both are correct. This table
quotes the committed Stage-3 value, **0.4567**, because every other row here comes from the same
Stage-3/6 tables. Elsewhere — §6.1, chapters 7 and 9 — the bar is quoted as **0.4559**, which is the
same rule **rebuilt on the shared base**; it reproduces the committed drawdown to seven digits and
the Sharpe to 8e-4. Mixing the two inside one table would be the error, so they are kept apart and
the difference is stated rather than rounded away.)*

**No regime variant beats per-currency RR with significance — the maximum |t| across all of them is
0.59.** Crisis-only de-risking lands within a whisker of the baseline.

The best-looking cell deserves its caveat rather than a promotion. `reg_mod` gets its higher point
estimate by de-risking the **highest-Sharpe** regime (Moderate, Sharpe 0.94), which is a vol-scaling
artifact plus mild specification search — it was a beyond-spec sensitivity added after the two
pre-registered variants, and it is labelled as such.

**Verdict: reject as a replacement, adopt as a diagnostic.** The regime series is kept as an
interpretive lens and a feature source, and it is not traded.

---

## 6.6 Re-reading all of this on the objective the desk actually stated

Everything above was verdicted on Sharpe. On 29 July the desk stated a different objective: capital
preservation through the tail, because one large loss breaks the compounding path.

**That does not change a single number. It changes which number decides.** Stages 3 and 6 were
therefore re-read against a rule fixed before computing:

> **Accept iff the net Sharpe cost is ≤ 0.02 AND the rule buys ≥ 1.0pp of MaxDD OR ≥ 5% relative
> CVaR₉₉.**

**Five of twelve tail rules flip to accept:**

| Book | Rule | ΔSharpe | ΔMaxDD | ΔCVaR₉₉ | New verdict |
|---|---|---|---|---|---|
| ALL | VIX percentile gate | −0.0007 | **+4.82pp** | n/p | **ACCEPT** ⟵ flip |
| ALL | Per-currency RR | −0.0092 | +1.70pp | −6.9% | **ACCEPT** ⟵ flip |
| ALL | Regime Mod→0.5 / Crisis→0.0 | **+0.0171** | +3.75pp | −9.5% | **ACCEPT** ⟵ flip |
| G10 | Per-currency RR | −0.0030 | +4.54pp | −7.3% | **ACCEPT** ⟵ flip |
| G10 | IV/RR linear ramp | −0.0106 | +2.03pp | −9.5% | **ACCEPT** ⟵ flip |
| ALL | VIX *threshold* (Stage 3) | −0.0247 | +4.39pp | −7.3% | REJECT — misses the budget by 0.005 |
| ALL | IV/RR binary, book level | −0.0970 | −2.02pp | −4.9% | REJECT (unchanged) |

→ `p4_reverdict_tail_objective.csv` (13 rules, no re-runs — committed CSVs only)

The line worth saying out loud: **the VIX percentile gate costs 0.0007 of Sharpe and buys 4.8 points
of maximum drawdown and +0.021 of Calmar.** It was written up as a reject because the verdict column
was Sharpe.

**Three caveats travel with this table**, and they live in the CSV's own `note` column rather than
only here:

1. **`reg_mod` is the strongest cell on both objectives, and §6.5's caveat still stands.** It
   de-risks the highest-Sharpe regime, its alpha is insignificant (t 0.59), and it was a beyond-spec
   sensitivity. **A re-verdict is a re-reading, not a promotion.**
2. **Stage 3's VIX threshold is reported as the near-miss it is** rather than rounded either way: it
   buys 4.39pp of drawdown but costs 0.0247 Sharpe against a 0.02 budget.
3. **"Vol targeting versus static" is excluded from the flip count as a category error.** It is the
   sizing standard, not a timing rule — it levers a 7.6%-volatility book up to the 10% target, so its
   11pp deeper drawdown is the target working as designed. The row is kept in the CSV and labelled
   `tail_rule=False`. Dropping a row because a mechanical rule gives an awkward answer is the failure
   mode this project exists to avoid.

**This is the most consequential correction in the project**, and it does not move a number anywhere.
It says that a body of work can be entirely correct and still answer the wrong question, and that
the fix is to re-read the evidence against the stated objective rather than to run more of it.

---

## 6.7 What this chapter establishes

1. **On a Sharpe objective, all four standard responses fail.** No exposure-timing rule has
   significant alpha (all |t| < 1.7); optimisation does not beat inverse volatility; momentum is
   dominated; regime timing does not beat the simplest hedge.
2. **Where a hedge is applied decides whether it is worth having.** The same signal rejected at book
   level is the preferred tail hedge per currency.
3. **On the tail objective, five of twelve rules flip to accept** — including one available today
   with no new modelling.
4. **The surviving refinements buy tail, not return**, which is the through-line of the whole report
   and the reason chapter 7's combined book looks the way it does.

The verdicts and the bars they failed against are collected in chapter 9.
