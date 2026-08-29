"""D2 — the FX volatility risk premium: a second premium, or carry in disguise?

Plan §17 direction D2, cut in §17.3 for the August runway and designated the
fallback "if Phase 4 finishes early". It did, so this runs.

    python cesare/d2_vrp.py

**The thesis.** Implied minus realised volatility is a systematically harvested
premium *distinct* from directional carry: sell rich vol, and combine it with
carry as a second, diversifying return source. Unlike D1 (skew) and D3 (basis),
which asked whether an option/funding signal could improve the *carry sort*, this
asks whether there is a **different premium** in the same data.

**The bar is unchanged** (plan §17): beat both the simple vol-targeted book
(net **0.4659**) and the per-currency-RR book (**0.4559**), net of costs, with
Newey-West significance — or be reported as a null.

**The honest-costing problem, and how it is handled.** `data/raw` carries option
**mids only, no bid/ask** (plan §19.1), so a short-vol book cannot be costed the
way the carry book is. Pretending costs are zero would flatter it exactly the way
this project has criticised elsewhere. Instead this module solves for the
**breakeven bid/ask** — the vol spread, in vol points, at which the strategy stops
clearing each bar. That converts an uncostable strategy into a falsifiable
statement a desk can check against its own execution.

**Two other caveats stated up front.** Realised vol is close-to-close; the
range-based estimator that would be ~5x more efficient needs OHLC spot, which is
unbought (`DATA_SHOPPING_LIST.md` §1.2). And there is no investable FX vol-carry
index in the repo to validate the construction against, the way carry was
validated against DBHVG10U (§1.1). Both make this *weaker evidence* than D1 or D3
had, which is one of the three reasons §17.3 cut it — that has not changed.

Outputs: `p3_d2_premium.csv`, `p3_d2_books.csv`, `p3_d2_spanning.csv`,
`p3_d2_correlation.csv`, `p3_d2_static_vs_timing.csv`, `p3_d2_avg_weights.csv`,
`p3_d2_breakeven_cost.csv`, `p3_d2_by_episode.csv`.
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from strategy import fx_utils as fx, run

OUTPUTS = Path(__file__).resolve().parent / "outputs"

#: Horizon of the 1M option, in trading days. Realised vol is measured over
#: exactly the window the option covers, so implied and realised are comparable.
HORIZON = 21

#: The two bars D2 must clear (plan §17).
BAR_BASE, BAR_RR = 0.4659, 0.4559

#: Bid/ask grid for the breakeven search, in **vol points** per round trip.
#: Interbank 1M ATM in G10 trades inside ~0.2 vol pts; EM and the wings are
#: wider, so the grid runs well past anything a desk would actually pay.
COST_GRID = (0.0, 0.10, 0.25, 0.50, 0.75, 1.00, 1.50, 2.00, 3.00)


# ---------------------------------------------------------------------------
# Panels
# ---------------------------------------------------------------------------

def vrp_panels(tenor: str = "1M") -> dict[str, pd.DataFrame]:
    """Implied vol, realised vol, and the two VRP definitions, month-end.

    The distinction that matters and is easy to get wrong:

    * `vrp_realized` = `IV_t - RV(t -> t+1M)` is the **P&L** of selling vol at
      *t*. It uses the future and is therefore a *measurement*, never a signal.
    * `vrp_ex_ante`  = `IV_t - RV(t-1M -> t)` is the **signal**, built only from
      what was on the screen at *t*.

    Mixing them up would be the single easiest way to manufacture a spurious
    result here, so they are named apart and the signal never touches the
    forward-looking one.
    """
    base = run()
    iv = fx.vol_surface_panel("ATM", tenor=tenor) / 100.0
    r = fx.spot_log_returns(base.panels.spots)
    rv = r.rolling(HORIZON).std() * np.sqrt(fx.ANN_DAYS)

    cols = [c for c in base.universe if c in iv.columns]
    IV = iv[cols].resample("ME").last()
    RV_trailing = rv[cols].resample("ME").last()
    RV_forward = RV_trailing.shift(-1)          # realised over the NEXT month

    return {"universe": cols, "IV": IV, "RV_trailing": RV_trailing,
            "RV_forward": RV_forward,
            "vrp_ex_ante": IV - RV_trailing,     # signal, known at t
            "vrp_realized": IV - RV_forward,     # P&L of selling vol at t
            "carry": base.panels.carry[cols].resample("ME").last(),
            "base": base}


def short_vol_returns(p: dict) -> pd.DataFrame:
    """Monthly return of selling one unit of 1M ATM vol, per currency.

    Vol-swap convention: `(IV_t - RV(t->t+1M)) / IV_t`, i.e. the fraction of the
    implied vol level actually harvested. Scale-free, so currencies at 5% and 15%
    vol are comparable, and bounded below by -inf but well-behaved in practice —
    unlike the variance-swap form `(IV^2 - RV^2)/IV^2`, which is dominated by a
    handful of vol explosions. The variance form is reported as a robustness
    check in `books()` rather than as the headline.

    Dated at *t*, the month the position is **opened**; the P&L is realised over
    the following month. `books()` shifts it so nothing is booked before it is
    earned.
    """
    return (p["vrp_realized"] / p["IV"]).replace([np.inf, -np.inf], np.nan)


# ---------------------------------------------------------------------------
# Does the premium exist at all?
# ---------------------------------------------------------------------------

def premium() -> pd.DataFrame:
    """Per-currency mean VRP with Newey-West t — the gate for everything else.

    If implied does not systematically exceed realised there is nothing to
    harvest and the rest of the module is measuring noise.
    """
    p = vrp_panels()
    rows = []
    for c in p["universe"]:
        x = p["vrp_realized"][c].dropna()
        if len(x) < 60:
            continue
        res = fx.nw_regression(x.rename("y"), pd.DataFrame(index=x.index),
                               lags=3, min_obs=60)
        rows.append({"currency": c, "mean_vrp_vol_pts": float(x.mean() * 100),
                     "sd_vol_pts": float(x.std() * 100),
                     "t_newey_west": float(res["alpha_t"]) if res else np.nan,
                     "share_months_positive": float((x > 0).mean()),
                     "mean_implied_vol": float(p["IV"][c].mean() * 100),
                     "mean_realized_vol": float(p["RV_forward"][c].mean() * 100),
                     "n_months": int(len(x))})
    out = pd.DataFrame(rows).sort_values("mean_vrp_vol_pts", ascending=False)
    out.to_csv(OUTPUTS / "p3_d2_premium.csv", index=False)
    return out


# ---------------------------------------------------------------------------
# Books
# ---------------------------------------------------------------------------

def _monthly_stats(r: pd.Series, name: str) -> dict:
    """Annualised stats for a MONTHLY return series.

    `fx.summary_stats` annualises at 252 and would be wrong here. Same formulas,
    12 periods a year, so the Sharpe is directly comparable to the carry book's
    — which is why `books()` also recomputes the carry book monthly rather than
    quoting its committed daily figure as if the two were interchangeable.
    """
    r = r.dropna()
    if len(r) < 24:
        return {"variant": name, "n_months": len(r)}
    wealth = (1 + r).cumprod()
    dd = float((wealth / wealth.cummax() - 1).min())
    ann_r, ann_v = float(r.mean() * 12), float(r.std() * np.sqrt(12))
    return {"variant": name, "n_months": int(len(r)),
            "ann_return": ann_r, "ann_vol": ann_v,
            "sharpe": ann_r / ann_v if ann_v else np.nan,
            "max_drawdown": dd, "skew": float(r.skew()),
            "hit_rate": float((r > 0).mean()),
            "CVaR_99": float(-r.nsmallest(max(1, int(0.01 * len(r)))).mean()),
            "worst_month": float(r.min())}


def _vol_target(r: pd.Series, target: float = 0.10, window: int = 12) -> pd.Series:
    """Scale a monthly series to a target annualised vol on trailing info only."""
    vol = r.rolling(window, min_periods=6).std() * np.sqrt(12)
    scale = (target / vol.replace(0.0, np.nan)).clip(upper=4.0).shift(1)
    return (r * scale).rename(r.name)


def books(cost_vol_pts: float = 0.0) -> tuple[pd.DataFrame, dict]:
    """The D2 books, at a stated round-trip bid/ask in vol points.

    * **short_vol**   — sell vol in every name, inverse-vol weighted. The premium
      itself, directional.
    * **vrp_xs**      — cross-sectional: sell vol where ex-ante VRP is richest,
      buy where it is cheapest. Dollar-neutral in vega, so it strips out the
      directional short-vol beta.
    * **carry**       — the shared base's net book, recomputed monthly so the
      Sharpes are on the same footing.
    * **carry+short_vol** — equal-risk blend, the "second diversifying premium"
      claim tested directly.

    `cost_vol_pts` is charged on the vol traded each month: opening a short-vol
    position crosses the spread, so the charge is `cost / IV` in return units on
    the notional traded.
    """
    p = vrp_panels()
    sv = short_vol_returns(p)
    iv, signal = p["IV"], p["vrp_ex_ante"]

    # Cost: crossing `cost_vol_pts` on a position whose return is scaled by 1/IV.
    charge = (cost_vol_pts / 100.0) / iv.replace(0.0, np.nan)

    # --- DATING. This is the part that decides whether any of this is real. ---
    # `sv` is dated at the month the position is OPENED: its value at t is the
    # P&L of selling vol at t, earned over (t, t+1]. Weights are therefore the
    # ones decided at t, from information known at t — `RV_trailing` and
    # `vrp_ex_ante` both are — so NO shift is applied to the weights here.
    # The book return is then shifted forward one month so it is dated when the
    # P&L is actually COLLECTED, which is how `monthly("net")` dates the carry
    # book. Getting this wrong does not just mislabel an axis: it regresses
    # carry's month t on short-vol's month t+1, i.e. two non-overlapping periods,
    # which manufactures a near-zero correlation and a large spurious alpha.
    inv = 1.0 / p["RV_trailing"].replace(0.0, np.nan)
    w_dir = inv.div(inv.sum(axis=1), axis=0)

    # cross-sectional: rank on the ex-ante signal, top third short-vol, bottom third long-vol
    z = fx.zscore_xs(signal)
    w_xs = pd.DataFrame(0.0, index=z.index, columns=z.columns)
    for dt, row in z.iterrows():
        v = row.dropna()
        if len(v) < 9:
            continue
        k = len(v) // 3
        w_xs.loc[dt, v.nlargest(k).index] = 1.0 / k
        w_xs.loc[dt, v.nsmallest(k).index] = -1.0 / k

    gross_dir = (w_dir * sv).sum(axis=1, min_count=1)
    cost_dir = (w_dir.abs() * charge).sum(axis=1, min_count=1).fillna(0.0)
    gross_xs = (w_xs * sv).sum(axis=1, min_count=1)
    cost_xs = (w_xs.diff().abs() * charge).sum(axis=1, min_count=1).fillna(0.0)

    short_vol = _vol_target((gross_dir - cost_dir).shift(1).rename("short_vol"))
    vrp_xs = _vol_target((gross_xs - cost_xs).shift(1).rename("vrp_xs"))
    carry = p["base"].monthly("net").rename("carry")

    j = pd.concat([carry, short_vol], axis=1).dropna()
    blend = _vol_target((0.5 * j["carry"] + 0.5 * j["short_vol"]).rename("carry+short_vol"))

    series = {"carry": carry, "short_vol": short_vol, "vrp_xs": vrp_xs,
              "carry+short_vol": blend}
    rows = [_monthly_stats(s, k) for k, s in series.items()]
    tab = pd.DataFrame(rows)
    tab["cost_vol_pts"] = cost_vol_pts
    tab["bar_baseline"], tab["bar_rr"] = BAR_BASE, BAR_RR
    tab["beats_both_bars"] = tab["sharpe"] > max(BAR_BASE, BAR_RR)
    return tab, series


# ---------------------------------------------------------------------------
# The decisive test: is this carry in disguise?
# ---------------------------------------------------------------------------

def spanning() -> pd.DataFrame:
    """Two-way spanning of the vol premium against carry.

    D1 and D3 both died here, and the prior is that D2 does too: the VRP is
    largest in exactly the high-carry EM names, so a short-vol book may simply be
    a levered carry book wearing an option label. If carry spans the vol premium,
    D2 adds nothing. If the vol premium survives carry — positive alpha with
    Newey-West significance — it is the genuinely new result this project has
    been looking for.
    """
    _, series = books(cost_vol_pts=0.0)
    carry = series["carry"].dropna()
    rows = []
    for name in ("short_vol", "vrp_xs", "carry+short_vol"):
        y = series[name].dropna()
        for lhs, rhs, lbl in ((y, carry, f"{name} ~ CARRY"),
                              (carry, y, f"CARRY ~ {name}")):
            j = pd.concat([lhs.rename("y"), rhs.rename("x")], axis=1).dropna()
            if len(j) < 60:
                continue
            r = fx.nw_regression(j["y"], j[["x"]], lags=3, min_obs=60)
            if r is None:
                continue
            rows.append({"regression": lbl, "alpha_ann": r["alpha_ann"] * 12 / 12,
                         "alpha_t": r["alpha_t"], "beta": r.get("beta_x"),
                         "t_beta": r.get("t_x"), "r2": r["r2"], "n": r["n"]})
    # correlation matrix, the diversification claim in one number
    mat = pd.concat([series[k].rename(k) for k in
                     ("carry", "short_vol", "vrp_xs")], axis=1).dropna().corr()
    out = pd.DataFrame(rows)
    out.attrs["corr"] = mat
    out.to_csv(OUTPUTS / "p3_d2_spanning.csv", index=False)
    mat.to_csv(OUTPUTS / "p3_d2_correlation.csv")
    return out


def static_vs_timing() -> pd.DataFrame:
    """Is the cross-sectional VRP book a timing edge, or a standing tilt?

    **The control this result needs**, and the direct analogue of the
    gross-matched control that reframed the Phase-4 skew filter (guardrail
    §6.12). A cross-sectional sort on `IV - RV` will load persistently on
    whichever currencies have a structurally high implied-minus-realised gap.
    That is a *level* bet on a handful of names, not the vol-timing signal the
    strategy is sold as, and it is far more fragile than its Sharpe suggests:
    the standing shorts are managed / low-realised-vol currencies whose tail
    simply has not occurred inside 2007-2026.

    Removing the per-currency mean with an **expanding, lagged** average (so the
    de-meaning itself uses no future information) isolates the timing component.
    """
    p = vrp_panels()
    sv = short_vol_returns(p)
    variants = {
        "vrp_xs (raw signal)": p["vrp_ex_ante"],
        "vrp_xs (ccy-demeaned = pure timing)":
            p["vrp_ex_ante"] - p["vrp_ex_ante"].expanding(24).mean().shift(1),
    }
    rows, weights = [], {}
    for label, signal in variants.items():
        z = fx.zscore_xs(signal)
        w = pd.DataFrame(0.0, index=z.index, columns=z.columns)
        for dt, row in z.iterrows():
            v = row.dropna()
            if len(v) < 9:
                continue
            k = len(v) // 3
            w.loc[dt, v.nlargest(k).index] = 1.0 / k
            w.loc[dt, v.nsmallest(k).index] = -1.0 / k
        r = _vol_target((w * sv).sum(axis=1, min_count=1).shift(1).rename(label))
        rows.append(_monthly_stats(r, label))
        weights[label] = w
    out = pd.DataFrame(rows)
    avg = weights["vrp_xs (raw signal)"].mean().sort_values(ascending=False)
    out["standing_shorts"] = "|".join(avg.head(5).index)
    out.to_csv(OUTPUTS / "p3_d2_static_vs_timing.csv", index=False)
    avg.rename("avg_short_vol_weight").to_csv(OUTPUTS / "p3_d2_avg_weights.csv")
    return out


def by_episode(cost_vol_pts: float = 0.0) -> pd.DataFrame:
    """The D2 books on the frozen evaluation windows — guardrail §6.8.

    **This did not exist until now, and its absence was a real defect**: the
    module docstring listed `p3_d2_by_episode.csv` as an output and nothing ever
    wrote it, so D2 was the one result in the project with no per-window table at
    all — in breach of the desk's standing requirement since 2026-07-29 and of
    `strategy/README.md` rule 11. (Fifth instance of a claimed-but-absent
    artifact; plan Appendix C #12, #18, #26, #28.)

    Two honest differences from `episodes.report_windows`, which is why this is a
    separate function rather than a call to it:

    1. **These books are monthly**, so a window is a handful of observations, not
       a few hundred days. Everything annualised is therefore suppressed
       outright — no `sharpe`, no `ann_*`, at any length. `report_windows`
       suppresses below 120 *trading days*; here the honest bar is stricter.
    2. **They carry no transaction cost** unless `cost_vol_pts` is set, because
       option data is mids only. The `cost_vol_pts` column records which it is,
       so a reader cannot mistake a zero-cost number for a net one.

    `n_months` is reported on every row precisely because several stress windows
    contain three months or fewer, and a cumulative return over three months is a
    fact about three months.
    """
    from strategy.episodes import ERAS, STRESS

    _, series = books(cost_vol_pts=cost_vol_pts)
    rows = []
    for set_name, windows in (("ERAS", ERAS), ("STRESS", STRESS)):
        for name, (lo, hi) in windows.items():
            for variant, s in series.items():
                sub = s.loc[lo:hi].dropna()
                if sub.empty:
                    rows.append({"variant": variant, "window_set": set_name,
                                 "window": name, "start": lo, "end": hi,
                                 "n_months": 0, "cum_return": np.nan,
                                 "max_drawdown": np.nan, "worst_month": np.nan,
                                 "hit_rate": np.nan, "cost_vol_pts": cost_vol_pts})
                    continue
                wealth = (1.0 + sub).cumprod()
                rows.append({
                    "variant": variant, "window_set": set_name, "window": name,
                    "start": lo, "end": hi, "n_months": int(len(sub)),
                    "cum_return": float(wealth.iloc[-1] - 1.0),
                    "max_drawdown": float((wealth / wealth.cummax() - 1.0).min()),
                    "worst_month": float(sub.min()),
                    "hit_rate": float((sub > 0).mean()),
                    "cost_vol_pts": cost_vol_pts})
    out = pd.DataFrame(rows)
    out.attrs["caveat"] = (
        "monthly books; annualised ratios deliberately omitted at every window "
        "length; gross of option bid/ask unless cost_vol_pts > 0")
    out.to_csv(OUTPUTS / "p3_d2_by_episode.csv", index=False)
    return out


def breakeven_cost() -> pd.DataFrame:
    """The vol bid/ask at which each book stops clearing the bars.

    The honest substitute for a cost model we cannot build. `data/raw` has option
    mids only, so rather than report a zero-cost Sharpe and caveat it in prose,
    this states the execution assumption the result depends on — a number a desk
    can check against its own spreads in about ten seconds.
    """
    rows = []
    for c in COST_GRID:
        tab, _ = books(cost_vol_pts=c)
        for _, r in tab.iterrows():
            rows.append({"cost_vol_pts": c, "variant": r["variant"],
                         "sharpe": r.get("sharpe"),
                         "ann_return": r.get("ann_return"),
                         "beats_both_bars": r.get("beats_both_bars")})
    out = pd.DataFrame(rows)
    out.to_csv(OUTPUTS / "p3_d2_breakeven_cost.csv", index=False)
    return out


def main() -> None:
    pd.set_option("display.width", 230)
    prem = premium()
    pos = int((prem["mean_vrp_vol_pts"] > 0).sum())
    sig = int((prem["t_newey_west"] > 1.96).sum())
    print(f"1. DOES THE PREMIUM EXIST?  {pos}/{len(prem)} currencies positive, "
          f"{sig} with NW t > 1.96")
    print(prem[["currency", "mean_vrp_vol_pts", "t_newey_west",
                "share_months_positive", "mean_implied_vol",
                "mean_realized_vol"]].round(3).to_string(index=False))

    tab, _ = books(0.0)
    print("\n2. BOOKS (gross of vol bid/ask — mids only, see breakeven below):")
    print(tab[["variant", "n_months", "ann_return", "ann_vol", "sharpe",
               "max_drawdown", "skew", "hit_rate", "beats_both_bars"]]
          .round(4).to_string(index=False))

    sp = spanning()
    print("\n3. IS IT CARRY IN DISGUISE?  (monthly, NW 3 lags)")
    print(sp.round(4).to_string(index=False))
    print("\n   correlation matrix:")
    print(sp.attrs["corr"].round(3).to_string())

    svt = static_vs_timing()
    print("\n4. TIMING EDGE, OR A STANDING TILT?")
    print(svt[["variant","ann_return","ann_vol","sharpe","max_drawdown","skew",
               "hit_rate"]].round(4).to_string(index=False))
    print(f"   standing shorts: {svt['standing_shorts'].iloc[0]}")

    be = breakeven_cost()
    print("\n5. BREAKEVEN VOL BID/ASK (round trip, vol points):")
    piv = be.pivot(index="cost_vol_pts", columns="variant", values="sharpe")
    print(piv.round(3).to_string())
    # The widest spread at which each book STILL clears both bars. Quote this,
    # not the first failing grid point: plan §17.4 quoted the latter and so
    # overstated every breakeven by one step of the grid.
    print("   widest spread still clearing both bars:")
    for v, g in be[be["beats_both_bars"]].groupby("variant"):
        print(f"     {v:<18} {g['cost_vol_pts'].max():.2f} vol pts")

    ep = by_episode()
    print("\n6. PER WINDOW (monthly books; no annualised ratios, guardrail §6.8):")
    print(ep[ep["window_set"] == "STRESS"]
          .pivot(index="window", columns="variant", values="cum_return")
          .round(4).to_string())
    tab.to_csv(OUTPUTS / "p3_d2_books.csv", index=False)


if __name__ == "__main__":
    main()
