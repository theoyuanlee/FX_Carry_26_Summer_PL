"""Monthly per-currency panel for crash-hedged carry: S, F, smile, carry sign.

Standalone data layer (LOG.md 2026-07-21 design decision): reads the repo's
own parquets directly, mirrors fxcarry conventions (POINT_SCALE, USD-per-FCU
inversion), writes one tidy monthly panel to research/crash_hedged/out/.

Row = (month_end, ccy): native-quote spot and 1M outright forward, the pair's
market-convention name, FCU-per-USD levels for carry bookkeeping, 1M smile
vols (ATM, 25/10/5-delta call and put sides, mid and ask), US 1M bill.
Everything downstream (hedged/unhedged books) consumes this one file.

Run: python research/crash_hedged/build_panel.py
"""
from __future__ import annotations

import pathlib

import numpy as np
import pandas as pd
import pyarrow.parquet as pq

DATA = pathlib.Path("data/raw")
OUT = pathlib.Path("research/crash_hedged/out")

# Conventions come from the library: point scales, quote directions, and the
# catalog's spot/forward tickers (which carry the NDF roots). The panel
# universe is every currency with vol surfaces on disk, named here.
from fxcarry import Catalog

_CATALOG = Catalog.with_legacy()

UNIVERSE = ["AUD", "CAD", "CHF", "CZK", "DKK", "EUR", "GBP", "HUF", "JPY",
            "KRW", "MXN", "NOK", "NZD", "PLN", "SEK", "SGD", "ZAR",       # original 17
            "BRL", "TRY", "CNH", "THB", "ILS", "INR", "TWD",              # EM pull
            "HKD", "RUB", "RON", "CLP", "COP", "IDR", "MYR", "PEN", "PHP"]  # broad pull
POINT_SCALE = {c: _CATALOG[c].point_scale for c in UNIVERSE}
# The pairs the market already quotes as dollars per foreign unit, so the ones
# that need inverting to reach the FCU-per-USD convention this panel stores.
QUOTED_USD_PER_FCU = {c for c in UNIVERSE if _CATALOG[c].quoted_usd_per_fcu}
PAIR = {c: _CATALOG[c].pair for c in UNIVERSE}
# forward roots come off the catalog's stored 1M tickers
FWD_ROOT = {c: _CATALOG[c].fwd_root for c in UNIVERSE}
# RUB stops being tradable at the February 2022 freeze; later prints are not
# executable and must not enter any book.
RUB_LAST_SIGNAL = "2022-01-31"
SMILE = ["V", "25R", "25B", "10R", "10B", "5R", "5B"]


def load_long(fname):
    """Read a long parquet with ``date`` as datetime64[ns].

    The older pulls store ``date`` as arrow ``date32``, which pandas hands back
    as Python ``date`` objects; pushing 16M of those through ``to_datetime``
    peaks over a gigabyte and dies on a busy machine. Going through arrow with
    ``date_as_object=False`` lands datetime64 straight away. The newer pulls are
    already ``timestamp[ms]``, so the cast keeps every frame on one unit before
    they meet in ``concat_dedup``.
    """
    df = pq.read_table(DATA / fname).to_pandas(date_as_object=False)
    df["date"] = df["date"].astype("datetime64[ns]")
    return df


def month_end_panel(df, tickers, field="PX_LAST"):
    """Long (ticker,date,field,value) -> month-end wide frame, one col/ticker."""
    sub = df[df["ticker"].isin(tickers) & (df["field"] == field)]
    wide = sub.pivot_table(index="date", columns="ticker", values="value")
    return wide.resample("ME").last()


def concat_dedup(*frames):
    """Concat long frames; on (ticker,date,field) collisions the LAST wins
    (list fresher pulls last)."""
    df = pd.concat(frames, ignore_index=True)
    return df.drop_duplicates(["ticker", "date", "field"], keep="last")


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    spot_l, fwd_l, vol_l, bill_l = (load_long(f) for f in
                                    ["spot_daily.parquet",
                                     "fwd_points_1m_daily.parquet",
                                     "fx_vol_daily.parquet",
                                     "tbill_daily.parquet"])
    # 2026-07-22 terminal pulls: EM pack, then the broad-venue pack
    sf_em = load_long("spot_fwd_em_daily.parquet")
    vol_em = load_long("fx_vol_em_daily.parquet")
    sf_br = load_long("spot_fwd_broad_daily.parquet")
    vol_br = load_long("fx_vol_broad_daily.parquet")
    spot_l = concat_dedup(spot_l, sf_em, sf_br)
    fwd_l = concat_dedup(fwd_l, sf_em, sf_br)
    vol_l = concat_dedup(vol_l, vol_em, vol_br)

    # spot tickers: majors are cross-style ("AUDUSD Curncy"), the USD-base
    # names are "USD{c} Curncy" -- both equal PAIR[c] + " Curncy"
    spot_tk = {c: f"{PAIR[c]} Curncy" for c in PAIR}
    fwd_tk = {c: f"{FWD_ROOT.get(c, c)}1M Curncy" for c in PAIR}
    spot = month_end_panel(spot_l, list(spot_tk.values()))
    fwd = month_end_panel(fwd_l, list(fwd_tk.values()))
    bill = month_end_panel(bill_l, ["GB1M Index"])["GB1M Index"] / 100.0

    vol_mid, vol_ask = {}, {}
    for c, pair in PAIR.items():
        tks = [f"{pair}{k}1M BGN Curncy" for k in SMILE]
        vol_mid[c] = month_end_panel(vol_l, tks)
        vol_ask[c] = month_end_panel(vol_l, tks, field="PX_ASK")

    rows = []
    for c, pair in PAIR.items():
        s_native = spot.get(spot_tk[c])
        pts = fwd.get(fwd_tk[c])
        if s_native is None or pts is None:
            print(f"SKIP {c}: missing spot or forward")
            continue
        f_native = s_native + pts / POINT_SCALE.get(c, 1e4)
        # FCU-per-USD levels for carry bookkeeping (library convention)
        s_fcu = 1.0 / s_native if c in QUOTED_USD_PER_FCU else s_native
        f_fcu = 1.0 / f_native if c in QUOTED_USD_PER_FCU else f_native
        frame = pd.DataFrame({
            "ccy": c, "pair": pair,
            "spot_native": s_native, "fwd_native": f_native,
            "spot_fcu": s_fcu, "fwd_fcu": f_fcu,
            # per-month log forward discount of the FOREIGN currency
            # (positive = paid to be long FCU forward = carry currency)
            "fwd_disc": np.log(f_fcu) - np.log(s_fcu),
            "usd_1m": bill,
        })
        vm, va = vol_mid[c].copy(), vol_ask[c].copy()
        vm.columns = [t.split(" ")[0].replace(pair, "") for t in vm.columns]
        va.columns = [t.split(" ")[0].replace(pair, "") for t in va.columns]
        for k in SMILE:
            key = k.replace("1M", "")
            frame[f"vol_{key}_mid"] = vm.get(k.replace("1M", "") + "1M",
                                             vm.get(k))
            frame[f"vol_{key}_ask"] = va.get(k.replace("1M", "") + "1M",
                                             va.get(k))
        rows.append(frame.reset_index().rename(columns={"date": "month_end",
                                                        "index": "month_end"}))

    panel = pd.concat(rows, ignore_index=True)
    # RUB: nothing after the freeze enters any book
    panel = panel[~((panel["ccy"] == "RUB")
                    & (panel["month_end"] > RUB_LAST_SIGNAL))]
    full_smile = panel[[f"vol_{k}_mid" for k in SMILE]].notna().all(axis=1)
    panel["smile_complete"] = full_smile
    panel = panel.dropna(subset=["spot_native", "fwd_native"])
    panel.to_parquet(OUT / "monthly_panel.parquet")

    # coverage report
    cov = (panel[full_smile].groupby("ccy")["month_end"]
           .agg(["min", "max", "count"]))
    print(cov)
    n_by_month = panel[full_smile].groupby("month_end")["ccy"].nunique()
    start8 = n_by_month[n_by_month >= 8].index.min()
    print(f"\nfirst month with >=8 complete smiles: {start8:%Y-%m}")
    print(f"panel rows: {len(panel)}, complete-smile rows: {int(full_smile.sum())}")


if __name__ == "__main__":
    main()
