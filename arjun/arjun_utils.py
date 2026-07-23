"""arjun_utils — personal analysis engine for the arjun/ notebooks.

Right now this does one thing: load clean, processed FX panels with a single
call, so notebooks don't repeat the import/setup boilerplate. The underlying
data construction (spots, carry, returns) is delegated to the shared team
engine at ``cesare/fx_utils.py`` — this module treats that as the data source
rather than reimplementing the parquet-loading and quote-convention plumbing.

Design intent: this is the seam where my work can diverge from the team's
headline strategy. New signals, weighting schemes, universe choices, and
diagnostics belong *here* (added over time as the direction firms up), built
on top of the shared panels below. For now it is deliberately minimal.

Typical use in a notebook:

    from arjun_utils import load_panels, PATHS

    panels = load_panels()
    spots, carry, xret, sret = panels.spots, panels.carry, panels.xret, panels.sret
"""

from __future__ import annotations

import sys
from dataclasses import dataclass
from pathlib import Path

import numpy as np  # noqa: F401  (re-exported for notebook convenience)
import pandas as pd


# ---------------------------------------------------------------------------
# Paths — resolved relative to this file, so notebooks work regardless of the
# directory they're launched from.
# ---------------------------------------------------------------------------
_THIS_DIR = Path(__file__).resolve().parent          # .../arjun
_REPO_ROOT = _THIS_DIR.parent                        # repo root
_ENGINE_DIR = _REPO_ROOT / "cesare"                  # shared engine lives here


@dataclass(frozen=True)
class _Paths:
    repo_root: Path = _REPO_ROOT
    engine_dir: Path = _ENGINE_DIR
    team_outputs: Path = _ENGINE_DIR / "outputs"     # committed team results (read-only)
    my_outputs: Path = _THIS_DIR / "outputs"         # my own deliverables land here


PATHS = _Paths()
PATHS.my_outputs.mkdir(exist_ok=True)

_ANN_DAYS = 252   # trading-day annualisation, matching the team engine


# ---------------------------------------------------------------------------
# Import the shared engine (cesare/fx_utils.py) as the data source.
# ---------------------------------------------------------------------------
if str(PATHS.engine_dir) not in sys.path:
    sys.path.insert(0, str(PATHS.engine_dir))

import fx_utils as fx  # noqa: E402  (must follow sys.path insert)


# ---------------------------------------------------------------------------
# Panels container
# ---------------------------------------------------------------------------
@dataclass
class Panels:
    """The core processed panels every downstream analysis builds on.

    All are date-indexed DataFrames with ISO currency codes as columns.
    """

    spots: pd.DataFrame   # USD per FX (up = FX appreciates vs USD)
    carry: pd.DataFrame   # annualised forward-implied carry
    xret: pd.DataFrame    # daily excess returns (carry accrual + spot move)
    sret: pd.DataFrame    # daily pure spot log returns
    g10_px: pd.DataFrame  # raw wide G10 spot+forward (kept for custom work)
    em_px: pd.DataFrame   # raw wide EM spot+forward

    tenor: str = "1M"     # forward tenor used to build the carry panel

    @property
    def universe(self) -> list[str]:
        return list(self.xret.columns)

    @property
    def g10(self) -> list[str]:
        return [c for c in self.universe if c in G10]

    @property
    def em(self) -> list[str]:
        return [c for c in self.universe if c in EM]

    def bucket_returns(self, bucket: str) -> pd.DataFrame:
        """Excess-return sub-panel for one bucket: ``'G10'`` or ``'EM'``."""
        cols = self.g10 if bucket.upper() == "G10" else self.em
        return self.xret[cols]

    def overview(self, bucket: str | None = None) -> pd.DataFrame:
        """Per-currency data card — the basics worth knowing before working
        with the panel: bucket (G10 / EM per my classification), sample
        start/end, and % coverage on the excess-return panel.

        Currencies outside both buckets (the pegs DKK/HKD carried by the raw
        panel) are excluded. Kept deliberately lean for now; performance/risk
        metrics can be layered on later. Pass ``bucket='G10'`` or ``'EM'`` to
        view one bucket only.
        """
        names = (self.g10 if bucket and bucket.upper() == "G10"
                 else self.em if bucket and bucket.upper() == "EM"
                 else self.g10 + self.em)
        n_total = self.xret.shape[0]
        rows = {}
        for ccy in names:
            r = self.xret[ccy].dropna()
            if r.empty:
                continue
            rows[ccy] = {
                "bucket": "G10" if ccy in G10 else "EM",
                "start": r.index.min().date(),
                "end": r.index.max().date(),
                "coverage_%": round(100 * len(r) / n_total, 1),
            }
        df = pd.DataFrame(rows).T.rename_axis("ccy")
        df["coverage_%"] = pd.to_numeric(df["coverage_%"], errors="coerce")
        return df.sort_values(["bucket", "coverage_%"], ascending=[True, False])


def load_panels(tenor: str = "1M", summary: bool = True) -> Panels:
    """Load and process the FX panels via the shared engine, in one call.

    Delegates all construction to ``cesare/fx_utils.py`` so the numbers match
    the team's engine exactly. ``tenor`` controls the forward tenor used for
    the carry panel (default 1M, matching the headline strategy).

    If ``summary`` is True (default) a compact load header is printed. Call
    ``.overview()`` on the returned object for the full per-currency card.
    """
    g10_px = fx.load_wide("g10_fx_spot_forward")
    em_px = fx.load_wide("em_fx_spot_forward")

    spots = fx.spots_usd_per_fx(g10_px, em_px)
    carry = fx.carry_panel(g10_px, em_px, tenor=tenor)
    xret = fx.excess_returns(spots, carry)
    sret = fx.spot_log_returns(spots)

    panels = Panels(spots=spots, carry=carry, xret=xret, sret=sret,
                    g10_px=g10_px, em_px=em_px, tenor=tenor)

    if summary:
        start, end = xret.index.min().date(), xret.index.max().date()
        yrs = (xret.index.max() - xret.index.min()).days / 365.25
        classified = panels.g10 + panels.em
        excluded = [c for c in panels.universe if c not in classified]
        print(f"FX carry panel  ·  {tenor} forward-implied carry")
        print(f"{'─' * 52}")
        print(f"  Universe    {len(classified)} currencies   "
              f"({len(panels.g10)} G10, {len(panels.em)} EM)")
        print(f"  Sample      {start}  →  {end}   ({yrs:.1f}y, {len(xret):,} obs)")
        print(f"  Panels      spots · carry · xret · sret")
        if excluded:
            print(f"  Excluded    {', '.join(excluded)}  (pegs, not standard G10)")
        print(f"{'─' * 52}")
        print("  .overview()  for the per-currency data card")

    return panels


def load_team_summary() -> pd.DataFrame:
    """Load the team's committed strategy summary stats — the reconciliation
    baseline — for when a new finding builds on the headline result.
    """
    return pd.read_csv(PATHS.team_outputs / "strategy_summary_stats.csv", index_col=0)


# ---------------------------------------------------------------------------
# Currency classification (my cut).
#
# G10 here is the standard FX G10 — the nine tradable majors vs USD. This is
# intentionally NOT the shared engine's developed-market list, which also
# includes the pegs DKK (→EUR) and HKD (→USD); those aren't standard G10 and
# behave like their pegs rather than as free-floating carry signals, so they
# sit in neither bucket and drop out of the G10/EM views below.
# ---------------------------------------------------------------------------
G10 = ["EUR", "JPY", "GBP", "CHF", "AUD", "NZD", "CAD", "NOK", "SEK"]
EM = [c for c in fx.EM if c != "CNY"]   # CNH covers offshore RMB; CNY is spot-only (no forwards)
ALL_CCY = G10 + EM