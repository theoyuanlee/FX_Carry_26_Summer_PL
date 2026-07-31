"""Grid-completion pull: make the 14 new pairs' data match the original
universe's shape (LOG.md 2026-07-22, "consistent universe").

- Vol surfaces: the original 19 pairs carry {V,25R,25B,10R,10B,5R,5B} at
  tenors {1W,1M,2M,3M,6M,9M,1Y,18M,2Y}. The 14 pairs added on 2026-07-22
  have only {V,25R,25B,10R,10B} x {1M,3M}. This pulls the difference.
- Forward points: the original catalog has tenors 1W..2Y in
  fwd_points_multi_daily.parquet. The 12 new/NDF roots have only 1M/3M.
  This pulls the remaining tenors.

Outputs: data/raw/fx_vol_grid_daily.parquet, fwd_points_grid_daily.parquet.
Run: .venv/Scripts/python.exe research/crash_hedged/pull_grid_completion.py
"""
from __future__ import annotations

import pathlib

from pull_em_options import bdh_long

RAW = pathlib.Path("data/raw")
START, END = "1995-01-01", "2026-07-22"
FIELDS = ["PX_LAST", "PX_BID", "PX_ASK"]

NEW_PAIRS = ["USDBRL", "USDTRY", "USDCNH", "USDTHB", "USDILS",
             "USDHKD", "USDRUB", "USDRON", "USDCLP", "USDCOP",
             "USDIDR", "USDMYR", "USDPEN", "USDPHP"]
ALL_TYPES = ["V", "25R", "25B", "10R", "10B", "5R", "5B"]
ALL_TENORS = ["1W", "1M", "2M", "3M", "6M", "9M", "1Y", "18M", "2Y"]
HAVE = {(t, tn) for t in ["V", "25R", "25B", "10R", "10B"]
        for tn in ["1M", "3M"]}
VOL_TICKERS = [f"{p}{t}{tn} BGN Curncy" for p in NEW_PAIRS
               for t in ALL_TYPES for tn in ALL_TENORS
               if (t, tn) not in HAVE]

FWD_ROOTS = ["BCN", "TRY", "CNH", "ILS", "IRN", "NTN",
             "IHO", "CHN", "CLN", "PSN", "RUB", "RON"]
FWD_TENORS_MISSING = ["1W", "2W", "2M", "6M", "9M", "12M", "18M", "2Y"]
FWD_TICKERS = [f"{r}{tn} Curncy" for r in FWD_ROOTS
               for tn in FWD_TENORS_MISSING]


def main():
    print(f"vol grid completion: {len(VOL_TICKERS)} tickers; "
          f"fwd tenors: {len(FWD_TICKERS)} tickers")
    vol = bdh_long(VOL_TICKERS, FIELDS, START, END)
    vol.to_parquet(RAW / "fx_vol_grid_daily.parquet")
    print(f"vol rows {len(vol):,}, tickers with data "
          f"{vol['ticker'].nunique()} of {len(VOL_TICKERS)}")

    fwd = bdh_long(FWD_TICKERS, FIELDS, START, END)
    fwd.to_parquet(RAW / "fwd_points_grid_daily.parquet")
    print(f"fwd rows {len(fwd):,}, tickers with data "
          f"{fwd['ticker'].nunique()} of {len(FWD_TICKERS)}")

    for df, name in [(vol, "vol"), (fwd, "fwd")]:
        got = df["ticker"].unique()
        want = VOL_TICKERS if name == "vol" else FWD_TICKERS
        missing = sorted(set(want) - set(got))
        print(f"\n{name}: {len(missing)} tickers returned nothing")
        if missing:
            print("  e.g.", missing[:10])


if __name__ == "__main__":
    main()
