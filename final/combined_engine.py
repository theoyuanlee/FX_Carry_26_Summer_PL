"""P4-C — the combined engine: components re-priced on the base, then laddered.

Plan §19.4. Base adoption stalled at 1 of 5, so §15's fallback becomes the primary
plan: rather than wait for four people to port their code, take each teammate's
**committed outputs** and re-price them on the shared base here. Every component
below is therefore labelled **re-priced, not rebuilt**, and its `reconstruction`
field states exactly how it was recovered. That is strictly worse than a real
port — it is my reading of their signal, not their specification of it — and
saying so is part of the deliverable.

    python final/combined_engine.py        # standalone table + both ladders

**This is the vendored copy** — the hand-off package's own definition of the
strategy, and the file `strategy/config.py` reads to build `run("COMBINED")`.
It differs from `cesare/combined_engine.py` in its four path constants and
nothing else (`PACKAGE_ROOT`, `OUTPUTS`, and the three input paths, all in the
block below); `tests/test_vendor_drift.py` declares that diff and fails on any
other. The rewiring is the point: in the multi-person repo the shared base had
to reach into a personal folder to learn what the strategy was, which is
backwards for a hand-off. Here the definition sits beside the engine.

Outputs (all to `final/evidence/`):

    p4_component_standalone.csv    each component alone, vs its own bar
    p4_component_by_episode.csv    the same components on ERAS + STRESS
    p4_combined_ladder.csv         add-one-in AND leave-one-out
    p4_combined_by_episode.csv     every rung on the frozen windows

Three protocol commitments, all fixed before any number was computed
(plan §6.9, §19.4):

1. **One change at a time**, against the immediately preceding book on this base
   — never against a number from another notebook, window or universe.
2. **Both ladders reported.** Add-one-in is order-dependent by construction and
   flatters whoever goes first; leave-one-out is the real test. If they disagree
   about a component, the component is not robust and this module says so rather
   than picking the flattering ladder.
3. **Pre-registered prior: the combination is worth less than the sum of its
   parts.** Seven components have already failed this bar. A negative combined
   result is the deliverable, not a disappointment.
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

#: The hand-off package root — the directory this file lives in. In the
#: multi-person repo the equivalent constant was `parents[1]` (the repo root),
#: because this module sat in a personal folder and had to reach up and across
#: into four other people's folders. Here everything it needs is a sibling, so it
#: reaches down instead. `sys.path.insert(0, ...)` at position 0 is deliberate:
#: it guarantees `import strategy` resolves to `final/strategy`, the vendored
#: engine, even when a repo-root `strategy/` is also importable.
PACKAGE_ROOT = Path(__file__).resolve().parent
if str(PACKAGE_ROOT) not in sys.path:
    sys.path.insert(0, str(PACKAGE_ROOT))

from strategy import fx_utils as fx, run
from strategy.episodes import ERAS, STRESS, report_windows
from strategy.overlays import ExternalLeg, compose_exposure, compose_overlays

#: Where the committed evidence lives. Re-running this module **overwrites** the
#: frozen CSVs in place — that is the point: a clean `git diff` after
#: `python final/combined_engine.py` is the reproduction proof. A dirty one is a
#: result worth reading before it is committed.
OUTPUTS = PACKAGE_ROOT / "evidence"

# --- slot criterion, fixed in advance (plan §19.4) --------------------------
#: A component earns its slot iff, net of costs, it improves MaxDD OR CVaR99 in
#: at least `SLOT_MIN_WINDOWS` of the six pre-2026 stress windows, AND costs less
#: than `SLOT_SHARPE_BUDGET` of whole-sample net Sharpe, AND survives
#: leave-one-out. Written here, above every computation, so it cannot be tuned
#: after seeing which components pass.
SLOT_WINDOWS = ("gfc_2008", "euro_2011", "taper_2013", "china_em_2015",
                "covid_2020", "rates_2022")
SLOT_MIN_WINDOWS = 4
SLOT_SHARPE_BUDGET = 0.05

#: Trailing window for the expanding hedge-ratio estimate. Arjun's value; kept so
#: the re-priced leg differs from his only in the book it is measured on.
HEDGE_WINDOW = 504

#: Percentile above which a risk-reversal / bad-skew reading counts as expensive.
EXPENSIVE_Q = 0.80


# ---------------------------------------------------------------------------
# Component inputs — every one of these reads a teammate's COMMITTED output
# ---------------------------------------------------------------------------

#: **VENDORED.** In the multi-person repo these three pointed into
#: `arjun/outputs/`, `vidhi/outputs/` and `theo/data/processed/` — which is why
#: `run("COMBINED")` used to die with `FileNotFoundError` the moment a teammate's
#: folder went away. They now point at byte-identical copies inside this package.
#: Source path, size, SHA-256 and the commit that produced each are recorded in
#: `inputs/PROVENANCE.md`; `tests/test_vendor_drift.py` re-checks the hashes.
#:
#: Vidhi's file is here even though her gate is **rejected**, so the rejection is
#: reproducible from inside `final/` rather than being something a reader has to
#: take on trust. Dafu's gate needs no file at all — it is one `exposure_scalar`
#: call on `data/raw/global_risk_wide.parquet`.
ARJUN_SERIES = PACKAGE_ROOT / "inputs" / "duration_hedge_series.csv"
VIDHI_MONTHLY = PACKAGE_ROOT / "inputs" / "adaptive_strategy_returns_monthly.csv"
THEO_PANEL = PACKAGE_ROOT / "inputs" / "fx_option_signal_panel.parquet"


def _require(path: Path, owner: str) -> Path:
    if not path.exists():
        raise FileNotFoundError(
            f"{owner}'s committed input is missing: {path}. The combined engine "
            f"re-prices committed outputs (plan §15 fallback); it cannot "
            f"reconstruct a component whose source file is absent.")
    return path


def arjun_duration_inputs() -> tuple[pd.Series, float]:
    """TLT daily return and the half-spread implied by Arjun's own cost model.

    The half-spread is **backed out** of his committed series rather than
    re-parsed from his Bloomberg workbook: he charges `HALF · |Δh|`, and both
    the gross and net hedged tracks are committed, so
    `HALF = median((gross - net) / |Δh|)` over the days the ratio moves. That
    recovers 0.678bp and reproduces his net series to 1.1e-15 — an exact
    reconstruction from committed data, with no dependency on a file only he has.
    """
    d = pd.read_csv(_require(ARJUN_SERIES, "Arjun"), index_col=0, parse_dates=True)
    tlt = d["TLT"].astype("float64").rename("TLT")
    h = d["h_expanding"].astype("float64").fillna(0.0)
    implied = (d["book"] - h * d["TLT"]) - d["hedged_net"]
    dh = h.diff().abs().fillna(0.0)
    moved = dh > 0
    half = float((implied[moved] / dh[moved]).median())
    return tlt, half


def hedge_ratio(book: pd.Series, instrument: pd.Series,
                window: int = HEDGE_WINDOW) -> pd.Series:
    """Expanding, real-time beta of `book` on `instrument`, lagged one day.

    The **expanding / real-time** estimate, never the in-sample fit. Arjun's own
    table reports both (0.5095 real-time vs 0.5265 in-sample) and only the first
    is a number anyone could have traded; quoting the second would be reporting a
    full-sample fit as a live result.
    """
    d = pd.concat([book.rename("b"), instrument.rename("i")], axis=1).dropna()
    beta = (d["b"].expanding(window).cov(d["i"]) / d["i"].expanding(window).var())
    return beta.shift(1).rename("hedge_ratio")


# ---------------------------------------------------------------------------
# The four components
# ---------------------------------------------------------------------------

def duration_leg(book: pd.Series | None = None) -> ExternalLeg:
    """Arjun's duration hedge as an `ExternalLeg` — long TLT against the book.

    The hedge ratio is re-estimated **on this base's own net book** with his
    estimator (expanding 504d, lagged), because a hedge ratio is a function of
    the book being hedged. `weight = -beta`: beta is negative (bonds rally when
    carry breaks), so the position is long TLT.

    Costed at the half-spread implied by his own model. See
    `duration_drift_cost` for the charge his model — and this one — omits.
    """
    tlt, half = arjun_duration_inputs()
    book = run().net if book is None else book
    beta = hedge_ratio(book, tlt)
    return ExternalLeg(returns=tlt, weight=-beta, cost_bps=half * 1e4, name="TLT")


def duration_drift_cost(book: pd.Series | None = None, rebal: str = "ME") -> dict:
    """The cost Arjun's model does not charge, quantified rather than asserted.

    His gross-net gap is 3.8e-5, which the plan reads as "the hedge is
    essentially unpriced". The real reason is narrower: he bills only the
    turnover from **re-estimating** the beta, and an expanding-window beta drifts
    very slowly (Σ|Δh| = 0.94 over eighteen years). What nobody bills is
    **rebalance drift** — holding the position at `beta ×` equity requires
    trading whenever TLT moves relative to the book, even with the ratio frozen.

    Modelled the way the position would actually be maintained: at each rebalance
    the held units have drifted by the instrument's compounded return relative to
    the book's, and are traded back to target.
    """
    tlt, half = arjun_duration_inputs()
    book = run().net if book is None else book
    beta = hedge_ratio(book, tlt)
    d = pd.concat([book.rename("b"), tlt.rename("i"), -beta.rename("w")],
                  axis=1).dropna()
    grid = d.resample(rebal).last().index
    target = d["w"].reindex(grid, method="ffill")
    growth_i = (1.0 + d["i"]).resample(rebal).prod()
    growth_b = (1.0 + d["b"]).resample(rebal).prod()
    drifted = target.shift(1) * (growth_i / growth_b).reindex(grid)
    traded = (target - drifted).abs().dropna()
    years = (d.index[-1] - d.index[0]).days / 365.25
    drag = float(traded.sum() * half / years)
    return {"ann_drift_cost": drag, "ann_drift_cost_bp": drag * 1e4,
            "rebalances": int(len(traded)),
            "mean_units_traded": float(traded.mean()),
            "half_spread_bp": half * 1e4}


def vix_gate(low_mult: float = 0.5) -> pd.Series:
    """Dafu's VIX percentile gate — half risk in the top fifth of a trailing 3y.

    The one component that needs no file at all: `dafu/regime_lab.py` defines it
    as exactly this call on the shared `data/raw`, so it reconstructs from the
    base rather than from his outputs. Verified to reproduce his committed
    headline to five decimals on net Sharpe, MaxDD, Calmar and turnover.

    Careful: this is NOT Stage 3's VIX rule, which is a level threshold scoring
    net 0.441. Do not merge the two numbers (plan §19.3).
    """
    return fx.exposure_scalar(fx.load_wide("global_risk")["VIX"],
                              lookback=756, q=0.80, low_mult=low_mult)


def regime_gate(shift: int = 0) -> pd.Series:
    """Vidhi's probability-scaled regime gate, recovered from her return ratio.

    She has not committed the probability series, but she has committed both the
    static and the probability-scaled monthly tracks, and the second is the first
    times the gate. So `probability_scaled / static` recovers the multiplier
    exactly — it lands in [0, 1] over 173 months from 2012-02, which is the
    check that the reconstruction is right rather than an artefact.

    Only the **gate** is portable. Her book's returns are `log_return(spot)` with
    the carry accrual never added (plan §18), which is why her static track shows
    Sharpe −0.71; none of her performance numbers transfer, and this gate is
    measured here on a book that actually harvests the carry it sorts on.

    **The lag convention is genuinely ambiguous and her outputs do not record
    it.** Her `ratio_t` is the multiplier applied to her month-*t* return, i.e.
    the decision made at *t−1*; the base's `exposure` is dated at the decision
    and applied from the next period. Dating it at *t* therefore risks the
    double-lag the README warns about, and dating it at *t−1* (`shift=-1`) risks
    the opposite. Both are reported (`regime_gate_lag_sensitivity`) because the
    verdict must not rest on a convention nobody wrote down — and it does not:
    the gate fails badly either way.

    Returned unlagged — the base samples and lags it.
    """
    m = pd.read_csv(_require(VIDHI_MONTHLY, "Vidhi"), parse_dates=["date"])
    m = m.set_index("date").sort_index()
    ratio = (m["probability_scaled"] / m["static"].replace(0.0, np.nan)).dropna()
    if not ratio.between(-1e-9, 1.0 + 1e-9).all():
        raise ValueError(
            f"recovered gate left [0,1] — the ratio reconstruction is not valid: "
            f"min {ratio.min():.4f} max {ratio.max():.4f}")
    out = ratio.clip(0.0, 1.0).rename("vidhi_regime_gate")
    return out.shift(shift).dropna() if shift else out


def regime_gate_lag_sensitivity() -> pd.DataFrame:
    """Vidhi's gate under both lag conventions, plus what it actually tracks.

    The diagnostic that matters more than either Sharpe: the gate's correlation
    with VIX is ~0 at every lead and lag. It de-risks about half of all months
    with no discernible relationship to market stress — which is consistent with
    §18's diagnosis that her model was fitted to cut losses on a book that was
    losing because it never collected the carry it sorted on.
    """
    vix = fx.load_wide("global_risk")["VIX"].resample("ME").last()
    rows = []
    for label, shift in (("as-committed (dated at the scaled month)", 0),
                         ("shifted -1M (dated at the decision month)", -1)):
        g = regime_gate(shift=shift)
        res = run(exposure=g, name="ALL")
        s = res.summary(benchmark=None).loc["ALL_net"]
        j = pd.concat([g.rename("g"), vix.rename("v")], axis=1).dropna()
        rows.append({"convention": label, "net_sharpe": float(s["sharpe"]),
                     "max_drawdown": float(s["max_drawdown"]),
                     "turnover": float(res.turnover),
                     "months": int(len(g)), "frac_de_risked": float((g < 1 - 1e-9).mean()),
                     "corr_vix_same": float(j["g"].corr(j["v"])),
                     "corr_vix_prev": float(j["g"].corr(j["v"].shift(1))),
                     "corr_vix_next": float(j["g"].corr(j["v"].shift(-1)))})
    return pd.DataFrame(rows)


def _theo_bad_skew() -> pd.DataFrame:
    """Theo's month-end bad-skew panel, pivoted to currencies x dates.

    Verified 2026-08-03: this column is **bit-identical** to
    `fx_utils.vol_surface_panel("RR", "1M")` resampled to month-end — max
    absolute difference 0.0 across all 21 shared currencies. His "bad skew" and
    the base's crash-positive risk reversal are the same number, which is the
    sharpest possible statement of the §19.1 collision.
    """
    t = pd.read_parquet(_require(THEO_PANEL, "Theo"))
    ok = t[t["option_data_quality_flag"].eq("ok")]
    return ok.pivot(index="month_end", columns="currency", values="bad_skew25_1m")


def skew_exclusion_overlay(weights: pd.DataFrame, ctx) -> pd.DataFrame:
    """Theo's bad-skew exclusion: drop the month's worst-skew quintile.

    His rule, from `theo/06_options_skew_and_vol_filters.ipynb`: exclude names
    whose bad skew is at or above the **cross-sectional** 80th percentile *that
    month*. That is a different conditioning axis from the project's adopted
    per-currency rule, which ranks each currency against its own trailing three
    years — same signal, different question ("worst in the cross-section today"
    vs "expensive for this currency by its own standards").

    Two deliberate departures from his implementation, both conservative:

    * He excludes **before** the sort, so his book re-normalises back to full
      gross. Here the positions are zeroed **after** sizing, so the book simply
      carries less risk. Re-normalising would violate the composition contract
      (`overlays.compose_overlays`) and would silently undo any gate composed
      before this one.
    * Month-end sampled and lagged one day, like every other signal in the base.
    """
    panel = _theo_bad_skew()
    daily = panel.reindex(weights.index.union(panel.index)).ffill().reindex(weights.index)
    cut = daily.quantile(EXPENSIVE_Q, axis=1)
    bad = (daily.ge(cut, axis=0) & daily.notna()).astype("float64")
    bad = (bad.resample(ctx.config.rebal).last()
           .reindex(weights.index, method="ffill").shift(1).fillna(0.0))
    bad = bad.reindex(columns=weights.columns, fill_value=0.0) > 0.5
    # `.where(weights.notna())` is not cosmetic: `mask` would turn a
    # pre-inception NaN weight into a real 0.0, `portfolio_returns` (min_count=1)
    # would then emit a return on a day the book does not exist, and the
    # evaluation window would silently start three months early — breaking
    # guardrail §6.7 and making the variant non-comparable to the baseline.
    return weights.mask(bad, 0.0).where(weights.notna())


def gross_matched_control(overlay):
    """Wrap a trimming overlay in its own de-risking control.

    **The control every trimming overlay needs and almost never gets.** An
    overlay that zeroes positions does two things at once: it drops *particular*
    names (selection) and it leaves the book holding *less notional*
    (de-risking). A shallower drawdown follows mechanically from the second,
    whatever the first is worth — so a filter can post a spectacular MaxDD
    improvement while its signal contributes nothing.

    This returns an overlay that reproduces the wrapped overlay's **daily gross
    exposure exactly** (to 8.9e-16) but spreads the reduction uniformly across
    every name. Any difference between the two books is then attributable to
    selection alone, and `nw_regression` of one on the other prices it.
    """
    def control(weights: pd.DataFrame, ctx) -> pd.DataFrame:
        trimmed = overlay(weights, ctx)
        g0 = weights.abs().sum(axis=1)
        ratio = (trimmed.abs().sum(axis=1) / g0.replace(0.0, np.nan)).fillna(1.0)
        return weights.mul(ratio, axis=0)
    control.__name__ = f"gross_matched_control({getattr(overlay,'__name__','overlay')})"
    return control


def rr_trim_overlay(weights: pd.DataFrame, ctx) -> pd.DataFrame:
    """The project's adopted per-currency RR rule — Theo's bar, not a component.

    Halve long positions whose crash insurance sits in the top quintile of that
    currency's own trailing three years (plan §9). Rebuilt here on the base from
    `strategy/examples/03_option_weight_overlay.py` so the bar and the variant
    are produced by the same code on the same day.

    It reproduces the committed Stage-3 `rrccy` book's MaxDD to seven digits
    (−0.2762329) but its net Sharpe to only 8e-4 (0.45592 vs the committed
    0.45668), with turnover 0.69282 vs 0.69410. The residual sits in cost and
    turnover, consistent with the notebook applying the trim at a slightly
    different point in the pipeline. **The rebuilt number is the bar used here**,
    per README rule 6: the comparison must be `run()` with one change against
    `run()` without it, not against a number from another notebook.
    """
    rr = fx.vol_surface_panel("RR", "1M").reindex(weights.index).ffill()
    rank = rr.rolling(756, min_periods=378).rank(pct=True)
    rank_rb = (rank.resample(ctx.config.rebal).last()
               .reindex(weights.index, method="ffill").shift(1))
    expensive = (rank_rb > EXPENSIVE_Q).reindex(
        columns=weights.columns, fill_value=False).astype(bool)
    scale = pd.DataFrame(1.0, index=weights.index, columns=weights.columns)
    scale[expensive & (weights > 0)] = 0.5
    return weights * scale


# ---------------------------------------------------------------------------
# Component registry — slot order is the §19.4 composition order
# ---------------------------------------------------------------------------

def components() -> list[dict]:
    """The four components, in the fixed composition order.

    `external_legs` first (additive, does not touch FX weights), then `exposure`
    (book-level scalars, which commute), then `weight_overlay` (per-name, last,
    so a trim is measured on an already-sized book). Declared in advance so the
    ladder is an assembly rather than a search over orderings.
    """
    base_net = run().net
    return [
        {"key": "duration", "owner": "Arjun", "slot": "external_legs",
         "label": "Duration hedge (long TLT)",
         "reconstruction": "re-priced, not rebuilt: TLT return from his committed "
                           "duration_hedge_series.csv; hedge ratio re-estimated on "
                           "THIS base's net book with his estimator (expanding 504d, "
                           "lagged); cost_bps backed out of his own gross-vs-net "
                           "series (0.678bp, reproduces his net to 1.1e-15)",
         "build": lambda: {"external_legs": (duration_leg(base_net),)}},
        {"key": "vix_gate", "owner": "Dafu", "slot": "exposure",
         "label": "VIX percentile gate (p80 / 756d)",
         "reconstruction": "exact: dafu/regime_lab.py defines it as one "
                           "fx.exposure_scalar call on shared data/raw, so no file "
                           "is needed; reproduces his committed headline to 5dp",
         "build": lambda: {"exposure": vix_gate()}},
        {"key": "regime_gate", "owner": "Vidhi", "slot": "exposure",
         "label": "Macro/regime probability gate",
         "reconstruction": "re-priced, not rebuilt: the gate recovered as "
                           "probability_scaled / static from her committed monthly "
                           "tracks (173 months from 2012-02, values in [0,1]). Only "
                           "the gate transfers — her book omits the carry accrual",
         "build": lambda: {"exposure": regime_gate()}},
        {"key": "skew_excl", "owner": "Theo", "slot": "weight_overlay",
         "label": "Bad-skew exclusion (XS top quintile)",
         "reconstruction": "re-priced, not rebuilt: his committed bad_skew25_1m "
                           "panel with his cross-sectional p80 rule, applied as a "
                           "post-sizing trim rather than a pre-sort exclusion. NOTE "
                           "his signal is bit-identical to fx.vol_surface_panel('RR')",
         "build": lambda: {"weight_overlay": skew_exclusion_overlay}},
    ]


# ---------------------------------------------------------------------------
# Measurement helpers
# ---------------------------------------------------------------------------

def _stats(result, basis: str = "net") -> dict:
    s = result.summary(benchmark=None)
    row = s.loc[[i for i in s.index if i.endswith(f"_{basis}")][0]]
    return {"ann_return": float(row["ann_return"]), "ann_vol": float(row["ann_vol"]),
            "sharpe": float(row["sharpe"]), "sortino": float(row["sortino"]),
            "calmar": float(row["calmar"]),
            "max_drawdown": float(row["max_drawdown"]), "skew": float(row["skew"]),
            "hit_rate": float(row["hit_rate"]), "CVaR_99": float(row["CVaR_99"]),
            "n_days": int(row["n_days"])}


def _nw_alpha(result, reference) -> dict:
    """Newey-West alpha of one book on another — always vs the PRECEDING rung.

    Regressing on the baseline instead is how a component collects credit for
    the work of everything added before it (plan §19.4).
    """
    out = fx.nw_regression(result.net.rename("y"),
                           reference.net.rename("ref").to_frame(), lags=5)
    if out is None:
        return {"alpha_ann": np.nan, "t_alpha": np.nan, "beta_ref": np.nan}
    return {"alpha_ann": float(out["alpha_ann"]), "t_alpha": float(out["alpha_t"]),
            "beta_ref": float(out.get("beta_ref", np.nan))}


def _window_tails(result, windows: dict) -> pd.DataFrame:
    """Per-window MaxDD and CVaR99 on the net book — the columns that decide.

    `report_windows` carries MaxDD but not CVaR99, so CVaR comes from
    `summary_stats` on the resliced book. No new statistic is implemented.
    """
    rows = []
    label = result.config.label()
    for name, (start, end) in windows.items():
        sub = result.reslice(start, end)
        stats = sub.summary(benchmark=None, min_obs=20)
        key = f"{label}_net"
        cvar = float(stats.loc[key, "CVaR_99"]) if key in stats.index else np.nan
        mdd = float(stats.loc[key, "max_drawdown"]) if key in stats.index else np.nan
        rows.append({"window": name, "max_drawdown": mdd, "CVaR_99": cvar,
                     "cum_return": float(sub.net.dropna().sum()),
                     "n_days": int(len(sub.net.dropna()))})
    return pd.DataFrame(rows).set_index("window")


def _tail_score(variant, reference, windows=SLOT_WINDOWS) -> dict:
    """How many of the six pre-2026 stress windows the change improves.

    "Improves" = a shallower drawdown OR a smaller CVaR99 than the reference
    book, measured window by window. This is criterion (i) of the slot rule.
    """
    sub = {k: STRESS[k] for k in windows}
    a, b = _window_tails(variant, sub), _window_tails(reference, sub)
    better_dd = (a["max_drawdown"] > b["max_drawdown"])          # less negative
    better_cv = (a["CVaR_99"] < b["CVaR_99"])
    wins = (better_dd | better_cv)
    return {"windows_improved": int(wins.sum()), "windows_tested": int(len(wins)),
            "windows_dd_better": int(better_dd.sum()),
            "windows_cvar_better": int(better_cv.sum()),
            "windows_won": "|".join(wins[wins].index)}


# ---------------------------------------------------------------------------
# Step 2 — each component standalone, one change at a time
# ---------------------------------------------------------------------------

def standalone() -> tuple[pd.DataFrame, pd.DataFrame]:
    """Each component alone on the base, against its own stated bar.

    Theo's bar is the per-currency RR book, not the raw baseline (plan §19.1):
    his signal overlaps completed work, and measuring it against the untouched
    baseline would credit it with a tail improvement the adopted RR rule already
    delivers — and would hand the desk two contradictory skew answers in one
    meeting.
    """
    base = run()
    rr_bar = run(weight_overlay=rr_trim_overlay, name="ALL")
    bars = {"baseline": base, "per-currency RR": rr_bar}

    rows, episodes = [], []
    reference_rows = [
        ("(bar) baseline", "Cesare", "-", base, base, "the shared base"),
        ("(bar) per-currency RR", "Cesare", "weight_overlay", rr_bar, base,
         "rebuilt on the base from examples/03; reproduces the committed rrccy "
         "MaxDD to 7 digits, its net Sharpe to 8e-4"),
    ]
    for label, owner, slot, res, ref, note in reference_rows:
        rows.append(_row(label, owner, slot, res, ref, note, bar="baseline"))
        episodes.extend(_episode_rows(label, res))

    for comp in components():
        res = run(name="ALL", **comp["build"]())
        ref = rr_bar if comp["key"] == "skew_excl" else base
        bar = "per-currency RR" if comp["key"] == "skew_excl" else "baseline"
        rows.append(_row(comp["label"], comp["owner"], comp["slot"], res, ref,
                         comp["reconstruction"], bar=bar))
        episodes.extend(_episode_rows(comp["label"], res))

    # The control that decides whether a trimming overlay's tail improvement is
    # selection or simply holding less. Compared against the overlay itself, not
    # against the baseline: the question is what the SIGNAL adds once the
    # de-risking is held identical.
    ctrl_fn = gross_matched_control(skew_exclusion_overlay)
    ctrl = run(weight_overlay=ctrl_fn, name="ALL")
    skew = run(weight_overlay=skew_exclusion_overlay, name="ALL")
    rows.append(_row("(control) gross-matched de-risk", "Cesare", "weight_overlay",
                     ctrl, skew,
                     "CONTROL, not a variant: identical daily gross to the bad-skew "
                     "exclusion (max diff 8.9e-16) but spread across every name, so "
                     "any difference is selection rather than de-risking",
                     bar="bad-skew exclusion"))
    episodes.extend(_episode_rows("(control) gross-matched de-risk", ctrl))

    table = pd.DataFrame(rows)
    by_ep = pd.DataFrame(episodes)
    table.to_csv(OUTPUTS / "p4_component_standalone.csv", index=False)
    by_ep.to_csv(OUTPUTS / "p4_component_by_episode.csv", index=False)
    return table, by_ep


def _row(label, owner, slot, res, ref, note, bar) -> dict:
    gross, net = _stats(res, "gross"), _stats(res, "net")
    alpha = _nw_alpha(res, ref) if res is not ref else {
        "alpha_ann": np.nan, "t_alpha": np.nan, "beta_ref": np.nan}
    tail = _tail_score(res, ref) if res is not ref else {
        "windows_improved": np.nan, "windows_tested": len(SLOT_WINDOWS),
        "windows_dd_better": np.nan, "windows_cvar_better": np.nan,
        "windows_won": ""}
    cfg = dict(res.config.describe())
    return {
        "variant": label, "owner": owner, "slot": slot, "bar": bar,
        "gross_sharpe": gross["sharpe"], "net_sharpe": net["sharpe"],
        "d_net_sharpe_vs_bar": net["sharpe"] - _stats(ref, "net")["sharpe"],
        "ann_return_net": net["ann_return"], "ann_vol_net": net["ann_vol"],
        "max_drawdown": net["max_drawdown"], "CVaR_99": net["CVaR_99"],
        "skew": net["skew"], "sortino": net["sortino"], "calmar": net["calmar"],
        "hit_rate": net["hit_rate"], "turnover": float(res.turnover),
        "cost_drag": float(res.cost_drag), "n_days": net["n_days"],
        **alpha, **tail,
        "external_coverage": "|".join(f"{k}:{v}" for k, v in
                                      res.external_coverage.items()) or None,
        "reconstruction": note,
        "window_start": str(res.window[0].date()), "window_end": str(res.window[1].date()),
        **{f"cfg_{k}": v for k, v in cfg.items()},
    }


def _episode_rows(label: str, res) -> list[dict]:
    out = []
    for tag, windows in (("ERAS", ERAS), ("STRESS", STRESS)):
        rep = report_windows(res, windows, which="both")
        rep.insert(0, "variant", label)
        rep.insert(1, "window_set", tag)
        out.extend(rep.to_dict("records"))
    return out


# ---------------------------------------------------------------------------
# Step 3 — the two ladders
# ---------------------------------------------------------------------------

def _config_for(keys: list[str]) -> dict:
    """Assemble config overrides for a set of components, in slot order.

    Several `exposure` components compose multiplicatively; several
    `weight_overlay` components chain with the gross-non-increasing assertion.
    """
    chosen = [c for c in components() if c["key"] in keys]
    legs, gates, overlays_ = [], [], []
    for comp in chosen:
        built = comp["build"]()
        legs.extend(built.get("external_legs", ()))
        if "exposure" in built:
            gates.append(built["exposure"])
        if "weight_overlay" in built:
            overlays_.append(built["weight_overlay"])
    cfg: dict = {"name": "ALL"}
    if legs:
        cfg["external_legs"] = tuple(legs)
    if gates:
        cfg["exposure"] = compose_exposure(*gates)
    if overlays_:
        cfg["weight_overlay"] = compose_overlays(*overlays_)
    return cfg


def _add_ladder(order, meta, rows, episodes, tag: str) -> object:
    """One add-one-in pass over `order`, appending rows. Returns the full book."""
    base = run()
    rows.append(_ladder_row(tag, 0, "baseline", "-", base, base, [], slot=None))
    episodes.extend(_episode_rows(f"{tag}0 baseline", base))
    prev, running = base, []
    for i, key in enumerate(order, start=1):
        running.append(key)
        res = run(**_config_for(running))
        rows.append(_ladder_row(tag, i, f"+ {meta[key]['label']}",
                                meta[key]["owner"], res, prev, list(running),
                                slot=_slot_verdict(res, prev), comp_key=key))
        episodes.extend(_episode_rows(f"{tag}{i} +{key}", res))
        prev = res
    return prev


def ladder() -> tuple[pd.DataFrame, pd.DataFrame]:
    """Both ladders, then a clean re-ladder over the survivors.

    Three passes, and the third exists because of a structural weakness in the
    first that is worth stating rather than hiding:

    * **`add`** — add-one-in over all components in the fixed slot order. Every
      rung is measured against the immediately preceding rung.
    * **`loo`** — leave-one-out from the full stack. This is the real test: a
      component that does not hurt when removed has not earned its slot.
    * **`final`** — add-one-in again over only the components that survived
      leave-one-out. This is **not** a search for a flattering configuration; it
      is criterion (iii) of the slot rule being applied. Once a component is
      rejected for making the book worse, every rung measured on top of it in
      the first pass was measured against a book that will not be built, and
      reporting those as the components' verdicts would be measurement error.
      The `final` ladder determines `ADOPTED` and the `COMBINED` preset.

    All three are written to the CSV. If `add` and `loo` disagree about a
    component, the `ladders_agree` column says so and the component is treated
    as not robust.
    """
    order = [c["key"] for c in components()]
    meta = {c["key"]: c for c in components()}
    rows, episodes = [], []

    full = _add_ladder(order, meta, rows, episodes, "add")

    survivors, loo_verdict = [], {}
    for key in order:
        keep = [k for k in order if k != key]
        res = run(**_config_for(keep))
        # Read the other way round: the FULL book is the variant and the reduced
        # book is the reference, so a positive d_net_sharpe means removing the
        # component HURT — i.e. it earned its slot.
        verdict = _slot_verdict(full, res)
        rows.append(_ladder_row("loo", np.nan, f"- {meta[key]['label']}",
                                meta[key]["owner"], res, full, keep, slot=verdict,
                                comp_key=key))
        episodes.extend(_episode_rows(f"loo -{key}", res))
        loo_verdict[key] = verdict
        if verdict["d_net_sharpe"] > 0:
            survivors.append(key)

    if survivors and survivors != order:
        final_full = _add_ladder(survivors, meta, rows, episodes, "final")
        # Criterion (iii) again, on the stack actually being proposed. The first
        # leave-one-out pass ran on a stack containing a component since rejected,
        # so its verdicts on the survivors were measured against a book nobody
        # will build. Re-running it is applying the rule, not re-rolling for a
        # better answer — and both passes stay in the CSV.
        for key in survivors:
            keep = [k for k in survivors if k != key]
            res = run(**_config_for(keep)) if keep else run()
            rows.append(_ladder_row("final_loo", np.nan, f"- {meta[key]['label']}",
                                    meta[key]["owner"], res, final_full, keep,
                                    slot=_slot_verdict(final_full, res),
                                    comp_key=key))
            episodes.extend(_episode_rows(f"final_loo -{key}", res))

    table = pd.DataFrame(rows)
    # Do the two ladders agree about each component?
    add_earned = {r["component"]: r.get("slot_earned")
                  for r in rows if r["ladder"] == "add" and r["component"]}
    table["ladders_agree"] = [
        (add_earned.get(r["component"]) == bool(r["d_net_sharpe"] > 0))
        if r["ladder"] == "loo" else np.nan for _, r in table.iterrows()]
    table["survivors"] = "|".join(survivors) or "(none)"

    by_ep = pd.DataFrame(episodes)
    table.to_csv(OUTPUTS / "p4_combined_ladder.csv", index=False)
    by_ep.to_csv(OUTPUTS / "p4_combined_by_episode.csv", index=False)
    return table, by_ep


def _slot_verdict(variant, reference) -> dict:
    """Criteria (i) and (ii) of the slot rule. (iii) is the ladder comparison."""
    tail = _tail_score(variant, reference)
    d_sharpe = _stats(variant, "net")["sharpe"] - _stats(reference, "net")["sharpe"]
    passes_tail = tail["windows_improved"] >= SLOT_MIN_WINDOWS
    passes_cost = d_sharpe > -SLOT_SHARPE_BUDGET
    return {**tail, "d_net_sharpe": d_sharpe,
            "slot_tail_ok": bool(passes_tail), "slot_cost_ok": bool(passes_cost),
            "slot_earned": bool(passes_tail and passes_cost)}


def _ladder_row(kind, rung, label, owner, res, ref, keys, slot,
                comp_key: str | None = None) -> dict:
    net = _stats(res, "net")
    gross = _stats(res, "gross")
    alpha = _nw_alpha(res, ref) if res is not ref else {
        "alpha_ann": np.nan, "t_alpha": np.nan, "beta_ref": np.nan}
    row = {
        "ladder": kind, "rung": rung, "step": label, "owner": owner,
        "component": comp_key, "components": "|".join(keys) or "(none)",
        "gross_sharpe": gross["sharpe"], "net_sharpe": net["sharpe"],
        "ann_return_net": net["ann_return"], "ann_vol_net": net["ann_vol"],
        "max_drawdown": net["max_drawdown"], "CVaR_99": net["CVaR_99"],
        "skew": net["skew"], "calmar": net["calmar"], "sortino": net["sortino"],
        "turnover": float(res.turnover), "cost_drag": float(res.cost_drag),
        "n_days": net["n_days"],
        "alpha_vs_prev_ann": alpha["alpha_ann"], "t_alpha_vs_prev": alpha["t_alpha"],
    }
    row.update(slot or {})
    row["slot_rule"] = (f"improve MaxDD or CVaR99 in >={SLOT_MIN_WINDOWS} of "
                        f"{len(SLOT_WINDOWS)} pre-2026 stress windows AND cost "
                        f"<{SLOT_SHARPE_BUDGET} net Sharpe AND survive LOO")
    return row


def combined_components(keys: list[str] | None = None) -> dict:
    """Config overrides for the frozen `COMBINED` preset.

    `strategy.config.combined_preset()` lazy-imports this. `keys` defaults to
    `ADOPTED` below, which is set from the ladder's verdict — so the preset is a
    record of what earned its slot, not a wish list.
    """
    cfg = _config_for(list(ADOPTED if keys is None else keys))
    cfg.pop("name", None)      # the preset supplies its own label
    return cfg


#: Components that earned a slot under the §19.4 rule. Set from the ladder.
#: An empty tuple means the honest answer was "none of them", in which case
#: `COMBINED` is the baseline and that null is the deliverable (plan §19.4).
ADOPTED: tuple[str, ...] = ("duration", "skew_excl")


def selection_vs_derisking() -> pd.DataFrame:
    """How much of a trimming overlay's tail gain is selection, and how much is
    just holding less?

    Three books at two risk levels: the baseline, the bad-skew exclusion, and a
    control with the exclusion's **exact daily gross** spread across all names.
    The baseline-to-control step is de-risking; the control-to-exclusion step is
    the signal. Reported because the honest answer changes the verdict.
    """
    base = run()
    skew = run(weight_overlay=skew_exclusion_overlay, name="ALL")
    ctrl = run(weight_overlay=gross_matched_control(skew_exclusion_overlay),
               name="ALL")
    rows = []
    for label, res, note in (
            ("baseline", base, "full risk, no filter"),
            ("gross-matched de-risk (control)", ctrl,
             "same daily gross as the filter, spread across every name"),
            ("bad-skew exclusion", skew, "the filter itself")):
        s = res.summary(benchmark=None).loc[f"{res.config.label()}_net"]
        rows.append({"book": label, "net_sharpe": float(s["sharpe"]),
                     "ann_vol": float(s["ann_vol"]),
                     "max_drawdown": float(s["max_drawdown"]),
                     "CVaR_99": float(s["CVaR_99"]), "skew": float(s["skew"]),
                     "turnover": float(res.turnover),
                     "cost_drag": float(res.cost_drag), "note": note})
    out = pd.DataFrame(rows)

    a = fx.nw_regression(skew.net.rename("y"),
                         ctrl.net.rename("control").to_frame(), lags=5)
    gross_err = float((skew.weights.abs().sum(axis=1)
                       - ctrl.weights.abs().sum(axis=1)).abs().max())
    out["alpha_selection_ann"] = a["alpha_ann"] if a else np.nan
    out["t_alpha_selection"] = a["alpha_t"] if a else np.nan
    out["gross_match_error"] = gross_err
    out.to_csv(OUTPUTS / "p4_selection_vs_derisking.csv", index=False)
    return out


def main() -> None:
    pd.set_option("display.width", 220)
    print("Duration-hedge cost check (the plan's 'essentially unpriced' claim):")
    for k, v in duration_drift_cost().items():
        print(f"  {k:22s} {v}")

    table, _ = standalone()
    print(f"\np4_component_standalone.csv     {len(table)} rows")
    cols = ["variant", "bar", "gross_sharpe", "net_sharpe", "d_net_sharpe_vs_bar",
            "max_drawdown", "CVaR_99", "turnover", "cost_drag",
            "alpha_ann", "t_alpha", "windows_improved"]
    print(table[cols].round(4).to_string(index=False))

    sel = selection_vs_derisking()
    print("\nSelection vs de-risking (p4_selection_vs_derisking.csv):")
    print(sel[["book", "net_sharpe", "ann_vol", "max_drawdown", "CVaR_99",
               "skew", "turnover"]].round(4).to_string(index=False))
    print(f"  NW alpha of selection over the gross-matched control: "
          f"{sel['alpha_selection_ann'].iloc[0]*100:+.3f}%/yr  "
          f"t {sel['t_alpha_selection'].iloc[0]:.2f}  "
          f"(gross match error {sel['gross_match_error'].iloc[0]:.1e})")

    lad, _ = ladder()
    print(f"\np4_combined_ladder.csv          {len(lad)} rows")
    lcols = ["ladder", "rung", "step", "net_sharpe", "ann_vol_net", "max_drawdown",
             "CVaR_99", "turnover", "alpha_vs_prev_ann", "t_alpha_vs_prev",
             "windows_improved", "d_net_sharpe", "slot_earned", "ladders_agree"]
    print(lad[lcols].round(4).to_string(index=False))


if __name__ == "__main__":
    main()
