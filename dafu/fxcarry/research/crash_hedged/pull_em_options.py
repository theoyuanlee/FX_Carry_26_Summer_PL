"""Terminal pull for the EM extension of crash-hedged carry (LOG.md plan).

Pulls, with full available history, in the repo's long format
(ticker/date/field/value):
- Vol surfaces: USD{BRL,TRY,CNH,THB,ILS} x {V,25R,25B,10R,10B} x {1M,3M},
  BGN source, PX_LAST/PX_BID/PX_ASK -> data/raw/fx_vol_em_daily.parquet
- Spot + NDF/outright forward points (1M,3M) for the five new pairs plus the
  forwards that unlock INR/TWD (IRN/NTN roots)
  -> data/raw/spot_fwd_em_daily.parquet

Chunked bdh with per-ticker retry, modeled on the team's bloomberg_data.py.
Run (terminal machine, Bloomberg logged in):
  .venv/Scripts/python.exe research/crash_hedged/pull_em_options.py
"""
from __future__ import annotations

import pathlib
import time

import pandas as pd
from xbbg import blp

RAW = pathlib.Path("data/raw")
START = "1995-01-01"
END = "2026-07-21"
PAIRS = ["USDBRL", "USDTRY", "USDCNH", "USDTHB", "USDILS"]
VOL_TYPES = ["V", "25R", "25B", "10R", "10B"]
TENORS = ["1M", "3M"]
FIELDS = ["PX_LAST", "PX_BID", "PX_ASK"]

VOL_TICKERS = [f"{p}{t}{tn} BGN Curncy"
               for p in PAIRS for t in VOL_TYPES for tn in TENORS]
SPOT_TICKERS = [f"{p} Curncy" for p in PAIRS]
FWD_ROOTS = ["BCN", "TRY", "CNH", "ILS", "THB", "IRN", "NTN"]
FWD_TICKERS = [f"{r}{tn} Curncy" for r in FWD_ROOTS for tn in TENORS]


def bdh_long(tickers, fields, start, end):
    """Chunked bdh -> long DataFrame(ticker,date,field,value); retries singles."""
    frames, failed = [], []
    for i in range(0, len(tickers), 25):
        chunk = tickers[i:i + 25]
        try:
            d = blp.bdh(chunk, fields, start, end)
            frames.append(pd.DataFrame(d.to_pandas()
                                       if hasattr(d, "to_pandas") else d))
        except Exception as e:
            print(f"chunk failed ({chunk[0]}...): {e}; retrying singles")
            failed.extend(chunk)
        time.sleep(0.25)
    for t in failed:
        try:
            d = blp.bdh([t], fields, start, end)
            frames.append(pd.DataFrame(d.to_pandas()
                                       if hasattr(d, "to_pandas") else d))
        except Exception as e:
            print(f"  {t}: FAILED ({e})")
        time.sleep(0.25)
    if not frames:
        return pd.DataFrame(columns=["ticker", "date", "field", "value"])
    out = pd.concat(frames, ignore_index=True)
    # normalize wide (ticker,field) MultiIndex output if this xbbg returns it
    if "ticker" not in out.columns:
        out = out.stack([0, 1], future_stack=True).rename("value").reset_index()
        out.columns = ["date", "ticker", "field", "value"]
    out["date"] = pd.to_datetime(out["date"])
    out = (out.dropna(subset=["value"])
           .drop_duplicates(["ticker", "date", "field"], keep="last")
           .sort_values(["ticker", "date", "field"])
           .reset_index(drop=True))
    return out[["ticker", "date", "field", "value"]]


def main():
    print(f"vol tickers: {len(VOL_TICKERS)}, spot: {len(SPOT_TICKERS)}, "
          f"fwd: {len(FWD_TICKERS)}")
    vol = bdh_long(VOL_TICKERS, FIELDS, START, END)
    vol.to_parquet(RAW / "fx_vol_em_daily.parquet")
    print(f"vol rows {len(vol)}, tickers {vol['ticker'].nunique()}")

    sf = bdh_long(SPOT_TICKERS + FWD_TICKERS, FIELDS, START, END)
    sf.to_parquet(RAW / "spot_fwd_em_daily.parquet")
    print(f"spot/fwd rows {len(sf)}, tickers {sf['ticker'].nunique()}")

    for df, name in [(vol, "vol"), (sf, "spot/fwd")]:
        cov = (df[df["field"] == "PX_LAST"].groupby("ticker")["date"]
               .agg(["min", "max", "count"]))
        print(f"\n=== {name} coverage ===")
        print(cov.to_string())


if __name__ == "__main__":
    main()
