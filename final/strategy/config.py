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
    in advance in `combined_engine.py`: improve MaxDD or CVaR99 in at least 4 of
    the 6 pre-2026 stress windows, cost under 0.05 whole-sample net Sharpe, and
    survive leave-one-out. Two of four components qualified.

    **A callable, not a constant.** It has to build data-derived objects (a
    hedge-ratio series, an option panel), so evaluating it at import time would
    make `import strategy` do file IO whether or not the preset is used.

    **VENDORED — one token differs from the shared base.** In the multi-person
    repo this function imported the components from a personal folder, because
    the assembly logic lived there and the shared base could not own it. In
    `final/` the strategy definition lives beside the engine, so the import below
    is unqualified and the dependency points the right way round for the first
    time. That single token is the entire diff between this file and
    `strategy/config.py`; `tests/test_vendor_drift.py` declares it and fails on
    any other difference.

    Raises `FileNotFoundError` naming the missing file if a vendored input is
    absent, rather than silently returning a thinner book.
    """
    from combined_engine import combined_components
    return ALL_BASELINE.with_(name="COMBINED", **combined_components())
def combined_tail_preset() -> StrategyConfig:
    """`COMBINED` **plus** the VIX percentile gate. `run("COMBINED_TAIL")`.

    **This is not the shipped strategy.** It is the documented alternative to the
    one genuinely contested verdict in the project, made runnable so the desk can
    price the decision instead of taking it on trust. `COMBINED` is the book that
    ships; this is the book you get if the VIX gate is read in rather than out.

    The contest, in one line: Dafu's gate fails criterion (i) of the §19.4 slot
    rule measured add-one-in (3 of 6 stress windows, on `duration`), and passes it
    measured leave-one-out on the stack actually proposed (4 of 6, on
    `duration|skew_excl`, which guardrail §6.13 privileges). Three of four
    measurements reject; the fourth accepts. The project ships the rejection
    because criterion (i) is an add-one-in test by construction, and taking the
    cost of a pre-registered rule rather than re-reading it after seeing the
    answer is what pre-registration is for. The cost is real and is stated
    wherever the verdict is: **0.043 net Sharpe and 5.4% relative CVaR99**.

    Reproduces `p4_combined_ladder.csv` row `ladder=final, rung=3`:
    gross 0.680807 · net 0.532265 · MaxDD -0.190665 · CVaR99 0.018942 ·
    turnover 0.605144 · cost drag 0.012298. Those are pre-existing committed
    numbers, not a new result — the rung was always in the ladder.

    Note the MaxDD is **identical** to `COMBINED`'s, and that is not a bug: the
    combined book's drawdown episode is 2013-05-17 -> 2013-12-05 and the gate is
    fully invested on all 145 days of it, so whole-sample MaxDD cannot see this
    gate at all. CVaR99 is the tail statistic that moves. See `VERDICTS.md`.
    """
    from combined_engine import combined_components
    return ALL_BASELINE.with_(
        name="COMBINED_TAIL",
        **combined_components(["duration", "vix_gate", "skew_excl"]))


# ---------------------------------------------------------------------------
# The delivered menu — one engine, three books (plan §21)
# ---------------------------------------------------------------------------
#
# The desk's Aug 12 condition was that every strategy presented comes with its
# pros and cons, and that the count stays small. These three are that menu. They
# are not three strategies: they are one book at three points on a single
# risk-appetite ladder, and each is strictly more protected than the one above.
#
#     OFFENSIVE   no overlays, vol target 15%   -- calm macro, risk-on
#     CORE        = COMBINED                    -- default, all-weather
#     DEFENSIVE   = COMBINED_TAIL               -- stress, tail fear
#
# CORE and DEFENSIVE are deliberately *aliases* rather than re-definitions. A
# second definition of a shipped book is a second thing that can drift from the
# ladder it is supposed to reproduce; an alias cannot. `test_combined.py` asserts
# the bit-identity rather than trusting the comment.
#
# No rule is provided for switching between them, and that omission is the honest
# part. Every exposure-timing rule this project tested came back null (plan §9,
# §12, §19.3), so a switching signal is exactly the thing the evidence says not to
# claim. The ladder is a mandate choice the desk makes, not a signal we trade.

#: Un-overlaid baseline, levered to a 15% vol target. `run("OFFENSIVE")`.
#:
#: **A risk dial, not an edge.** Its net Sharpe is 0.4606 against the baseline's
#: 0.4659 — statistically the same book, deliberately. What changes is the
#: quantity of it held: 7.64%/yr of return against 5.21%, and a -41.2% maximum
#: drawdown against -29.3%. Leverage is a mandate parameter, and no alpha is
#: being claimed for it.
#:
#: 15% is the top of a plateau, not an argmax. Across targets 10/12/13/15/18% the
#: net Sharpe runs 0.4659 / 0.4656 / 0.4645 / 0.4606 / 0.4430 — flat to 15%, then
#: it breaks as `lev_cap` starts truncating the highest-vol days (0% of days at
#: the cap at a 10% target, 6.9% at 15%, 17.5% at 18%). Picking the last flat
#: point rather than the highest number is the rule `examples/04_parameter_sweep.py`
#: gives teammates: read the grid for plateaus, not peaks.
#:
#: The overlays are left OFF on purpose. They are what trims the high-carry EM
#: names, which is exactly where the good states come from — in the 2022 rates
#: selloff this book returns +40.2% where CORE returns +9.2%. An offensive mandate
#: wants that participation; it is also why this book loses the most in a crash.
OFFENSIVE = ALL_BASELINE.with_(name="OFFENSIVE", vol_target=0.15)


def core_preset() -> StrategyConfig:
    """The shipped book, under its menu name. `run("CORE")` == `run("COMBINED")`.

    An alias, so there is exactly one definition of the strategy. Best Calmar of
    the three at 0.211, shallowest drawdown at -19.1%, and the only one of the
    three whose components each cleared the pre-registered slot rule.
    """
    return combined_preset().with_(name="CORE")


def defensive_preset() -> StrategyConfig:
    """CORE plus the VIX gate, under its menu name. `run("DEFENSIVE")`.

    **Read the caveat before quoting the ratios.** This book has the best Sharpe
    (0.5323), Sortino (0.760), Calmar (0.219) and CVaR99 (0.0189) of the three —
    better than CORE on every one. It is still not the default, because the gate
    it adds failed the slot rule fixed before any component was measured. That
    decision costs 0.043 of net Sharpe and it is paid rather than re-argued; see
    `combined_tail_preset` and `VERDICTS.md`. Offered here as a named mandate for
    a desk that has decided it is in a stress regime — which is a judgement the
    desk makes, not one this book forecasts.
    """
    return combined_tail_preset().with_(name="DEFENSIVE")


#: Five books resolve through callables; ALL/G10/EM/OFFENSIVE are constants.
#: `COMBINED` is the strategy and `CORE` is its menu name. `COMBINED_TAIL` is the
#: documented alternative (see `combined_tail_preset`), `DEFENSIVE` its menu name,
#: and neither is the default anywhere.
PRESETS = {"ALL": ALL_BASELINE, "G10": G10_BASELINE, "EM": EM_BASELINE,
           "COMBINED": combined_preset, "COMBINED_TAIL": combined_tail_preset,
           "OFFENSIVE": OFFENSIVE, "CORE": core_preset,
           "DEFENSIVE": defensive_preset}
