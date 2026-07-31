"""Analysis layer: the four pre-registered questions, tables and figures.

Q1 Jurek bound out of sample: give-up share = |mean(hedged-unhedged)| /
   mean(unhedged), with Newey-West t on the monthly diff (6 lags).
Q2 The wedge: the moneyness ladder in one table (+ BEKR overlay column).
Q3 What insurance bought: event-month table, hedged vs unhedged.
Q4 Price of tail insurance over time: rolling book premium by arm.
Variants: headline (mid vols, native-orientation strikes), ask-vol stress,
Jurek-uniform orientation. Outputs to out/: main_table.csv, events.csv,
premium_ts.parquet, figures fig_ch_*.pdf.
Run: python research/crash_hedged/analysis.py
"""
from __future__ import annotations

import pathlib
import sys

import matplotlib as mpl
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import statsmodels.api as sm

sys.path.insert(0, "research/crash_hedged")
import hedged_carry as hc

OUT = pathlib.Path("research/crash_hedged/out")
FIG = pathlib.Path("docs/tutorials/latex/figures")
ARMS = ["z_jurek_10d", "z_jurek_25d", "z_jurek_atm", "z_bekr_atmf",
        "z_ps", "z_ps_cross"]
LABEL = {"z_unhedged": "unhedged", "z_jurek_10d": "10d hedge",
         "z_jurek_25d": "25d hedge", "z_jurek_atm": "ATM hedge",
         "z_bekr_atmf": "BEKR ATMF", "z_ps": "spread-financed",
         "z_ps_cross": "spread-financed (crossed)",
         "z_lev10": "floored, stress-sized"}
COLOR = {"z_unhedged": "#0072B2", "z_jurek_10d": "#009E73",
         "z_jurek_25d": "#D55E00", "z_jurek_atm": "#CC79A7",
         "z_bekr_atmf": "#888888"}

mpl.rcParams.update({
    "font.family": "serif", "font.size": 9, "axes.spines.top": False,
    "axes.spines.right": False, "axes.grid": True, "grid.color": "#dddddd",
    "grid.linewidth": 0.5, "axes.axisbelow": True, "legend.frameon": False,
    "figure.dpi": 150})


def nw_t(series, lags=6):
    s = series.dropna()
    if len(s) < 24:
        return np.nan
    res = sm.OLS(s.values, np.ones(len(s))).fit(
        cov_type="HAC", cov_kwds={"maxlags": lags})
    return float(res.tvalues[0])


def arm_rows(port, variant, universe, weighting):
    rows = []
    u = port["z_unhedged"].dropna()
    for col in ["z_unhedged"] + ARMS:
        r = port[col].dropna()
        diff = (port[col] - port["z_unhedged"]).dropna()
        ann = r.mean() * 12
        rows.append({
            "variant": variant, "universe": universe, "weighting": weighting,
            "arm": LABEL[col], "ann_ret": ann,
            "sharpe": ann / (r.std() * np.sqrt(12)),
            "skew": r.skew(), "worst_mo": r.min(),
            "max_dd": ((1 + r).cumprod() / (1 + r).cumprod().cummax() - 1).min(),
            "diff_ann": diff.mean() * 12, "diff_t": nw_t(diff),
            "giveup_share": (-diff.mean() * 12 / (u.mean() * 12)
                             if col != "z_unhedged" else np.nan),
            "n": len(r)})
    return rows


def main():
    variants = {
        "headline": hc.build_legs("mid", "native"),
        "ask_vol": hc.build_legs("ask", "native"),
        "jurek_uniform": hc.build_legs("mid", "uniform"),
    }
    rows, ports = [], {}
    for vname, legs in variants.items():
        em = sorted(set(legs["ccy"].unique()) - set(hc.G10))
        for uni, ccys in [("G10", hc.G10), ("EM", em),
                          ("ALL", sorted(legs["ccy"].unique()))]:
            for wgt in ["EQL", "SPR"]:
                port = hc.portfolio(legs, ccys, wgt)
                port = port[(port.index >= "2006-01-01")
                            & (port.index <= "2026-06-30")]
                rows += arm_rows(port, vname, uni, wgt)
                ports[(vname, uni, wgt)] = port
    main_table = pd.DataFrame(rows)
    main_table.to_csv(OUT / "main_table.csv", index=False)

    hl = main_table[main_table["variant"] == "headline"]
    print(hl.round(3).to_string(index=False))

    # ---- strategy arms: floored carry, stress-sized ------------------------
    # Ex-ante leverage from the book's KNOWN 10d floor: L_t = budget/|floor|,
    # capped at 3x; floor is set at initiation, so no lookahead. Budget 5%/mo.
    strat_rows = []
    for (vname, uni, wgt), port in ports.items():
        if vname != "headline" or "floor_10d" not in port:
            continue
        L = (0.05 / port["floor_10d"].abs()).clip(upper=3.0)
        z_lev = (port["z_jurek_10d"] * L).dropna()
        r = z_lev
        u = port["z_unhedged"].dropna()
        diff = (z_lev - port["z_unhedged"]).dropna()
        strat_rows.append({
            "universe": uni, "weighting": wgt, "arm": LABEL["z_lev10"],
            "ann_ret": r.mean() * 12,
            "sharpe": r.mean() * 12 / (r.std() * np.sqrt(12)),
            "skew": r.skew(), "worst_mo": r.min(),
            "max_dd": ((1 + r).cumprod() / (1 + r).cumprod().cummax() - 1).min(),
            "diff_ann": diff.mean() * 12, "diff_t": nw_t(diff),
            "avg_leverage": float(L.mean()),
            "unhedged_ann": u.mean() * 12, "n": len(r)})
    strat = pd.DataFrame(strat_rows)
    strat.to_csv(OUT / "strategy_table.csv", index=False)
    print("\nFloored carry, stress-sized (5%/mo budget, ex-ante floor sizing):")
    print(strat.round(3).to_string(index=False))

    # ---- per-currency carry vs insurance (the centerpiece) -----------------
    hl_legs = variants["headline"]
    w = hl_legs[(hl_legs["ret_month"] >= "2006-01-01")
                & (hl_legs["ret_month"] <= "2026-06-30")].copy()
    for d in ("10d", "25d"):
        w[f"giveup_{d}"] = w["z_unhedged"] - w[f"z_jurek_{d}"]
    pc = (w.groupby("ccy").agg(
        months=("z_unhedged", "size"),
        pct_long=("q", lambda s: (s > 0).mean()),
        carry_long=("fwd_disc", lambda s: s[s > 0].mean() * 12),
        z_ann=("z_unhedged", lambda s: s.mean() * 12),
        prem10_ann=("prem_10d", lambda s: s.mean() * 12),
        prem25_ann=("prem_25d", lambda s: s.mean() * 12),
        giveup10_ann=("giveup_10d", lambda s: s.mean() * 12),
        giveup25_ann=("giveup_25d", lambda s: s.mean() * 12),
    ).sort_values("carry_long", ascending=False))
    pc.to_csv(OUT / "per_currency.csv")
    print("\nPer-currency (2006-01..2026-06): carry when long, leg mean, "
          "insurance premia and give-up, %/yr")
    print((pc * [1, 100, 100, 100, 100, 100, 100, 100]).round(2).to_string())

    # ---- events table (settlement months) ----------------------------------
    ev_months = ["2008-09-30", "2008-10-31", "2008-11-30", "2011-09-30",
                 "2015-01-31", "2016-06-30", "2020-03-31"]
    ev = []
    for uni in ["G10", "ALL"]:
        port = ports[("headline", uni, "EQL")]
        for mth in ev_months:
            if pd.Timestamp(mth) in port.index:
                row = port.loc[pd.Timestamp(mth)]
                ev.append({"universe": uni, "month": mth,
                           **{LABEL[c]: row[c] for c in
                              ["z_unhedged", "z_jurek_25d", "z_jurek_atm"]}})
    events = pd.DataFrame(ev)
    events.to_csv(OUT / "events.csv", index=False)

    # ---- premium time series (G10 EQL book, %/yr) --------------------------
    legs = variants["headline"]
    g10 = legs[legs["ccy"].isin(hc.G10)]
    prem = (g10.groupby("month_end")[["prem_10d", "prem_25d", "prem_atm"]]
            .mean() * 12 * 100)
    prem = prem[(prem.index >= "2006-01-01") & (prem.index <= "2026-06-30")]
    prem.to_parquet(OUT / "premium_ts.parquet")

    # ---- figures -----------------------------------------------------------
    FIG.mkdir(parents=True, exist_ok=True)
    port = ports[("headline", "G10", "EQL")]

    fig, ax = plt.subplots(figsize=(6.2, 3.0))
    DY = {"z_unhedged": 8, "z_jurek_10d": 16, "z_jurek_25d": -14,
          "z_jurek_atm": 0}
    for col in ["z_unhedged", "z_jurek_10d", "z_jurek_25d", "z_jurek_atm"]:
        w = (1 + port[col].dropna()).cumprod()
        ax.plot(w.index, w.values, color=COLOR[col], lw=1.5)
        ax.annotate(LABEL[col], xy=(w.index[-1], w.iloc[-1]),
                    xytext=(6, DY[col]), textcoords="offset points",
                    va="center", fontsize=8.5, color=COLOR[col])
    ax.axhline(1, color="#444444", lw=0.8)
    ax.set_ylabel("Growth of \\$1 (G10, equal-weight)")
    ax.set_xlim(pd.Timestamp("2006-01-01"), pd.Timestamp("2030-06-30"))
    ax.grid(axis="x", visible=False)
    fig.tight_layout()
    fig.savefig(FIG / "fig_ch_tracks.pdf")
    plt.close(fig)

    fig, axes = plt.subplots(1, 2, figsize=(6.4, 2.6), sharey=True)
    for ax, uni in zip(axes, ["G10", "EM"]):
        sub = hl[(hl["universe"] == uni) & (hl["weighting"] == "EQL")]
        arms = ["unhedged", "10d hedge", "25d hedge", "ATM hedge"]
        vals = [float(sub[sub["arm"] == a]["ann_ret"].iloc[0]) * 100
                for a in arms]
        cols = [COLOR[k] for k in ["z_unhedged", "z_jurek_10d",
                                   "z_jurek_25d", "z_jurek_atm"]]
        ax.bar(arms, vals, color=cols, width=0.6)
        ax.axhline(0, color="#444444", lw=0.8)
        ax.set_title(uni, loc="left")
        ax.tick_params(axis="x", labelrotation=25)
        ax.grid(axis="x", visible=False)
    axes[0].set_ylabel("Ann. return (%/yr)")
    fig.tight_layout()
    fig.savefig(FIG / "fig_ch_ladder.pdf")
    plt.close(fig)

    fig, ax = plt.subplots(figsize=(6.2, 2.6))
    roll = prem.rolling(12, min_periods=6).mean()
    for col, key in [("prem_atm", "z_jurek_atm"), ("prem_25d", "z_jurek_25d"),
                     ("prem_10d", "z_jurek_10d")]:
        ax.plot(roll.index, roll[col], color=COLOR[key], lw=1.5)
        ax.annotate({"prem_atm": "ATM", "prem_25d": "25d",
                     "prem_10d": "10d"}[col],
                    xy=(roll.index[-1], roll[col].iloc[-1]), xytext=(6, 0),
                    textcoords="offset points", va="center", fontsize=8.5,
                    color=COLOR[key])
    ax.set_ylabel("Book insurance premium (%/yr)")
    ax.set_xlim(pd.Timestamp("2006-01-01"), pd.Timestamp("2029-06-30"))
    ax.grid(axis="x", visible=False)
    fig.tight_layout()
    fig.savefig(FIG / "fig_ch_premium.pdf")
    plt.close(fig)

    g10ev = events[events["universe"] == "G10"].set_index("month")
    fig, ax = plt.subplots(figsize=(6.2, 2.6))
    x = np.arange(len(g10ev))
    for i, (lab, key) in enumerate([("unhedged", "z_unhedged"),
                                    ("25d hedge", "z_jurek_25d"),
                                    ("ATM hedge", "z_jurek_atm")]):
        ax.bar(x + (i - 1) * 0.27, g10ev[lab] * 100, width=0.25,
               color=COLOR[key], label=lab)
    ax.axhline(0, color="#444444", lw=0.8)
    ax.set_xticks(x, [m[:7] for m in g10ev.index], rotation=25)
    ax.set_ylabel("Month return (%)")
    ax.legend(loc="lower right", fontsize=8)
    ax.grid(axis="x", visible=False)
    fig.tight_layout()
    fig.savefig(FIG / "fig_ch_events.pdf")
    plt.close(fig)

    print("\nfigures + tables written")


if __name__ == "__main__":
    main()
