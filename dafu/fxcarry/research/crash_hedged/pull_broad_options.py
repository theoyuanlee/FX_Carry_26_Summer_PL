"""Broad-venue terminal pull: every remaining USD pair with a plausible
option surface, plus the spots and NDF forwards that widen the vanilla book.

The original 19-pair vol scope followed the BER/LRV catalog. This pull drops
that constraint (LOG.md 2026-07-22): attempt HKD, RUB, RON surfaces, retry
the six the team's pull found unquoted (CLP, COP, IDR, MYR, PEN, PHP), and
fetch the spots/forwards missing for the wider carry book. Failed tickers
come back empty and are logged, which settles what exists on this
entitlement. RUB trades until the 2022 freeze; the ingest caps it there.

Outputs: data/raw/fx_vol_broad_daily.parquet, spot_fwd_broad_daily.parquet.
Run: .venv/Scripts/python.exe research/crash_hedged/pull_broad_options.py
"""
from __future__ import annotations

import pathlib

import pandas as pd

from pull_em_options import bdh_long  # same chunked long-format fetcher

RAW = pathlib.Path("data/raw")
START, END = "1995-01-01", "2026-07-22"
FIELDS = ["PX_LAST", "PX_BID", "PX_ASK"]

VOL_PAIRS = ["USDHKD", "USDRUB", "USDRON",
             "USDCLP", "USDCOP", "USDIDR", "USDMYR", "USDPEN", "USDPHP"]
VOL_TICKERS = [f"{p}{t}{tn} BGN Curncy" for p in VOL_PAIRS
               for t in ["V", "25R", "25B", "10R", "10B"] for tn in ["1M", "3M"]]
SPOT_TICKERS = [f"USD{c} Curncy" for c in ["RUB", "RON", "CLP", "COP", "PEN"]]
FWD_TICKERS = [f"{root}{tn} Curncy" for root in
               ["RUB", "RON", "CHN", "CLN", "PSN", "IHO"] for tn in ["1M", "3M"]]


def main():
    print(f"attempting {len(VOL_TICKERS)} vol, {len(SPOT_TICKERS)} spot, "
          f"{len(FWD_TICKERS)} fwd tickers")
    vol = bdh_long(VOL_TICKERS, FIELDS, START, END)
    vol.to_parquet(RAW / "fx_vol_broad_daily.parquet")
    sf = bdh_long(SPOT_TICKERS + FWD_TICKERS, FIELDS, START, END)
    sf.to_parquet(RAW / "spot_fwd_broad_daily.parquet")

    got_vol = sorted({t[:6] for t in vol["ticker"].unique()})
    print(f"\nvol rows {len(vol)}; pairs with data: {got_vol}")
    print("pairs attempted but empty:",
          sorted(set(VOL_PAIRS) - set(got_vol)))
    for df, name in [(vol, "vol"), (sf, "spot/fwd")]:
        cov = (df[df["field"] == "PX_LAST"].groupby("ticker")["date"]
               .agg(["min", "max", "count"]))
        print(f"\n=== {name} coverage ===")
        print(cov.to_string())


if __name__ == "__main__":
    main()
