"""P4-B — forecasting the tail, and whether it beats a single VIX threshold.

Plan §19.3, the desk's central ask (2026-07-29): *forecast tail events and bake
the signal into the strategy*. Target the loss, not the return — one crash breaks
the compounding path, so minimising large losses is worth more than adding
incremental gains.

    python cesare/tail_forecast.py

**This is framed as a falsification exercise, and the framing is pre-registered
rather than applied afterwards.** Sixteen features against ~230 monthly
observations, competing with one VIX percentile threshold that is already in the
repo and already works. (§19.3 calls it "twelve features"; its own bulleted list
enumerates sixteen once the levels-and-changes are counted separately. The list
is implemented as written — the count in the prose was wrong, which if anything
sharpens the point about complexity.) The honest prior, given that Stages 3 and 6 both found
that de-risking on risk indicators sells premium roughly one-for-one, is that the
learned forecast loses. **If it loses, that is the finding: it is reported and
the model is not iterated to make it win.**

Three bars, fixed in §19.3 before any of this was written:

1. the baseline (**net 0.4659**) and the per-currency-RR book (**0.4559**
   rebuilt on this base);
2. the **dumb incumbent** — Dafu's VIX percentile gate, net **0.46527**,
   MaxDD **−24.50%**, Calmar **0.1815**. A learned forecast on sixteen features
   that cannot beat one threshold has not earned its complexity;
3. the desk's alternative route: a material MaxDD / CVaR99 improvement at
   ≤ 0.02 net Sharpe cost, **demonstrated per episode**, not whole-sample.

Outputs: `p4_tail_forecast_eval.csv`, `p4_tail_overlay_stats.csv`,
`p4_tail_overlay_by_episode.csv`.
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from sklearn.linear_model import LogisticRegression
from sklearn.metrics import roc_auc_score
from sklearn.preprocessing import StandardScaler

from strategy import fx_utils as fx, run
from strategy.episodes import ERAS, STRESS, report_windows

OUTPUTS = Path(__file__).resolve().parent / "outputs"

# --- §13 purged walk-forward spec, inherited verbatim ----------------------
MIN_TRAIN, TEST_SIZE, EMBARGO = 60, 12, 1

#: Worst-decile definition of a "tail month". Computed on the TRAINING fold only.
TAIL_Q = 0.10

#: L2 strength. One value, not a grid: tuning C on ~230 observations against a
#: one-parameter incumbent would be exactly the complexity this test is meant to
#: price. Stated before the run.
L2_C = 1.0

#: How a forecast becomes an exposure. Deliberately the SAME ACTION as the
#: incumbent — half risk when the signal is in the top fifth — so the comparison
#: is signal-vs-signal rather than mapping-vs-mapping. The threshold is the
#: training folds' own p80 of predicted probability, never the full sample's.
GATE_Q, GATE_LOW = 0.80, 0.5

#: The pre-registered bars (plan §19.3).
BARS = {"baseline": 0.4659, "per-currency RR": 0.4559,
        "VIX percentile gate (incumbent)": 0.46527}
INCUMBENT = {"net_sharpe": 0.46527, "max_drawdown": -0.24503, "calmar": 0.18150}


# ---------------------------------------------------------------------------
# The CV scheme §13 specified and nobody had built
# ---------------------------------------------------------------------------

def purged_walkforward(index, min_train: int = MIN_TRAIN,
                       test_size: int = TEST_SIZE, embargo: int = EMBARGO):
    """Expanding-window walk-forward with a purge gap (López de Prado, 2018).

    Yields `(train_positions, test_positions)`. The training block **stops
    `embargo` observations before** the test block starts, which is the whole
    point: the target at month *t* is the return realised over month *t+1*, so a
    training row immediately adjacent to the test block shares an outcome period
    with it and leaks. Never shuffled k-fold — the observations are a time
    series and shuffling would let the model train on the future.

    Specified in plan §13 and inherited by P4-B verbatim. It did not exist
    anywhere in the repo before this module, despite being cited — the same
    pattern as Appendix C #18.
    """
    n = len(index)
    start = min_train
    while start < n:
        stop = min(start + test_size, n)
        train_end = start - embargo
        if train_end >= min_train:
            yield np.arange(0, train_end), np.arange(start, stop)
        start = stop


# ---------------------------------------------------------------------------
# Features — all known at month-end t, predicting t+1 (guardrail §6.1)
# ---------------------------------------------------------------------------

def _me(frame):
    """Month-end sample. `ME` only — guardrail §6.10: left-labelled aliases leak."""
    return frame.resample("ME").last()


def feature_panel(result=None) -> pd.DataFrame:
    """The §19.3 feature list, monthly, trailing-only (sixteen columns).

    Every column is a level or a change observable at the month-end close. No
    macro releases (vintage/revision problems at this frequency, plan §8).
    """
    result = run() if result is None else result
    gr, mp = fx.load_wide("global_risk"), fx.load_wide("macro_market_proxies")
    embi = fx.load_em_risk()
    rr = fx.vol_surface_panel("RR", "1M").mean(axis=1)     # XS mean 25d RR

    vix, move = _me(gr["VIX"]), _me(gr["MOVE"])
    g7, em = _me(gr["JPMVXYG7"]), _me(gr["JPMVXYEM"])
    dxy, u2, curve = _me(gr["DXY"]), _me(gr["USGG2YR"]), _me(gr["USYC2Y10"])
    fci = _me(mp["BFCIUS"])
    embi_m, rr_m = _me(embi), _me(rr)

    daily_net = result.net
    book_vol = _me(daily_net.rolling(60, min_periods=30).std() * np.sqrt(fx.ANN_DAYS))
    book_ret = result.monthly("net")
    dispersion = _me(result.signal.std(axis=1))

    X = pd.DataFrame({
        "vix": vix, "d_vix": vix.diff(),
        "move": move,
        "jpmvxy_g7": g7, "jpmvxy_em": em, "d_jpmvxy_em": em.diff(),
        "rr_xs_mean": rr_m,
        "embi": embi_m, "d_embi": embi_m.diff(),
        "dxy_3m": np.log(dxy) - np.log(dxy.shift(3)),
        "d_ust2y": u2.diff(), "curve_2s10s": curve,
        "bfcius": fci,
        "book_vol_60d": book_vol, "carry_dispersion": dispersion,
        "book_ret_trailing": book_ret,
    })
    return X.dropna(how="all")


def build_dataset(result=None) -> tuple[pd.DataFrame, pd.Series]:
    """Features at *t*, next month's book return as the outcome at *t*.

    The shift is the no-lookahead contract: row *t* pairs what was on the screen
    at the month-end close with the return that followed it.
    """
    result = run() if result is None else result
    X = feature_panel(result)
    y_next = result.monthly("net").shift(-1)
    data = X.join(y_next.rename("y_next"), how="inner").dropna()
    return data.drop(columns="y_next"), data["y_next"]


# ---------------------------------------------------------------------------
# Estimation
# ---------------------------------------------------------------------------

def walk_forward(X: pd.DataFrame, y: pd.Series) -> tuple[pd.DataFrame, pd.Series,
                                                         pd.DataFrame]:
    """Strictly out-of-sample P(tail) under the purged scheme.

    Everything that could leak is fit inside the fold: the tail threshold is the
    *training* returns' 10th percentile, the scaler's mean and variance come from
    training rows only, and the embargo drops the adjacent observation.
    """
    folds, probs, coefs = [], {}, []
    for k, (tr, te) in enumerate(purged_walkforward(X.index)):
        Xtr, Xte = X.iloc[tr], X.iloc[te]
        ytr, yte = y.iloc[tr], y.iloc[te]

        cut = float(ytr.quantile(TAIL_Q))          # train-only threshold
        ltr, lte = (ytr <= cut).astype(int), (yte <= cut).astype(int)
        if ltr.nunique() < 2:
            continue

        scaler = StandardScaler().fit(Xtr)
        model = LogisticRegression(penalty="l2", C=L2_C, max_iter=2000,
                                   class_weight="balanced")
        model.fit(scaler.transform(Xtr), ltr)
        p = model.predict_proba(scaler.transform(Xte))[:, 1]
        probs.update(dict(zip(Xte.index, p)))

        auc = (roc_auc_score(lte, p) if lte.nunique() > 1 else np.nan)
        folds.append({"fold": k, "train_n": len(tr), "test_n": len(te),
                      "test_start": str(Xte.index[0].date()),
                      "test_end": str(Xte.index[-1].date()),
                      "tail_cut": cut, "n_tail_in_test": int(lte.sum()),
                      "auc": auc,
                      "hit_rate": float(((p > 0.5).astype(int) == lte).mean()),
                      "mean_prob": float(p.mean())})
        coefs.append(pd.Series(model.coef_[0], index=X.columns, name=k))

    return (pd.DataFrame(folds), pd.Series(probs).sort_index().rename("p_tail"),
            pd.DataFrame(coefs))


def probability_to_exposure(p: pd.Series, q: float = GATE_Q,
                            low: float = GATE_LOW) -> pd.Series:
    """P(tail) -> exposure, with the same shape as the incumbent it must beat.

    Half risk when the forecast is in the top fifth of its own **expanding**
    history, so the threshold at month *t* uses only probabilities produced
    before *t*. A full-sample quantile here would be a lookahead of exactly the
    kind this module exists to avoid, and it would flatter the model against an
    incumbent that has no such advantage.
    """
    cut = p.expanding(min_periods=24).quantile(q).shift(1)
    return pd.Series(np.where(p > cut, low, 1.0), index=p.index,
                     name="tail_gate").astype("float64")


# ---------------------------------------------------------------------------
# Evaluation against the three pre-registered bars
# ---------------------------------------------------------------------------

def _stats(res) -> dict:
    s = res.summary(benchmark=None)
    net = s.loc[[i for i in s.index if i.endswith("_net")][0]]
    gross = s.loc[[i for i in s.index if i.endswith("_gross")][0]]
    return {"gross_sharpe": float(gross["sharpe"]), "net_sharpe": float(net["sharpe"]),
            "ann_return": float(net["ann_return"]), "ann_vol": float(net["ann_vol"]),
            "max_drawdown": float(net["max_drawdown"]),
            "CVaR_99": float(net["CVaR_99"]), "skew": float(net["skew"]),
            "calmar": float(net["calmar"]), "sortino": float(net["sortino"]),
            "turnover": float(res.turnover), "cost_drag": float(res.cost_drag),
            "n_days": int(net["n_days"])}


def evaluate() -> dict:
    """Run the whole thing and verdict it against all three bars."""
    base = run()
    X, y = build_dataset(base)
    folds, p_tail, coefs = walk_forward(X, y)

    gate = probability_to_exposure(p_tail)
    # The continuous mapping is reported BESIDE the pre-registered binary one as
    # the spread across the mapping choice (README rule 7), not as a second bite.
    cont = (1.0 - p_tail).clip(0.0, 1.0).rename("tail_gate_continuous")

    vix_gate = fx.exposure_scalar(fx.load_wide("global_risk")["VIX"],
                                  lookback=756, q=0.80, low_mult=0.5)
    variants = {
        "baseline": base,
        "VIX percentile gate (incumbent)": run(exposure=vix_gate, name="ALL"),
        "tail forecast (binary p80 gate)": run(exposure=gate, name="ALL"),
        "tail forecast (continuous 1-p)": run(exposure=cont, name="ALL"),
    }

    rows, episodes = [], []
    base_stats = _stats(base)
    for label, res in variants.items():
        st = _stats(res)
        # Regressing the baseline on itself would report a meaningless t of 6+.
        alpha = (None if res is base else
                 fx.nw_regression(res.net.rename("y"),
                                  base.net.rename("base").to_frame(), lags=5))
        rows.append({
            "variant": label, **st,
            "d_net_sharpe_vs_baseline": st["net_sharpe"] - base_stats["net_sharpe"],
            "d_maxdd_pp_vs_baseline":
                (st["max_drawdown"] - base_stats["max_drawdown"]) * 100,
            "d_net_sharpe_vs_incumbent": st["net_sharpe"] - INCUMBENT["net_sharpe"],
            "d_maxdd_pp_vs_incumbent":
                (st["max_drawdown"] - INCUMBENT["max_drawdown"]) * 100,
            "d_calmar_vs_incumbent": st["calmar"] - INCUMBENT["calmar"],
            "alpha_vs_baseline_ann": alpha["alpha_ann"] if alpha else np.nan,
            "t_alpha_vs_baseline": alpha["alpha_t"] if alpha else np.nan,
            **{f"bar_{k}": v for k, v in BARS.items()},
            **{f"cfg_{k}": v for k, v in res.config.describe().items()},
        })
        for tag, windows in (("ERAS", ERAS), ("STRESS", STRESS)):
            rep = report_windows(res, windows, which="both")
            rep.insert(0, "variant", label)
            rep.insert(1, "window_set", tag)
            episodes.extend(rep.to_dict("records"))

    stats = pd.DataFrame(rows)
    by_ep = pd.DataFrame(episodes)

    # Feature importances, with the stability caveat carried in the table itself
    # rather than in prose nobody reads next to the number.
    imp = pd.DataFrame({
        "feature": coefs.columns,
        "mean_coef": coefs.mean().values,
        "std_coef": coefs.std().values,
        "sign_stability": (np.sign(coefs).mean().abs()).values,
        "n_folds": len(coefs),
    }).sort_values("mean_coef", key=abs, ascending=False)
    imp["caveat"] = ("standardised L2 coefficients across purged folds; with "
                     f"{len(coefs)} folds and {len(X.columns)} correlated risk "
                     "features these are NOT stable and must not be read as an "
                     "economic ranking — sign_stability is |mean sign|, 1.0 = "
                     "never flips")

    folds.to_csv(OUTPUTS / "p4_tail_forecast_eval.csv", index=False)
    imp.to_csv(OUTPUTS / "p4_tail_feature_importance.csv", index=False)
    stats.to_csv(OUTPUTS / "p4_tail_overlay_stats.csv", index=False)
    by_ep.to_csv(OUTPUTS / "p4_tail_overlay_by_episode.csv", index=False)
    return {"folds": folds, "importance": imp, "stats": stats,
            "by_episode": by_ep, "p_tail": p_tail, "X": X}


def verdict(stats: pd.DataFrame, folds: pd.DataFrame) -> str:
    """The adopt/reject call against all three bars, mechanically."""
    row = stats.set_index("variant").loc["tail forecast (binary p80 gate)"]
    auc = float(folds["auc"].mean())
    beats_simple = row["net_sharpe"] > max(BARS["baseline"], BARS["per-currency RR"])
    beats_incumbent = (row["net_sharpe"] > INCUMBENT["net_sharpe"]
                       and row["max_drawdown"] > INCUMBENT["max_drawdown"])
    tail_route = (row["d_net_sharpe_vs_baseline"] >= -0.02
                  and row["d_maxdd_pp_vs_baseline"] >= 1.0)
    empty = int((folds["n_tail_in_test"] == 0).sum())
    lines = [
        f"folds with NO tail month in the test block   : {empty} of {len(folds)} "
        f"(AUC undefined there — a real small-sample limit, not a bug)",
        f"mean OOS AUC across {len(folds)} purged folds : {auc:.4f} "
        f"({'no better than a coin' if abs(auc - 0.5) < 0.05 else 'some signal'})",
        f"bar 1 — beats 0.4659 / 0.4559 net Sharpe      : "
        f"{'YES' if beats_simple else 'NO'} ({row['net_sharpe']:.4f})",
        f"bar 2 — beats the VIX gate on Sharpe AND MaxDD: "
        f"{'YES' if beats_incumbent else 'NO'} "
        f"(dSharpe {row['d_net_sharpe_vs_incumbent']:+.4f}, "
        f"dMaxDD {row['d_maxdd_pp_vs_incumbent']:+.2f}pp)",
        f"bar 3 — tail route (<=0.02 Sharpe, >=1pp MaxDD): "
        f"{'YES' if tail_route else 'NO'} "
        f"(dSharpe {row['d_net_sharpe_vs_baseline']:+.4f}, "
        f"dMaxDD {row['d_maxdd_pp_vs_baseline']:+.2f}pp)",
    ]
    passed = beats_simple or beats_incumbent or tail_route
    lines.append("")
    lines.append("VERDICT: " + (
        "the tail forecast clears at least one pre-registered bar — re-run the "
        "§19.4 ladder with it added."
        if passed else
        "REJECT — null. Sixteen features on ~230 monthly observations do not beat "
        "one VIX threshold. Per plan §19.3 this is reported as the finding and "
        "the model is NOT iterated to make it win."))
    return "\n".join(lines)


def main() -> None:
    pd.set_option("display.width", 220)
    out = evaluate()
    print(f"Purged walk-forward: {len(out['folds'])} folds, "
          f"{len(out['X'])} monthly observations, {out['X'].shape[1]} features "
          f"(min_train={MIN_TRAIN}, test_size={TEST_SIZE}, embargo={EMBARGO})\n")
    print(out["folds"][["fold", "train_n", "test_n", "test_start", "test_end",
                        "n_tail_in_test", "auc", "hit_rate"]].round(4).to_string(index=False))
    print("\nOverlay vs the three pre-registered bars:")
    cols = ["variant", "gross_sharpe", "net_sharpe", "max_drawdown", "CVaR_99",
            "calmar", "turnover", "alpha_vs_baseline_ann", "t_alpha_vs_baseline"]
    print(out["stats"][cols].round(4).to_string(index=False))
    print("\nFeature importance (see the caveat column):")
    print(out["importance"][["feature", "mean_coef", "std_coef",
                             "sign_stability"]].round(4).to_string(index=False))
    print("\n" + verdict(out["stats"], out["folds"]))


if __name__ == "__main__":
    main()
