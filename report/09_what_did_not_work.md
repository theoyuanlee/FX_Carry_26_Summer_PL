# 9. What did not work

*Chapter 9 of the final report (plan §14.3 item 7). Draft 2026-08-03; D1 restated on model-free skewness 2026-08-04.*
*Every number below is reproducible from a committed CSV in `cesare/outputs/`.*

---

## 9.0 Why this is a chapter and not a footnote

Over nineteen years of daily data, **nine** distinct attempts to improve on a simple
vol-targeted, inverse-vol-weighted EM-plus-G10 carry book have failed to beat it net of costs.
Four were standard embellishments from the literature. Three were deliberately non-standard signals
built to differentiate this project. Two came out of the August integration work. Every one of them
was specified with a falsifiable bar *before* it was run, and every one is reported here with the
bar it failed against.

That accumulated negative evidence is the most defensible thing this project has produced. A desk
deciding whether to allocate to FX carry is better served by knowing which nine improvements do not
work than by a tenth backtest that does — because the nine were all things a reasonable person would
have tried, and each one would have cost money to discover live.

**The bar, unchanged throughout.** Any variant must beat, net of costs and with Newey–West
significance, *both* the simple vol-targeted book (**ALL net Sharpe 0.4659**) and the
per-currency-risk-reversal-hedged book (**0.4559** rebuilt on the shared base) — **or** clear the
desk's alternative: a material MaxDD / CVaR₉₉ improvement at ≤ 0.02 net Sharpe cost, demonstrated
per stress window rather than whole-sample.

---

## 9.1 The four standard embellishments

### Crash hedging does not add alpha (Stage 3)

No exposure-timing rule has significant net alpha on its baseline — **all |t| < 1.7**. This is not a
failure of implementation; it is what the theory predicts. Carry compensates priced crash risk, so
de-risking on elevated risk indicators sells the premium roughly one-for-one.

The refinement that matters: the *book-level* binary IV/RR hedge is **rejected outright** for the
combined book net of costs (0.4659 → 0.3690, with a *worse* drawdown), while *per-currency* RR
conditioning buys the tail improvement (skew −0.65 → −0.60, CVaR₉₉ 2.9% → 2.7%) for about one
Sharpe point. Where the hedge is applied decides whether it is worth having.

→ `stage3_dynamic_comparison.csv`

### Optimization does not beat inverse vol (Stage 4)

Equal-weight, ERC and mean-variance were all compared against inverse-vol with everything else held
fixed and every variant re-vol-targeted, so the comparison is scale-free.

| Scheme | Net Sharpe | MaxDD | Skew | α vs inv_vol (t) |
|---|---|---|---|---|
| Inverse vol (incumbent) | **0.47** | −0.29 | −0.65 | — |
| ERC | 0.44 | −0.32 | −0.56 | −0.2%/yr (−0.5) |
| Equal weight | 0.34 | −0.32 | −0.52 | −1.2%/yr (−1.8) |
| Mean-variance (μ = carry) | 0.32 | −0.52 | −1.15 | −1.1%/yr (−0.8) |

**Mean-variance is the worst track in the entire project.** With μ set to noisy monthly carry it
churns (highest turnover), concentrates into the position cap, and inherits a much fatter left tail
— a textbook demonstration of optimizing on estimation error.

→ `stage4_weighting_comparison.csv`

### Momentum is dominated (Stage 5)

Both combination methods give up Sharpe *and* worsen the drawdown: the double-sort filter reaches
0.37 with a −51% drawdown, the 50/50 blend 0.16 with −49%, against pure carry's 0.47 / −29%.
Filtering thins each leg, and vol targeting then levers up the concentrated book.

Standalone momentum genuinely diversifies (near-zero correlation with carry, positive skew, lower
CVaR₉₉) but loses money net, so it is not investable here. The one apparent win — the G10 blend at a
252-day lookback — is a **single cell**: only that lookback, only that universe, gone in the combined
book. That is lookback mining, and it is reported as such rather than adopted.

→ `stage5_momentum_comparison.csv`

### Regime timing is a diagnostic, not a rule (Stage 6)

The regime lens is genuinely informative. Carry is a calm-market phenomenon: Sharpe 0.57 in Low,
0.94 in Moderate, and **0.00 in Crisis at roughly 1.5× the volatility** — about 6% of days carrying
the crash risk and contributing nothing.

But as an *allocation* rule it fails. No regime variant beats per-currency RR with significance
(max |t| = 0.59). The best-looking variant (Moderate → 0.5, Crisis → 0.0) gets its edge by de-risking
the **highest-Sharpe** regime, which is a vol-scaling artifact plus mild specification search. Adopt
the regime series as a lens; do not trade it.

→ `stage6_regime_stats.csv`, `stage6_conditional_by_regime.csv`

---

## 9.2 The three novel signals (Phase 3)

These were the attempts to find something the literature had not already priced, using data most
carry books do not have: full FX option surfaces, onshore EM fixings, multi-tenor forwards.

### D1 — option-implied skew: null, and the published claim reverses

Five variants on the matched 21-name option universe. **None beats the matched vanilla carry book
(0.496)**, let alone the published bars, and every net alpha versus carry is negative.

The flagship test was Li–Sarno–Zinna's claim that a skewness risk premium (SRP) *subsumes* carry.
That claim is defined on **model-free** risk-neutral skewness, and the first version of this test
did not use one — it used the 25Δ risk-reversal/ATM smile slope as a proxy, because
`fx_utils.implied_skew_panel`'s docstring asserted that a Bakshi–Kapadia–Madan measure "would need
the whole strike chain, which the 3-point (ATM/RR/BF) surface here does not provide".

**That assertion was false.** The surface is five-point: 10Δ risk reversals and butterflies are
present for all 21 names with the same coverage as the 25Δ pair, and five points are enough to
interpolate a smile and integrate it. So the test was rebuilt properly — a Breeden–Litzenberger
risk-neutral density from the five-point smile, then its third central moment
(`cesare/bkm_skew.py`) — and re-run. **The rebuild is licensed by an exact reconciliation:** the
proxy variants reproduce the originally committed D1 numbers to four decimals, so the only thing
that changes between the two runs is the risk-neutral leg.

| Variant | 25Δ slope proxy | model-free BKM | α vs carry (t) |
|---|---|---|---|
| U21 carry (anchor) | 0.4962 | 0.4962 | — |
| implied skew, long crash-priced | 0.1316 | **0.0339** | −4.00%/yr (**−2.36**) |
| skewness risk premium | −0.0906 | **−0.0611** | −3.06%/yr (−1.39) |
| clean carry (Jurek) | −0.0309 | −0.0684 | −3.16%/yr (−1.33) |

Spanning, now on the construction the claim is actually about:

| Regression | α (ann) | t(α) | β | R² |
|---|---|---|---|---|
| SRP ~ CARRY | −0.18% | −0.16 | 0.30 | 0.16 |
| CARRY ~ SRP | **+3.22%** | **+2.23** | 0.53 | 0.16 |

**Carry subsumes SRP, not the other way round — and the null is no longer contingent on an
approximation.** Sorting on model-free crash pricing is now *significantly* worse than carry
(t −2.36, where the proxy gave an insignificant −1.59). The option market's crash pricing is
economically real, and Stage 2 measures it, but it is not a tradable edge over the simple book.

**The durable finding here is methodological, and it outlives the null.** The proxy and the
model-free measure agree strongly on *which* currencies are crash-priced — cross-sectional rank
correlation **0.886**, with an economically sensible pattern (JPY and CHF the only positive names,
i.e. the funding currencies that rally in crises; TRY, MXN, BRL and ZAR the most crash-priced). But
they barely agree on *month-to-month changes at all*: median per-currency change correlation
**0.0198**. A pooled level correlation of 0.98 hides this completely, because it is mostly
cross-sectional level dispersion. **The 25Δ smile slope is a good cross-sectional proxy for
risk-neutral skewness and a nearly useless time-series one** — which is why a cross-sectional sort
was insensitive to the upgrade, and why anyone using the risk reversal as a *timing* signal should
not.

The wrong docstring has been corrected. Recording why it mattered: it was not a harmful claim, it
was an *unchecked* one, and it is the fourth time in this project that a confidently stated
"the data does not support this" turned out to be untested.

→ `p3_d1_bkm_comparison.csv`, `p3_d1_bkm_spanning.csv`, `p3_d1_bkm_signal_agreement.csv`,
`skew_carry_comparison.csv`, `srp_carry_spanning.csv`

### D3 — cross-currency basis: null, and honestly a weak test

The basis is only measurable where onshore fixings exist, which confines the tradable universe to
seven restricted EM names — and on *that* universe the matched vanilla carry book is itself
**negative (−0.32)**. Every basis variant is negative too; chasing the most dollar-short names is
significantly worse (t = −2.8).

**This null is reported with its limitation attached rather than as a clean result.** Two fixable
data problems crippled it: the USD LIBOR funding leg was discontinued 2024-09-30 (a SOFR-OIS leg
would extend the window ~2 years), and the universe contains no G10 at all, because the G10
dollar-funding basis the literature studies needs quoted basis swaps this repo does not have. D3 is
the Phase-3 result most likely to change with better data, and saying so is part of reporting it.

→ `basis_carry_comparison.csv`, `basis_carry_spanning.csv`

### D6 — term structure of carry: null, and the 1M point dominates

| Tenor | Gross Sharpe | Net Sharpe | Turnover | Cost drag |
|---|---|---|---|---|
| **1M** | **0.6284** | **0.4659** | 0.675 | 1.81%/yr |
| 3M | 0.4875 | 0.3501 | 0.526 | 1.55%/yr |
| 6M | 0.5148 | 0.3697 | 0.450 | 1.64%/yr |
| 12M | 0.5657 | 0.3995 | 0.426 | 1.87%/yr |

Holding longer-dated carry gives up return without buying anything, on gross **and** on net.

This table is also a methodological warning. Before the cost model was fixed, the net column showed
drag *rising* from 1.81% to 4.84%/yr while turnover *fell* — an impossible combination that turned
out to be a real defect: the roll leg was billed on the rebalance grid rather than the forward-tenor
grid. The direction of the D6 result never changed, but for a while it rested on reading only the
gross column.

→ `tenor_sweep.csv`

---

## 9.3 The integration nulls (Phase 4, August)

### The macro/regime probability gate does not survive being put on a real book

Re-priced on the shared base, the gate takes the book from **0.4659 to 0.0964** — the single most
destructive component tested in this project. Removing it from the combined stack improves net
Sharpe by **+0.33**.

The diagnostic is more interesting than the number. The gate's correlation with VIX is
**≈ 0 at every lead and lag** (−0.014 same month, −0.004 previous, +0.069 next). It de-risks roughly
half of all months with no discernible relationship to market stress. That is consistent with how it
was fitted: on a book whose returns omitted the carry accrual entirely, and which was therefore
losing money it should have been earning. A gate trained to cut losses on a book that should not
have been losing has learned to switch off a profitable strategy.

**The verdict does not depend on a judgement call.** The lag convention is ambiguous — the committed
outputs do not record whether the multiplier is dated at the decision month or the month it scaled —
and the gate fails badly under both (0.0964 and 0.0525).

→ `p4_component_standalone.csv`, `p4_combined_ladder.csv`

### The tail-event forecast does not beat one VIX threshold

The desk's central ask, run as a pre-registered falsification exercise: predict
P(next-month book return in the worst decile), sixteen features, ~228 monthly observations, purged
walk-forward (`min_train=60, test_size=12, embargo=1`), L2 logistic, everything fitted inside the
fold including the tail threshold and the scaler.

**Mean out-of-sample AUC across 13 purged folds: 0.4685** — worse than a coin flip.

| Bar | Result |
|---|---|
| Beat 0.4659 / 0.4559 net Sharpe | **NO** — 0.4179 |
| Beat the VIX gate on Sharpe *and* MaxDD | **NO** — ΔSharpe −0.047, ΔMaxDD −4.23pp |
| Tail route (≤0.02 Sharpe cost, ≥1pp MaxDD) | **NO** — ΔSharpe −0.048, ΔMaxDD +0.58pp |

Two honest caveats on the *test*, not on the verdict: **7 of 13 folds contain no tail month at all**
in their test block, so AUC is undefined there — with ~23 tail months in the whole sample, this
question may simply not be answerable at monthly frequency on nineteen years of data. And the
fitted coefficients are not stable enough to read as an economic ranking (reported with a
`sign_stability` column so nobody does).

**Per the pre-registered protocol the model was not iterated to make it win.** The finding is that
sixteen features and a cross-validation scheme lose to one threshold on one series — which is a real
answer to "should we forecast the tail?", and a cheaper one than finding out later.

→ `p4_tail_forecast_eval.csv`, `p4_tail_overlay_stats.csv`, `p4_tail_feature_importance.csv`

---

## 9.4 The finding that changes how the successes should be read

Two components *did* earn a slot in the combined engine (Chapter 6). One of them — a bad-skew
exclusion filter — posts a spectacular tail improvement: maximum drawdown −29.3% → −22.0%, CVaR₉₉
−29%, and better numbers in **all six** pre-2026 stress windows.

Almost none of that is the signal.

An exclusion filter does two things at once: it drops *particular* names, and it leaves the book
holding *less notional*. A shallower drawdown follows mechanically from the second whatever the
first is worth. Running a control that reproduces the filter's **exact daily gross exposure**
(matched to 8.9e-16) but spreads the reduction uniformly across every name:

| Book | Net Sharpe | Ann vol | MaxDD | CVaR₉₉ | Skew |
|---|---|---|---|---|---|
| Baseline | 0.4659 | 11.2% | −29.3% | 0.0292 | −0.65 |
| Gross-matched de-risk (**control**) | 0.4062 | 8.5% | −22.5% | 0.0222 | −0.63 |
| Bad-skew exclusion | 0.4360 | 8.9% | −22.0% | 0.0206 | **−0.31** |

Of the 7.3pp drawdown improvement, **6.8pp is de-risking and 0.5pp is selection.** The Newey–West
alpha of the filter over its own gross-matched control is +1.25%/yr with **t = 0.92** — inside noise,
like everything else in this chapter.

The one thing selection genuinely buys is **skew: −0.63 → −0.31**, which de-risking does not deliver
at all. That is a real and useful property. It is also a much smaller claim than the headline
drawdown number, and reporting the headline without this control would have been the most
misleading number in the project.

**Generalisation, and the reason this section exists:** any overlay that zeroes or trims positions
should be reported against a de-risking control that matches its gross. Otherwise "my filter cut the
drawdown by a third" means "my filter holds a third less risk", which the reader could have achieved
by halving the position size.

→ `p4_selection_vs_derisking.csv`

---

## 9.5 The through-line

> The 2007–2026 carry premium lives in EM, and it is compensation for crash risk. Every attempt to
> avoid the crash — by hedging it, by optimizing around it, by timing it with momentum, regimes,
> option skew, the dollar-funding basis, the forward curve, a macro probability model, or a
> supervised tail forecast — sells the premium at roughly the same rate it removes the risk.

That is not nine unlucky results. It is one economic fact observed nine times, and it is the finding
this project would defend in front of the desk.

**What follows from it, practically.** Risk management in this book should be judged on the tail and
priced honestly, not sold as alpha: the two components that earned a slot in Chapter 6 buy drawdown
and skew, and their Sharpe contributions are statistically indistinguishable from zero — max |t| =
1.16 anywhere in the ladder. A desk running this strategy should size it for the crash it will
take, not hope to dodge it.
