"""The strategy, replicable: sorted carry book +/- the 25d/10d spread overlay.

Consolidates the 2026-07-22 session's ad-hoc runs into one script (LOG.md):

1. Team-style book on our own panel: rank currencies by 1M forward discount,
   long the top-5 / short the bottom-5, equal weight, monthly. Legs enter
   only when the sorted side agrees with the sign rule (rare mismatches
   dropped and counted).
2. Arms: vanilla carry, spread-financed (sell 25d / buy 10d per leg, mid
   vols), spread-financed crossed (sell at bid vol / buy at ask vol).
3. Forward transaction costs, house model on OWN quoted spreads: maintained
   notional rolls at the POINTS half-spread, weight changes pay the OUTRIGHT
   half-spread (PX_BID/PX_ASK from spot/fwd parquets incl. the EM pull).
   Forward costs are identical across arms, so the overlay pickup is
   forward-cost-invariant; only the option fill touches it.
4. Also runs, for the record: the sign-book EM SPR variant and the
   premium-gap weighting (tested 2026-07-22, does not beat SPR).

Windows: 2008-01+ (house convention, crash in sample) and 2009-01+.
Output: out/strategy_results.csv + printed table.
Run: .venv/Scripts/python.exe research/crash_hedged/strategy.py
"""
from __future__ import annotations

import pathlib
import sys

import numpy as np
import pandas as pd
import statsmodels.api as sm

sys.path.insert(0, "research/crash_hedged")
import build_panel as bp
import hedged_carry as hc

OUT = pathlib.Path("research/crash_hedged/out")
K = 5                     # names per leg in the sorted book
END = "2026-06-30"
WINDOWS = ["2008-01-01", "2009-01-01"]
# The 24 names of the pre-expansion panel. The regression anchors are pinned
# to this book; the broad book (all 33, added 2026-07-22) reports beside it.
INSURED24 = ["AUD", "CAD", "CHF", "CZK", "DKK", "EUR", "GBP", "HUF", "JPY",
             "KRW", "MXN", "NOK", "NZD", "PLN", "SEK", "SGD", "ZAR",
             "BRL", "TRY", "CNH", "THB", "ILS", "INR", "TWD"]


def nw_t(s, lags=6):
    s = s.dropna()
    if len(s) < 24:
        return np.nan
    return float(sm.OLS(s.values, np.ones(len(s))).fit(
        cov_type="HAC", cov_kwds={"maxlags": lags}).tvalues[0])


def ann_sr(r):
    r = r.dropna()
    return r.mean() * 12, r.mean() * 12 / (r.std() * np.sqrt(12))


def month_end_field(df, tickers, field):
    sub = df[df["ticker"].isin(tickers) & (df["field"] == field)]
    return (sub.pivot_table(index="date", columns="ticker", values="value")
            .resample("ME").last())


def half_spreads():
    """Per-currency month-end relative half-spreads: points-only (the roll)
    and outright (weight changes), from own PX_BID/PX_ASK."""
    spot_l = bp.concat_dedup(bp.load_long("spot_daily.parquet"),
                             bp.load_long("spot_fwd_em_daily.parquet"))
    fwd_l = bp.concat_dedup(bp.load_long("fwd_points_1m_daily.parquet"),
                            bp.load_long("spot_fwd_em_daily.parquet"))
    out = {}
    for c, pair in bp.PAIR.items():
        st, ft = f"{pair} Curncy", f"{bp.FWD_ROOT.get(c, c)}1M Curncy"
        sc = bp.POINT_SCALE.get(c, 1e4)
        try:
            sb = month_end_field(spot_l, [st], "PX_BID")[st]
            sa = month_end_field(spot_l, [st], "PX_ASK")[st]
            sm_ = month_end_field(spot_l, [st], "PX_LAST")[st]
            pb = month_end_field(fwd_l, [ft], "PX_BID")[ft]
            pa = month_end_field(fwd_l, [ft], "PX_ASK")[ft]
        except KeyError:
            continue
        fmid = sm_ + (pb + pa) / 2 / sc
        out[c] = pd.DataFrame({
            "hs_out": ((sa + pa / sc) - (sb + pb / sc)).abs() / 2 / fmid,
            "hs_pts": (pa - pb).abs() / 2 / sc / fmid})
    return out


def sorted_book(legs, ccys=None):
    """Top/bottom-K equal-weight book; returns portfolio frame + fwd costs.
    ``ccys`` restricts the ranked universe (None = every currency priced)."""
    sub = legs.dropna(subset=["z_unhedged", "z_ps"]).copy()
    if ccys is not None:
        sub = sub[sub["ccy"].isin(ccys)]
    sub["rank"] = sub.groupby("month_end")["fwd_disc"].rank(ascending=False)
    sub["n"] = sub.groupby("month_end")["ccy"].transform("count")
    sel = sub[((sub["rank"] <= K) & (sub["q"] > 0))
              | ((sub["rank"] > sub["n"] - K) & (sub["q"] < 0))].copy()
    sel["w"] = np.where(sel["q"] > 0, 1 / K, -1 / K)

    port = pd.DataFrame({
        c: (sel[c] * (1 / K)).groupby(sel["ret_month"]).sum(min_count=1)
        for c in ["z_unhedged", "z_ps", "z_ps_cross"]})

    hs = half_spreads()
    W = sel.pivot_table(index="month_end", columns="ccy",
                        values="w").fillna(0.0)
    dW = W.diff().abs()
    dW.iloc[0] = W.iloc[0].abs()
    cost = pd.Series(0.0, index=W.index)
    for c in W.columns:
        if c not in hs:
            continue
        h = hs[c].reindex(W.index)
        cost = cost.add(W[c].abs() * h["hs_pts"] + dW[c] * h["hs_out"],
                        fill_value=0.0)
    cost.index = cost.index + pd.offsets.MonthEnd(1)
    port["fwd_cost"] = cost.reindex(port.index).fillna(0.0)
    n_mismatch = int(2 * K * port.shape[0] - len(sel))
    return port, n_mismatch


def main():
    legs = hc.build_legs("mid", "native")
    books = {"sorted24": sorted_book(legs, INSURED24),
             "sorted-broad": sorted_book(legs)}
    em = sorted(set(legs["ccy"].unique()) - set(hc.G10))
    spr = hc.portfolio(legs, em, "SPR")

    rows = []
    for start in WINDOWS:
        s = spr[(spr.index >= start) & (spr.index <= END)]
        for bname, (port, _) in books.items():
            p = port[(port.index >= start) & (port.index <= END)]
            for arm, lab in [("z_unhedged", "vanilla"), ("z_ps", "strategy"),
                             ("z_ps_cross", "strategy full-spread")]:
                g_ann, g_sr = ann_sr(p[arm])
                n_ann, n_sr = ann_sr(p[arm] - p["fwd_cost"])
                d = (p[arm] - p["z_unhedged"]).dropna()
                rows.append({"window": start[:4], "book": bname,
                             "arm": lab, "gross_ann": g_ann, "gross_sr": g_sr,
                             "net_ann": n_ann, "net_sr": n_sr,
                             "pickup_ann": d.mean() * 12 if arm != "z_unhedged" else np.nan,
                             "pickup_t": nw_t(d) if arm != "z_unhedged" else np.nan})
        for arm, lab in [("z_unhedged", "vanilla"), ("z_ps", "strategy")]:
            a, r = ann_sr(s[arm][(s.index >= start)])
            d = (s["z_ps"] - s["z_unhedged"]).dropna()
            d = d[d.index >= start]
            rows.append({"window": start[:4], "book": "sign-book EM SPR",
                         "arm": lab, "gross_ann": a, "gross_sr": r,
                         "net_ann": np.nan, "net_sr": np.nan,
                         "pickup_ann": d.mean() * 12 if arm == "z_ps" else np.nan,
                         "pickup_t": nw_t(d) if arm == "z_ps" else np.nan})
    res = pd.DataFrame(rows)
    res.to_csv(OUT / "strategy_results.csv", index=False)
    for bname, (_, n_mismatch) in books.items():
        print(f"{bname}: {n_mismatch} sign-mismatch leg-months dropped")
    print(res.round(3).to_string(index=False))

    # regression anchors from the 2026-07-22 session (LOG.md), pinned to the
    # 24-name book so universe expansion cannot silently move them
    a = res[(res["window"] == "2008") & (res["book"] == "sorted24")]
    van = a[a["arm"] == "vanilla"].iloc[0]
    st = a[a["arm"] == "strategy"].iloc[0]
    assert abs(van["net_ann"] - 0.0318) < 5e-4 and abs(st["net_ann"] - 0.0438) < 5e-4, \
        "net levels moved vs logged session numbers"
    assert abs(st["pickup_ann"] - 0.0120) < 5e-4 and abs(st["pickup_t"] - 2.64) < 0.05, \
        "pickup moved vs logged session numbers"
    print("\nREGRESSION ANCHORS OK (match LOG.md 2026-07-22 numbers)")


if __name__ == "__main__":
    main()
