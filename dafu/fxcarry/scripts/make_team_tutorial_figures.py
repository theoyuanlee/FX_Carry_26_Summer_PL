"""Generate figures for the team-survey tutorial from teammates' committed outputs.

Reads only committed CSVs/parquets in FX_Carry_26_Summer_PL; writes PDFs into
fxcarry/docs/tutorials/latex/figures/.
"""
import pathlib

import matplotlib as mpl
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

TEAM = pathlib.Path("D:/GitHub/summer-26/bofa/repos/FX_Carry_26_Summer_PL")
OUT = pathlib.Path("D:/GitHub/summer-26/bofa/repos/fxcarry/docs/tutorials/latex/figures")
OUT.mkdir(parents=True, exist_ok=True)

mpl.rcParams.update({
    "font.family": "serif",
    "font.size": 9,
    "axes.titlesize": 9.5,
    "axes.labelsize": 9,
    "axes.spines.top": False,
    "axes.spines.right": False,
    "axes.grid": True,
    "grid.color": "#dddddd",
    "grid.linewidth": 0.5,
    "axes.axisbelow": True,
    "legend.frameon": False,
    "figure.dpi": 150,
})

# fixed categorical assignment (validated palette): entity -> hue, never cycled
C_ALL = "#0072B2"   # combined G10+EM book
C_G10 = "#D55E00"   # G10-only
C_EM = "#009E73"    # EM-only
C_ALT = "#CC79A7"   # secondary variant
C_BMK = "#888888"   # external benchmarks (dashed)


def endlabel(ax, x, y, text, color, dx=8, dy=0):
    ax.annotate(text, xy=(x, y), xytext=(dx, dy), textcoords="offset points",
                va="center", ha="left", fontsize=8.5, color=color)


def trim_trailing_zeros(s):
    nz = s[s != 0]
    return s.loc[:nz.index[-1]] if len(nz) else s


# ---------------------------------------------------------------- fig 1: team tracks
r = pd.read_csv(TEAM / "cesare/outputs/strategy_returns_daily.csv",
                index_col=0, parse_dates=True)
fig, ax = plt.subplots(figsize=(6.2, 3.0))
series = [("ALL_net", "Combined G10+EM, net", C_ALL, "-", 0),
          ("G10_net", "G10 only, net", C_G10, "-", -6),
          ("DBHVG10U", "DB G10 carry index", C_BMK, "--", 0),
          ("FXCTEM8", "DB EM carry index", "#bbbbbb", "--", 8)]
for col, lab, c, ls, dy in series:
    s = trim_trailing_zeros(r[col].dropna().loc["2007-05-01":"2026-06-30"])
    w = (1 + s).cumprod()
    ax.plot(w.index, w.values, color=c, ls=ls, lw=1.5)
    endlabel(ax, w.index[-1], w.iloc[-1], lab.split(",")[0], c, dy=dy)
ax.set_ylabel("Growth of \\$1")
ax.set_xlim(pd.Timestamp("2007-05-01"), pd.Timestamp("2031-06-30"))
ax.grid(axis="x", visible=False)
fig.tight_layout()
fig.savefig(OUT / "fig_team_tracks.pdf")
plt.close(fig)

# ------------------------------------------------------- fig 2: rolling 3y Sharpe
s = r["ALL_net"].dropna().loc["2007-05-01":"2026-06-30"]
roll = (s.rolling(756, min_periods=504).mean()
        / s.rolling(756, min_periods=504).std()) * np.sqrt(252)
fig, ax = plt.subplots(figsize=(6.2, 2.4))
ax.plot(roll.index, roll.values, color=C_ALL, lw=1.5)
ax.axhline(0, color="#444444", lw=0.8)
ax.axhline(0.466, color="#444444", lw=0.8, ls=":")
ax.annotate("full-sample net Sharpe 0.47", xy=(pd.Timestamp("2008-06-01"), 0.466),
            xytext=(0, 4), textcoords="offset points", fontsize=8, color="#444444")
ax.set_ylabel("Rolling 3y Sharpe (net)")
ax.grid(axis="x", visible=False)
fig.tight_layout()
fig.savefig(OUT / "fig_rolling_sharpe.pdf")
plt.close(fig)

# ---------------------------------------------------------- fig 3: attribution bars
a = pd.read_csv(TEAM / "arjun/outputs/attribution_by_currency.csv", index_col=0)
a = a.sort_values("contrib_ann")
fig, ax = plt.subplots(figsize=(6.2, 4.6))
colors = [C_EM if g == "EM" else C_G10 for g in a["group"]]
ax.barh(a.index, a["contrib_ann"] * 100, color=colors, height=0.62)
ax.axvline(0, color="#444444", lw=0.8)
ax.set_xlabel("Contribution to combined-book net return (% per year)")
ax.grid(axis="y", visible=False)
handles = [mpl.patches.Patch(color=C_EM, label="EM"),
           mpl.patches.Patch(color=C_G10, label="G10")]
ax.legend(handles=handles, loc="lower right")
fig.tight_layout()
fig.savefig(OUT / "fig_attribution.pdf")
plt.close(fig)

# -------------------------------------------------- fig 4: theo universes (wealth)
t = pd.read_parquet(TEAM / "theo/data/processed/em_carry_strategy_returns.parquet")
strat_style = {"G10": (C_G10, "G10"),
               "EM ex-CNH": (C_EM, "EM ex-CNH"),
               "EM incl-CNH": (C_ALT, "EM incl-CNH"),
               "G10 + EM ex-CNH": (C_ALL, "G10 + EM ex-CNH")}
fig, ax = plt.subplots(figsize=(6.2, 3.0))
for name, (c, lab) in strat_style.items():
    g = t[t["strategy"] == name].set_index("month_end")["wealth_gross"].dropna()
    ax.plot(g.index, g.values, color=c, lw=1.5)
    endlabel(ax, g.index[-1], g.iloc[-1], lab, c)
ax.set_ylabel("Growth of \\$1 (gross)")
ax.set_xlim(pd.Timestamp("2007-01-01"), pd.Timestamp("2031-06-30"))
ax.grid(axis="x", visible=False)
fig.tight_layout()
fig.savefig(OUT / "fig_theo_universes.pdf")
plt.close(fig)

# ------------------------------------------------ fig 5: theo roll-cost frontier
cmp_ = pd.read_parquet(TEAM / "theo/data/processed/g10_em_carry_comparison.parquet")
cmp_ = cmp_.assign(bps=cmp_["cost_bps"].fillna(0.0))
fig, ax = plt.subplots(figsize=(6.2, 2.8))
for name, (c, lab) in strat_style.items():
    g = cmp_[cmp_["strategy"] == name].sort_values("bps")
    ax.plot(g["bps"], g["sharpe_ratio"], color=c, lw=1.5, marker="o", ms=3.5)
    ax.annotate(lab, xy=(g["bps"].iloc[-1], g["sharpe_ratio"].iloc[-1]),
                xytext=(6, 0), textcoords="offset points", va="center",
                fontsize=8.5, color=c)
ax.axhline(0, color="#444444", lw=0.8)
ax.set_xlabel("Assumed roll cost (bp per month on rolled notional)")
ax.set_ylabel("Gross Sharpe $\\rightarrow$ net Sharpe")
ax.set_xlim(-1, 62)
fig.tight_layout()
fig.savefig(OUT / "fig_cost_frontier.pdf")
plt.close(fig)

# ----------------------------------------------------------- fig 6: vidhi adaptive
v = pd.read_csv(TEAM / "vidhi/outputs/adaptive_strategy_returns_monthly.csv",
                index_col=0, parse_dates=True)
fig, ax = plt.subplots(figsize=(6.2, 2.8))
for col, lab, c, dy in [("static", "static carry", C_ALL, 0),
                        ("binary_filter", "binary regime filter", C_G10, -8),
                        ("probability_scaled", "probability-scaled", C_EM, 8)]:
    s = v[col].dropna()
    w = (1 + s).cumprod()
    ax.plot(w.index, w.values, color=c, lw=1.5)
    endlabel(ax, w.index[-1], w.iloc[-1], lab, c, dy=dy)
ax.axhline(1, color="#444444", lw=0.8)
ax.set_ylabel("Growth of \\$1 (net)")
ax.set_xlim(pd.Timestamp("2007-01-01"), pd.Timestamp("2033-06-30"))
ax.grid(axis="x", visible=False)
fig.tight_layout()
fig.savefig(OUT / "fig_vidhi_adaptive.pdf")
plt.close(fig)

# ------------------------------------------------------ fig 7: the carry signal
def carry_series(wide, spot_tk, fwd_tk, scale, usd_per_fx):
    s = pd.to_numeric(wide[(spot_tk, "PX_LAST")], errors="coerce")
    p = pd.to_numeric(wide[(fwd_tk, "PX_LAST")], errors="coerce")
    f = s + p / scale
    carry = np.log(s / f) * 12.0
    if not usd_per_fx:
        carry = -carry
    carry.index = pd.to_datetime(carry.index)
    return carry.resample("ME").last().dropna() * 100

g10w = pd.read_parquet(TEAM / "data/raw/g10_fx_spot_forward_wide.parquet")
emw = pd.read_parquet(TEAM / "data/raw/em_fx_spot_forward_wide.parquet")

panelA = {
    "AUD": (carry_series(g10w, "AUD Curncy", "AUD1M Curncy", 1e4, True), C_ALL),
    "CHF": (carry_series(g10w, "CHF Curncy", "CHF1M Curncy", 1e4, False), C_G10),
    "JPY": (carry_series(g10w, "JPY Curncy", "JPY1M Curncy", 1e2, False), C_EM),
}
panelB = {
    "TRY": (carry_series(emw, "TRY Curncy", "TRY1M Curncy", 1e4, False), C_ALL),
    "BRL": (carry_series(emw, "BRL Curncy", "BCN1M Curncy", 1e4, False), C_G10),
    "MXN": (carry_series(emw, "MXN Curncy", "MXN1M Curncy", 1e4, False), C_EM),
}
fig, axes = plt.subplots(1, 2, figsize=(6.4, 2.8))
for ax, panel, title in [(axes[0], panelA, "G10"), (axes[1], panelB, "Emerging markets")]:
    for name, (c, col) in panel.items():
        ax.plot(c.index, c.values, color=col, lw=1.2)
        endlabel(ax, c.index[-1], c.iloc[-1], name, col, dx=4)
    ax.axhline(0, color="#444444", lw=0.8)
    ax.set_title(title, loc="left")
    ax.grid(axis="x", visible=False)
    ax.set_xlim(pd.Timestamp("2007-01-01"), pd.Timestamp("2030-06-30"))
axes[0].set_ylabel("1M forward-implied carry (% p.a.)")
fig.tight_layout()
fig.savefig(OUT / "fig_carry_signal.pdf")
plt.close(fig)

for name, (c, _) in {**panelA, **panelB}.items():
    print(f"{name}: mean {c.mean():5.1f}%  last {c.iloc[-1]:5.1f}%  min {c.min():6.1f}  max {c.max():6.1f}")
print("figures written to", OUT)
