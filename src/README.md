# `src/` — the Bloomberg data pull

**You almost certainly do not need to run anything in here.** The data these scripts produce is
already committed to [`../data/raw/`](../data/raw/), so every number in the project reproduces
without a terminal. This folder exists to *refresh* the snapshots, and refreshing needs a Bloomberg
Terminal and an entitlement.

---

| File | What it does | Needs a terminal? |
|---|---|---|
| `bloomberg_data.py` | The automated pull: `xbbg` → `blpapi` → terminal. Chunked requests across every ticker group, writing `*_wide.parquet` and `*_long.parquet` plus the coverage and failure CSVs | **Yes** |
| `convert_extra_xlsx.py` | Converts the hand-pulled supplement `data/raw/FX_extra_data.xlsx` (benchmarks, EMBI, onshore fixings) into parquet | No — `openpyxl` only |

## Running the pull

```bash
pip install -r ../requirements.txt -r ../requirements-bbg.txt   # alongside, not instead of
python src/bloomberg_data.py
```

`blpapi` is not on PyPI by default:

```bash
pip install --index-url=https://blpapi.bloomberg.com/repository/releases/python/simple blpapi
```

Output lands in `src/bloomberg_fx_carry_raw/` (next to the script, not the working directory), from
where it is reviewed and moved into `../data/raw/`. The date range is set at the top of the script:
`START_DATE = "2007-01-01"`, `END_DATE` = today.

## The supplement converter

```bash
python src/convert_extra_xlsx.py     # no terminal, no entitlement
```

Some series could not be pulled programmatically and were exported from the terminal by hand into
`data/raw/FX_extra_data.xlsx`. This turns that workbook into the parquet groups the rest of the
repo reads.
