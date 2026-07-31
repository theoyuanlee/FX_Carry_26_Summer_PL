"""Figures for the crash-hedged carry slide deck (docs/slides/).

Redraws the four charts that notebooks/03_crash_hedged_carry.ipynb makes
inline, sized for a 16:9 beamer frame, into
docs/tutorials/latex/figures/fig_nb_*.pdf.  Nothing is re-derived: the
scatter and the smile come straight off the panel, the give-up panels off
out/per_currency.csv, and the wealth curve off out/tutorial_series.parquet,
which is the same book the notebook reconciles against in Step 9.

Run: .venv/Scripts/python.exe research/crash_hedged/make_deck_figures.py
"""
from __future__ import annotations

import pathlib

import matplotlib as mpl
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from fxcarry import Smile


def _smile_vol(atm, rr, bf, side):
    """One wing off a three-number quote, atm + bf +- rr/2, via the library."""
    return Smile(atm=atm, risk_reversal={25: rr}, butterfly={25: bf}).vol(25, side)

OUT = pathlib.Path("research/crash_hedged/out")
FIG = pathlib.Path("docs/tutorials/latex/figures")
G10 = ["AUD", "CAD", "CHF", "EUR", "GBP", "JPY", "NOK", "NZD", "SEK"]
START, END = "2008-01-01", "2026-06-30"

mpl.rcParams.update({
    "font.family": "serif", "font.size": 8, "axes.spines.top": False,
    "axes.spines.right": False, "axes.grid": True, "grid.color": "#dddddd",
    "grid.linewidth": 0.5, "axes.axisbelow": True, "legend.frameon": False,
    "figure.dpi": 150})
BLUE, ORANGE, GREEN, GREY = "#0072B2", "#D55E00", "#009E73", "#888888"


def crash_scatter(panel):
    """Average carry against the worst month the position took."""
    w = panel[(panel["month_end"] >= START) & (panel["month_end"] <= END)].copy()
    w["s_usd"] = np.where(w["pair"].str.endswith("USD"),
                          w["spot_native"], 1 / w["spot_native"])
    w["move"] = w.groupby("ccy")["s_usd"].transform(lambda s: np.log(s).diff())
    w["against"] = np.sign(w.groupby("ccy")["fwd_disc"].transform("mean")) * w["move"]
    c = w.groupby("ccy").agg(carry=("fwd_disc", "mean"), worst=("against", "min"))
    c["carry"] *= 1200
    c["worst"] *= 100

    fig, ax = plt.subplots(figsize=(6.2, 2.35))
    is_g10 = c.index.isin(G10)
    ax.scatter(c.loc[is_g10, "carry"], c.loc[is_g10, "worst"], s=20,
               color=BLUE, label="G10")
    ax.scatter(c.loc[~is_g10, "carry"], c.loc[~is_g10, "worst"], s=20,
               color=ORANGE, label="EM")
    for k in ["TRY", "RUB", "BRL", "ZAR", "MXN", "RON", "HUF", "AUD", "JPY", "CHF"]:
        ax.annotate(k, (c.loc[k, "carry"], c.loc[k, "worst"]), fontsize=7,
                    xytext=(3, 3), textcoords="offset points", color="#444444")
    slope, icpt = np.polyfit(c["carry"], c["worst"], 1)
    xs = np.array([c["carry"].min(), c["carry"].max()])
    ax.plot(xs, icpt + slope * xs, color=GREY, lw=1.2)
    ax.annotate(f"slope {slope:.2f},  corr {c['carry'].corr(c['worst']):+.2f}",
                xy=(0.985, 0.06), xycoords="axes fraction", ha="right",
                fontsize=8, color="#444444")
    ax.margins(x=0.08)
    ax.set_xlabel("Average carry (%/yr)")
    ax.set_ylabel("Worst month (%)")
    ax.legend(loc="upper right", fontsize=8)
    fig.tight_layout(pad=0.4)
    fig.savefig(FIG / "fig_nb_crash.pdf")
    plt.close(fig)
    return slope, float(c["carry"].corr(c["worst"]))


def smile(panel):
    """USDJPY 1M smile, a calm month against a crisis month."""
    def points(date):
        r = panel[(panel["ccy"] == "JPY") & (panel["month_end"] == date)].iloc[0]
        p = {}
        for d in (10, 25):
            p[f"{d}d put"] = _smile_vol(r["vol_V_mid"], r[f"vol_{d}R_mid"],
                                        r[f"vol_{d}B_mid"], "put")
        p["ATM"] = r["vol_V_mid"]
        for d in (25, 10):
            p[f"{d}d call"] = _smile_vol(r["vol_V_mid"], r[f"vol_{d}R_mid"],
                                         r[f"vol_{d}B_mid"], "call")
        return pd.Series(p)

    calm, crisis = points("2026-06-30"), points("2008-10-31")
    fig, ax = plt.subplots(figsize=(6.2, 2.30))
    ax.plot(crisis.index, crisis.values, marker="o", ms=4, color=ORANGE, lw=1.6,
            label="October 2008 (crisis)")
    ax.plot(calm.index, calm.values, marker="o", ms=4, color=BLUE, lw=1.6,
            label="June 2026 (calm)")
    ax.set_ylabel("Implied volatility (%/yr)")
    ax.set_ylim(0, None)
    ax.legend(loc="upper center", fontsize=8)
    fig.tight_layout(pad=0.4)
    fig.savefig(FIG / "fig_nb_smile.pdf")
    plt.close(fig)
    return calm, crisis


def giveup(per):
    """The same give-up under two denominators, stacked on one x-axis."""
    per = per.copy()
    per["share10"] = per["giveup10_ann"] / per["prem10_ann"] * 100
    per["share25"] = per["giveup25_ann"] / per["prem25_ann"] * 100
    is_g10 = per.index.isin(G10)
    x = np.arange(len(per))

    fig, axes = plt.subplots(2, 1, figsize=(6.2, 3.05), sharex=True)
    panels = [(axes[0], "giveup10_ann", "giveup25_ann", 100,
               "%/yr of carry", 0.05, "bottom"),
              (axes[1], "share10", "share25", 1, "% of premium paid",
               0.93, "top")]
    for ax, c10, c25, k, ylab, ty, tva in panels:
        ax.vlines(x, per[c10] * k, per[c25] * k, color="0.82", lw=1.2)
        ax.scatter(x, per[c10] * k, s=14, color=BLUE, zorder=3,
                   label="10-delta (disaster cover)")
        ax.scatter(x, per[c25] * k, s=14, color=ORANGE, zorder=3,
                   label="25-delta (ordinary cover)")
        ax.axhline(0, color="#444444", lw=0.8)
        ax.set_ylabel(ylab, fontsize=8)
        ax.grid(axis="x", visible=False)
        em = per[~is_g10]
        ax.annotate(f"EM avg  10d {em[c10].mean() * k:+.2f}   "
                    f"25d {em[c25].mean() * k:+.2f}",
                    xy=(0.015, ty), xycoords="axes fraction", va=tva,
                    fontsize=7.5, color="#444444",
                    bbox=dict(fc="white", ec="none", pad=1.2))
    axes[0].legend(loc="lower center", bbox_to_anchor=(0.5, 1.0),
               fontsize=7.5, ncol=2, borderpad=0.1)
    axes[1].set_xticks(x)
    axes[1].set_xticklabels([f"{c}*" if c in G10 else c for c in per.index],
                            rotation=90, fontsize=6.5)
    for lbl, g in zip(axes[1].get_xticklabels(), is_g10):
        lbl.set_color(GREEN if g else "#222222")
    fig.tight_layout(pad=0.35, h_pad=0.6)
    fig.savefig(FIG / "fig_nb_giveup.pdf")
    plt.close(fig)
    return per, is_g10


def wealth():
    """Growth of a dollar, net of forward costs."""
    t = pd.read_parquet(OUT / "tutorial_series.parquet")
    net = pd.DataFrame({"plain": t["z_unhedged"] - t["fwd_cost"],
                        "strategy": t["z_ps"] - t["fwd_cost"]}).dropna()
    net = net[(net.index >= START) & (net.index <= END)]
    nav = (1 + net).cumprod()

    fig, ax = plt.subplots(figsize=(6.2, 2.30))
    ax.plot(nav.index, nav["plain"], color=BLUE, lw=1.6, label="plain carry, net")
    ax.plot(nav.index, nav["strategy"], color=ORANGE, lw=1.8, label="strategy, net")
    ax.set_ylabel("Growth of \\$1")
    ax.legend(loc="upper left", fontsize=8)
    fig.tight_layout(pad=0.4)
    fig.savefig(FIG / "fig_nb_wealth.pdf")
    plt.close(fig)
    return net, nav


def main():
    FIG.mkdir(parents=True, exist_ok=True)
    panel = pd.read_parquet(OUT / "monthly_panel.parquet")
    per = pd.read_csv(OUT / "per_currency.csv", index_col=0)

    slope, corr = crash_scatter(panel)
    print(f"crash scatter : slope {slope:.2f}, corr {corr:+.2f}")

    calm, crisis = smile(panel)
    print(f"smile         : calm ATM {calm['ATM']:.2f}, "
          f"crisis ATM {crisis['ATM']:.2f}, "
          f"crisis/calm 10d put {crisis['10d put'] / calm['10d put']:.1f}x")

    per, is_g10 = giveup(per)
    for name, m in [("G10", is_g10), ("EM ", ~is_g10)]:
        s = per[m]
        print(f"{name} giveup   : %/yr  10d {s['giveup10_ann'].mean() * 100:+.2f}  "
              f"25d {s['giveup25_ann'].mean() * 100:+.2f}  "
              f"(25d dearer {int((s['giveup25_ann'] > s['giveup10_ann']).sum())}"
              f"/{int(m.sum())})  |  %prem  10d {s['share10'].mean():+.0f}  "
              f"25d {s['share25'].mean():+.0f}  "
              f"(10d dearer {int((s['share10'] > s['share25']).sum())}/{int(m.sum())})")
    print(f"prem ratio    : 25d / 10d = "
          f"{(per['prem25_ann'] / per['prem10_ann']).mean():.2f}x")

    net, nav = wealth()
    for c in net.columns:
        a = net[c].mean() * 12
        print(f"{c:9s}     : {a * 100:.2f}%/yr, Sharpe {a / (net[c].std() * np.sqrt(12)):.2f}, "
              f"worst month {net[c].min() * 100:.1f}%, final ${nav[c].iloc[-1]:.2f}")

    print("figures:", sorted(p.name for p in FIG.glob("fig_nb_*.pdf")))


if __name__ == "__main__":
    main()
