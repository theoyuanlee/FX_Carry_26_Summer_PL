# BofA Summer Project Lab — FX Carry · deck material for 2026-08-05

*Cesare Bavaresco · shared base (`strategy/`) + integration track.*
*Assembled entirely from committed CSVs — no new computation. Every figure carries its source.*

The desk's four beats: **current results · what we did · what we have · what is next.**
Per the Jul 29 standing requirement, results are shown **per stress window first**; whole-sample
statistics are supporting evidence only.

---

## Slide 1 — The headline: we changed which number decides

> Under a **Sharpe** objective this project rejected tail protection four times.
> Under the objective the desk **actually stated on Jul 29**, it did not.

The verdict column was Sharpe. The desk's objective is capital preservation through the tail. We
re-read every Stage-3 and Stage-6 rule against a decision rule **fixed before computing**:

> **Accept iff the net Sharpe cost is ≤ 0.02 AND the rule buys ≥ 1.0pp of MaxDD OR ≥ 5% relative CVaR₉₉.**

**Five of twelve rules flip to ACCEPT.**

| Book | Rule | ΔSharpe | ΔMaxDD | ΔCVaR₉₉ | New verdict |
|---|---|---|---|---|---|
| ALL | **VIX percentile gate** (Dafu) | −0.0007 | **+4.82pp** | n/p | **ACCEPT** ⟵ flip |
| ALL | **Per-currency RR** | −0.0092 | +1.70pp | −6.9% | **ACCEPT** ⟵ flip |
| ALL | **Regime Mod→0.5 / Crisis→0.0** | **+0.0171** | +3.75pp | −9.5% | **ACCEPT** ⟵ flip |
| G10 | **Per-currency RR** | −0.0030 | +4.54pp | −7.3% | **ACCEPT** ⟵ flip |
| G10 | **IV/RR linear ramp** | −0.0106 | +2.03pp | −9.5% | **ACCEPT** ⟵ flip |
| ALL | VIX *threshold* (Stage 3) | −0.0247 | +4.39pp | −7.3% | REJECT — misses the 0.02 budget by 0.005 |
| ALL | IV/RR binary, book-level | −0.0970 | −2.02pp | −4.9% | REJECT (unchanged) |

**The single line to say out loud:** the VIX percentile gate costs **0.0007 of Sharpe** and buys
**4.8 points of maximum drawdown** and **+0.021 of Calmar**. It is available today, with no new
modelling.

*Source: `cesare/outputs/p4_reverdict_tail_objective.csv` (13 rules, no re-runs — committed CSVs only).*

**Three caveats travel with this table**, and they are in the CSV's own `note` column, not just here:
1. `reg_mod` is the strongest cell on *both* objectives, but §12's caveat stands — it de-risks the
   *highest-Sharpe* regime (Moderate, 0.94), its NW alpha is insignificant (t = 0.59), and it was a
   beyond-spec sensitivity. **A re-verdict is a re-reading, not a promotion.**
2. Stage 3's VIX threshold is reported as the near-miss it is, not rounded either way.
3. "Vol targeting vs static" is **excluded from the flip count** as a category error — it is the
   sizing standard, not a timing rule, so its deeper drawdown is the vol target working. The row is
   kept and labelled `tail_rule=False`; dropping a row because the mechanical rule gives an awkward
   answer is the failure mode we are trying to avoid.

---

## Slide 2 — Per stress window: answering the Jul 22 ask directly

Eight frozen stress windows, net of costs. Windows under 120 trading days quote cumulative return,
MaxDD and worst day — **never an annualised Sharpe**; annualising a ratio off 64 days of COVID is
noise wearing a decimal point. The code enforces this, not our memory.

| Window | n | Cum net | MaxDD | Worst day | |
|---|---|---|---|---|---|
| `gfc_2008` | 217 | −5.9% | −17.8% | −4.0% | Lehman |
| `euro_2011` | 392 | −5.1% | −19.0% | −4.9% | EZ sovereign |
| **`taper_2013`** | 109 | **−12.9%** | **−19.1%** | −4.0% | **see slide 3** |
| `china_em_2015` | 196 | −5.2% | −9.9% | −2.9% | CNY devaluation |
| **`covid_2020`** | 64 | **−19.6%** | **−24.0%** | −3.8% | worst window in the sample |
| `rates_2022` | 216 | **+25.5%** | −6.6% | −2.2% | **control — carry's best crisis** |
| **`oil_2026`** | 85 | **+10.1%** | **−1.8%** | −1.8% | desk-nominated, Jul 22 |
| **`semis_2026`** | 65 | **+11.7%** | **−1.8%** | −1.8% | desk-nominated, Jul 22 |

### The direct answer to the Jul 22 question

> **Neither 2026 shock was FX-carry stress.**

Both windows are *strongly positive* with a **−1.8%** drawdown. The oil and semiconductor shocks hit
equities and supply chains; they did not hit this book. That is a clean negative answer to a direct
question, and it cost half a day.

`rates_2022` is in the table deliberately as the **control**: carry's *best* crisis. Without it this
reads as a list of disasters chosen to flatter a hedge.

*Source: `cesare/outputs/p4_stress_table_baseline.csv`, reproducible from `strategy.episodes.STRESS`.*

---

## Slide 3 — We found the aggregation failure in our own tooling

> **The 2013 taper tantrum is the second-worst window in the sample, and it was invisible in every
> episode list this repo had.**

- Buried inside the "taper + EM 2013-16" era bucket — which shows a **positive** 0.29 Sharpe and
  +13% of total P&L.
- Absent entirely from the previous hard-coded six-window list.
- **−12.9% cumulative, −19.1% drawdown in five months.**

This is precisely the aggregation failure the desk complained about on Jul 29, found in our own
tooling rather than argued in the abstract. It is the concrete case for the standing per-window
requirement.

**Two further things it had been hiding.** Until this cycle the reporting layer returned an *empty
table* for any window shorter than 120 trading days — so `covid_2020` (64d), `oil_2026` (85d),
`semis_2026` (65d) **and `taper_2013` (109d)** were unreportable. Four of eight stress windows,
including both the desk named personally, and including the window we now use to make this argument.

*Source: `cesare/outputs/p4_stress_table_baseline.csv` vs `p4_episode_table_baseline.csv`.*

---

## Slide 4 — Where the risk sits and where the gains come from

The Jul 15 ask: decompose the rate differential, split long leg vs short leg. Annualised
contribution over 2007-05 → 2026-06, **reconciling to the book's gross return at 3.9e-17**:

| Leg | Annualised contribution |
|---|---|
| **carry, long leg** | **+14.31%** |
| carry, short leg | +2.47% |
| **spot, long leg** | **−10.43%** |
| spot, short leg | +0.67% |
| **total = gross** | **+7.03%** |

**Carry accrual is ~2.4× the realised P&L, and spot gives back over half of it — essentially all of
that on the long leg.**

Year by year:

> **Carry on the long leg is positive in all 20 years, including all 7 losing years.**
> Every losing year (2008, 2011, 2013, 2015, 2018, 2020, 2021) is a **spot** event on the long leg.
> Never a carry event.

### The one-line reframe

> **The trade is not "earn carry". It is "earn carry and survive spot."**

That reframes what risk management is *for* in this book, and it is why the desk's tail objective is
the right objective: the carry leg has never been the problem.

*Source: `cesare/outputs/p4_leg_decomposition.csv` (ME + QE + YE + annualised full sample).*

---

## Slide 5 — What we have / what is next

**What we have.** One shared base (`strategy/`, v1.1.0) that every workstream can be measured on:
27 currencies, 2007-05 → 2026-06, net of real bid/ask costs, benchmarked against investable carry
indices, with 23 acceptance tests green on every run. Frozen evaluation windows so "which episodes"
is no longer a per-person choice. The per-window standard is now enforced by code and written into
the contract teammates' AI agents read.

*Process evidence, one line:* two base defects were found by execution and fixed this cycle — short
windows were silently unreportable, and the roll-leg cost was billed on the rebalance grid rather
than the forward-tenor grid. Both fixes are **bit-identical at the committed baseline** (0.0e+00),
so no published number moved.

**What is next (Aug 12 / Aug 19).**
1. **Fold the six workstreams into one engine** — a composition layer, then an add-one-in *and*
   leave-one-out ladder with the slot criterion fixed in advance. Pre-registered prior, stated now so
   it cannot be spun later: **the combination is expected to be worth less than the sum of its parts.**
2. **Forecast the tail and bake it in** — the desk's central ask. It must beat a genuinely
   competitive incumbent: a single VIX percentile threshold. Twelve features on 230 monthly
   observations against one threshold — if it loses, that is the finding and we will report it.
3. **The null-results chapter** — three novel signals and four standard embellishments have failed
   to beat the simple book. That accumulated negative evidence is the most defensible thing this
   project has produced, and it is a report chapter, not a footnote.

---

### Appendix — baseline reconciliation

| Book | Gross Sharpe | Net Sharpe | MaxDD |
|---|---|---|---|
| `run()` — ALL, 27 names | 0.6284 | **0.4659** | −29.3% |
| `run("G10")` — 9 names | 0.1669 | 0.1191 | −38.2% |

Turnover 0.675470 · cost drag 1.8146611%/yr · `test_reconciliation.py` 12/12 ·
`test_episodes.py` 11/11.
