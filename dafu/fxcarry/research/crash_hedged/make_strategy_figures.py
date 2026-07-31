"""Numbers and figures for the spread-financed carry tutorial (tutorial 3).

Everything the tutorial asserts is computed here from our own panel, dumped to
out/tutorial_numbers.json (for transcription into the .tex) and drawn into
docs/tutorials/latex/figures/fig_sf_*.pdf.

Sections, in the order the tutorial uses them:
  1 leg      one worked leg-month, mid and at any fill fraction
  2 rungs    per-currency P&L of the rung sold and the rung owned (P vs Q)
  3 uip      the Fama regression on our own panel (why carry pays at all)
  4 book     rank -> weights -> book, one month shown in full
  5 costs    forward roll vs weight-change half-spreads, and the cancellation
  6 fill     book pickup as a function of the option fill fraction, exactly
  7 infer    HAC t against lag choice; overlay vs book regression
  8 peso     the bounded-disaster test the spread structure allows
Run: .venv/Scripts/python.exe research/crash_hedged/make_strategy_figures.py
"""
from __future__ import annotations

import json
import pathlib
import sys

import matplotlib as mpl
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import statsmodels.api as sm
from scipy import stats as sps

sys.path.insert(0, "research/crash_hedged")
import hedged_carry as hc
import strategy as st
from fxcarry import Black76

_MODEL = Black76()

OUT = pathlib.Path("research/crash_hedged/out")
FIG = pathlib.Path("docs/tutorials/latex/figures")
TAU = hc.TAU
K = st.K
WIN = {"2008": "2008-01-01", "2009": "2009-01-01"}
END = "2026-06-30"

mpl.rcParams.update({
    "font.family": "serif", "font.size": 9, "axes.spines.top": False,
    "axes.spines.right": False, "axes.grid": True, "grid.color": "#dddddd",
    "grid.linewidth": 0.5, "axes.axisbelow": True, "legend.frameon": False,
    "figure.dpi": 150})
BLUE, ORANGE, GREEN, PINK, GREY = ("#0072B2", "#D55E00", "#009E73",
                                   "#CC79A7", "#888888")
N = {}          # everything the tutorial quotes


def f4(x):
    return None if x is None or not np.isfinite(x) else round(float(x), 6)


# ---------------------------------------------------------------- ingredients
def enrich():
    """Legs plus every ingredient needed to re-price the overlay at any fill."""
    p = pd.read_parquet(OUT / "monthly_panel.parquet").sort_values(
        ["ccy", "month_end"])
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
        r = hc.leg_returns(row, "mid", "native")
        side = "p" if r["q"] > 0 else "c"
        vm, va = hc.fcu_side_vols(row, side, "mid"), hc.fcu_side_vols(row, side, "ask")
        r.update(month_end=row["month_end"], ccy=row["ccy"],
                 fwd_disc=row["fwd_disc"], pair=row["pair"],
                 S=row["spot_usd_per_fcu"], F=row["fwd_usd_per_fcu"],
                 Sn=row["spot_next"], r_d=row["usd_1m"],
                 s25=vm["25d"], s10=vm["10d"], a25=va["25d"], a10=va["10d"])
        recs.append(r)
    legs = pd.DataFrame(recs)
    legs["ret_month"] = legs["month_end"] + pd.offsets.MonthEnd(1)
    legs["cp"] = np.where(legs["q"] > 0, -1.0, 1.0)
    legs["pay25"] = np.maximum(legs["cp"] * (legs["Sn"] - legs["k_25d"]), 0.0)
    legs["pay10"] = np.maximum(legs["cp"] * (legs["Sn"] - legs["k_10d"]), 0.0)
    return legs.dropna(subset=["z_ps"]).reset_index(drop=True)


def overlay_at_fill(l, phi):
    """Overlay P&L per leg at fill fraction phi (0 = mid, 1 = full spread).

    Sell the 25d at mid - phi*(ask-mid), buy the 10d at mid + phi*(ask-mid);
    strikes stay on the mid smile, which is what the desk quotes against."""
    kind = np.where(l["cp"] < 0, "put", "call")
    s25 = np.maximum(l["s25"] - phi * (l["a25"] - l["s25"]), 1e-4)
    s10 = l["s10"] + phi * (l["a10"] - l["s10"])
    disc, grow = np.exp(-l["r_d"] * TAU), np.exp(l["r_d"] * TAU)
    p25 = np.array([_MODEL.value(o, F, Kk, s, TAU, discount=d)
                    for F, Kk, s, d, o in zip(l["F"], l["k_25d"], s25, disc, kind)])
    p10 = np.array([_MODEL.value(o, F, Kk, s, TAU, discount=d)
                    for F, Kk, s, d, o in zip(l["F"], l["k_10d"], s10, disc, kind)])
    sell = (p25 * grow - l["pay25"]) / l["F"]
    buy = (l["pay10"] - p10 * grow) / l["F"]
    return sell + buy


def select(legs, ccys=None):
    """The book: rank by carry, top-K long / bottom-K short, sign must agree."""
    sub = legs.dropna(subset=["z_unhedged", "z_ps"]).copy()
    if ccys is not None:
        sub = sub[sub["ccy"].isin(ccys)]
    sub["rank"] = sub.groupby("month_end")["fwd_disc"].rank(ascending=False)
    sub["n"] = sub.groupby("month_end")["ccy"].transform("count")
    sel = sub[((sub["rank"] <= K) & (sub["q"] > 0))
              | ((sub["rank"] > sub["n"] - K) & (sub["q"] < 0))].copy()
    sel["w"] = np.where(sel["q"] > 0, 1 / K, -1 / K)
    return sub, sel


def book_from(sel, cols):
    return pd.DataFrame({c: (sel[c] * (1 / K)).groupby(sel["ret_month"]).sum(
        min_count=1) for c in cols})


def nw_t(s, lags=6):
    s = pd.Series(s).dropna()
    return float(sm.OLS(s.values, np.ones(len(s))).fit(
        cov_type="HAC", cov_kwds={"maxlags": lags}).tvalues[0])


def ann_sr(r):
    r = pd.Series(r).dropna()
    a = r.mean() * 12
    return a, a / (r.std() * np.sqrt(12))


def main():
    FIG.mkdir(parents=True, exist_ok=True)
    legs = enrich()
    N["universe"] = {"n_ccy": int(legs["ccy"].nunique()),
                     "n_leg_months": int(len(legs)),
                     "first": str(legs["month_end"].min().date()),
                     "last": str(legs["month_end"].max().date())}

    # ---------------------------------------------------------------- 1 leg
    anchor = legs[(legs["ccy"] == "JPY")
                  & (legs["month_end"] == "2026-06-30")].iloc[0]
    phis = np.linspace(0, 1, 11)
    one = legs[(legs["ccy"] == "JPY") & (legs["month_end"] == "2026-06-30")]
    curve = np.array([float(overlay_at_fill(one, p).iloc[0]) for p in phis])
    lin = curve[0] + phis * (curve[-1] - curve[0])
    N["leg"] = {k: f4(anchor[k]) for k in
                ["q", "S", "F", "Sn", "r_d", "s25", "s10", "a25", "a10",
                 "k_25d", "k_10d", "pay25", "pay10", "sell_25d", "buy_10d",
                 "z_unhedged", "z_ps", "z_ps_cross", "ps_carry_pickup",
                 "ps_bound"]}
    N["leg"]["K25_native"] = f4(1 / anchor["k_25d"])
    N["leg"]["K10_native"] = f4(1 / anchor["k_10d"])
    N["leg"]["S_native"] = f4(1 / anchor["S"])
    N["leg"]["F_native"] = f4(1 / anchor["F"])
    N["leg"]["Sn_native"] = f4(1 / anchor["Sn"])
    N["leg"]["fill_curve"] = [f4(x) for x in curve]
    N["leg"]["fill_linear_maxdev"] = f4(np.abs(curve - lin).max())
    N["leg"]["breakeven_leg"] = f4(curve[0] / (curve[0] - curve[-1]))

    # the month the sold rung actually paid out
    worst = legs.loc[legs["sell_25d"].idxmin()]
    N["leg_itm"] = {k: f4(worst[k]) for k in
                    ["q", "S", "F", "Sn", "k_25d", "k_10d", "pay25", "pay10",
                     "sell_25d", "buy_10d", "z_unhedged", "z_ps", "ps_bound",
                     "ps_carry_pickup"]}
    N["leg_itm"].update(ccy=worst["ccy"], month=str(worst["month_end"].date()),
                        pair=worst["pair"])

    # ------------------------------------------------------------- 2 rungs
    w = legs[(legs["ret_month"] >= "2006-01-01") & (legs["ret_month"] <= END)]
    rung = (w.groupby("ccy").agg(months=("sell_25d", "size"),
                                 sell25=("sell_25d", "mean"),
                                 buy10=("buy_10d", "mean"),
                                 prem25=("prem_25d", "mean"),
                                 prem10=("prem_10d", "mean")) * 1)
    rung[["sell25", "buy10", "prem25", "prem10"]] *= 12
    rung["overlay"] = rung["sell25"] + rung["buy10"]
    rung = rung.sort_values("overlay", ascending=False)
    rung.to_csv(OUT / "rung_pnl.csv")
    N["rungs"] = {
        "all_sell25": f4(w["sell_25d"].mean() * 12),
        "all_buy10": f4(w["buy_10d"].mean() * 12),
        "all_sell25_t": f4(nw_t(w.groupby("ret_month")["sell_25d"].mean())),
        "all_buy10_t": f4(nw_t(w.groupby("ret_month")["buy_10d"].mean())),
        "g10_sell25": f4(w[w["ccy"].isin(hc.G10)]["sell_25d"].mean() * 12),
        "g10_buy10": f4(w[w["ccy"].isin(hc.G10)]["buy_10d"].mean() * 12),
        "em_sell25": f4(w[~w["ccy"].isin(hc.G10)]["sell_25d"].mean() * 12),
        "em_buy10": f4(w[~w["ccy"].isin(hc.G10)]["buy_10d"].mean() * 12),
        "top": [[i, f4(r["sell25"]), f4(r["buy10"])]
                for i, r in rung.head(6).iterrows()],
        "bottom": [[i, f4(r["sell25"]), f4(r["buy10"])]
                   for i, r in rung.tail(3).iterrows()]}

    fig, ax = plt.subplots(figsize=(6.3, 2.9))
    o = rung.sort_values("sell25", ascending=False)
    x = np.arange(len(o))
    ax.bar(x - 0.19, o["sell25"] * 100, width=0.36, color=ORANGE,
           label="sell the 25d rung")
    ax.bar(x + 0.19, o["buy10"] * 100, width=0.36, color=GREEN,
           label="own the 10d rung")
    ax.axhline(0, color="#444444", lw=0.8)
    ax.set_xticks(x, o.index, rotation=90, fontsize=7)
    ax.set_ylabel("Realized P&L (%/yr per leg)")
    ax.legend(loc="upper right", fontsize=8)
    ax.grid(axis="x", visible=False)
    fig.tight_layout()
    fig.savefig(FIG / "fig_sf_rungs.pdf")
    plt.close(fig)

    # --------------------------------------------------------------- 3 uip
    p = pd.read_parquet(OUT / "monthly_panel.parquet").sort_values(
        ["ccy", "month_end"])
    base_is_fcu = p["pair"].str.endswith("USD")
    p["s_usd"] = np.where(base_is_fcu, p["spot_native"], 1 / p["spot_native"])
    p["f_usd"] = np.where(base_is_fcu, p["fwd_native"], 1 / p["fwd_native"])
    p["s_next"] = p.groupby("ccy")["s_usd"].shift(-1)
    fam = p.dropna(subset=["s_usd", "f_usd", "s_next"]).copy()
    fam = fam[(fam["month_end"] >= "2006-01-01") & (fam["month_end"] <= END)]
    fam["fs"] = np.log(fam["f_usd"] / fam["s_usd"])      # forward premium
    fam["ds"] = np.log(fam["s_next"] / fam["s_usd"])     # realized spot change
    fam["rx"] = fam["ds"] - fam["fs"]
    X = sm.add_constant(fam["fs"].values)
    fit = sm.OLS(fam["ds"].values, X).fit(
        cov_type="cluster", cov_kwds={"groups": fam["month_end"].values})
    b, se = float(fit.params[1]), float(fit.bse[1])
    N["uip"] = {"n": int(len(fam)), "a": f4(fit.params[0] * 12),
                "b": f4(b), "b_se": f4(se), "t_b_eq_1": f4((b - 1) / se),
                "t_b_eq_0": f4(b / se), "r2": f4(fit.rsquared),
                "mean_rx_ann": f4(fam["rx"].mean() * 12),
                "mean_rx_t": f4(nw_t(fam.groupby("month_end")["rx"].mean()))}
    g10m = fam["ccy"].isin(hc.G10)
    for lab, m in [("g10", g10m), ("em", ~g10m)]:
        f2 = sm.OLS(fam.loc[m, "ds"].values,
                    sm.add_constant(fam.loc[m, "fs"].values)).fit(
            cov_type="cluster", cov_kwds={"groups": fam.loc[m, "month_end"].values})
        N["uip"][f"b_{lab}"] = f4(f2.params[1])
        N["uip"][f"b_{lab}_se"] = f4(f2.bse[1])

    XLO, XHI, YLO, YHI = -30.0, 15.0, -90.0, 90.0
    fx, fy = fam["fs"] * 1200, fam["ds"] * 1200
    inside = (fx > XLO) & (fx < XHI) & (fy > YLO) & (fy < YHI)
    N["uip"]["plot_clipped"] = int((~inside).sum())
    q = pd.qcut(fam["fs"], 12, duplicates="drop")
    binned = fam.groupby(q, observed=True)[["fs", "ds"]].mean() * 1200

    fig, ax = plt.subplots(figsize=(6.3, 2.9))
    ax.scatter(fx[inside], fy[inside], s=3, alpha=0.15, color=BLUE,
               edgecolors="none")
    xs = np.linspace(XLO / 1200, XHI / 1200, 50)
    ax.plot(xs * 1200, xs * 1200, color="#444444", lw=1.2, ls="--",
            label="UIP: slope 1")
    ax.plot(xs * 1200, (fit.params[0] + b * xs) * 1200, color=ORANGE, lw=1.8,
            label=f"fitted: slope {b:.2f} (s.e. {se:.2f})")
    ax.plot(binned["fs"], binned["ds"], "o", color=ORANGE, ms=5,
            markeredgecolor="white", markeredgewidth=0.6, zorder=5,
            label="means of 12 equal bins")
    ax.legend(loc="upper left", fontsize=8)
    ax.set_xlabel("Forward premium $f_t-s_t$ (%/yr)")
    ax.set_ylabel("Realized spot change (%/yr)")
    ax.set_xlim(XLO, XHI)
    ax.set_ylim(YLO, YHI)
    fig.tight_layout()
    fig.savefig(FIG / "fig_sf_uip.pdf")
    plt.close(fig)

    # -------------------------------------------------------------- 4 book
    sub, sel = select(legs)
    port = book_from(sel, ["z_unhedged", "z_ps", "z_ps_cross"])
    ref, n_mis = st.sorted_book(hc.build_legs("mid", "native"))
    chk = float((port["z_ps"] - ref["z_ps"]).abs().max())
    N["book"] = {"n_mismatch": int(n_mis), "reconcile_max_abs": f4(chk)}

    m = pd.Timestamp("2026-06-30")
    snap = sub[sub["month_end"] == m].sort_values("fwd_disc", ascending=False)
    held = set(sel[sel["month_end"] == m]["ccy"])
    N["book"]["month"] = str(m.date())
    N["book"]["snapshot"] = [
        [r["ccy"], f4(r["fwd_disc"] * 1200), int(r["rank"]), int(r["q"]),
         r["ccy"] in held] for _, r in snap.iterrows()]
    N["book"]["n_ranked"] = int(len(snap))

    # --------------------------------------------------------------- 5 costs
    hs = st.half_spreads()
    W = sel.pivot_table(index="month_end", columns="ccy", values="w").fillna(0.0)
    dW = W.diff().abs()
    dW.iloc[0] = W.iloc[0].abs()
    roll = pd.Series(0.0, index=W.index)
    move = pd.Series(0.0, index=W.index)
    for c in W.columns:
        if c not in hs:
            continue
        h = hs[c].reindex(W.index)
        roll = roll.add(W[c].abs() * h["hs_pts"], fill_value=0.0)
        move = move.add(dW[c] * h["hs_out"], fill_value=0.0)
    roll.index = roll.index + pd.offsets.MonthEnd(1)
    move.index = move.index + pd.offsets.MonthEnd(1)
    turn = (dW.sum(axis=1) / (2 * W.abs().sum(axis=1))).mean()
    N["costs"] = {"turnover": f4(turn)}
    for lab, s0 in WIN.items():
        r_ = roll[(roll.index >= s0) & (roll.index <= END)]
        m_ = move[(move.index >= s0) & (move.index <= END)]
        N["costs"][lab] = {"roll_ann": f4(r_.mean() * 12),
                           "move_ann": f4(m_.mean() * 12),
                           "total_ann": f4((r_ + m_).mean() * 12)}
    ex = {c: f4(float(hs[c]["hs_pts"].dropna().mean())) for c in
          ["JPY", "AUD", "TRY", "BRL", "IDR"] if c in hs}
    ex_o = {c: f4(float(hs[c]["hs_out"].dropna().mean())) for c in
            ["JPY", "AUD", "TRY", "BRL", "IDR"] if c in hs}
    N["costs"]["example_pts"] = ex
    N["costs"]["example_out"] = ex_o

    # ---------------------------------------------------------------- 6 fill
    cost = (roll + move).reindex(port.index).fillna(0.0)
    port["fwd_cost"] = cost
    grid = np.linspace(0, 1, 21)
    ov = {}
    for phi in grid:
        sel[f"ov{phi:.2f}"] = overlay_at_fill(sel, phi).values
        ov[phi] = (sel[f"ov{phi:.2f}"] * (1 / K)).groupby(
            sel["ret_month"]).sum(min_count=1)
    N["books"] = {}
    for lab, s0 in WIN.items():
        pw = port[(port.index >= s0) & (port.index <= END)]
        d = {}
        for arm, name in [("z_unhedged", "vanilla"), ("z_ps", "strategy"),
                          ("z_ps_cross", "strategy_crossed")]:
            g, gs = ann_sr(pw[arm])
            n_, ns = ann_sr(pw[arm] - pw["fwd_cost"])
            diff = (pw[arm] - pw["z_unhedged"]).dropna()
            d[name] = {"gross_ann": f4(g), "gross_sr": f4(gs),
                       "net_ann": f4(n_), "net_sr": f4(ns), "n": int(len(pw)),
                       "pickup_ann": f4(diff.mean() * 12) if arm != "z_unhedged" else None,
                       "pickup_t": f4(nw_t(diff)) if arm != "z_unhedged" else None,
                       "worst_mo": f4(pw[arm].min()),
                       "skew": f4(pw[arm].skew())}
        oa, os_ = ann_sr(ov[0.0][(ov[0.0].index >= s0) & (ov[0.0].index <= END)])
        d["overlay_alone"] = {"ann": f4(oa), "sharpe": f4(os_),
                              "t": f4(nw_t(ov[0.0][(ov[0.0].index >= s0)
                                                   & (ov[0.0].index <= END)]))}
        curve_b = [f4(ov[g_][(ov[g_].index >= s0)
                             & (ov[g_].index <= END)].mean() * 12) for g_ in grid]
        d["fill_curve"] = curve_b
        yy = np.array(curve_b)
        j = np.where(yy <= 0)[0]
        if len(j):
            i0 = j[0]
            be = (grid[i0 - 1] + (grid[i0] - grid[i0 - 1]) * yy[i0 - 1]
                  / (yy[i0 - 1] - yy[i0])) if i0 else 0.0
        else:
            be = np.nan
        d["breakeven_fill"] = f4(be)
        d["breakeven_linear"] = f4(yy[0] / (yy[0] - yy[-1]))
        N["books"][lab] = d
    N["books"]["fill_grid"] = [f4(g_) for g_ in grid]

    # who can actually be filled: break-even fill per currency, held legs only
    h = sel[(sel["ret_month"] >= WIN["2008"]) & (sel["ret_month"] <= END)]
    per = h.groupby("ccy")[["ov0.00", "ov1.00"]].mean()
    per["n"] = h.groupby("ccy").size()
    per["be"] = per["ov0.00"] / (per["ov0.00"] - per["ov1.00"])
    per = per[per["n"] >= 24].sort_values("be", ascending=False)
    N["books"]["breakeven_by_ccy"] = [
        [i, int(r["n"]), f4(r["ov0.00"] * 12), f4(r["be"])]
        for i, r in per.iterrows()]

    fig, ax = plt.subplots(figsize=(6.3, 2.8))
    for lab, col in [("2008", BLUE), ("2009", ORANGE)]:
        y = np.array(N["books"][lab]["fill_curve"]) * 100
        ax.plot(grid * 100, y, color=col, lw=1.8)
        be = N["books"][lab]["breakeven_fill"]
        ax.plot([be * 100], [0], "o", color=col, ms=5)
        ax.annotate(f"{lab}+: break-even {be*100:.0f}%",
                    xy=(be * 100, 0), xytext=(6, 14 if lab == "2008" else -20),
                    textcoords="offset points", fontsize=8.5, color=col)
    ax.axhline(0, color="#444444", lw=0.8)
    ax.set_xlabel("Fraction of the quoted option spread paid (%)")
    ax.set_ylabel("Overlay P&L (%/yr)")
    fig.tight_layout()
    fig.savefig(FIG / "fig_sf_fill.pdf")
    plt.close(fig)

    # -------------------------------------------------------------- 7 infer
    N["infer"] = {}
    for lab, s0 in WIN.items():
        pw = port[(port.index >= s0) & (port.index <= END)]
        d = (pw["z_ps"] - pw["z_unhedged"]).dropna()
        N["infer"][lab] = {
            "n": int(len(d)), "mean_mo": f4(d.mean()), "sd_mo": f4(d.std()),
            "t_iid": f4(d.mean() / (d.std() / np.sqrt(len(d)))),
            "t_by_lag": [[int(L), f4(nw_t(d, L))] for L in
                         [0, 1, 3, 6, 9, 12, 18]],
            "ac1": f4(d.autocorr(1)), "ac2": f4(d.autocorr(2)),
            "ac3": f4(d.autocorr(3)),
            "skew": f4(d.skew()), "kurt": f4(d.kurtosis()),
            "worst": f4(d.min()), "best": f4(d.max()),
            "share_pos": f4((d > 0).mean())}
        # is the overlay just more carry?
        yx = pd.concat([d.rename("ov"), pw["z_unhedged"].rename("bk")],
                       axis=1).dropna()
        reg = sm.OLS(yx["ov"].values,
                     sm.add_constant(yx["bk"].values)).fit(
            cov_type="HAC", cov_kwds={"maxlags": 6})
        N["infer"][lab].update(
            alpha_ann=f4(reg.params[0] * 12), alpha_t=f4(reg.tvalues[0]),
            beta=f4(reg.params[1]), beta_t=f4(reg.tvalues[1]),
            r2=f4(reg.rsquared), corr=f4(yx["ov"].corr(yx["bk"])))
        worst10 = yx.nsmallest(10, "bk")
        N["infer"][lab]["overlay_in_worst10"] = f4(worst10["ov"].mean())
        N["infer"][lab]["book_in_worst10"] = f4(worst10["bk"].mean())
        # bootstrap: the t-test leans on a mean whose sample skew is -1.6
        rng = np.random.default_rng(20260722)
        v = d.values
        draw = rng.choice(v, size=(20000, len(v)), replace=True)
        N["infer"][lab]["boot_p_iid"] = f4(
            float(((draw.mean(axis=1) - v.mean()) >= v.mean()).mean()))
        L = 6
        nb = int(np.ceil(len(v) / L))
        starts = rng.integers(0, len(v) - L, size=(20000, nb))
        idx = (starts[:, :, None] + np.arange(L)[None, None, :]).reshape(20000, -1)
        bm = v[idx[:, :len(v)]].mean(axis=1)
        N["infer"][lab]["boot_p_block"] = f4(
            float(((bm - v.mean()) >= v.mean()).mean()))
        # where the pickup comes from: premium collected less payouts
        coll = (sel["ps_carry_pickup"] * (1 / K)).groupby(
            sel["ret_month"]).sum(min_count=1)
        coll = coll[(coll.index >= s0) & (coll.index <= END)]
        N["infer"][lab]["collected_ann"] = f4(coll.mean() * 12)
        N["infer"][lab]["payout_ann"] = f4(coll.mean() * 12 - d.mean() * 12)
        # the rungs, restricted to the legs the book actually holds
        h = sel[(sel["ret_month"] >= s0) & (sel["ret_month"] <= END)]
        N["infer"][lab]["held_sell25_ann"] = f4(h["sell_25d"].mean() * 12)
        N["infer"][lab]["held_buy10_ann"] = f4(h["buy_10d"].mean() * 12)
        N["infer"][lab]["held_n"] = int(len(h))

        # a disaster need not arrive in one month: the sequence risk
        o_ = ov[0.0][(ov[0.0].index >= s0) & (ov[0.0].index <= END)]
        nav = (1 + o_).cumprod()
        N["infer"][lab]["overlay_worst_12m"] = f4(
            float(o_.rolling(12).sum().min()))
        N["infer"][lab]["overlay_maxdd"] = f4(
            float((nav / nav.cummax() - 1).min()))
        N["infer"][lab]["book_maxdd"] = f4(float(
            ((1 + pw["z_unhedged"]).cumprod()
             / (1 + pw["z_unhedged"]).cumprod().cummax() - 1).min()))
        N["infer"][lab]["strat_maxdd"] = f4(float(
            ((1 + pw["z_ps"]).cumprod()
             / (1 + pw["z_ps"]).cumprod().cummax() - 1).min()))

    pd.DataFrame({"z_unhedged": port["z_unhedged"], "z_ps": port["z_ps"],
                  "z_ps_cross": port["z_ps_cross"], "fwd_cost": port["fwd_cost"],
                  "overlay": ov[0.0]}).to_parquet(
        OUT / "tutorial_series.parquet")

    # G10-only book: same construction, five of nine names
    _, sel10 = select(legs, hc.G10)
    p10 = book_from(sel10, ["z_unhedged", "z_ps"])
    for lab, s0 in WIN.items():
        pw = p10[(p10.index >= s0) & (p10.index <= END)]
        dd = (pw["z_ps"] - pw["z_unhedged"]).dropna()
        a_, s_ = ann_sr(pw["z_unhedged"])
        N["infer"][lab]["g10_book"] = {
            "vanilla_ann": f4(a_), "vanilla_sr": f4(s_),
            "pickup_ann": f4(dd.mean() * 12), "pickup_t": f4(nw_t(dd)),
            "n": int(len(pw))}

    # --------------------------------------------------------------- 8 peso
    bound = (sel["ps_bound"] * (1 / K)).groupby(sel["ret_month"]).sum(min_count=1)
    ovl = ov[0.0]
    N["peso"] = {}
    for lab, s0 in WIN.items():
        b_ = bound[(bound.index >= s0) & (bound.index <= END)]
        o_ = ovl[(ovl.index >= s0) & (ovl.index <= END)]
        mo = float(o_.mean())
        worst_possible = float(b_.mean())          # collected - bound is worse
        p_needed = mo / worst_possible
        n_ = int(len(o_))
        N["peso"][lab] = {
            "n": n_, "mean_mo": f4(mo), "bound_mean": f4(worst_possible),
            "bound_max": f4(b_.max()), "bound_min": f4(b_.min()),
            "p_needed": f4(p_needed),
            "expected_hits": f4(p_needed * n_),
            "p_unobservable_5pct": f4(1 - 0.05 ** (1 / n_)),
            "prob_zero_at_p_needed": f4(
                float(sps.binom.cdf(0, n_, p_needed))),
            "realized_min": f4(float(o_.min())),
            "worst_vs_bound": f4(float((o_ / b_).min()))}

    fig, axes = plt.subplots(1, 2, figsize=(6.4, 2.7))
    ax = axes[0]
    s0 = WIN["2008"]
    o_ = ovl[(ovl.index >= s0) & (ovl.index <= END)]
    b_ = bound.reindex(o_.index)
    frac = (o_ / b_) * 100
    ax.axhline(-100, color="#444444", lw=1.0, ls="--")
    ax.vlines(frac.index, 0, frac.values, color=ORANGE, lw=0.7)
    ax.axhline(0, color="#444444", lw=0.8)
    ax.annotate("everything the spread can lose", xy=(frac.index[3], -96),
                fontsize=7.5, color="#444444", va="bottom")
    i = frac.idxmin()
    ax.annotate(f"worst month: {frac.min():.0f}%", xy=(i, frac.min()),
                xytext=(10, -2), textcoords="offset points", fontsize=7.5,
                color=ORANGE)
    ax.set_ylim(-108, 30)
    ax.set_ylabel("Month P&L (% of the month's bound)")
    ax.set_xticks(pd.date_range("2008-01-01", "2026-01-01", freq="4YS"))
    ax.set_xticklabels([d.year for d in
                        pd.date_range("2008-01-01", "2026-01-01", freq="4YS")])
    ax.grid(axis="x", visible=False)
    ax = axes[1]
    for lab, col in [("2008", BLUE), ("2009", ORANGE)]:
        t = np.array([r[1] for r in N["infer"][lab]["t_by_lag"]])
        L = [r[0] for r in N["infer"][lab]["t_by_lag"]]
        ax.plot(L, t, "o-", color=col, ms=3.5, lw=1.4, label=f"{lab}+")
    ax.axhline(1.96, color="#444444", lw=0.8, ls=":")
    ax.set_xlabel("Newey--West lags")
    ax.set_ylabel("$t$ on the pickup")
    ax.set_ylim(0, None)
    ax.legend(loc="lower left", fontsize=8)
    fig.tight_layout()
    fig.savefig(FIG / "fig_sf_bound.pdf")
    plt.close(fig)

    # ------------------------------------------------------------ 9 payoff
    a = anchor
    span = np.linspace(0.955, 1.075, 500)
    Sn_grid = a["F"] * span
    cp = a["cp"]
    vanilla = np.exp(a["r_d"] * TAU) * a["q"] * (Sn_grid / a["F"] - 1)
    p25 = np.maximum(cp * (Sn_grid - a["k_25d"]), 0.0)
    p10 = np.maximum(cp * (Sn_grid - a["k_10d"]), 0.0)
    grow = np.exp(a["r_d"] * TAU)
    prem25 = a["sell_25d"] + a["pay25"] / a["F"]      # collected, financed
    prem10 = a["buy_10d"] * -1 + a["pay10"] / a["F"]
    ovl_g = (prem25 - p25 / a["F"]) + (p10 / a["F"] - prem10)
    fig, ax = plt.subplots(figsize=(6.3, 2.9))
    ax.plot(1 / Sn_grid, vanilla * 100, color=BLUE, lw=1.6, label="carry leg")
    ax.plot(1 / Sn_grid, (vanilla + ovl_g) * 100, color=ORANGE, lw=1.8,
            label="carry leg $+$ sold 25d/10d spread")
    ax.plot(1 / Sn_grid, ovl_g * 100, color=GREEN, lw=1.2, ls="--",
            label="the overlay alone")
    for k, lab, dy in [(a["k_25d"], "$K_{25}$ sold", 0.0),
                       (a["k_10d"], "$K_{10}$ owned", -0.7)]:
        ax.axvline(1 / k, color=GREY, lw=0.8, ls=":")
        ax.annotate(lab, xy=(1 / k, 4.6 + dy), fontsize=8, color="#555555",
                    ha="center", backgroundcolor="white")
    ax.annotate(f"premium collected {a['ps_carry_pickup']*100:.2f}%",
                xy=(1 / (a["F"] * 0.97), a["ps_carry_pickup"] * 100),
                xytext=(0, 14), textcoords="offset points", fontsize=8,
                color=GREEN, ha="center")
    ax.annotate(f"floor of the overlay: $-${a['ps_bound']*100 - a['ps_carry_pickup']*100:.2f}%",
                xy=(1 / (a["F"] * 1.065),
                    (a["ps_carry_pickup"] - a["ps_bound"]) * 100),
                xytext=(0, -16), textcoords="offset points", fontsize=8,
                color=GREEN, ha="center")
    ax.axhline(0, color="#444444", lw=0.8)
    ax.set_xlabel("Settlement spot (yen per dollar).  The book is short yen: its crash is to the right.")
    ax.set_ylabel("Leg return (%)")
    ax.legend(loc="lower left", fontsize=8)
    ax.invert_xaxis()
    fig.tight_layout()
    fig.savefig(FIG / "fig_sf_payoff.pdf")
    plt.close(fig)

    (OUT / "tutorial_numbers.json").write_text(json.dumps(N, indent=1))
    print(json.dumps(N, indent=1)[:1500])
    print("\nfigures:", sorted(p.name for p in FIG.glob("fig_sf_*.pdf")))


if __name__ == "__main__":
    main()
