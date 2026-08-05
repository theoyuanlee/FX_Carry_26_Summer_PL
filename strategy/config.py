"""StrategyConfig — every knob of the team's base FX carry strategy.

One frozen dataclass holds the entire specification of a backtest. The defaults
ARE the project's published baseline (plan §4: combined 27-name book, net Sharpe
0.4659), so `run()` with no arguments reproduces the committed headline numbers
exactly. An extension changes one field and leaves everything else alone — that
is what makes two teammates' results comparable.

Every field maps to a parameter of an existing `fx_utils` function; nothing here
invents new behaviour. See `strategy/README.md` for the reference table and the
extension patterns.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Callable, Sequence

import pandas as pd

from .overlays import ExternalLeg

# Universe rules locked in plan §5.1: HKD/DKK are pegged (degenerate vol) and
# CNY has no deliverable forwards (CNH is the tradable RMB leg).
DEFAULT_EXCLUDE: tuple[str, ...] = ("HKD", "DKK", "CNY")

# The 9 tradable G10 names, in the order used by every committed output.
G10_TRADABLE: tuple[str, ...] = ("AUD", "CAD", "CHF", "EUR", "GBP",
                                 "JPY", "NOK", "NZD", "SEK")


@dataclass(frozen=True)
class StrategyConfig:
    """Full specification of one carry backtest.

    Defaults = the published ALL (G10+EM) book. Construct with keyword
    overrides, or derive from a preset with `preset.with_(...)`.

    Universe
    --------
    universe : "ALL" | "G10" | "EM" | explicit sequence of currency codes.
        "ALL" is every currency with data minus `exclude` (27 names); "G10" is
        the 9 tradable majors; "EM" is ALL minus G10 (18 names). Pass a list to
        study an arbitrary subset (drop a name, hand-pick a basket).
    exclude : names removed from the "ALL"/"EM" resolutions. Ignored when
        `universe` is an explicit sequence — an explicit list is taken literally.
    tenor : forward tenor for the carry signal and the cost model ("1M".."12M").

    Signal
    ------
    signal : "carry" (forward-implied carry, the baseline), "momentum"
        (`fx_utils.momentum_panel`), a ready-made daily DataFrame panel, or a
        callable `f(panels) -> DataFrame` receiving the loaded `Panels` object.
        A custom panel must be daily, columns = currencies, and must contain no
        information beyond date t (the base samples it month-end and lags it).
    momentum_lookback : lookback in days when `signal="momentum"`.
    filter_signal : optional same-shaped panel for a directional double sort
        (keep longs where >= 0, shorts where <= 0) — the Stage-5 overlay.

    Sort and within-leg weighting
    -----------------------------
    n_buckets : sort buckets; None resolves to 3 for a G10-sized universe and 5
        otherwise, matching the committed books.
    weighting : "inv_vol" (baseline) | "equal" | "erc" | "mvo".
    max_leg_share : cap on any single name's share of its leg.
    min_per_leg : rebalance dates with a thinner leg keep the previous weights.
    vol_window : trailing window for the inverse-vol leg weights.
    cov_window : trailing window for the "erc"/"mvo" covariance.
    rebal : rebalance frequency ("ME", "QE", "W", "2W", ...).

    Sizing
    ------
    vol_target : annualised vol target; None skips vol targeting entirely
        (leaving the unit gross-2 book).
    vol_target_window, lev_cap, vol_floor : `fx_utils.vol_target_weights` args.

    Overlays — the extension hooks
    ------------------------------
    exposure : Series of exposure multipliers (1.0 = fully invested). Applied to
        the vol-targeted weights *before* returns and costs, so a de-risking
        rule pays for the trades it triggers. Resampled to the rebalance grid
        and lagged one period — pass an unlagged signal, the base lags it.
    weight_overlay : callable `f(weights, ctx) -> weights` applied last. Use for
        per-currency overlays (an option hedge on the long leg, a manual
        position edit). `ctx` is the `OverlayContext` with the panels.
    external_legs : tuple of `overlays.ExternalLeg` — non-FX instruments held
        alongside the book (a bond hedge, a futures overlay). Each adds `Σ w·r`
        to `gross` and `Σ|Δw|·cost_bps/1e4` to `cost` in `core.run` step 6, so
        an external instrument earns its return AND pays its own transaction
        costs. This exists because the two hooks above genuinely cannot express
        an additional asset: `portfolio_returns` intersects columns and would
        drop it, and `roundtrip_cost` raises on a name with no half-spread
        series. Default `()` is an exact no-op. Stack several with
        `overlays.compose_exposure` / `compose_overlays` for the other two hooks.
    extra_lag : additional days of weight lag ON TOP of the base's own one-day
        lag. 0 for research; 1, 2, 3 for implementation-lag stress tests.

    Costs and window
    ----------------
    costs : charge `fx_utils.roundtrip_cost` (bid/ask half-spreads + roll).
    cost_multiple : scale all half-spreads — cost-stress sensitivity.
    start, end : evaluation window; None = the natural common window of the
        book (first to last non-NaN return).
    """

    # --- universe -----------------------------------------------------------
    universe: str | Sequence[str] = "ALL"
    exclude: tuple[str, ...] = DEFAULT_EXCLUDE
    tenor: str = "1M"

    # --- signal -------------------------------------------------------------
    signal: str | pd.DataFrame | Callable = "carry"
    momentum_lookback: int = 63
    filter_signal: pd.DataFrame | None = None

    # --- sort and within-leg weighting --------------------------------------
    n_buckets: int | None = None
    weighting: str = "inv_vol"
    max_leg_share: float = 0.40
    min_per_leg: int = 2
    vol_window: int = 60
    cov_window: int = 250
    rebal: str = "ME"

    # --- sizing -------------------------------------------------------------
    vol_target: float | None = 0.10
    vol_target_window: int = 60
    lev_cap: float = 4.0
    vol_floor: float = 0.01

    # --- overlays -----------------------------------------------------------
    exposure: pd.Series | None = None
    weight_overlay: Callable | None = None
    external_legs: tuple[ExternalLeg, ...] = ()
    extra_lag: int = 0

    # --- costs and window ---------------------------------------------------
    costs: bool = True
    cost_multiple: float = 1.0
    start: str | pd.Timestamp | None = None
    end: str | pd.Timestamp | None = None

    # --- labelling ----------------------------------------------------------
    name: str = ""

    def __post_init__(self) -> None:
        if self.weighting not in ("equal", "inv_vol", "erc", "mvo"):
            raise ValueError(
                f"weighting must be equal/inv_vol/erc/mvo, got {self.weighting!r}")
        if isinstance(self.signal, str) and self.signal not in ("carry", "momentum"):
            raise ValueError(
                f"signal must be 'carry', 'momentum', a DataFrame or a callable, "
                f"got {self.signal!r}")
        if self.extra_lag < 0:
            raise ValueError(f"extra_lag must be >= 0, got {self.extra_lag}")
        if self.vol_target is not None and self.vol_target <= 0:
            raise ValueError(f"vol_target must be > 0 or None, got {self.vol_target}")
        if not isinstance(self.external_legs, tuple):
            raise TypeError(
                f"external_legs must be a tuple (it is part of a frozen config), "
                f"got {type(self.external_legs).__name__}")
        bad = [l for l in self.external_legs if not isinstance(l, ExternalLeg)]
        if bad:
            raise TypeError(f"external_legs entries must be ExternalLeg, got {bad}")
        names = [l.name for l in self.external_legs]
        if len(set(names)) != len(names):
            # They become columns of `contrib`, where a duplicate would silently
            # double-count one leg's P&L and break contrib.sum(1) == gross.
            raise ValueError(f"external_legs names must be unique, got {names}")

    def with_(self, **overrides) -> "StrategyConfig":
        """Copy with fields replaced — the idiomatic way to vary one knob.

        >>> ALL_BASELINE.with_(weighting="erc", name="erc")
        """
        return replace(self, **overrides)

    def label(self) -> str:
        """Short human label for tables: `name` if set, else a diff vs default."""
        if self.name:
            return self.name
        base = StrategyConfig()
        diffs = [f"{f}={getattr(self, f)!r}"
                 for f in ("universe", "weighting", "n_buckets", "rebal",
                           "vol_target", "vol_window", "max_leg_share", "tenor")
                 if getattr(self, f) != getattr(base, f)]
        return ", ".join(diffs) if diffs else "baseline"

    def describe(self) -> dict:
        """Flat dict of the scalar settings — for provenance columns in outputs."""
        return {
            "universe": self.universe if isinstance(self.universe, str)
            else "|".join(self.universe),
            "tenor": self.tenor,
            "signal": self.signal if isinstance(self.signal, str) else "custom",
            "n_buckets": self.n_buckets,
            "weighting": self.weighting,
            "max_leg_share": self.max_leg_share,
            "vol_window": self.vol_window,
            "rebal": self.rebal,
            "vol_target": self.vol_target,
            "lev_cap": self.lev_cap,
            "extra_lag": self.extra_lag,
            "costs": self.costs,
            "cost_multiple": self.cost_multiple,
            "exposure": self.exposure is not None,
            "weight_overlay": getattr(self.weight_overlay, "__name__", None)
            if self.weight_overlay is not None else None,
            "external_legs": "|".join(l.name for l in self.external_legs) or None,
        }


# ---------------------------------------------------------------------------
# Presets — the two committed headline books (plan §4)
# ---------------------------------------------------------------------------

# Presets leave `n_buckets=None` on purpose so it re-resolves from the universe
# size (quintiles for the full cross-section, terciles for a single region). That
# way `run(universe="G10")` is the G10 book, not the ALL book with 1 name a leg.

#: Combined G10+EM quintile book. THE team baseline: net Sharpe 0.4659.
ALL_BASELINE = StrategyConfig(universe="ALL", name="ALL")

#: G10-only tercile book: net Sharpe 0.119. The "carry doesn't work in majors" leg.
G10_BASELINE = StrategyConfig(universe="G10", name="G10")

#: EM-only tercile book, for the EM-vs-G10 attribution.
EM_BASELINE = StrategyConfig(universe="EM", name="EM")


def combined_preset() -> StrategyConfig:
    """The frozen Phase-4 combined engine (plan §19.4). `run("COMBINED")`.

    The baseline plus the components that earned a slot under the criterion fixed
    in advance in `cesare/combined_engine.py`: improve MaxDD or CVaR99 in at
    least 4 of the 6 pre-2026 stress windows, cost under 0.05 whole-sample net
    Sharpe, and survive leave-one-out. Two of four components qualified.

    **A callable, not a constant, for two reasons.** It has to build data-derived
    objects (a hedge-ratio series, an option panel), so evaluating it at import
    time would make `import strategy` do file IO — and it would run on every
    teammate's machine whether or not they use the preset. And its inputs are
    teammates' *committed outputs*, re-priced here rather than rebuilt (§15
    fallback), so the assembly logic belongs in `cesare/`, not in the shared
    base. The import below is therefore deliberately lazy and deliberately
    one-directional: `cesare` imports `strategy`, never the reverse, except at
    the moment this preset is actually requested.

    Raises `FileNotFoundError` naming the missing file if a teammate's committed
    input is absent, rather than silently returning a thinner book.
    """
    from cesare.combined_engine import combined_components
    return ALL_BASELINE.with_(name="COMBINED", **combined_components())


#: `run("COMBINED")` resolves through the callable; the other three are constants.
PRESETS = {"ALL": ALL_BASELINE, "G10": G10_BASELINE, "EM": EM_BASELINE,
           "COMBINED": combined_preset}
