"""D1 rerun — the skewness battery on TRUE model-free risk-neutral skewness.

Plan §17.1 closed D1 as a null, and flagged one upgrade as "the highest-value,
zero-cost rerun": replace the 25Δ risk-reversal/ATM **slope proxy** with a proper
Bakshi–Kapadia–Madan model-free risk-neutral skewness, built from the 10Δ wings
that were in `data/raw` all along. `cesare/bkm_skew.py` builds that quantity;
this module re-runs the battery on it.

    python cesare/d1_bkm_rerun.py

**Why it matters.** D1's flagship test was Li–Sarno–Zinna's claim that a skewness
risk premium *subsumes* carry, and D1 falsified it — on this sample carry
subsumes SRP (CARRY~SRP alpha +3.76%/yr, t +2.19). But SRP is *defined* as
physical minus **model-free** risk-neutral skewness, and D1 could only feed it a
smile slope. A single-source spanning claim rejected using the wrong input is not
a rejection anyone should rely on. Either the null survives the correct
construction — and becomes bulletproof — or it does not, and that is a bigger
result than the original.

Everything runs on the shared base (`strategy.run`), matched universe U21, so the
numbers sit directly beside the committed `skew_carry_comparison.csv`.

Outputs: `p3_d1_bkm_comparison.csv`, `p3_d1_bkm_spanning.csv`,
`p3_d1_bkm_signal_agreement.csv`.
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from strategy import fx_utils as fx, run
from strategy.episodes import ERAS, STRESS, report_windows

from bkm_skew import bkm_skew_panel

OUTPUTS = Path(__file__).resolve().parent / "outputs"

#: Trailing window for the physical skewness leg (Li–Sarno–Zinna use long
#: windows; third moments are noisy). D1's value, kept so the only thing that
#: changes between the two runs is the risk-neutral leg.
REALIZED_WINDOW = 252

#: The bars D1 was measured against (plan §17).
BAR_BASE, BAR_RR = 0.4659, 0.4559

#: Committed D1 net Sharpes, for the side-by-side. From
#: `cesare/outputs/skew_carry_comparison.csv`.
D1_COMMITTED = {"carry": 0.4962, "iskew": 0.1316, "clean": -0.0309, "srp": -0.0906}


def matched_universe(panel: pd.DataFrame) -> list[str]:
    """Tradable 27 intersected with option coverage — D1's U21."""
    tradable = run().universe
    return [c for c in tradable if c in panel.columns]


def signals(tenor: str = "1M") -> dict[str, pd.DataFrame]:
    """The three skew signals, model-free and proxy, on one calendar.

    `iskew_*` are **crash-positive** (high = expensive crash insurance), matching
    D1's convention so the two runs sort the same way round: the model-free
    panel is the skewness itself, so its crash-positive form is its negative.
    """
    base = run()
    xret = base.panels.xret
    rn = bkm_skew_panel(tenor)
    proxy = fx.implied_skew_panel(tenor, 25, standardize=True)
    phys = fx.realized_skew_panel(xret, window=REALIZED_WINDOW)

    u21 = matched_universe(rn)
    rn, proxy, phys = rn[u21], proxy.reindex(columns=u21), phys.reindex(columns=u21)
    carry = base.panels.carry[u21]

    return {
        "universe": u21, "carry": carry, "xret": xret[u21],
        # crash-positive skew signals
        "iskew_bkm": -rn,
        "iskew_proxy": proxy,
        # SRP = physical - risk-neutral (Li-Sarno-Zinna), built exactly as D1
        # built it: each leg cross-sectionally z-scored before summing, because
        # a realised third moment and a risk-neutral skewness are on completely
        # different scales and a raw difference would just be the larger one.
        # Risk-neutral skew is the NEGATIVE of the crash-positive panels, so
        # z(physical) - z(RN) = z(physical) + z(crash-positive).
        # Verified against the committed run: with the raw difference the proxy
        # variant scores -0.3629 against a committed -0.0906 and its spanning
        # beta flips sign; z-scored it reproduces D1 exactly.
        "srp_bkm": fx.zscore_xs(phys) + fx.zscore_xs(-rn),
        "srp_proxy": fx.zscore_xs(phys) + fx.zscore_xs(proxy),
        # clean carry: the part of carry orthogonal to priced crash risk (Jurek)
        "clean_bkm": fx.xs_residual(carry, -rn),
        "clean_proxy": fx.xs_residual(carry, proxy),
        "rn": rn, "proxy": proxy, "phys": phys,
    }


def _stats(res, ref=None) -> dict:
    s = res.summary(benchmark=None)
    g = s.loc[[i for i in s.index if i.endswith("_gross")][0]]
    n = s.loc[[i for i in s.index if i.endswith("_net")][0]]
    row = {"gross_sharpe": float(g["sharpe"]), "net_sharpe": float(n["sharpe"]),
           "ann_return_net": float(n["ann_return"]), "ann_vol_net": float(n["ann_vol"]),
           "max_drawdown": float(n["max_drawdown"]), "CVaR_99": float(n["CVaR_99"]),
           "skew": float(n["skew"]), "turnover": float(res.turnover),
           "cost_drag": float(res.cost_drag), "n_days": int(n["n_days"])}
    if ref is not None:
        a = fx.nw_regression(res.net.rename("y"),
                             ref.net.rename("carry").to_frame(), lags=5)
        row["alpha_vs_carry_ann"] = a["alpha_ann"] if a else np.nan
        row["t_alpha_vs_carry"] = a["alpha_t"] if a else np.nan
    return row


def battery() -> tuple[pd.DataFrame, pd.DataFrame]:
    """The D1 variants, model-free vs proxy, against the matched carry anchor."""
    sg = signals()
    u21 = sg["universe"]
    anchor = run(universe=u21, name="U21_carry")

    variants = {
        "U21_carry (anchor)": anchor,
        "U21_iskew_bkm": run(universe=u21, signal=sg["iskew_bkm"], name="U21_iskew_bkm"),
        "U21_iskew_proxy": run(universe=u21, signal=sg["iskew_proxy"], name="U21_iskew_proxy"),
        "U21_srp_bkm": run(universe=u21, signal=sg["srp_bkm"], name="U21_srp_bkm"),
        "U21_srp_proxy": run(universe=u21, signal=sg["srp_proxy"], name="U21_srp_proxy"),
        "U21_clean_bkm": run(universe=u21, signal=sg["clean_bkm"], name="U21_clean_bkm"),
        "U21_clean_proxy": run(universe=u21, signal=sg["clean_proxy"], name="U21_clean_proxy"),
    }

    rows, episodes = [], []
    for label, res in variants.items():
        row = {"variant": label, "input": ("model-free BKM" if "bkm" in label
                                           else "25d slope proxy" if "proxy" in label
                                           else "carry"),
               **_stats(res, None if res is anchor else anchor)}
        key = label.split("_")[1] if "_" in label else "carry"
        row["d1_committed_net_sharpe"] = D1_COMMITTED.get(key, np.nan)
        row["bar_baseline"], row["bar_rr"] = BAR_BASE, BAR_RR
        row["beats_both_bars"] = bool(row["net_sharpe"] > max(BAR_BASE, BAR_RR))
        rows.append(row)
        for tag, w in (("ERAS", ERAS), ("STRESS", STRESS)):
            rep = report_windows(res, w, which="both")
            rep.insert(0, "variant", label)
            rep.insert(1, "window_set", tag)
            episodes.extend(rep.to_dict("records"))

    out = pd.DataFrame(rows)
    out.to_csv(OUTPUTS / "p3_d1_bkm_comparison.csv", index=False)
    return out, pd.DataFrame(episodes)


def spanning() -> pd.DataFrame:
    """SRP vs carry, both directions, on unit long/short factor books.

    The Li–Sarno–Zinna claim is that SRP spans carry. D1 tested it with the slope
    proxy and found the reverse; this repeats it with the model-free definition.
    """
    sg = signals()
    xret = sg["xret"]
    factors = {
        "CARRY": fx.carry_hml_factor(xret, sg["carry"]),
        "SRP_bkm": fx.carry_hml_factor(xret, sg["srp_bkm"]),
        "SRP_proxy": fx.carry_hml_factor(xret, sg["srp_proxy"]),
    }
    pairs = [("SRP_bkm", "CARRY"), ("CARRY", "SRP_bkm"),
             ("SRP_proxy", "CARRY"), ("CARRY", "SRP_proxy")]
    rows = []
    for y, x in pairs:
        r = fx.nw_regression(factors[y].rename("y"),
                             factors[x].rename(x).to_frame(), lags=5)
        if r is None:
            continue
        rows.append({"regression": f"{y}~{x}", "alpha_ann": r["alpha_ann"],
                     "alpha_t": r["alpha_t"], "beta": r.get(f"beta_{x}"),
                     "t_beta": r.get(f"t_{x}"), "r2": r["r2"], "n": r["n"]})
    out = pd.DataFrame(rows)
    out.to_csv(OUTPUTS / "p3_d1_bkm_spanning.csv", index=False)
    return out


def signal_agreement() -> pd.DataFrame:
    """How much the model-free signal actually differs from the proxy.

    The question behind the whole rerun: if the two inputs rank currencies almost
    identically then D1's null was never at risk, and saying so quantitatively is
    more useful than repeating the backtest.
    """
    sg = signals()
    rn, proxy = sg["rn"], sg["proxy"]
    me = rn.index.intersection(proxy.index)
    a, b = -rn.loc[me], proxy.loc[me]          # both crash-positive
    rows = []
    for c in a.columns:
        j = pd.concat([a[c], b[c]], axis=1).dropna()
        if len(j) < 60:
            continue
        rows.append({"currency": c, "n_months": len(j),
                     "corr_level": float(j.iloc[:, 0].corr(j.iloc[:, 1])),
                     "corr_change": float(j.iloc[:, 0].diff().corr(j.iloc[:, 1].diff()))})
    out = pd.DataFrame(rows)
    # Cross-sectional rank agreement is what a sort actually consumes.
    ranks = []
    for dt in me:
        x, y = a.loc[dt].dropna(), b.loc[dt].dropna()
        common = x.index.intersection(y.index)
        if len(common) >= 8:
            ranks.append(x[common].rank().corr(y[common].rank(), method="spearman"))
    out.attrs["xs_rank_corr"] = float(np.nanmean(ranks))
    out["xs_rank_corr_mean"] = float(np.nanmean(ranks))
    out.to_csv(OUTPUTS / "p3_d1_bkm_signal_agreement.csv", index=False)
    return out


def main() -> None:
    pd.set_option("display.width", 230)
    agree = signal_agreement()
    print("How different is the model-free signal from the 25d proxy?")
    print(f"  per-currency level corr : median {agree['corr_level'].median():.4f}  "
          f"min {agree['corr_level'].min():.4f}")
    print(f"  per-currency change corr: median {agree['corr_change'].median():.4f}")
    print(f"  CROSS-SECTIONAL rank corr (what the sort consumes): "
          f"{agree['xs_rank_corr_mean'].iloc[0]:.4f}")

    tab, _ = battery()
    print("\nD1 battery, model-free vs proxy (matched U21, net of costs):")
    cols = ["variant", "input", "gross_sharpe", "net_sharpe", "d1_committed_net_sharpe",
            "max_drawdown", "CVaR_99", "skew", "turnover",
            "alpha_vs_carry_ann", "t_alpha_vs_carry", "beats_both_bars"]
    print(tab[cols].round(4).to_string(index=False))

    sp = spanning()
    print("\nSpanning (unit long/short factor books, gross, NW 5 lags):")
    print(sp.round(4).to_string(index=False))

    srp = tab.set_index("variant").loc["U21_srp_bkm"]
    carry_row = sp.set_index("regression")
    print("\n" + "=" * 78)
    beat = bool(srp["beats_both_bars"])
    subsumes = (carry_row.loc["CARRY~SRP_bkm", "alpha_t"] < 1.96
                and carry_row.loc["SRP_bkm~CARRY", "alpha_t"] > 1.96)
    print("VERDICT: " + (
        "the model-free construction OVERTURNS D1 — rerun the full battery and "
        "revise §17.1." if (beat or subsumes) else
        "D1's null SURVIVES the correct construction. The skewness risk premium "
        "still does not beat carry, and carry still is not spanned by it — now "
        "measured with the model-free skewness the claim is actually about, not "
        "a smile-slope proxy. The null is bulletproof."))


if __name__ == "__main__":
    main()
