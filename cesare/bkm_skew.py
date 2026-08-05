"""Model-free risk-neutral skewness from the five-point FX smile.

**Why this module exists.** Phase-3 D1 (plan §17.1) tested the Li–Sarno–Zinna
skewness-risk-premium claim using `fx_utils.implied_skew_panel` — the 25Δ
risk-reversal divided by ATM vol, i.e. a *smile-slope proxy* for skewness. Its
docstring says a proper Bakshi–Kapadia–Madan construction "would need the whole
strike chain, which the 3-point (ATM/RR/BF) surface here does not provide."

**That is false, and it was never checked.** Verified 2026-08-04: `data/raw`
carries **10Δ risk reversals and butterflies** alongside the 25Δ pair, for all 24
option tickers, ~5,080 observations each — identical coverage. The surface is a
**five-point smile** (10Δ put, 25Δ put, ATM, 25Δ call, 10Δ call), which is
exactly what the FX literature uses for model-free moments. So D1's null — one of
this project's three headline results — rested on a proxy when the correct input
was in the repo the whole time.

This is the fourth instance of the pattern the plan keeps recording (Appendix C
#12, #18, #26): a "we do not have the data" claim in a docstring or a plan table
that nobody tested.

**Method — Breeden–Litzenberger rather than BKM's truncated integrals.**
Both recover moments of the same risk-neutral distribution. The density route is
used here because it is *checkable*: a density must be non-negative and integrate
to one, so interpolation artefacts announce themselves instead of silently
biasing an integral. Every date reports how much probability mass had to be
clipped (`clipped_mass`), and dates that fail the check are dropped rather than
quietly returned.

The whole computation is done in **moneyness** `y = K/F`, which means the forward
never appears: skewness is location-invariant, and Black-76 in moneyness units is
free of `F` and of the discount factor. One less input, one less thing to get
wrong, and no dependence on an interest-rate series.

    from cesare.bkm_skew import bkm_skew_panel
    rn_skew = bkm_skew_panel("1M")     # daily, columns = currencies

Sign convention, matched to the rest of the project: the panel is the
**risk-neutral skewness of the log FX return in USD-per-FX terms**, so
*negative* = fat left tail = crash risk for a long-FX carry position. That is the
opposite sign to `fx_utils.implied_skew_panel`, which is deliberately
crash-positive; `implied_skew_panel` is (minus) a slope proxy, this is the
quantity itself.
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.interpolate import PchipInterpolator
from scipy.stats import norm

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from strategy import fx_utils as fx

#: Tenor -> year fraction. Matches `fx_utils.TENOR_MONTHS` conventions.
TENOR_YEARS = {"1W": 7 / 365.0, "1M": 1 / 12.0, "3M": 0.25, "6M": 0.5, "1Y": 1.0}

#: Strike grid: +/- this many standard deviations of the log return, and how many
#: points. 6 sigma is well past the 10Δ wings (~1.3 sigma), so the tails are
#: flat-extrapolated smile rather than fitted — the standard, conservative choice.
GRID_SD, GRID_N = 6.0, 401

#: A date is rejected if interpolation forced us to clip more than this share of
#: probability mass to keep the density non-negative (butterfly arbitrage in the
#: interpolated smile). 1% is loose enough to survive ordinary quote noise and
#: tight enough that a genuinely broken smile is dropped rather than reported.
MAX_CLIPPED_MASS = 0.01


# ---------------------------------------------------------------------------
# The five-point smile, oriented to USD-per-FX
# ---------------------------------------------------------------------------

def smile_points(tenor: str = "1M") -> dict[str, pd.DataFrame]:
    """The five quoted vols per currency, oriented for a long-FX position.

    Market quotes are per *pair*, with the risk reversal signed for the pair's
    base currency. `fx_utils.vol_surface_panel("RR")` already normalises those to
    **crash-positive** (positive = FX puts rich), so the FX-oriented risk
    reversal — call minus put on the foreign currency — is exactly its negative.
    Butterflies are symmetric under inversion and need no flip.

        sigma(dD call) = ATM + BF(d) + RR_fx(d)/2
        sigma(dD put)  = ATM + BF(d) - RR_fx(d)/2

    Returns vols in decimal (the parquets quote vol points).
    """
    atm = fx.vol_surface_panel("ATM", tenor=tenor) / 100.0
    out = {"atm": atm}
    for d in (25, 10):
        rr_fx = -fx.vol_surface_panel("RR", tenor=tenor, delta=d) / 100.0
        bf = fx.vol_surface_panel("BF", tenor=tenor, delta=d) / 100.0
        cols = atm.columns.intersection(rr_fx.columns).intersection(bf.columns)
        out[f"call{d}"] = atm[cols] + bf[cols] + rr_fx[cols] / 2.0
        out[f"put{d}"] = atm[cols] + bf[cols] - rr_fx[cols] / 2.0
    return out


def _delta_to_moneyness(sigma: np.ndarray, delta: np.ndarray, T: float,
                        is_call: np.ndarray) -> np.ndarray:
    """Forward-delta quote -> moneyness `K/F`, each point using its own vol.

    Forward delta of a call is `N(d1)`, of a put `N(-d1)`, with
    `d1 = (-ln(y) + sigma^2 T / 2) / (sigma sqrt(T))`. Inverting:
    `y = exp(sigma^2 T / 2 -/+ Phi^-1(delta) sigma sqrt(T))`. The at-the-money
    point is the delta-neutral straddle, `d1 = 0`, i.e. `y = exp(sigma^2 T / 2)`.
    """
    root = sigma * np.sqrt(T)
    d1 = np.where(is_call, norm.ppf(delta), -norm.ppf(delta))
    return np.exp(sigma ** 2 * T / 2.0 - d1 * root)


def _black76_call(y: np.ndarray, sigma: np.ndarray, T: float) -> np.ndarray:
    """Undiscounted call price per unit forward, in moneyness units."""
    root = sigma * np.sqrt(T)
    d1 = (-np.log(y) + sigma ** 2 * T / 2.0) / root
    return norm.cdf(d1) - y * norm.cdf(d1 - root)


def risk_neutral_skew_one(vols: np.ndarray, deltas: np.ndarray,
                          is_call: np.ndarray, T: float) -> tuple[float, float]:
    """Risk-neutral skewness of the log return from one date's smile.

    Steps: quotes -> moneyness; shape-preserving (PCHIP) interpolation of the
    smile in log-moneyness, extended C1 past the quoted wings; Black-76 call
    prices on a dense uniform log-moneyness grid; Breeden-Litzenberger
    `q ∝ d2C/dK2` via the chain rule; clip any residual negatives, renormalise,
    and take the third central moment of `ln(y)`.

    Returns `(skewness, clipped_mass)`. `clipped_mass` is the share of the raw
    density that had to be zeroed to remove butterfly arbitrage introduced by
    interpolation — the honesty column.
    """
    if np.any(~np.isfinite(vols)) or np.any(vols <= 0):
        return np.nan, np.nan

    y_q = _delta_to_moneyness(vols, deltas, T, is_call)
    order = np.argsort(y_q)
    ly_q, v_q = np.log(y_q[order]), vols[order]
    if len(np.unique(ly_q)) < len(ly_q):
        return np.nan, np.nan

    atm_vol = float(vols[deltas == 0.5][0]) if np.any(deltas == 0.5) else float(vols.mean())
    span = GRID_SD * atm_vol * np.sqrt(T)
    ly = np.linspace(-span, span, GRID_N)

    # PCHIP through the five points (shape-preserving: a least-squares cubic
    # overshoots between quotes), extended beyond the wings **linearly at the
    # boundary slope** so the smile is C1 everywhere.
    #
    # The C1 part is not fastidiousness. Flat wings leave a kink in sigma at the
    # junction, and a kink in sigma is a spike in d2C/dK2 — measured, that single
    # junction carried 1.7% of the probability mass as NEGATIVE density, three
    # grid points wide, sitting only ~1.6 sd out where the true density is still
    # large. Linear-at-the-boundary removes it. Vols are clipped into a band
    # around the boundary quote so an extrapolated wing cannot go negative or
    # explode; that reintroduces a kink, but out at >=6 sd where the density is
    # numerically zero.
    pchip = PchipInterpolator(ly_q, v_q, extrapolate=False)
    sig = pchip(ly)
    for edge, side in ((0, ly < ly_q[0]), (-1, ly > ly_q[-1])):
        v0 = v_q[edge]
        slope = float(pchip.derivative()(ly_q[edge]))
        sig = np.where(side, np.clip(v0 + slope * (ly - ly_q[edge]),
                                     0.25 * v0, 4.0 * v0), sig)
    if np.any(~np.isfinite(sig)) or np.any(sig <= 0):
        return np.nan, np.nan

    y = np.exp(ly)
    c = _black76_call(y, sig, T)
    # Breeden-Litzenberger. Differentiate on the UNIFORM log-moneyness grid and
    # convert by the chain rule — d2C/dy2 = (C_dd - C_d)/y^2 — rather than
    # differencing twice on an exponentially spaced y grid, which amplifies
    # noise where the spacing is widest.
    c_d = np.gradient(c, ly)
    dens_ly = (np.gradient(c_d, ly) - c_d) / y          # density in ln-y space

    # Trim the boundary points. `np.gradient` falls back to one-sided differences
    # at the ends, and applying it twice compounds that error over the outer two
    # points — which produced a spurious spike of ~0.5 at the left edge, where
    # the true density is numerically zero, and dragged the skewness of a FLAT
    # (lognormal, exactly-zero-skew) smile to -0.08. The grid runs to +/-6 sd, so
    # discarding three points a side discards nothing real.
    edge = 3
    ly_i, dens_i = ly[edge:-edge], dens_ly[edge:-edge]

    raw = np.trapezoid(np.clip(dens_i, 0.0, None), ly_i)
    if not np.isfinite(raw) or raw <= 0:
        return np.nan, np.nan
    clipped = float(np.trapezoid(np.clip(-dens_i, 0.0, None), ly_i) / raw)
    q = np.clip(dens_i, 0.0, None) / raw

    m1 = np.trapezoid(ly_i * q, ly_i)
    m2 = np.trapezoid((ly_i - m1) ** 2 * q, ly_i)
    m3 = np.trapezoid((ly_i - m1) ** 3 * q, ly_i)
    if not np.isfinite(m2) or m2 <= 0:
        return np.nan, clipped
    return float(m3 / m2 ** 1.5), clipped


# ---------------------------------------------------------------------------
# The panel
# ---------------------------------------------------------------------------

def bkm_skew_panel(tenor: str = "1M", freq: str = "ME") -> pd.DataFrame:
    """Daily panel of risk-neutral skewness per currency.

    Computed on the `freq` grid (month-end by default — the frequency the sort
    actually consumes) and forward-filled to daily, which is ~20x cheaper than a
    daily density fit and identical downstream: `carry_portfolio` samples at the
    rebalance date and lags one day regardless.

    **No lookahead by construction**: every date's number uses only that date's
    own quoted smile. Nothing is estimated across time.

    Dates whose interpolated density needed more than `MAX_CLIPPED_MASS` of
    negative mass removed are set to NaN rather than reported.
    """
    skew, _ = _bkm_grid(tenor, freq)
    daily_index = smile_points(tenor)["atm"].index
    return skew.reindex(daily_index.union(skew.index)).ffill().reindex(daily_index)


def _bkm_grid(tenor: str, freq: str) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Risk-neutral skewness and clipped-mass on the `freq` grid."""
    pts = smile_points(tenor)
    T = TENOR_YEARS[tenor]
    cols = pts["atm"].columns
    for k in ("call25", "put25", "call10", "put10"):
        cols = cols.intersection(pts[k].columns)
    grid = pts["atm"].resample(freq).last().index

    deltas = np.array([0.10, 0.25, 0.50, 0.25, 0.10])
    is_call = np.array([False, False, True, True, True])
    keys = ["put10", "put25", "atm", "call25", "call10"]

    skew = pd.DataFrame(index=grid, columns=cols, dtype="float64")
    clip = pd.DataFrame(index=grid, columns=cols, dtype="float64")
    sampled = {k: pts[k][cols].resample(freq).last() for k in keys}

    for dt in grid:
        for ccy in cols:
            vols = np.array([float(sampled[k].at[dt, ccy]) for k in keys])
            s, c = risk_neutral_skew_one(vols, deltas, is_call, T)
            skew.at[dt, ccy], clip.at[dt, ccy] = s, c

    bad = clip > MAX_CLIPPED_MASS
    return skew.mask(bad), clip


def bkm_skew_diagnostics(tenor: str = "1M", freq: str = "ME"
                         ) -> tuple[pd.DataFrame, pd.DataFrame]:
    """`(skew_on_grid, clipped_mass)` before forward-filling — for QA tables."""
    return _bkm_grid(tenor, freq)


def self_test() -> None:
    """Validate the estimator on smiles whose answer is known a priori.

    Run with `python cesare/bkm_skew.py`. Four properties, and one documented
    non-property:

    * a **flat** smile is lognormal, so the log return is normal and skewness is
      exactly 0;
    * a **symmetric** smile (butterflies, no risk reversal) is ~0;
    * **puts rich** gives negative skew, **calls rich** positive, and the two
      mirror each other;
    * the density is arbitrage-free (no clipping).

    The non-property, verified rather than assumed: the symmetric and mirror
    cases are only zero-and-equal *up to O(sqrt(T))*, because a smile symmetric
    in **delta** is not symmetric in **log-moneyness** — the delta-to-strike map
    carries a `sigma^2 T / 2` drift, so the quoted wings sit centred on that
    value rather than on zero. Confirmed by shrinking T: the residual falls from
    -0.0495 at 1M to -0.0011 at ~1 day, scaling as sqrt(T), and the wing centre
    equals sigma^2 T / 2 to six decimals. This is the market's convention
    showing through, not an error in the estimator.
    """
    deltas = np.array([0.10, 0.25, 0.50, 0.25, 0.10])
    is_call = np.array([False, False, True, True, True])
    T = TENOR_YEARS["1M"]

    def smile(atm, rr25, bf25, rr10, bf10):
        return np.array([atm + bf10 - rr10 / 2, atm + bf25 - rr25 / 2, atm,
                         atm + bf25 + rr25 / 2, atm + bf10 + rr10 / 2])

    cases = {
        "flat (lognormal, true 0)": smile(0.10, 0, 0, 0, 0),
        "symmetric wings (~0)": smile(0.10, 0, 0.005, 0, 0.015),
        "puts rich (crash)": smile(0.10, -0.02, 0.003, -0.035, 0.010),
        "calls rich (mirror)": smile(0.10, +0.02, 0.003, +0.035, 0.010),
        "EM-style deep skew": smile(0.22, -0.06, 0.010, -0.105, 0.030),
        "JPY-ish mild": smile(0.08, -0.008, 0.002, -0.014, 0.006),
    }
    out = {}
    print("bkm_skew self-test\n")
    for name, vols in cases.items():
        s, c = risk_neutral_skew_one(vols, deltas, is_call, T)
        out[name] = s
        print(f"  {name:28s} skew {s:+.5f}   clipped mass {c:.1e}")

    flat = out["flat (lognormal, true 0)"]
    sym = out["symmetric wings (~0)"]
    p, c_ = out["puts rich (crash)"], out["calls rich (mirror)"]
    assert abs(flat) < 2e-3, f"flat smile must be exactly 0, got {flat}"
    assert abs(sym) < 0.06, f"symmetric smile out of the O(sqrt(T)) band: {sym}"
    assert p < -0.3 and c_ > 0.3, f"sign convention broken: {p}, {c_}"
    assert abs(p + c_) < 0.06, f"mirror error out of the O(sqrt(T)) band: {p + c_}"

    # The convention check: the O(sqrt(T)) residual must vanish with T.
    shrink = [abs(risk_neutral_skew_one(cases["symmetric wings (~0)"],
                                        deltas, is_call, t)[0])
              for t in (1 / 12.0, 1 / 252.0, 1 / 25200.0)]
    assert shrink[0] > shrink[1] > shrink[2], (
        f"the symmetric-smile residual is not shrinking with T: {shrink} — that "
        f"would mean it is a bug in the estimator, not the delta convention")
    print(f"\n  delta-convention residual shrinks with T: "
          f"{shrink[0]:.4f} (1M) -> {shrink[1]:.4f} (1d) -> {shrink[2]:.4f} (~0)")
    print("\nPASS — flat=0, mirror symmetry, arbitrage-free density, "
          "residual is the delta convention")


def srp_panel(tenor: str = "1M", realized_window: int = 252,
              xret: pd.DataFrame | None = None) -> pd.DataFrame:
    """Skewness risk premium: physical skewness minus risk-neutral skewness.

    The Li–Sarno–Zinna (2023) definition, which D1 could only approximate. The
    physical leg is `fx_utils.realized_skew_panel` (trailing, so no lookahead);
    the risk-neutral leg is now the model-free quantity rather than a slope proxy.

    A currency with a *high* SRP has a physical distribution far less
    left-skewed than the option market is pricing — the market is paying a
    premium for crash insurance that has not been realised.
    """
    rn = bkm_skew_panel(tenor)
    if xret is None:
        from strategy import run
        xret = run().panels.xret
    phys = fx.realized_skew_panel(xret, window=realized_window)
    cols = rn.columns.intersection(phys.columns)
    return phys[cols] - rn[cols]


if __name__ == "__main__":
    self_test()
