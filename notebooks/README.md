# `notebooks/` — legacy scratch, kept deliberately

One early notebook from the first week of the project, before the workstreams split into per-person
folders and before [`strategy/`](../strategy/) existed.

| File | What it is |
|---|---|
| `view_data.ipynb` | A first look at the raw Bloomberg pull — what arrived, over what date range |
| `outputs/data_timerange.csv` | Its one output: the per-ticker date coverage of the July 1 pull |

**It is kept rather than deleted, as a recorded decision** (project plan §14.4), because it is the
first artifact in the repo and the date-range scan behind it is still the quickest way to see what
the original pull contained.

**It is superseded for any working purpose.** For data coverage read
[`../data/README.md`](../data/README.md) and `data/raw/download_coverage_summary.csv`; for a real
audit read [`../vidhi/notebooks/01_data_audit.ipynb`](../vidhi/notebooks/01_data_audit.ipynb). Nothing
in the project reads anything in this folder.
