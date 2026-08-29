# 5. Return drivers and crash risk

*Chapter 5 of the final report. Draft, 2026-08-04.*
*Every number below is reproducible from a committed CSV in `evidence/`.*

---

## 5.0 The question this chapter answers

Chapter 4 established that the book earns 7.0%/yr gross, that the premium lives in EM, and that its
losses are spot events on the long leg. This chapter asks *why* — which is the question that decides
whether the strategy is a risk premium worth harvesting or a pattern that happened.

Three answers, in increasing order of how much they constrain what comes later:

1. **The economic licence.** The forward is a biased predictor of spot, and the bias is the premium.
2. **The factor identity.** This is a levered, risk-managed carry factor, not a new signal.
3. **The compensation.** Carry loads negatively on funding stress, which is the failure mode
   chapters 6 and 7 spend their time trying to manage.

---

## 5.1 The economic licence: the forward-premium puzzle holds in sample

Uncovered interest parity predicts that a currency trading at a forward discount will depreciate by
exactly that discount, leaving no excess return. Regressing the next-month spot change on the forward
premium should therefore give a slope of 1.

Pooled across 29 currencies and **6,713 currency-months**:

| | b | Newey–West t | R² | n |
|---|---|---|---|---|
| **Pooled** | **0.733** | **4.48** | 0.010 | 6,713 |

→ `uip_fama.csv`

The slope is 0.733, significantly different from zero but **materially below 1**. High-carry
currencies do depreciate — the slope is positive, so the market is not simply wrong about direction —
but they **do not depreciate enough to offset their rate advantage**. That gap is the carry premium,
and it is the whole trade.

Two honesty notes on this result, because it is doing a lot of work.

**The R² is 0.010.** The forward premium explains one percent of the variance of next-month spot
returns. This is not a forecasting relationship; it is a *risk premium* relationship. The trade earns
its return by being paid to bear something, not by predicting anything, and that distinction governs
everything in chapter 9: a strategy that tries to time when the premium will be paid is trying to
forecast a series with an R² of 0.01.

**Almost nothing is significant per currency.** Of the 29 individual regressions, only **IDR**
(b = −1.63, t = −2.45) and **TRY** (b = 0.84, t = 2.48) reach significance, and they point in
opposite directions. The result is a *pooled* one and should only ever be quoted as such. A
per-currency reading of this table would be noise.

---

## 5.2 The factor identity: levered HML, not a new signal

Regressing each track's daily returns on the Lustig–Roussanov–Verdelhan factors (DOL, the average
dollar return; HML_FX, the high-minus-low carry factor):

| Track | β on DOL | t | β on HML_FX | t | α (ann) | t(α) | R² |
|---|---|---|---|---|---|---|---|
| G10 gross | 0.333 | 10.1 | 0.619 | 15.0 | −0.2% | −0.11 | 0.349 |
| **Combined gross** | −0.139 | −5.2 | **1.392** | **42.5** | **+2.2%** | **1.56** | **0.692** |

→ `crash_regressions.csv`, `regression_lrv.csv`

**The combined book is approximately 1.4× the academic carry factor, with an R² of 0.69 and an alpha
of 2.2%/yr that is not statistically significant (t 1.56).** This is exactly what a well-built carry
sort should look like, and it is worth stating plainly rather than obscuring: **we have not
discovered a new signal.** What the construction adds over the raw factor is risk management —
inverse-volatility leg weights, a position cap, vol targeting, a realistic cost model — and the
information ratios against the investable indices (0.27 for G10, 0.50 for combined) say that sizing
adds value over the index construction. But the return source is the known one.

This matters for how the rest of the report is read. Every subsequent chapter is an attempt to
improve the *management* of a known premium, not to find a new one — with the single exception of
chapter 8, which is the only place a genuinely different premium appears.

A momentum factor is near-orthogonal: the combined track loads +0.16 on a momentum HML (t 6.1) with
its HML loading and alpha unchanged, and G10 loads +0.07 (t 1.7). Carry and momentum are close to
independent here, which is why chapter 9 can report that combining them adds nothing without that
being a statement about multicollinearity.

---

## 5.3 The compensation: what the book is short

If carry is a risk premium, the book should lose money when the risk it is being paid to bear
materialises. Controlling for DOL and HML_FX, and regressing on daily changes in FX implied
volatility, the 25Δ risk reversal, and the EMBI sovereign spread:

| Track | β ΔIV | t | β ΔRR | t | β ΔEMBI | t |
|---|---|---|---|---|---|---|
| G10 gross | −0.003 | **−5.98** | +0.006 | +2.89 | −0.011 | **−4.07** |
| Combined gross | −0.001 | −1.18 | −0.003 | −2.07 | −0.005 | **−3.91** |

→ `crash_regressions.csv`

**The robust result is the EMBI loading.** Both tracks load significantly negatively on changes in
the emerging-market sovereign spread — t −4.07 and t −3.91. When dollar funding tightens and EM
credit widens, this book loses money. That is the compensation story, and it is consistent across
both universes.

**A correction to our own earlier characterisation.** Internal notes described both tracks as loading
negatively on implied volatility "with t-statistics of roughly −4 to −6". That is true for G10
(t −5.98) but **not for the combined book, where the ΔIV loading is −1.18 and not significant**. The
combined book's measurable crash exposure is to *credit and funding stress*, not to FX volatility as
such. The distinction matters because it says which conditioning variable a hedge should key off, and
it partly explains why the volatility-based hedges in chapter 9 underperform the EMBI-adjacent ones.

**One coefficient must not be read at face value.** The G10 ΔRR loading is *positive* and significant
(+2.89), which would naively suggest the G10 book benefits when crash insurance gets more expensive.
It does not. ΔIV and ΔRR are correlated at 0.38, and in the multivariate specification ΔIV absorbs
the crash variation, leaving ΔRR to pick up the residual. This is collinearity, not a hedge property,
and it is flagged here because a reader scanning the table would otherwise draw the opposite
conclusion.

---

## 5.4 Where the premium is earned, conditionally

Splitting the vol-targeted book's returns by a lagged three-state regime classifier built from VIX,
aggregate FX implied volatility and the EMBI spread:

| Regime | n days | Ann. return | Ann. vol | Sharpe | Skew | Share of P&L |
|---|---|---|---|---|---|---|
| Low | 3,603 | 6.0% | 10.7% | 0.57 | −0.71 | 62% |
| Moderate | 822 | 10.6% | 11.3% | **0.94** | −0.27 | 25% |
| **Crisis** | 277 | **−0.0%** | **15.9%** | **−0.00** | **−0.98** | **0%** |

→ `stage6_conditional_by_regime.csv`, `regime_series.csv`

**The carry premium is a calm-market phenomenon.** It earns a Sharpe of 0.57 in Low and 0.94 in
Moderate, and **exactly nothing in Crisis at roughly 1.5× the volatility** — about 6% of days that
carry the crash risk and contribute none of the return. The crisis days are the recognisable ones:
the 2008 GFC, the 2015–16 China/EM episode, COVID 2020 and the 2022 risk-off.

This is the single most actionable diagnostic in the report, and it is also a trap. It obviously
suggests de-risking in Crisis. Chapter 9 records what happens when that is actually tested: because
the premium is *compensation* for exactly this risk, de-risking on elevated risk indicators sells
the premium roughly one-for-one, and no timing rule built on it produces significant alpha.

---

## 5.5 What was deliberately not tested

The original project outline listed MOVE, the TED spread, financial-conditions indices, inflation,
GDP, PMI, payrolls, industrial production and unemployment as candidate drivers. **These were not
downloaded and are not in this report.** Monthly macro releases have vintage and revision problems at
a daily evaluation frequency: using a final-revision GDP print to explain a daily return in the month
it was released is a lookahead, and correcting it properly requires a vintage database this project
does not have.

The daily, market-based proxy set used here — VIX, FX implied volatility, risk reversals, EMBI, DXY,
UST 2-year, 2s10s — was a deliberate substitution rather than an oversight, and it is stated as one.
The cost is that the report can say what the book is exposed to in market terms but not in
macroeconomic ones.

---

## 5.6 What this chapter establishes

1. The premium exists because the forward is a biased predictor (pooled b = 0.733, t 4.48), but the
   relationship has an R² of 0.01 — it is a risk premium, not a forecast.
2. The book is a levered carry factor (β 1.39 on HML_FX, R² 0.69) with insignificant alpha. The
   contribution is risk management, not signal discovery.
3. It is compensated for **funding and credit stress** (ΔEMBI t ≈ −4 on both tracks). Its exposure to
   FX implied volatility is significant in G10 only, not in the combined book.
4. It earns its return in calm and moderate markets and nothing at all in crisis, at higher
   volatility.

Point 4 is the opportunity every subsequent chapter chases, and point 3 is the reason they mostly
fail: you cannot avoid the bad states of a risk premium without giving up the premium.
