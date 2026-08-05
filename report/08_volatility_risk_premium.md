# 8. The volatility risk premium

*Chapter 8 of the final report. Draft, 2026-08-04.*
*Every number below is reproducible from a committed CSV in `cesare/outputs/`.*

---

## 8.0 Why this chapter is separate from chapter 9

Chapter 9 collects nine nulls. This one is not a null, and putting it there would misfile the only
result in the project that clears its pre-registered bar. It also is not a recommendation, and
putting it in the combined engine would misfile it the other way. It sits on its own because its
status is genuinely in between: **a real premium, measured on data we already own, that we cannot
yet prove is harvestable after costs.**

The distinction that makes it interesting is not statistical, it is structural. Every other idea in
this project asked the same question — *can some signal improve the carry sort?* — and the answer
was no nine times. This asks a different one: **is there a second, distinct premium in the same
data?** The answer to that appears to be yes.

**Status: adopted as a qualified positive for the report. Not folded into the `COMBINED` book.**
The reason is stated in §8.5 and is not negotiable: `COMBINED` is a costed, executable book, and
this strategy cannot be costed on the data in the repo. Folding an uncostable strategy into a costed
preset would undo the honesty the rest of the project was built on.

---

## 8.1 Per window first

Per guardrail §6.8, the window table leads. These books are **monthly**, so a stress window is a
handful of observations rather than a few hundred days. Annualised ratios are therefore suppressed
at *every* window length here — a stricter bar than the 120-trading-day rule the daily books use,
because a Sharpe computed on three monthly returns is not a number, it is a rounding artifact.

Cumulative return by stress window, gross of option bid/ask:

| Window | n (months) | carry | short_vol | vrp_xs | carry+short_vol |
|---|---|---|---|---|---|
| `gfc_2008` | 10 | −5.9% | −6.8% | **+40.4%** | −8.1% |
| `euro_2011` | 18 | −5.1% | **+63.7%** | +54.4% | +27.1% |
| `taper_2013` | 5 | −12.9% | −1.7% | −11.4% | −9.0% |
| `china_em_2015` | 9 | −5.2% | −7.3% | **+25.8%** | −6.9% |
| `covid_2020` | 3 | −19.6% | −21.7% | **+9.2%** | −17.8% |
| `rates_2022` | 10 | +25.5% | +5.5% | +34.5% | +15.8% |
| `oil_2026` | 4 | +10.1% | +17.3% | +15.5% | +17.8% |
| `semis_2026` | 3 | +11.7% | +17.0% | +16.5% | +27.3% |

→ `p3_d2_by_episode.csv`

Two readings, and the second matters more than the first.

**The directional short-vol book behaves exactly as theory says it should.** It loses in the GFC, in
the taper tantrum, in the China devaluation and worst of all in COVID (−21.7% in three months). It
is short a crash-risk premium, and it pays out in crashes. Nothing surprising here, and nothing
alarming: this is a premium being earned for bearing a risk that occasionally shows up.

**The cross-sectional book does not, and that is the problem.** `vrp_xs` is **positive in seven of
the eight stress windows**, including **+40.4% through the GFC with a drawdown of exactly zero** —
it did not have a single down month between September 2008 and June 2009 — and **+9.2% through
COVID**. A vega-neutral short-volatility strategy that makes money in every crisis in the sample,
with no drawdown in the worst one, is not a strategy that has proven it has no tail. It is a
strategy whose tail has not yet occurred. §8.4 shows where that comes from.

---

## 8.2 The premium exists, and it is not marginal

Selling one-month at-the-money implied volatility and paying realised volatility over the following
month earns a positive average in **20 of the 21 currencies with option coverage**. The single
exception, CHF, is −0.003 vol points, which is zero. **13 of the 21 are individually significant**
at a Newey–West t above 1.96.

Observation-weighted across all **4,565 currency-months**, the premium is **+0.69 volatility points
per month**, positive in **68%** of months.

| Largest | vol pts | NW t | | Smallest | vol pts | NW t |
|---|---|---|---|---|---|---|
| TRY | +2.83 | 3.79 | | CHF | −0.00 | −0.01 |
| THB | +1.89 | 5.02 | | AUD | +0.09 | 0.29 |
| INR | +1.42 | 6.35 | | NOK | +0.17 | 0.67 |
| KRW | +1.38 | 2.44 | | HUF | +0.23 | 0.79 |
| MXN | +1.00 | 2.89 | | SEK | +0.27 | 1.35 |

→ `p3_d2_premium.csv`

The cross-sectional pattern is the first warning sign and should be read now rather than in the
caveats: **the premium is concentrated in exactly the currencies whose volatility is managed** —
TRY, THB, INR, KRW — and is approximately zero in the free-floating majors. A large measured gap
between implied and realised volatility in a managed currency is partly a genuine risk premium and
partly compensation for a regime that has not broken during the sample.

---

## 8.3 The books

Monthly, vol-targeted to 10%, **gross of option bid/ask** — see §8.5, which is where that
qualification is cashed out rather than waved at.

| Book | Ann. return | Ann. vol | Sharpe | MaxDD | Skew | Hit rate | Worst month |
|---|---|---|---|---|---|---|---|
| carry (monthly, for comparability) | 5.4% | 11.5% | 0.4708 | −25.2% | −0.49 | 57.4% | −14.0% |
| **short_vol** (directional) | 18.4% | 14.4% | **1.2719** | −23.1% | **−2.13** | 78.4% | −21.8% |
| **vrp_xs** (vega-neutral cross-section) | 23.4% | 13.9% | **1.6891** | −23.4% | **+1.66** | 73.1% | −8.5% |
| carry + short_vol (50/50) | 14.1% | 14.4% | 0.9840 | **−18.0%** | −0.24 | 74.2% | −15.0% |

→ `p3_d2_books.csv`

The two skew numbers are the whole story in miniature. `short_vol` has a skew of **−2.13**: it is
short a crash premium and it looks like it. `vrp_xs` has a skew of **+1.66** — *positive* skew on a
short-volatility book, which is close to a contradiction in terms and is the strongest single piece
of evidence that its risk is unmeasured rather than absent.

---

## 8.4 It is not carry in disguise — but two thirds of it is a standing tilt

### The spanning test, which is the one every other idea failed

| Regression | α (ann) | t(α) | β | R² |
|---|---|---|---|---|
| `short_vol ~ CARRY` | **+3.33%** | **+4.58** | 0.51 | 0.16 |
| `CARRY ~ short_vol` | −0.19% | −0.30 | 0.32 | 0.16 |
| `vrp_xs ~ CARRY` | **+5.08%** | **+6.05** | −0.17 | 0.02 |
| `CARRY ~ vrp_xs` | +1.60% | +2.76 | −0.12 | 0.02 |

→ `p3_d2_spanning.csv`

**The volatility premium spans carry; carry does not span it.** `short_vol` earns +3.33%/yr over a
carry exposure at t 4.58, while carry earns nothing over it (t −0.30). That is the largest
t-statistic anywhere in this project, and it is the exact test that killed D1 and D3 — where carry
subsumed the candidate signal, not the other way round.

The cross-sectional book is different again and worth stating precisely: **`vrp_xs` and carry each
have significant alpha over the other** (t +6.05 and t +2.76), with an R² of 0.02 and a correlation
of −0.14. Neither spans the other because they are close to unrelated. That is a cleaner claim than
"it beats carry": it is a genuinely different source of return.

### And now the caveat that changes the reading

Removing the per-currency mean of the signal with an expanding, lagged average — that is, keeping
only the *timing* component and throwing away the standing tilt — does this:

| `vrp_xs` | Sharpe | MaxDD | Skew | CVaR₉₉ | Worst month |
|---|---|---|---|---|---|
| raw signal | **1.6891** | −23.4% | **+1.66** | 8.4% | −8.5% |
| currency-demeaned (pure timing) | **0.5473** | **−48.7%** | **−1.84** | 21.6% | −35.8% |

→ `p3_d2_static_vs_timing.csv`

**Two thirds of the Sharpe was a standing short position, not a timing signal.** And when the
standing tilt is removed, the positive skew *inverts* — +1.66 to −1.84 — and the drawdown doubles.
The strategy that remains looks exactly like what a short-volatility book is supposed to look like.

The standing shorts are **TRY, MXN, THB, KRW and INR** (`p3_d2_avg_weights.csv`), and the standing
longs are CHF, AUD, NZD, CAD and NOK. So the raw book is, on average, short volatility in five
managed EM currencies and long volatility in the free-floating majors, and it holds that position
more or less permanently. Its positive skew and its untouched GFC drawdown are properties of that
position, not of the signal.

This is guardrail §6.12 — the discipline that separated selection from de-risking in the combined
engine — applied to a different strategy, and it reaches the same kind of conclusion: **the
headline number is mostly a structural exposure, and the part that is genuinely a signal is much
smaller.** A 0.55 Sharpe with a −48.7% drawdown is not nothing, but it is a very different claim
from 1.69, and it is the one that should be defended.

---

## 8.5 It cannot be costed, and what we did instead

`data/raw` carries option **mids only**. There is no bid/ask on any volatility surface in this
repository, so the transaction cost of a strategy that trades volatility every month cannot be
computed. This is the same limitation that blocks a premium-paying option hedge (chapter 10).

Publishing a zero-cost Sharpe and caveating it in prose would be exactly the failure this project
has criticised elsewhere. Instead the module **solves for the breakeven** — the round-trip
volatility spread at which each book stops clearing both carry bars:

| Round-trip spread (vol pts) | carry | short_vol | vrp_xs | carry+short_vol |
|---|---|---|---|---|
| 0.00 | 0.471 | 1.272 | 1.689 | 0.984 |
| 0.10 | 0.471 | **1.022** | **1.074** | **0.826** |
| 0.25 | 0.471 | **0.650** | 0.188 ✗ | **0.585** |
| 0.50 | 0.471 | 0.043 ✗ | −1.114 ✗ | 0.188 ✗ |
| 1.00 | 0.471 | −1.076 ✗ | −3.064 ✗ | −0.543 ✗ |

→ `p3_d2_breakeven_cost.csv` (✗ = no longer clears both bars)

**The widest spread at which each book still clears both bars is 0.25 vol points for `short_vol`
and `carry+short_vol`, and 0.10 vol points for `vrp_xs`.**

That has to be read against the market. Interbank one-month at-the-money volatility in G10 trades
inside roughly 0.2 vol points round-trip; EM is materially wider. So:

- `short_vol` and the blend survive a G10-realistic spread, with little margin.
- **`vrp_xs` — the 1.69-Sharpe headline — does not.** It stops clearing the bar somewhere between
  0.10 and 0.25 vol points, which is *inside* G10 interbank, and its largest positions are in EM
  names where spreads are several times wider.

Combined with §8.4, the honest summary of the cross-sectional book is: two thirds of its return is a
standing tilt whose tail has not occurred, and the remaining third does not survive a realistic
spread. **It is a measurement, not a strategy.**

*(A correction to our own earlier write-up: plan §17.4 originally reported these breakevens as ~0.5,
~0.5 and ~0.25. Those are the first grid points at which each book **fails**, not the last at which
it passes, so every figure was one grid step too generous. The table above reads the
`beats_both_bars` column directly.)*

---

## 8.6 What would change the verdict

Two data purchases, and they are now the highest-value asks in the project:

1. **Option bid/ask.** Without it §8.5 is a breakeven statement rather than a result. With it, the
   short-vol book becomes either a strategy or a documented null, and the same purchase unblocks the
   premium-paying hedge that chapter 10 lists as a limitation.
2. **An investable FX volatility-carry index.** The carry book is validated against DBHVG10U and
   FXCTEM8 — external, investable series that confirm it trades the premium it claims to. There is
   no equivalent here, so nothing independently confirms that this construction is the premium
   rather than an artifact of our own implementation.

A third, cheaper improvement: realised volatility here is close-to-close. A range-based estimator
would be several times more efficient and needs OHLC spot, which is also unbought.

**These three gaps were the stated reason this direction was cut in the first place** (plan §17.3),
and running it has not closed any of them. It has established that there is something there worth
buying the data to test properly — which is a useful result, and a smaller one than the headline
Sharpe suggests.

---

## 8.7 Verdict

**A qualified positive.** The FX volatility risk premium is real, broad (20 of 21 currencies),
economically large, and — uniquely in this project — it survives the spanning test against carry
with the largest t-statistic we have measured anywhere (4.58). It is a genuinely different premium
in the same data, not another attempt to improve the carry sort, and that is why it succeeded where
nine other attempts failed.

It is **not** a recommendation, for three reasons that travel with it:

1. Two thirds of the cross-sectional Sharpe is a standing short in five managed EM currencies whose
   tail has not occurred inside 2007–2026. Strip it and 1.69 becomes 0.55, with the skew inverting
   and the drawdown doubling.
2. It cannot be costed on mids-only data, and the cross-sectional book's breakeven spread of 0.10
   vol points is inside G10 interbank, let alone EM.
3. The evidence is weaker by construction than D1's or D3's — close-to-close realised volatility, no
   external index to validate against.

It is therefore reported as the project's most interesting finding and its clearest data request,
and it stays out of the executable book.
