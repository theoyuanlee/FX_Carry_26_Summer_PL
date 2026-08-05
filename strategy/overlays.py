"""Composition of overlays, and the external-instrument leg.

`StrategyConfig` carries exactly **one** `exposure` Series and **one**
`weight_overlay` callable. Phase 4 needs to stack four teammates' components in
one book (plan §19.4), so this module supplies the two composers — plus the one
thing neither hook can express.

Three pieces, in order of subtlety:

1. `compose_exposure(*series)` — the easy one. Gates are multiplicative
   de-risking factors, so their product is the "any gate says de-risk" rule, and
   multiplication is associative and commutative: **component order cannot
   change the answer**, which is what lets the §19.4 fold-in ladder claim its
   result is an assembly rather than a search over orderings.

2. `compose_overlays(*fns)` — the one with a contract. Chaining per-currency
   overlays is not just `f(g(w))`, because *an overlay that re-normalises gross
   exposure silently undoes the gate that ran before it*. Two defences:
   every step receives the SAME `ctx` (which carries `weights_unit`, the
   pre-sizing book, not the running weights), and every step is asserted
   **gross-non-increasing** at runtime. Overlays may scale positions down; they
   may never re-normalise back up. Without that assertion a "hedge" can quietly
   restore the risk a gate just removed and then take credit for the gate's
   drawdown improvement.

3. `ExternalLeg` — the component that fits neither hook, verified rather than
   assumed. A duration hedge adds a **new instrument** (a bond), not a
   reweighting of an FX pair. Routing it through `weight_overlay` fails twice:
   `fx_utils.portfolio_returns` intersects columns and would silently drop it,
   so it never earns its return, and `fx_utils.roundtrip_cost` raises
   `ValueError: No half-spread series for [...]`, so it can never pay its cost.
   No amount of overlay cleverness fixes that — it is an additional asset, and
   it needs its own field (`StrategyConfig.external_legs`, consumed in
   `core.run` step 6).

Everything here is a no-op at its neutral setting — `compose_exposure()` with no
gates, `compose_overlays()` with no overlays, `external_legs=()` — so adding the
machinery cannot move a committed number. `tests/test_overlays.py` asserts that
to 0.0e+00.

This module imports only numpy/pandas, so it sits below `config` and `core` in
the import graph and cannot create a cycle.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable

import numpy as np
import pandas as pd

__all__ = ["ExternalLeg", "compose_exposure", "compose_overlays",
           "GROSS_TOLERANCE"]


#: Slack allowed by the gross-non-increasing assertion in `compose_overlays`.
#: Absolute *and* relative, because a gross-2 book vol-targeted up to 4x leverage
#: carries ~8 units of notional and float error scales with it. Loose enough that
#: reordering a sum cannot trip it, tight enough that a re-normalisation (which
#: restores whole percent of gross) always does.
GROSS_TOLERANCE = 1e-9


# ---------------------------------------------------------------------------
# 1. Exposure gates
# ---------------------------------------------------------------------------

def compose_exposure(*series: pd.Series, floor: float = 0.0,
                     cap: float | None = None) -> pd.Series:
    """Combine total-exposure gates into one multiplier series.

    The product on the union of the inputs' indices, with each gate's missing
    dates treated as fully invested (1.0) rather than as zero — the
    `fx_utils.exposure_scalar` convention that a *missing signal is not a reason
    to be out of the market*. A gate that only starts in 2012 therefore leaves
    2007-2011 alone instead of flattening the book.

    Multiplicative, so this is the "any gate says de-risk" rule: two gates each
    halving risk give 0.25, not 0.5. That is deliberate — gates are independent
    risk vetoes, and a book that ignored the second veto would be claiming a
    diversification benefit between two risk-off signals that fire together.

    `floor` and `cap` clip the result. `floor=0.0` is the default because a
    negative exposure would flip the book's sign, which no de-risking rule
    should ever do. Pass `cap=1.0` to forbid levering up.

    With no arguments returns an empty Series — which `core._apply_exposure`
    resolves to 1.0 everywhere, i.e. an exact no-op.

    >>> compose_exposure(vix_gate, regime_gate, cap=1.0)
    """
    if not series:
        return pd.Series(dtype="float64", index=pd.DatetimeIndex([]), name="exposure")

    index = series[0].index
    for s in series[1:]:
        index = index.union(s.index)
    index = index.sort_values()

    out = pd.Series(1.0, index=index, dtype="float64")
    for s in series:
        out = out * s.reindex(index).astype("float64").fillna(1.0)
    return out.clip(lower=floor, upper=cap).rename("exposure")


# ---------------------------------------------------------------------------
# 2. Per-currency overlays
# ---------------------------------------------------------------------------

def _gross(weights: pd.DataFrame) -> pd.Series:
    return weights.abs().sum(axis=1, min_count=1)


def _assert_non_increasing(before: pd.DataFrame, after: pd.DataFrame,
                           label: str) -> None:
    """Raise if `after` holds more gross notional on any day than `before`.

    This is the composition contract, enforced rather than documented. The
    failure mode it catches is specific and silent: an overlay that re-normalises
    its output back to a target gross undoes whatever de-risking ran before it,
    and then inherits credit for the earlier component's drawdown improvement in
    the fold-in ladder.
    """
    g0, g1 = _gross(before), _gross(after)
    both = g0.notna() & g1.notna()
    if not both.any():
        return
    excess = (g1[both] - g0[both]) - GROSS_TOLERANCE * (1.0 + g0[both].abs())
    if bool((excess > 0).any()):
        worst = excess.idxmax()
        raise ValueError(
            f"overlay {label!r} increased gross exposure on {worst.date()}: "
            f"{g0[worst]:.6f} -> {g1[worst]:.6f}. Overlays may scale positions "
            f"down, never re-normalise back up — otherwise this overlay undoes "
            f"the gate that ran before it (strategy/overlays.py)."
        )


def compose_overlays(*fns: Callable) -> Callable:
    """Chain `weight_overlay` callables left to right into one callable.

    Each step is called as `f(weights, ctx)` and receives the **same** `ctx`
    every time — deliberately. `ctx.weights_unit` is the pre-sizing book, so an
    overlay keys off what the sort decided, not off what the previous overlay
    did. Two hedges that each react to the other's output would make the stack's
    result depend on an ordering nobody chose.

    After every step the result is asserted gross-non-increasing (see
    `_assert_non_increasing`). Shape is preserved: each step is reindexed back
    onto the incoming index and columns, so an overlay that drops a currency
    cannot silently shrink the book.

    With no arguments returns an identity function — an exact no-op.

    >>> run(weight_overlay=compose_overlays(skew_filter, option_trim))
    """
    steps = tuple(fns)

    def _chained(weights: pd.DataFrame, ctx) -> pd.DataFrame:
        out = weights
        for fn in steps:
            before = out
            out = fn(before, ctx)
            if not isinstance(out, pd.DataFrame):
                raise TypeError(
                    f"overlay {getattr(fn, '__name__', fn)!r} returned "
                    f"{type(out).__name__}, expected a DataFrame of weights")
            out = out.reindex(index=before.index, columns=before.columns)
            _assert_non_increasing(before, out, getattr(fn, "__name__", repr(fn)))
        return out

    _chained.__name__ = "+".join(getattr(f, "__name__", "overlay")
                                 for f in steps) or "identity"
    return _chained


# ---------------------------------------------------------------------------
# 3. External instrument legs
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class ExternalLeg:
    """One non-FX instrument held alongside the carry book.

    The escape hatch for a component that is an *additional asset* rather than a
    reweighting — Arjun's duration hedge (a bond ETF) being the case that forced
    it. Consumed by `core.run` step 6: the leg adds `Σ w·r` to `gross` and
    `Σ|Δw| · cost_bps/1e4` to `cost`, so it earns its return **and pays its own
    transaction costs**, which is the whole reason it lives in the engine rather
    than being netted off a return series in a notebook.

    Attributes
    ----------
    returns : daily simple/log return of **one unit** of the instrument.
        Reindexed onto the book's calendar; a date with no quote earns nothing
        from this leg rather than poisoning the book's return with NaN. Days
        where the leg holds a position but has no quote are counted and exposed
        as `StrategyResult.external_coverage`, so a data gap is visible rather
        than silently free.
    weight : signed units held per unit of book equity. A `float` for a constant
        position, or a `Series` for a time-varying one — which is **sampled on
        the rebalance grid and lagged one period** by `core.run`, exactly like
        `exposure`, so a hedge ratio estimated at month-end t is effective from
        the next trading day. Pass it unlagged; the base lags it. Dates before
        the series starts hold **nothing** (0.0) — the neutral position for a
        leg is flat, not invested, which is the opposite of the `exposure`
        convention and is why the two do not share a code path.
    cost_bps : round-trip cost in basis points per unit of |Δweight|.
    name : column label in `StrategyResult.external` and in `contrib`. Must be
        unique across a config's legs.

    Note the honest limit this class does *not* remove: it prices a linear
    instrument. A premium-paying option hedge needs an option price, and
    `data/raw` carries option **mids only** — see plan §19.1 and
    `cesare/DATA_SHOPPING_LIST.md` §2.2.
    """

    returns: pd.Series
    weight: pd.Series | float = 0.0
    cost_bps: float = 0.0
    name: str = "external"

    def __post_init__(self) -> None:
        if not isinstance(self.returns, pd.Series):
            raise TypeError(
                f"ExternalLeg.returns must be a Series, got {type(self.returns).__name__}")
        if not isinstance(self.returns.index, pd.DatetimeIndex):
            raise TypeError("ExternalLeg.returns must have a DatetimeIndex")
        if isinstance(self.weight, pd.Series):
            if not isinstance(self.weight.index, pd.DatetimeIndex):
                raise TypeError("ExternalLeg.weight Series must have a DatetimeIndex")
        elif not np.isscalar(self.weight):
            raise TypeError(
                f"ExternalLeg.weight must be a Series or a float, "
                f"got {type(self.weight).__name__}")
        if self.cost_bps < 0:
            raise ValueError(f"cost_bps must be >= 0, got {self.cost_bps}")

    # -- consumption (called by core.run step 6) ----------------------------

    def held(self, index: pd.Index, rebal: str) -> pd.Series:
        """Units actually held each day: rebalance-sampled, lagged one period.

        Mirrors `core._apply_exposure` and `fx_utils.vol_target_weights` — a
        decision made at a rebalance date is effective the next trading day,
        never on the day it is made. A scalar weight needs no lag: a constant
        carries no information about the future.
        """
        if np.isscalar(self.weight):
            return pd.Series(float(self.weight), index=index, name=self.name)
        w = self.weight.astype("float64").resample(rebal).last()
        return (w.reindex(index, method="ffill").shift(1).fillna(0.0)
                .rename(self.name))

    def pnl(self, index: pd.Index, rebal: str) -> pd.Series:
        """Daily P&L contribution `w · r` on the book's calendar."""
        w = self.held(index, rebal)
        r = self.returns.astype("float64").reindex(index)
        return (w * r).fillna(0.0).rename(self.name)

    def cost(self, index: pd.Index, rebal: str) -> pd.Series:
        """Daily transaction cost `|Δw| · cost_bps / 1e4`.

        The inception trade is charged, matching `fx_utils.roundtrip_cost`
        (which sets `dw.iloc[0] = w.iloc[0]` for exactly this reason): putting
        the position on is a real trade.
        """
        w = self.held(index, rebal)
        dw = w.diff()
        if len(dw):
            dw.iloc[0] = w.iloc[0]
        return (dw.abs().fillna(0.0) * self.cost_bps / 1e4).rename(self.name)

    def missing_days(self, index: pd.Index, rebal: str,
                     live: pd.Series | None = None) -> int:
        """Days the leg holds a position but has no quote (a silent-zero count).

        `live` restricts the count to days the book itself is trading. Without
        it the figure is dominated by pre-inception dates, where the leg has no
        quote *and* the book has no return — which is not a data gap, just the
        panel being longer than the book. `core.run` passes `gross.notna()`.
        """
        w = self.held(index, rebal)
        r = self.returns.reindex(index)
        gap = (w != 0.0) & r.isna()
        if live is not None:
            gap &= live.reindex(index).fillna(False).astype(bool)
        return int(gap.sum())
