"""The base backtest: `run(config) -> StrategyResult`.

This module is orchestration only. Every financial computation is delegated to
`strategy.fx_utils`, the engine that produced the project's committed results —
so a book built here is the same book, by construction, not by resemblance.

Order of operations (fixed, and the reason results are comparable):

    1. panels        load_wide -> spots_usd_per_fx -> carry_panel -> excess_returns
    2. signal        carry / momentum / user panel
    3. sort          carry_portfolio(...)          -> unit weights (gross 2)
    4. size          vol_target_weights(...)       -> vol-targeted weights
    5. overlays      exposure scalar, then weight_overlay, then extra_lag
    6. P&L           portfolio_returns; roundtrip_cost; external_legs;
                     net = gross - cost

Step 5 sits BEFORE step 6 deliberately: overlays move *weights*, so the cost
model prices the trades an overlay triggers and the reported turnover includes
them. An overlay applied to a return series instead would be free, which
flatters every risk-management rule ever tested.

With no overlays and default settings the pipeline is identical to
`cesare/strategy_backtest.ipynb` §1-4 — asserted in `tests/test_reconciliation.py`.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from functools import lru_cache
from typing import Sequence

import pandas as pd

from . import fx_utils as fx
from .config import G10_TRADABLE, PRESETS, StrategyConfig

__all__ = ["Panels", "OverlayContext", "StrategyResult", "run", "load_panels",
           "resolve_universe"]


# ---------------------------------------------------------------------------
# Panels — the shared, cached data layer
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class Panels:
    """Daily currency panels, all columns = currency codes, index = trading days.

    `xret` is the tradable excess return and satisfies, exactly,
    `xret == spot_component + carry_component` (asserted in the tests): the spot
    log return plus the previous day's annualised carry accrued over 1/252.
    Attribution work should use the split rather than re-deriving it.
    """

    tenor: str
    spots: pd.DataFrame           # USD-per-FX spot levels
    carry: pd.DataFrame           # annualised forward-implied carry, ln(S/F)
    xret: pd.DataFrame            # daily excess returns
    spot_component: pd.DataFrame  # log spot returns
    carry_component: pd.DataFrame # lagged carry / 252
    hs_outright: pd.DataFrame     # relative half-spread, outright forward
    hs_points: pd.DataFrame       # relative half-spread, FX-swap points

    @property
    def currencies(self) -> list[str]:
        return list(self.xret.columns)


@lru_cache(maxsize=8)
def load_panels(tenor: str = "1M") -> Panels:
    """Load and build every shared panel for `tenor`. Cached per process.

    The cache matters: a robustness sweep rebuilds the book ~80 times and the
    parquet load plus panel construction is the slow part, not the sort.
    """
    g10_px = fx.load_wide("g10_fx_spot_forward")
    em_px = fx.load_wide("em_fx_spot_forward")
    spots = fx.spots_usd_per_fx(g10_px, em_px)
    carry = fx.carry_panel(g10_px, em_px, tenor=tenor)
    xret = fx.excess_returns(spots, carry)
    cols = xret.columns
    hs_out, hs_pts = fx.forward_halfspreads(tenor=tenor)
    return Panels(
        tenor=tenor,
        spots=spots,
        carry=carry,
        xret=xret,
        spot_component=fx.spot_log_returns(spots)[cols],
        carry_component=(carry[cols].shift(1) / fx.ANN_DAYS),
        hs_outright=hs_out,
        hs_points=hs_pts,
    )


def resolve_universe(universe: str | Sequence[str], panels: Panels,
                     exclude: tuple[str, ...] = ()) -> list[str]:
    """Turn a universe spec into an explicit, ordered list of currency codes.

    "ALL" / "EM" apply `exclude` (the pegged and non-deliverable names);
    "G10" is the fixed 9 tradable majors; an explicit sequence is taken
    literally (so you can deliberately study a pegged name), intersected with
    what the data actually has.
    """
    if isinstance(universe, str):
        key = universe.upper()
        available = [c for c in panels.xret.columns if c not in exclude]
        if key == "ALL":
            return available
        if key == "G10":
            return [c for c in G10_TRADABLE if c in panels.xret.columns]
        if key == "EM":
            return [c for c in available if c not in G10_TRADABLE]
        raise ValueError(f"universe must be ALL/G10/EM or a list, got {universe!r}")
    names = [c for c in universe if c in panels.xret.columns]
    missing = [c for c in universe if c not in panels.xret.columns]
    if missing:
        raise ValueError(f"no data for {missing}; available: {list(panels.xret.columns)}")
    return names


# ---------------------------------------------------------------------------
# Overlay context — what a weight_overlay callable receives
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class OverlayContext:
    """Everything a `weight_overlay` needs to decide how to modify weights.

    The overlay signature is `f(weights, ctx) -> weights`: take the daily
    vol-targeted weight panel, return a panel with the same index and columns.
    Anything you return is what gets traded, costed and reported — so an
    overlay that halves a position also halves that position's carry.
    """

    config: StrategyConfig
    panels: Panels
    universe: list[str]
    weights_unit: pd.DataFrame   # pre-vol-target, gross 2
    signal: pd.DataFrame         # the panel the sort ran on


# ---------------------------------------------------------------------------
# Result
# ---------------------------------------------------------------------------

@dataclass
class StrategyResult:
    """Output of one backtest — weights, returns and their decompositions.

    Guarantees (all asserted in `tests/test_reconciliation.py`):
    - `contrib.sum(axis=1) == gross` exactly, so per-currency attribution adds up;
    - `panels.xret == spot_component + carry_component` exactly;
    - `net == gross - cost`;
    - with a default config, `net` reproduces the committed headline stats.
    """

    config: StrategyConfig
    panels: Panels
    universe: list[str]
    signal: pd.DataFrame
    weights_unit: pd.DataFrame    # after the sort, gross 2, before vol targeting
    weights: pd.DataFrame         # what is actually held: post sizing and overlays
    gross: pd.Series
    cost: pd.Series
    net: pd.Series
    window: tuple[pd.Timestamp, pd.Timestamp]
    #: Daily P&L of each `config.external_legs` entry, one column per leg, NaN
    #: wherever `gross` is NaN so the `contrib` identity survives. Empty when
    #: there are no legs, which is the baseline.
    external: pd.DataFrame = field(default_factory=pd.DataFrame)
    #: Per-leg count of days the leg held a position but had no quote and so
    #: earned nothing. Non-zero is not necessarily wrong (a US bond ETF has no
    #: quote on a US holiday the FX book still trades) but it must be visible.
    external_coverage: dict = field(default_factory=dict)

    # --- derived views ------------------------------------------------------

    @property
    def xret(self) -> pd.DataFrame:
        """Excess returns, restricted to the traded universe and window."""
        return self._win(self.panels.xret[self.universe])

    @property
    def spot_component(self) -> pd.DataFrame:
        return self._win(self.panels.spot_component[self.universe])

    @property
    def carry_component(self) -> pd.DataFrame:
        return self._win(self.panels.carry_component[self.universe])

    @property
    def contrib(self) -> pd.DataFrame:
        """Per-instrument P&L contribution; rows sum to `gross` exactly.

        One column per traded currency, plus one per `external_legs` entry. The
        legs are included rather than reported separately so that
        `contrib.sum(axis=1) == gross` stays true *with* a hedge attached — an
        attribution table that silently stops adding up once someone bolts on a
        bond leg is worse than no guarantee at all.
        """
        cols = self.weights.columns.intersection(self.panels.xret.columns)
        out = self._win(self.weights[cols] * self.panels.xret[cols])
        if not self.external.empty:
            out = out.join(self._win(self.external), how="left")
        return out

    @property
    def turnover_daily(self) -> pd.Series:
        """Daily two-sided turnover Σ|Δw| of the traded weights."""
        return self._win(self.weights.fillna(0.0).diff().abs().sum(axis=1)
                         ).rename("turnover")

    @property
    def turnover(self) -> float:
        """Average one-sided turnover per rebalance period (`fx_utils.turnover`)."""
        return fx.turnover(self._win(self.weights), rebal=self.config.rebal)

    @property
    def cost_drag(self) -> float:
        """Annualised cost drag in return units."""
        return float(self.cost.reindex(self.net.dropna().index).mean() * fx.ANN_DAYS)

    def _win(self, obj):
        return obj.loc[self.window[0]:self.window[1]]

    # --- reporting ----------------------------------------------------------

    def summary(self, benchmark: pd.Series | str | None = "auto",
                min_obs: int = 120) -> pd.DataFrame:
        """Gross and net performance stats (`fx_utils.summary_stats`).

        `benchmark="auto"` picks the investable index the project benchmarks
        against: DBHVG10U for a G10 book, FXCTEM8 otherwise (plan §6.4). Pass a
        Series to use your own, or None to skip the information ratio.

        `min_obs` is the minimum number of observations a column needs before
        any statistic is computed; below it `summary_stats` drops the column, so
        the default 120 makes a short window return an EMPTY frame rather than
        an error. That is why this passthrough exists: an episode study on the
        COVID crash (64 trading days), the 2013 taper tantrum (109) or either
        2026 shock (85 / 65) is unreportable without it. Lower it to stat a
        short window — but per plan guardrail §6.8, quote cumulative return,
        MaxDD, worst day and n_days there, never an annualised Sharpe off 64
        days. `episodes.report_windows` enforces that for you.
        """
        bench = self._resolve_benchmark(benchmark)
        label = self.config.label()
        frame = pd.DataFrame({f"{label}_gross": self.gross, f"{label}_net": self.net})
        return fx.summary_stats(frame, benchmark=bench, min_obs=min_obs)

    def _resolve_benchmark(self, benchmark) -> pd.Series | None:
        if benchmark is None:
            return None
        if isinstance(benchmark, pd.Series):
            return benchmark
        if isinstance(benchmark, str) and benchmark != "auto":
            return fx.benchmark_returns()[benchmark]
        is_g10 = (isinstance(self.config.universe, str)
                  and self.config.universe.upper() == "G10")
        ticker = "DBHVG10U" if is_g10 else "FXCTEM8"
        bmk = fx.benchmark_returns()
        return bmk[ticker] if ticker in bmk.columns else None

    def monthly(self, which: str = "net") -> pd.Series:
        """Month-end compounded returns — for overlays that decide monthly."""
        r = getattr(self, which)
        return (1.0 + r.fillna(0.0)).resample("ME").prod() - 1.0

    # --- post-hoc re-pricing (no rebuild) -----------------------------------

    def returns_from_weights(self, weights: pd.DataFrame) -> pd.Series:
        """Gross return of an arbitrary weight panel on this book's returns.

        Lets you re-price a modified weight panel — e.g. `weights.shift(2)` for
        an implementation-lag stress — without re-running the sort.
        """
        return self._win(fx.portfolio_returns(weights, self.panels.xret, "gross"))

    def cost_from_weights(self, weights: pd.DataFrame,
                          multiple: float = 1.0) -> pd.Series:
        """Transaction cost of an arbitrary weight panel, half-spreads × `multiple`.

        `multiple` is the cost-stress knob: 2.0 asks "does the edge survive
        double the spreads?" without rebuilding the book.
        """
        return self._win(fx.roundtrip_cost(weights,
                                           self.panels.hs_outright * multiple,
                                           self.panels.hs_points * multiple,
                                           tenor=self.panels.tenor))

    def reslice(self, start=None, end=None) -> "StrategyResult":
        """Same book, different evaluation window (e.g. the 2008 crisis only).

        Re-slices the existing series — it does not re-estimate anything, so
        trailing windows still use the data before `start`, which is what you
        want for a subperiod study.
        """
        lo = pd.Timestamp(start) if start is not None else self.window[0]
        hi = pd.Timestamp(end) if end is not None else self.window[1]
        return StrategyResult(
            config=self.config.with_(start=lo, end=hi), panels=self.panels,
            universe=self.universe, signal=self.signal,
            weights_unit=self.weights_unit, weights=self.weights,
            gross=self.gross.loc[lo:hi], cost=self.cost.loc[lo:hi],
            net=self.net.loc[lo:hi], window=(lo, hi),
            external=self.external.loc[lo:hi] if not self.external.empty
            else self.external,
            external_coverage=self.external_coverage)

    def __repr__(self) -> str:
        head = (f"<StrategyResult {self.config.label()!r} | {len(self.universe)} ccy | "
                f"{self.window[0].date()}->{self.window[1].date()}")
        s = self.summary(benchmark=None)
        if len(s) < 2:
            # Too few observations for annualised stats (summary_stats min_obs).
            # Echoing a resliced crisis window in a notebook must not raise, so
            # report the window and defer the ratio to episodes.report_windows.
            return f"{head} | {len(self.net.dropna())} days, too short for annualised stats>"
        g, n = s.iloc[0]["sharpe"], s.iloc[1]["sharpe"]
        return f"{head} | Sharpe gross {g:.3f} net {n:.3f}>"


# ---------------------------------------------------------------------------
# The run
# ---------------------------------------------------------------------------

def _resolve_signal(config: StrategyConfig, panels: Panels) -> pd.DataFrame:
    sig = config.signal
    if callable(sig) and not isinstance(sig, pd.DataFrame):
        sig = sig(panels)
    if isinstance(sig, pd.DataFrame):
        return sig
    if sig == "carry":
        return panels.carry
    if sig == "momentum":
        return fx.momentum_panel(panels.xret, lookback=config.momentum_lookback)
    raise ValueError(f"unsupported signal {sig!r}")


def _default_buckets(n_names: int) -> int:
    """3 buckets for a single-region book, 5 for the full cross-section.

    Matches the committed books: G10 (9 names) and EM-only (18) are terciles,
    the combined 27-name book is quintiles.
    """
    return 3 if n_names <= 18 else 5


def _apply_exposure(weights: pd.DataFrame, exposure: pd.Series,
                    rebal: str) -> pd.DataFrame:
    """Scale weights by a lagged exposure multiplier.

    Sampled on the rebalance grid and shifted one period, mirroring
    `vol_target_weights` — so an exposure decision made at month-end t is
    effective from the next trading day, never on the day it is made. Dates
    before the exposure series starts are left fully invested (1.0), the
    `fx_utils.exposure_scalar` convention: a missing signal is not a reason to
    be out of the market.
    """
    e = exposure.resample(rebal).last()
    daily = e.reindex(weights.index, method="ffill").shift(1).fillna(1.0)
    return weights.mul(daily, axis=0)


def run(config: StrategyConfig | str | None = None, **overrides) -> StrategyResult:
    """Run the base carry backtest.

    >>> run()                                  # the team baseline (ALL, net 0.4659)
    >>> run("G10")                             # a preset by name
    >>> run(weighting="erc")                   # baseline with one knob changed
    >>> run(ALL_BASELINE.with_(vol_target=0.15))

    `config` may be a `StrategyConfig`, a preset name ("ALL"/"G10"/"EM") or None
    for the default; keyword `overrides` are applied on top.
    """
    cfg: StrategyConfig
    if config is None:
        cfg = PRESETS["ALL"]
    elif isinstance(config, str):
        key = config.upper()
        if key not in PRESETS:
            raise ValueError(f"unknown preset {config!r}; have {sorted(PRESETS)}")
        preset = PRESETS[key]
        # A preset may be a callable that BUILDS its config — "COMBINED" has to
        # load teammate inputs, and doing that at import time would make
        # `import strategy` touch the filesystem for everyone who never uses it.
        cfg = preset() if callable(preset) else preset
    else:
        cfg = config
    config = cfg.with_(**overrides) if overrides else cfg

    panels = load_panels(config.tenor)
    universe = resolve_universe(config.universe, panels, config.exclude)
    signal = _resolve_signal(config, panels)
    n_buckets = config.n_buckets or _default_buckets(len(universe))

    # 3. sort into legs, weight within leg (ffill + 1-day lag applied inside)
    weights_unit = fx.carry_portfolio(
        signal, panels.xret, n_buckets=n_buckets, rebal=config.rebal,
        vol_window=config.vol_window, min_per_leg=config.min_per_leg,
        universe=universe, max_leg_share=config.max_leg_share,
        filter_signal=config.filter_signal, weighting=config.weighting,
        cov_window=config.cov_window)
    if not isinstance(weights_unit.index, pd.DatetimeIndex):
        # carry_portfolio skipped every rebalance date, so it returned an empty
        # frame. Almost always too few names for the requested bucket count.
        raise ValueError(
            f"no rebalance date produced weights: {len(universe)} currencies into "
            f"{n_buckets} buckets leaves {len(universe) // n_buckets} per leg, below "
            f"min_per_leg={config.min_per_leg}. Lower n_buckets or widen the universe.")

    # 4. size to the vol target
    if config.vol_target is not None:
        weights = fx.vol_target_weights(
            weights_unit, panels.xret, target=config.vol_target,
            window=config.vol_target_window, rebal=config.rebal,
            lev_cap=config.lev_cap, vol_floor=config.vol_floor)
    else:
        weights = weights_unit.copy()

    # 5. overlays: exposure gate, then per-currency overlay, then extra lag
    if config.exposure is not None:
        weights = _apply_exposure(weights, config.exposure, config.rebal)
    if config.weight_overlay is not None:
        ctx = OverlayContext(config=config, panels=panels, universe=universe,
                             weights_unit=weights_unit, signal=signal)
        weights = config.weight_overlay(weights, ctx)
        if not weights.index.equals(panels.xret.index):
            weights = weights.reindex(panels.xret.index)
    if config.extra_lag:
        weights = weights.shift(config.extra_lag)

    # 6. P&L
    gross = fx.portfolio_returns(weights, panels.xret, "gross")
    if config.costs:
        cost = fx.roundtrip_cost(weights,
                                 panels.hs_outright * config.cost_multiple,
                                 panels.hs_points * config.cost_multiple,
                                 tenor=config.tenor)
    else:
        cost = pd.Series(0.0, index=gross.index, name="tcost")

    # 6b. external instrument legs (bond hedges, futures overlays). Each earns
    # Σ w·r and pays Σ|Δw|·cost_bps/1e4, so an added asset is costed like every
    # other position rather than netted off a return series for free. Masked to
    # `gross`'s own NaN pattern, so pre-inception days stay NaN and the
    # `contrib.sum(axis=1) == gross` identity survives. `()` is an exact no-op:
    # nothing below runs.
    index, live = gross.index, gross.notna()
    external = pd.DataFrame(index=index)
    external_coverage: dict[str, int] = {}
    for leg in config.external_legs:
        external[leg.name] = leg.pnl(index, config.rebal).where(live)
        gross = gross.add(external[leg.name], fill_value=0.0).where(live)
        if config.costs:
            leg_cost = leg.cost(index, config.rebal) * config.cost_multiple
            cost = cost.add(leg_cost.where(live, 0.0), fill_value=0.0)
        external_coverage[leg.name] = leg.missing_days(index, config.rebal, live)
    gross = gross.rename("gross")
    cost = cost.rename("tcost")

    net = (gross - cost).rename("net")

    live = gross.dropna().index
    if len(live) == 0:
        raise ValueError(f"no live returns for config {config.label()!r} — "
                         f"universe {universe} may be too small to sort")
    lo = pd.Timestamp(config.start) if config.start is not None else live[0]
    hi = pd.Timestamp(config.end) if config.end is not None else live[-1]

    return StrategyResult(
        config=config, panels=panels, universe=universe, signal=signal,
        weights_unit=weights_unit, weights=weights,
        gross=gross.loc[lo:hi], cost=cost.loc[lo:hi], net=net.loc[lo:hi],
        window=(lo, hi), external=external.loc[lo:hi] if len(external.columns)
        else external, external_coverage=external_coverage)
