"""Crash-hedged carry: Jurek crash-neutral ladder + BEKR ATM overlay.

Implements, per currency-month in the USD-per-FCU quote (S$ = dollars per
foreign unit, so every pair is oriented the same way and payoffs are in USD):

- Unhedged carry (Jurek 2009 WP eq. 5 via CIP): long FCU iff the FCU trades
  at a forward discount in FCU-per-USD terms (fwd_disc > 0), else short;
  excess return z = q * e^{r_d tau} * (S'/F - 1), q = +/-1.
- Jurek crash-neutral hedge (eqs. 8-13): long leg holds (1 - q_p*d_p) FCU
  spot + q_p puts, q_p = e^{r_f tau}/(1 + e^{r_f tau} d_p); short leg is the
  mirror with calls. Payoff flat beyond the strike; delta-hedged at
  initiation; premium financed at r_d; return on hedged funding capital.
  Strikes: spot-delta inversion (his eq. 17 = optmath pips closed form) at
  10d/25d; ATM = delta-neutral straddle K = F e^{s^2 tau/2} (his eq. 18).
- BEKR overlay (w14054 eq. 14): same forward book plus 1/F options at the
  ATM-FORWARD strike (their JPM arm), premium financed at r_d. Not
  delta-hedged - the construction wedge Jurek's fn. 13 points at.

Vol orientation: quoted RR/BF are call-minus-put on the pair's BASE. For
XXXUSD pairs base = FCU, so FCU-call vol = atm + bf + rr/2; for USDXXX pairs
an FCU put is the quoted call side. Deltas follow Jurek: uniform spot delta,
premium-unadjusted, all pairs (convention risk logged; market-convention
robustness arm later).

Rates: r_d = US 1M bill (as continuous), r_f = r_d - 12*ln(F$/S$) by CIP.
Outputs: out/leg_returns.parquet (per ccy-month, all arms), out/summary.csv.
Run: python research/crash_hedged/hedged_carry.py
"""
from __future__ import annotations

import pathlib
import sys

import numpy as np
import pandas as pd
from scipy.stats import norm

from fxcarry import Black76, Smile

_MODEL = Black76()


def _smile_vol(atm, rr, bf, side):
    """One wing off a three-number quote, atm + bf +- rr/2.

    The library's own algebra by way of `Smile`. Units pass straight through, so
    vol points in gives vol points out. The delta key is arbitrary because only
    one wing is ever built per call.
    """
    return Smile(atm=atm, risk_reversal={25: rr}, butterfly={25: bf}).vol(25, side)

OUT = pathlib.Path("research/crash_hedged/out")
TAU = 1.0 / 12.0
G10 = ["AUD", "CAD", "CHF", "EUR", "GBP", "JPY", "NOK", "NZD", "SEK"]
ARMS = [("10d", 0.10), ("25d", 0.25), ("atm", None)]


def fcu_side_vols(row, side, field="mid"):
    """Vol (decimal) of an FCU call ('c') or FCU put ('p') at 25/10 delta and
    ATM, from the quoted pair smile. Quoted RR/BF reference the pair's base."""
    base_is_fcu = row["pair"].endswith("USD")
    quoted_side = ("call" if side == "c" else "put") if base_is_fcu else \
                  ("put" if side == "c" else "call")
    out = {"atm": row[f"vol_V_{field}"] / 100.0}
    for d in (25, 10):
        out[f"{d}d"] = _smile_vol(row[f"vol_V_{field}"],
                                  row[f"vol_{d}R_{field}"],
                                  row[f"vol_{d}B_{field}"],
                                  quoted_side) / 100.0
    return out


def leg_returns(row, field="mid", orientation="native"):
    """All arms' one-month excess returns for one currency-month.

    orientation="native": strikes from the quote's native-pair delta (what
    Bloomberg deltas mean) — headline. "uniform": Jurek's uniform $/FCU
    spot-delta convention — robustness arm.
    """
    S, F = row["spot_usd_per_fcu"], row["fwd_usd_per_fcu"]
    Sn = row["spot_next"]
    r_d = row["usd_1m"]
    r_f = r_d - np.log(F / S) / TAU
    q = 1.0 if row["fwd_disc"] > 0 else -1.0          # +1 = long FCU
    grow_d, grow_f = np.exp(r_d * TAU), np.exp(r_f * TAU)

    res = {"q": q, "z_unhedged": q * grow_d * (Sn / F - 1.0)}

    side = "p" if q > 0 else "c"                       # protection direction
    vols = fcu_side_vols(row, side, field)
    cp = -1 if q > 0 else +1                           # FCU put / FCU call

    base_is_fcu = row["pair"].endswith("USD")
    S_nat, F_nat = row["spot_native"], row["fwd_native"]
    strikes, prem_fcu = {}, {}
    for arm, delta in ARMS:
        sig = vols[arm]
        if not np.isfinite(sig) or sig <= 0:
            res[f"z_jurek_{arm}"] = np.nan
            res[f"prem_{arm}"] = np.nan
            continue
        # Strikes from the quote's NATIVE orientation (what Bloomberg deltas
        # mean), then converted to $/FCU. For XXXUSD pairs native IS $/FCU.
        # orientation="uniform" reads deltas in $/FCU (Jurek's convention).
        kind = "put" if cp < 0 else "call"
        kind_nat = "call" if cp < 0 else "put"         # inverted pair flips it
        if orientation == "uniform" or base_is_fcu:
            if delta is None:
                K = _MODEL.atm_strike(F, sig, TAU)
            else:
                K = _MODEL.strike_from_delta(delta, kind, F, sig, TAU,
                                             base_rate=r_f)
        else:
            if delta is None:                          # native DNS ATM strike
                K_nat = _MODEL.atm_strike(F_nat, sig, TAU)
            else:                                      # FCU put = USD call
                K_nat = _MODEL.strike_from_delta(delta, kind_nat, F_nat, sig, TAU,
                                                 base_rate=r_d)
            K = 1.0 / K_nat
        prem = _MODEL.value(kind, F, K, sig, TAU,      # $ per FCU notional
                            discount=np.exp(-r_d * TAU))
        st = sig * np.sqrt(TAU)
        d1 = (np.log(F / K) + 0.5 * sig**2 * TAU) / st
        res[f"prem_{arm}"] = prem / S                  # per $ of spot capital
        strikes[arm], prem_fcu[arm] = K, prem

        if q > 0:                                      # long FCU + put
            d_p = -np.exp(-r_f * TAU) * norm.cdf(-d1)
            qty = grow_f / (1.0 + grow_f * d_p)        # = e^{rf tau}/N(d1)
            capital = (1.0 - qty * d_p) * S + qty * prem
            payoff = qty * max(K, Sn) - grow_d * capital
            floor = (qty * K - grow_d * capital) / capital
        else:                                          # short FCU + call
            d_c = np.exp(-r_f * TAU) * norm.cdf(d1)
            qty = grow_f / (1.0 - grow_f * d_c)
            capital = (1.0 + qty * d_c) * S - qty * prem
            payoff = grow_d * capital - qty * min(K, Sn)
            floor = (grow_d * capital - qty * K) / capital
        res[f"z_jurek_{arm}"] = payoff / capital
        res[f"floor_{arm}"] = floor

    # BEKR overlay at the ATM-forward strike, notional 1/F, not delta-hedged
    sig = vols["atm"]
    if np.isfinite(sig) and sig > 0:
        prem = _MODEL.value("put" if cp < 0 else "call", F, F, sig, TAU,
                            discount=np.exp(-r_d * TAU))
        opt_payoff = max(cp * (Sn - F), 0.0)
        res["z_bekr_atmf"] = (res["z_unhedged"]
                              + (opt_payoff - prem * grow_d) / F)
        res["prem_bekr"] = prem / F
    else:
        res["z_bekr_atmf"] = np.nan
        res["prem_bekr"] = np.nan

    # Spread-financed carry (the strategy the measurement points at):
    # vanilla position + SHORT the 25d/10d put-spread on the leg's crash
    # side (sell the overpriced 25d protection, buy the cheap 10d wing),
    # BEKR-style 1/F notionals. Versus vanilla: collects the measured
    # overpricing gap up front; the incremental loss is hard-bounded at
    # (K25-K10)/F per leg-month; beyond the 10d strike the leg behaves
    # like vanilla again (shifted by that bounded amount).
    if all(a in strikes for a in ("10d", "25d")):
        pay25 = max(cp * (Sn - strikes["25d"]), 0.0)
        pay10 = max(cp * (Sn - strikes["10d"]), 0.0)
        res["sell_25d"] = (prem_fcu["25d"] * grow_d - pay25) / F   # rung sold
        res["buy_10d"] = (pay10 - prem_fcu["10d"] * grow_d) / F    # rung owned
        res["z_ps"] = res["z_unhedged"] + res["sell_25d"] + res["buy_10d"]
        res["ps_carry_pickup"] = (prem_fcu["25d"] - prem_fcu["10d"]) * grow_d / F
        res["k_25d"], res["k_10d"] = strikes["25d"], strikes["10d"]
        res["ps_bound"] = abs(strikes["25d"] - strikes["10d"]) / F  # max add'l loss
        # two-sided execution: SELL the 25d at its bid vol, BUY the 10d at
        # its ask vol (bid ~= 2*mid - ask; PX_LAST is the midpoint on these
        # quotes), same mid-smile strikes. Stored so analysis can build the
        # crossed-spread strategy without re-deriving strikes.
        va = fcu_side_vols(row, side, "ask")
        sig25_bid = max(2.0 * vols["25d"] - va["25d"], 1e-4)
        kind = "put" if cp < 0 else "call"
        disc = np.exp(-r_d * TAU)
        prem25_bid = _MODEL.value(kind, F, strikes["25d"], sig25_bid, TAU,
                                  discount=disc)
        prem10_ask = _MODEL.value(kind, F, strikes["10d"], va["10d"], TAU,
                                  discount=disc)
        res["z_ps_cross"] = (res["z_unhedged"]
                             + (prem25_bid * grow_d - pay25) / F
                             + (pay10 - prem10_ask * grow_d) / F)
    else:
        for c in ("z_ps", "ps_carry_pickup", "z_ps_cross", "sell_25d",
                  "buy_10d", "k_25d", "k_10d", "ps_bound"):
            res[c] = np.nan
    return res


def build_legs(field="mid", orientation="native"):
    p = pd.read_parquet(OUT / "monthly_panel.parquet")
    p = p.sort_values(["ccy", "month_end"])
    # USD-per-FCU orientation from native quotes
    base_is_fcu = p["pair"].str.endswith("USD")
    p["spot_usd_per_fcu"] = np.where(base_is_fcu, p["spot_native"],
                                     1.0 / p["spot_native"])
    p["fwd_usd_per_fcu"] = np.where(base_is_fcu, p["fwd_native"],
                                    1.0 / p["fwd_native"])
    p["spot_next"] = p.groupby("ccy")["spot_usd_per_fcu"].shift(-1)
    need = ["spot_usd_per_fcu", "fwd_usd_per_fcu", "spot_next", "usd_1m",
            "fwd_disc", "vol_V_mid", "vol_25R_mid", "vol_25B_mid",
            "vol_10R_mid", "vol_10B_mid"]
    p = p.dropna(subset=need)
    recs = []
    for _, row in p.iterrows():
        r = leg_returns(row, field, orientation)
        r.update(month_end=row["month_end"], ccy=row["ccy"],
                 fwd_disc=row["fwd_disc"])
        recs.append(r)
    legs = pd.DataFrame(recs)
    # settlement month: returns realize at t+1
    legs["ret_month"] = legs["month_end"] + pd.offsets.MonthEnd(1)
    return legs


def portfolio(legs, ccys, weighting="EQL"):
    sub = legs[legs["ccy"].isin(ccys)].copy()
    if weighting == "SPR":
        w = sub.groupby("month_end")["fwd_disc"].transform(
            lambda s: s.abs() / s.abs().sum())
    else:
        w = 1.0 / sub.groupby("month_end")["ccy"].transform("count")
    sub["w"] = w
    cols = [c for c in sub.columns
            if c.startswith("z_") or c in ("floor_10d", "ps_carry_pickup")]
    out = {}
    for c in cols:
        out[c] = (sub[c] * sub["w"]).groupby(sub["ret_month"]).sum(min_count=1)
    return pd.DataFrame(out)


def stats(r):
    r = r.dropna()
    ann, vol = r.mean() * 12, r.std() * np.sqrt(12)
    nav = (1 + r).cumprod()
    return {"ann_ret": ann, "ann_vol": vol,
            "sharpe": ann / vol if vol > 0 else np.nan,
            "skew": r.skew(), "worst_mo": r.min(),
            "max_dd": (nav / nav.cummax() - 1).min(), "n": len(r)}


def main():
    legs = build_legs("mid")
    legs.to_parquet(OUT / "leg_returns.parquet")

    rows = []
    for uni_name, ccys, start in [("G10", G10, "2006-01-01"),
                                  ("ALL", sorted(legs["ccy"].unique()),
                                   "2006-01-01"),
                                  ("G10sub_2003", G10, "2003-10-01")]:
        for wgt in ["EQL", "SPR"]:
            port = portfolio(legs, ccys, wgt)
            port = port[port.index >= start].loc[:"2026-06-30"]
            if uni_name == "G10sub_2003":
                port = port.dropna()
            for col in port.columns:
                s = stats(port[col])
                s.update(universe=uni_name, weighting=wgt, arm=col)
                rows.append(s)
            if uni_name == "G10" and wgt == "EQL":
                port.to_parquet(OUT / "portfolio_G10_EQL.parquet")
            if uni_name == "ALL" and wgt == "EQL":
                port.to_parquet(OUT / "portfolio_ALL_EQL.parquet")

    summ = pd.DataFrame(rows)[["universe", "weighting", "arm", "ann_ret",
                               "ann_vol", "sharpe", "skew", "worst_mo",
                               "max_dd", "n"]]
    summ.to_csv(OUT / "summary.csv", index=False)
    pd.set_option("display.width", 160)
    print(summ.round(3).to_string(index=False))


if __name__ == "__main__":
    main()
