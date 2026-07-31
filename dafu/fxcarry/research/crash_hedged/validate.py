"""Pre-registered pipeline validation (tutorial §9 'success and kill criteria').

Checks, on the actual leg_returns/monthly_panel outputs:
 1. Tutorial anchor: the USDJPY 2026-06-30 row reproduces Example 1-3 numbers
    (25d premium 0.390%/mo of spot, 10d 0.146%, ATM(DNS) 0.913%).
 2. Floor identity (BEKR eq. 16 / Jurek eq. 10): when the option expires ITM,
    the Jurek hedged return equals its analytic floor; and no hedged return
    ever falls below the floor by more than numerical noise.
 3. Nesting: |mean(hedged - unhedged)| increases with hedge moneyness
    (10d < 25d < ATM), per universe.
 4. Premium monotone: prem_atm > prem_25d > prem_10d in >= 99% of rows.
 5. No-lookahead: signal/vol dated t, settlement at t+1 (structural check on
    the ret_month offset).
Run: python research/crash_hedged/validate.py
"""
import sys

import numpy as np
import pandas as pd
from scipy.stats import norm

from fxcarry import Black76

_MODEL = Black76()

TAU = 1 / 12
OUT = "research/crash_hedged/out"
legs = pd.read_parquet(f"{OUT}/leg_returns.parquet")
panel = pd.read_parquet(f"{OUT}/monthly_panel.parquet")
ok = True

# ---- 1. tutorial anchor row -------------------------------------------------
row = legs[(legs["ccy"] == "JPY") & (legs["month_end"] == "2026-06-30")]
r = row.iloc[0]
t1 = (abs(r["prem_25d"] * 100 - 0.390) < 0.02
      and abs(r["prem_10d"] * 100 - 0.146) < 0.01
      and abs(r["prem_atm"] * 100 - 0.913) < 0.03 and r["q"] == -1)
ok &= t1
print(f"1. tutorial anchor (JPY 2026-06): prem 25d {r['prem_25d']*100:.3f} "
      f"(0.390) 10d {r['prem_10d']*100:.3f} (0.146) atm {r['prem_atm']*100:.3f} "
      f"(0.913), short-JPY leg: {'OK' if t1 else 'MISMATCH'}")

# ---- 2. floor identity ------------------------------------------------------
# rebuild per-row floor for the jurek 25d arm and compare where ITM
p = panel.sort_values(["ccy", "month_end"]).copy()
base_is_fcu = p["pair"].str.endswith("USD")
p["S"] = np.where(base_is_fcu, p["spot_native"], 1 / p["spot_native"])
p["F"] = np.where(base_is_fcu, p["fwd_native"], 1 / p["fwd_native"])
p["Sn"] = p.groupby("ccy")["S"].shift(-1)
m = p.merge(legs[["ccy", "month_end", "q", "z_jurek_25d"]],
            on=["ccy", "month_end"], how="inner").dropna(
    subset=["Sn", "usd_1m", "vol_V_mid", "vol_25R_mid", "vol_25B_mid",
            "z_jurek_25d", "spot_native", "fwd_native"])
viol = worst = 0.0
n_itm = 0
for _, x in m.iterrows():
    r_d = x["usd_1m"]
    r_f = r_d - np.log(x["F"] / x["S"]) / TAU
    base_is_fcu = x["pair"].endswith("USD")
    # protection side: FCU put if long (q>0) else FCU call; map to quoted side
    sgn = -0.5 if (base_is_fcu == (x["q"] > 0)) else +0.5
    sig = (x["vol_V_mid"] + x["vol_25B_mid"] + sgn * x["vol_25R_mid"]) / 100
    cp = -1 if x["q"] > 0 else 1
    kind = "put" if cp < 0 else "call"
    if base_is_fcu:
        K = _MODEL.strike_from_delta(0.25, kind, x["F"], sig, TAU,
                                     base_rate=r_f)
    else:
        K_nat = _MODEL.strike_from_delta(0.25, "call" if cp < 0 else "put",
                                         x["fwd_native"], sig, TAU,
                                         base_rate=r_d)
        K = 1.0 / K_nat
    prem = _MODEL.value(kind, x["F"], K, sig, TAU,
                        discount=np.exp(-r_d * TAU))
    st = sig * np.sqrt(TAU)
    d1 = (np.log(x["F"] / K) + 0.5 * sig**2 * TAU) / st
    gd, gf = np.exp(r_d * TAU), np.exp(r_f * TAU)
    if x["q"] > 0:
        dlt = -np.exp(-r_f * TAU) * norm.cdf(-d1)
        qty = gf / (1 + gf * dlt)
        cap = (1 - qty * dlt) * x["S"] + qty * prem
        floor = (qty * K - gd * cap) / cap
        itm = x["Sn"] <= K
    else:
        dlt = np.exp(-r_f * TAU) * norm.cdf(d1)
        qty = gf / (1 - gf * dlt)
        cap = (1 + qty * dlt) * x["S"] - qty * prem
        floor = (gd * cap - qty * K) / cap
        itm = x["Sn"] >= K
    gap = x["z_jurek_25d"] - floor
    worst = min(worst, gap)
    if itm:
        n_itm += 1
        if abs(gap) > 1e-10:
            viol += 1
t2 = viol == 0 and worst > -1e-10
ok &= t2
print(f"2. floor identity: {n_itm} ITM leg-months, {int(viol)} violations; "
      f"min(z - floor) = {worst:.2e}: {'OK' if t2 else 'FAIL'}")

# ---- 3. nesting: mean give-up ordered by moneyness --------------------------
port = pd.read_parquet(f"{OUT}/portfolio_G10_EQL.parquet").dropna()
d10 = (port["z_unhedged"] - port["z_jurek_10d"]).mean()
d25 = (port["z_unhedged"] - port["z_jurek_25d"]).mean()
datm = (port["z_unhedged"] - port["z_jurek_atm"]).mean()
t3 = 0 < d10 < d25 < datm
ok &= t3
print(f"3. nesting (G10 EQL mean give-up %/yr): 10d {d10*1200:.2f} < "
      f"25d {d25*1200:.2f} < atm {datm*1200:.2f}: {'OK' if t3 else 'FAIL'}")

# ---- 4. premium monotone ----------------------------------------------------
pr = legs[["prem_10d", "prem_25d", "prem_atm"]].dropna()
frac = ((pr["prem_atm"] > pr["prem_25d"]) & (pr["prem_25d"] > pr["prem_10d"])).mean()
t4 = frac >= 0.99
ok &= t4
print(f"4. premium monotone atm>25d>10d in {frac:.1%} of rows: "
      f"{'OK' if t4 else 'FAIL'}")

# ---- 5. settlement offset ---------------------------------------------------
t5 = legs["ret_month"].equals(legs["month_end"] + pd.offsets.MonthEnd(1))
ok &= t5
print(f"5. settlement month = signal month + 1 in all rows: "
      f"{'OK' if t5 else 'FAIL'}")

# ---- 6. the overlay stays inside its own bound ------------------------------
# Proposition 4.1 of the spread-financed tutorial: the sold 25d / owned 10d
# structure can never lose more than |K25 - K10| / F beyond the premium it
# collected, whatever the settlement spot does.
ps = legs[["sell_25d", "buy_10d", "ps_carry_pickup", "ps_bound"]].dropna()
over = ps["sell_25d"] + ps["buy_10d"]
slack_lo = (over - (ps["ps_carry_pickup"] - ps["ps_bound"])).min()
slack_hi = (ps["ps_carry_pickup"] - over).min()
t6 = slack_lo > -1e-10 and slack_hi > -1e-10
ok &= t6
print(f"6. overlay within [collected-bound, collected] in all {len(ps)} "
      f"leg-months; worst slack {min(slack_lo, slack_hi):.2e}: "
      f"{'OK' if t6 else 'FAIL'}")

print("\nALL CHECKS PASS" if ok else "\nCHECKS FAILED")
sys.exit(0 if ok else 1)
