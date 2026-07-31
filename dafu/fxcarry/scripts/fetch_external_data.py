"""Fetch the non-Bloomberg series BER Section 3 (Tables 2 to 4) needs and are
not in the DVC/Box pull: the Fama and French factors and 25 portfolios (Ken
French Data Library) and a consumption series (FRED). These are free, public
and permanent, so they live in ``data/external`` committed to git, not in DVC.

Run once (needs internet):

    python scripts/fetch_external_data.py

Writes ``data/external/{ff_factors,ff25,consumption}.parquet``. Those are read
directly with pandas rather than through the library, which reads the long-format
Bloomberg pulls under ``data/raw``, so notebook execution itself needs no network.
"""

from __future__ import annotations

import io
import re
import urllib.request
import zipfile
from pathlib import Path

import pandas as pd

OUT = Path(__file__).resolve().parent.parent / "data" / "external"
KF = "https://mba.tuck.dartmouth.edu/pages/faculty/ken.french/ftp/"
FRED = "https://fred.stlouisfed.org/graph/fredgraph.csv?id="


def _get(url: str) -> bytes:
    with urllib.request.urlopen(url, timeout=60) as r:  # noqa: S310 (trusted hosts)
        return r.read()


def _parse_kf_monthly(zip_bytes: bytes) -> pd.DataFrame:
    """First monthly (YYYYMM) block of a Ken French CSV -> month-end frame in
    decimals. Ken French files carry header text, then a header row starting
    with a comma, then YYYYMM rows, then other blocks (annual, equal-weighted).
    We take the first monthly block only."""
    z = zipfile.ZipFile(io.BytesIO(zip_bytes))
    lines = z.read(z.namelist()[0]).decode("latin-1").splitlines()
    hdr = next(i for i, line in enumerate(lines) if line.startswith(","))
    cols = [c.strip() for c in lines[hdr].split(",")[1:]]
    rows: dict[str, list[float]] = {}
    for line in lines[hdr + 1:]:
        m = re.match(r"^\s*(\d{6})\s*,(.*)$", line)
        if not m:
            if rows:
                break  # first monthly block ended
            continue
        vals = [
            float(x) if x.strip() not in ("", "-99.99", "-999") else float("nan")
            for x in m.group(2).split(",")
        ]
        rows[m.group(1)] = vals
    df = pd.DataFrame.from_dict(rows, orient="index", columns=cols)
    df.index = pd.to_datetime(df.index, format="%Y%m") + pd.offsets.MonthEnd(0)
    return df / 100.0


def _parse_fred(csv_bytes: bytes, name: str) -> pd.Series:
    df = pd.read_csv(io.BytesIO(csv_bytes))
    df.columns = ["date", name]
    ser = pd.Series(
        pd.to_numeric(df[name], errors="coerce").to_numpy(),
        index=pd.to_datetime(df["date"]),
        name=name,
    ).dropna()
    return ser


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)

    ff = _parse_kf_monthly(_get(KF + "F-F_Research_Data_Factors_CSV.zip"))
    ff.columns = [c.replace("-", "_") for c in ff.columns]  # Mkt-RF -> Mkt_RF
    ff.to_parquet(OUT / "ff_factors.parquet")
    print(f"ff_factors : {ff.shape} {list(ff.columns)} {ff.index.min().date()}..{ff.index.max().date()}")

    ff25 = _parse_kf_monthly(_get(KF + "25_Portfolios_5x5_CSV.zip"))
    ff25.to_parquet(OUT / "ff25.parquet")
    print(f"ff25       : {ff25.shape} {ff25.index.min().date()}..{ff25.index.max().date()}")

    # Real personal consumption expenditures per capita, quarterly, chained $.
    # (BER use nondurables+services; the chained real components only start in
    # 2007, so we use total real PCE per capita, which reaches back to 1947.)
    cons = _parse_fred(_get(FRED + "A794RX0Q048SBEA"), "real_pce_pc")
    cons.to_frame().to_parquet(OUT / "consumption.parquet")
    print(f"consumption: {cons.shape} {cons.index.min().date()}..{cons.index.max().date()}")


if __name__ == "__main__":
    main()
