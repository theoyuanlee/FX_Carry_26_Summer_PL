# FX Carry — Data Shopping List

*Author: Cesare Bavaresco · created 2026-07-14.*
*Purpose: data that would let us **run D2 (FX volatility risk premium)** and **rerun D1 (skew) / D3 (basis)** on
stronger footing. Companion to [`FX_Carry_Strategy_Project_Plan.md`](FX_Carry_Strategy_Project_Plan.md) §17.*

Everything below is a *want*, not a blocker — D2 can run today on data already in `data/raw/`, and D1/D3 are
already complete (both null). This list is about making each analysis **better / more defensible / wider in
universe**, in priority order.

**All tickers are Bloomberg unless noted.** Where I'm not 100% sure of the exact ticker I say so — please
confirm the tenor code on the terminal (the *field* set and *resolution* are the parts to get right). Store any
pull under `data/raw/` in the same wide+long parquet convention as the existing groups, via `src/bloomberg_data.py`.

**Priority legend:** 🟢 free (already in repo — just use it) · 🔴 high (materially changes a result / unblocks a
window) · 🟡 medium (nice-to-have, sharpens) · ⚪ low (only if we pursue D4–D6).

---

## 0. Free wins — already in `data/raw/`, just unused (no purchase)

Verified present with full 2007→2026 coverage on 2026-07-14. **No data request needed — these are code changes,
flagged here so they aren't accidentally "bought" again.**

| Item | Where | What it unlocks |
|---|---|---|
| 🟢 **10Δ risk-reversals & butterflies** (`…10R{t}`, `…10B{t}`) | `g10_fx_options` / `em_fx_options` parquet | The option surface is a **5-point smile** (ATM, 25R, 25B, 10R, 10B), not the 3-point set the D1 helper assumes. Enables a proper **model-free (Bakshi–Kapadia–Madan) risk-neutral skewness** — the *correct* input for the Li–Sarno–Zinna SRP D1 tested with only a 25Δ smile-slope proxy. |
| 🟢 **ATM vol at 5 tenors** (1W/1M/3M/6M/1Y) | same | D2's entire **VRP term structure** (implied vs realized at each horizon) is available now. Also feeds D6 (term structure of carry). Notebooks currently read 1M only. |

> Action: extend `vol_surface_panel` callers to read `delta=10` and `tenor∈{1W,1M,3M,6M,1Y}`. This is the first
> thing to do before buying anything for D1/D2.

---

## 1. D2 — FX Volatility Risk Premium (the next analysis) 🔴/🟡

D2 = harvest implied − realized vol (sell rich vol), as a premium **distinct** from directional carry. The ATM
term structure (above) is enough to *start*. These make the return proxy cleaner and the result externally
validated — exactly how carry was validated against DBHVG10U.

| # | Item | Ticker(s) | Fields | Res | Range | Why we want it | Prio |
|---|---|---|---|---|---|---|---|
| 1.1 | **Investable FX vol-carry benchmark index** — the DBHVG10U analog for *vol* (a rules-based short-vol / vol-carry strategy index, G10 and EM if available) | *Confirm on terminal.* Candidates: a bank "FX Volatility Carry" / "Vol Premium" strategy index (e.g. DB `DBV…`, JPM, Barclays, UBS series) | `PX_LAST` | daily | 2007→now | External validation of our VRP construction (does our track track a real investable vol premium?) and a benchmark for the stats table. This is the single most valuable D2 add. | 🔴 |
| 1.2 | **OHLC daily spot** for the whole FX universe | existing spot tickers (e.g. `EUR Curncy`, `USDJPY`-style) | **`PX_OPEN`, `PX_HIGH`, `PX_LOW`** (we already have `PX_LAST`) | daily | 2007→now | Range-based realized-vol estimators (Garman–Klass / Parkinson / Yang–Zhang) are ~5× more efficient than close-to-close. Realized vol is *half* of VRP, so this directly sharpens the signal. Cheap — same tickers, extra fields. | 🔴 |
| 1.3 | **FX vol level / benchmark indices** (conditioners & controls) | `CVIX Index` (DB Currency Vol), `JPMVXYG7 Index` (JPM G7 vol), `JPMVXYEM Index` (JPM EM vol) | `PX_LAST` | daily | 2007→now | A ready aggregate implied-vol gauge to condition/normalize the VRP book and cross-check our own cross-sectional ATM mean. | 🟡 |
| 1.4 | **FX variance-swap rates** (if the terminal has history) | *Confirm on terminal* (variance-swap / vol-swap quotes per pair) | `PX_LAST` | daily | as far back as available | The *cleanest* model-free VRP (variance-swap fixing − realized variance) with no smile-integration approximation. Often thin history → treat as optional upgrade over the 5-point-smile BKM approach. | 🟡 |
| 1.5 | **MOVE index** (US rate vol) | `MOVE Index` | `PX_LAST` | daily | 2007→now | A vol-of-rates control/conditioner; also closes the Stage-2 "MOVE not downloaded" gap. Useful across D2 and D3. | 🟡 |

**Realized-vol note:** if intraday (e.g. 5-min) spot were ever available it would give the best realized variance,
but that is a large pull and **OHLC (1.2) captures most of the benefit** — do not buy intraday unless everything
else is done.

---

## 2. D1 — Crash-Risk-Premium (skew) Carry — rerun better 🟢/🟡

D1 is **done (null)**. Two things would make a rerun more defensible; the first costs nothing.

| # | Item | Ticker(s) | Fields | Res | Range | Why we want it | Prio |
|---|---|---|---|---|---|---|---|
| 2.1 | **Use the 10Δ wings we already have** (see §0) | — in repo — | — | — | — | Rebuild the SRP with true model-free risk-neutral skewness instead of the 25Δ RR/ATM slope proxy. If SRP *still* fails to beat carry with the correct construction, the D1 null is bulletproof. **Do this before buying 2.2.** | 🟢 |
| 2.2 | **Option surfaces for the 6 missing EM**: CLP, COP, IDR, MYR, PEN, PHP | `USDCLPV1M Curncy`, `USDCLP25R1M`, `USDCLP25B1M`, `USDCLP10R1M`, `USDCLP10B1M` (and 3M/6M/1Y); repeat for COP/IDR/MYR/PEN/PHP | `PX_LAST` (+`PX_BID`/`PX_ASK` for costs) | daily | 2007→now (NDF-vol history may be shorter/thin) | Lets D1 — and *every* option-based analysis (D2, Stage-6 regime IV, crash regressions) — run on the **full tradable 27** instead of the matched U21. Closes the standing "no option surfaces for these 6" gap in plan §5.2. | 🟡 |
| 2.3 | **Fuller strike grid (5Δ / 35Δ)** if cheap | `…5R{t}` / `…5B{t}` per pair | `PX_LAST` | daily | 2007→now | Marginal — 10Δ+25Δ+ATM is already enough for a solid BKM skew. Only worth it if the terminal gives it for free. | ⚪ |

---

## 3. D3 — Cross-Currency Basis / Dollar-Funding Carry — rerun better 🔴

D3 is **done (null)**, but it was crippled by two data limits, **both fixable**. This is where new data has the
highest chance of *changing* a verdict, because D3's failure was largely a universe/window artifact (7 restricted
EM names, a carry anchor that was itself negative on TRY).

### Correction to the plan's stated caveat
The plan/memory say "onshore fixings end 2024-09." **That is wrong.** Verified 2026-07-14: the onshore EM fixings
(BUBOR/WIBR/TRLIB/TELBOR/THFX/IRSWO/SHIF) and the NDFs/forwards **all run to 2026-06/07**. The true cap is the
**USD funding leg**: synthetic **USD LIBOR `US0001M`/`US0003M` was discontinued 2024-09-30**, so `interest_diff_vs_usd`
(and thus `cip_basis`) dies there. Replace that leg → the whole D3 window extends ~2 years for free-ish.

| # | Item | Ticker(s) | Fields | Res | Range | Why we want it | Prio |
|---|---|---|---|---|---|---|---|
| 3.1 | **USD OIS curve** (replace discontinued USD LIBOR leg) | USD **SOFR-OIS**: `USOSFR` curve (e.g. `USOSFR3 Curncy` ≈ 3M) and/or **Fed Funds OIS** `USSO` curve (e.g. `USSOC Curncy` ≈ 3M, longer history back to 2007); SOFR fixing `SOFRRATE Index` — *confirm exact 1M/3M tenor tickers* | `PX_LAST` | daily | 2007→now | Unblocks the D3 window to 2026 **and** modernizes the basis to the DTV-consistent OIS convention (Libor was always the wrong USD leg post-2008). Highest-leverage D3 fix. | 🔴 |
| 3.2 | **Direct G10 cross-currency basis swaps** (3M, + 1Y for term) | typical `xxBSy` form: EUR `EUBS3`, JPY `JYBS3`, GBP `BPBS3`, CHF `SFBS3`, AUD `ADBS3`, NZD `NDBS3`, CAD `CDBS3`, SEK `SKBS3`, NOK `NKBS3` — all `Curncy`; *confirm suffixes on terminal* | `PX_LAST` | daily | 2007→now | **The** upgrade. The repo can't compute a G10 basis (no onshore fixings), so D3 was stuck on 7 restricted EM. These are quoted market instruments → gives us the **G10 dollar-funding basis the Du–Tepper–Verdelhan literature actually studies**. Could flip D3 from "null on a weak EM universe" to a real test. | 🔴 |
| 3.3 | **EM OIS / local-swap rates** for a cleaner EM basis | per-name onshore OIS/IRS (e.g. MXN TIIE-OIS, ZAR, KRW-CCS-implied) — *confirm* | `PX_LAST` | daily | 2007→now | A basis off OIS (not onshore Libor-style fixings) is the modern definition; may also let us **add EM names beyond the 7** with tradable xccy basis (e.g. MXN, ZAR). | 🟡 |
| 3.4 | **Extend/refresh onshore fixings** (only if any lag) | existing onshore tickers (BUBOR/WIBR/TRLIB/TELBOR/THFX/IRSWO/SHIF) | `PX_LAST` | daily | keep current | Already run to 2026-07 — just keep them fresh on the next terminal pull. No new purchase. | 🟢 |

---

## 4. Optional — only if we pursue D4–D6 or want more Stage-2 controls ⚪

Not needed for D1/D2/D3. Listed so a single terminal session can grab everything.

| # | Item | Ticker(s) / Source | Fields | Res | Range | For |
|---|---|---|---|---|---|---|
| 4.1 | **CFTC IMM speculative positioning** (net non-commercial, G10 + MXN/BRL/ZAR) | CFTC COT report — **free at cftc.gov** (Legacy/TFF); or Bloomberg CFTC positioning tickers | net longs/shorts, open interest | **weekly** (Tue, released Fri) | 2007→now | **D5** — crowding / carry-unwind timing (the parked positioning thread). Thin EM coverage. |
| 4.2 | **REER / PPP real exchange rates** | **BIS effective exchange rates** (free, bis.org), broad+narrow; or Bloomberg `…REER` | index level | **monthly** | 2007→now | **D4** — a value factor (real-rate mean reversion) to add to carry+momentum+dollar. |
| 4.3 | **Multi-tenor forwards for all EM** (term structure of carry) | EM NDF/forward roots at 1W/1M/3M/6M/12M (G10 already has all five; some EM only partial) | `PX_LAST`,`PX_BID`,`PX_ASK` | daily | 2007→now | **D6** — harvest forward-curve slope / roll-down rather than the single 1M point. |
| 4.4 | **TED spread / US financial-conditions index** | `... TED`, a FCI series (e.g. Bloomberg US FCI, Chicago Fed NFCI free from FRED) | `PX_LAST` | daily/weekly | 2007→now | Stage-2 controls; funding-stress conditioners alongside MOVE (1.5) and the basis-stress index. |

---

## Priority summary — if you only pull a few things

1. 🟢 **Nothing to buy first:** wire up the **10Δ wings** and **5-tenor ATM** already in `data/raw/` (§0). That
   alone lets D2 start and D1 rerun properly.
2. 🔴 **For D3 (best shot at changing a verdict):** **USD SOFR-OIS leg** (3.1) + **G10 xccy basis swaps** (3.2).
3. 🔴 **For D2 (cleaner + validated):** **investable FX vol-carry benchmark** (1.1) + **OHLC spot** (1.2).
4. 🟡 **For D1 full-universe:** the **6 missing EM option surfaces** (2.2).

Everything else is sharpening or future-direction (D4–D6).
