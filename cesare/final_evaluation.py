"""Phase-4 reporting tables — the W1 (P4-A) deliverables.

Everything here writes to `cesare/outputs/`. It is a module rather than notebook
cells because these tables are **living artifacts**: §14.2 stands them up in W1
and refreshes them every week through the Aug 31 hand-in, so a weekly refresh
should be one function call, not a re-execute-all. `cesare/final_evaluation.ipynb`
imports this and displays the results.

    python cesare/final_evaluation.py          # rebuild every table

Six outputs (plan §19.2, §17.3, §19.3, §14.2):

    p4_episode_table_baseline.csv    baseline on the 9 frozen ERAS
    p4_stress_table_baseline.csv     baseline on the 8 frozen STRESS windows
    p4_leg_decomposition.csv         carry/spot x long/short, ME + QE + YE + full
    tenor_sweep.csv                  D6 term structure, re-priced after the F2 fix
    p4_reverdict_tail_objective.csv  Stages 3 & 6 re-read on the desk's objective
    final_comparison.csv             every named variant, all six workstreams

Two conventions run through all of it, both from plan §6:

* every table reports **gross and net** and records what produced it —
  `config.describe()` plus the evaluation window, which `describe()` omits;
* nothing is re-run that has already been committed. The re-verdict and the
  comparison table read CSVs; only the episode tables and the tenor sweep call
  `run()`, because they are new measurements rather than re-readings.
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
from strategy.episodes import ERAS, STRESS, leg_decomposition, report_windows

OUTPUTS = Path(__file__).resolve().parent / "outputs"

# --- the tail objective, stated before anything is computed (plan §19 bar) ----
# "a material tail improvement (MaxDD / CVaR99) at <= 0.02 Sharpe cost". The two
# thresholds below are what "material" means, fixed here so the rule cannot be
# tuned after seeing which rules pass.
TAIL_SHARPE_BUDGET = 0.02      # max net Sharpe a rule may give up
TAIL_MAXDD_GAIN_PP = 1.0       # percentage points of MaxDD improvement required
TAIL_CVAR_GAIN_REL = 0.05      # or 5% relative CVaR99 improvement


# ---------------------------------------------------------------------------
# Provenance
# ---------------------------------------------------------------------------

def provenance(result) -> dict:
    """`config.describe()` plus the window, which `describe()` does not carry."""
    meta = dict(result.config.describe())
    meta.update(window_start=str(result.window[0].date()),
                window_end=str(result.window[1].date()),
                n_currencies=len(result.universe))
    return meta


def _stamp(frame: pd.DataFrame, result) -> pd.DataFrame:
    out = frame.copy()
    for key, value in provenance(result).items():
        out[key] = value
    return out


# ---------------------------------------------------------------------------
# P4-A: the two window tables
# ---------------------------------------------------------------------------

def episode_tables(result=None) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Baseline on `ERAS` and on `STRESS`, gross and net, with provenance."""
    result = run() if result is None else result
    eras = _stamp(report_windows(result, ERAS, which="both"), result)
    stress = _stamp(report_windows(result, STRESS, which="both"), result)
    eras.to_csv(OUTPUTS / "p4_episode_table_baseline.csv", index=False)
    stress.to_csv(OUTPUTS / "p4_stress_table_baseline.csv", index=False)
    return eras, stress


# ---------------------------------------------------------------------------
# P4-A: the per-leg accrual (the Jul 15 desk ask)
# ---------------------------------------------------------------------------

def leg_table(result=None, tol: float = 1e-12) -> pd.DataFrame:
    """Carry/spot x long/short at ME, QE and YE, plus annualised full-sample.

    Raises if the split does not reconcile to `gross`. The plan's provisional
    figures came from a reconstruction that summed to 7.32% against a 7.03%
    book; the acceptance criterion here is reconciliation, not proximity, so a
    failure must stop the table being written rather than be rounded away.
    """
    result = run() if result is None else result
    frames = []
    for freq in ("ME", "QE", "YE"):
        block = leg_decomposition(result, freq).reset_index()
        block.insert(0, "freq", freq)
        block["period"] = block["period"].dt.date.astype(str)
        frames.append(block)

    daily = leg_decomposition(result, None)
    full = (daily[["carry_long", "carry_short", "spot_long", "spot_short",
                   "total", "gross"]].mean() * fx.ANN_DAYS)
    full["resid"] = float(full["total"] - full["gross"])
    frames.append(pd.DataFrame([{"freq": "FULL", "period": "ann_contribution",
                                 **full.to_dict()}]))

    out = pd.concat(frames, ignore_index=True)
    err = float(out["resid"].abs().max())
    if err >= tol:
        raise AssertionError(
            f"per-leg split does not reconcile to gross: max|resid| {err:.2e} >= {tol:.0e}")
    out = _stamp(out, result)
    out.to_csv(OUTPUTS / "p4_leg_decomposition.csv", index=False)
    return out


# ---------------------------------------------------------------------------
# D6 re-priced: the tenor sweep (plan §17.3, missing from outputs/ until now)
# ---------------------------------------------------------------------------

def tenor_sweep() -> pd.DataFrame:
    """1M/3M/6M/12M x gross/net, turnover and cost drag.

    §17.3 and Appendix A both cite `outputs/tenor_sweep.csv` as D6's output, but
    it was never written — the D6 null had no committed CSV behind it. It does
    now, and its net column is meaningful for the first time: before the F2 fix
    the roll leg was billed on the rebalance grid, so a 12M forward was charged
    twelve rolls a year of the 12M points spread and the drag ROSE to 4.84%/yr
    while turnover FELL (guardrail §6.11).
    """
    rows = []
    for tenor in ("1M", "3M", "6M", "12M"):
        res = run(tenor=tenor)
        stats = res.summary(benchmark=None)
        rows.append({
            "tenor": tenor,
            "gross_sharpe": float(stats.iloc[0]["sharpe"]),
            "net_sharpe": float(stats.iloc[1]["sharpe"]),
            "ann_return_net": float(stats.iloc[1]["ann_return"]),
            "ann_vol_net": float(stats.iloc[1]["ann_vol"]),
            "max_drawdown_net": float(stats.iloc[1]["max_drawdown"]),
            "turnover": float(res.turnover),
            "cost_drag": float(res.cost_drag),
            "window_start": str(res.window[0].date()),
            "window_end": str(res.window[1].date()),
        })
    out = pd.DataFrame(rows)
    out.to_csv(OUTPUTS / "tenor_sweep.csv", index=False)
    return out


# ---------------------------------------------------------------------------
# P4-B prep: re-verdict Stages 3 and 6 on the tail objective (plan §19.3)
# ---------------------------------------------------------------------------

#: (book, rule label, source file, row, baseline row, §9/§12 verdict, adopted?)
#:
#: `_NOT_TAIL_RULES` below marks entries the tail test does not apply to. Vol
#: targeting is the sizing standard, not an exposure-timing rule: it levers a
#: 7.6%-vol static book up to the 10% target, so of course its MaxDD is deeper.
#: Comparing drawdowns across two books held at different volatilities is not
#: what the desk's objective means, and reading its mechanical "flip" as a real
#: one would be a category error. It stays in the table — dropping a row because
#: the answer is inconvenient is the failure mode this project is built to avoid
#: — but it is labelled and excluded from the flip count.
_REVERDICT_RULES = [
    ("ALL", "Vol targeting (vs static)", "stage3_dynamic_comparison.csv",
     "ALL_voltgt_net", "ALL_static_net", "adopt as sizing standard — no alpha claim", True),
    ("ALL", "VIX threshold (Stage 3 rule)", "stage3_dynamic_comparison.csv",
     "ALL_vix_net", "ALL_voltgt_net", "tail-insurance-only", False),
    ("ALL", "IV/RR binary, book-level", "stage3_dynamic_comparison.csv",
     "ALL_ivrr_net", "ALL_voltgt_net", "combined REJECT", False),
    ("ALL", "IV/RR linear ramp", "stage3_dynamic_comparison.csv",
     "ALL_ivrr_lin_net", "ALL_voltgt_net", "dominated — reject", False),
    ("ALL", "Per-currency RR (longs only)", "stage3_dynamic_comparison.csv",
     "ALL_rrccy_net", "ALL_voltgt_net", "tail-insurance-only — preferred", False),
    ("G10", "VIX threshold (Stage 3 rule)", "stage3_dynamic_comparison.csv",
     "G10_vix_net", "G10_voltgt_net", "tail-insurance-only", False),
    ("G10", "IV/RR binary, book-level", "stage3_dynamic_comparison.csv",
     "G10_ivrr_net", "G10_voltgt_net", "G10 tail-insurance-only", False),
    ("G10", "IV/RR linear ramp", "stage3_dynamic_comparison.csv",
     "G10_ivrr_lin_net", "G10_voltgt_net", "dominated — reject", False),
    ("G10", "Per-currency RR (longs only)", "stage3_dynamic_comparison.csv",
     "G10_rrccy_net", "G10_voltgt_net", "tail-insurance-only — preferred", False),
    ("ALL", "Regime: Crisis -> 0.5", "stage6_regime_stats.csv",
     "ALL_reg_half_net", "ALL_voltgt_net", "REJECT as replacement", False),
    ("ALL", "Regime: Crisis -> 0.0", "stage6_regime_stats.csv",
     "ALL_reg_off_net", "ALL_voltgt_net", "REJECT as replacement", False),
    ("ALL", "Regime: Moderate -> 0.5, Crisis -> 0.0", "stage6_regime_stats.csv",
     "ALL_reg_mod_net", "ALL_voltgt_net", "REJECT as replacement", False),
]

#: Dafu's VIX percentile gate lives in his own table with different column
#: names. It is in scope because §19.3 names it as the incumbent bar.
_DAFU_RULE = ("ALL", "VIX percentile gate (Dafu, p80/756d)",
              "dafu/outputs/headline.csv", "VIX-rule (incumbent)", "baseline",
              "not verdicted in §9/§12 — Sharpe-neutral, so never adopted", False)

#: Rules the tail test does not apply to (see the comment on _REVERDICT_RULES).
_NOT_TAIL_RULES = {"Vol targeting (vs static)"}

_NOTES = {
    "Vol targeting (vs static)":
        "NOT A TAIL RULE — the sizing standard. It levers a 7.6%-vol static book "
        "to the 10% target, so its deeper MaxDD is the target working, not a "
        "tail failure. Comparing drawdowns across books held at different vol is "
        "outside what the desk's objective means. Shown for completeness and "
        "excluded from the flip count.",
    "VIX threshold (Stage 3 rule)":
        "DIFFERENT RULE from Dafu's percentile gate — a level threshold, not a "
        "trailing-percentile gate. Do not merge the two numbers (§19.3).",
    "VIX percentile gate (Dafu, p80/756d)":
        "The §19.3 incumbent. Half risk when VIX is in the top fifth of a "
        "trailing 3y. CVaR99 not published in headline.csv, so the tail test "
        "runs on MaxDD alone.",
    "Regime: Moderate -> 0.5, Crisis -> 0.0":
        "Carry §12's caveat forward: this de-risks the HIGHEST-Sharpe regime "
        "(Moderate, 0.94), its NW alpha is insignificant (t 0.59) and it is a "
        "beyond-spec sensitivity. A re-verdict is a re-reading, not a promotion.",
    "Per-currency RR (longs only)":
        "Breaks dollar-neutrality by design (mean net FX exposure -0.10). The "
        "long-USD tilt in crises IS the hedge; report it as an exposure.",
}


def _tail_verdict(d_sharpe: float, d_maxdd_pp: float, d_cvar_rel: float) -> str:
    if d_sharpe < -TAIL_SHARPE_BUDGET:
        return "REJECT"
    tail_gain = (d_maxdd_pp >= TAIL_MAXDD_GAIN_PP
                 or (pd.notna(d_cvar_rel) and d_cvar_rel <= -TAIL_CVAR_GAIN_REL))
    return "ACCEPT" if tail_gain else "REJECT"


def reverdict() -> pd.DataFrame:
    """Stages 3 and 6 re-read under the desk's capital-preservation objective.

    No re-runs: this reads the committed CSVs. The project verdicted everything
    on Sharpe; the desk's stated objective (2026-07-29) is capital preservation
    through the tail, and the question is which verdicts change when the column
    that decides changes.
    """
    tables = {name: pd.read_csv(OUTPUTS / name, index_col=0)
              for name in ("stage3_dynamic_comparison.csv", "stage6_regime_stats.csv")}
    dafu = pd.read_csv(REPO_ROOT / "dafu" / "outputs" / "headline.csv", index_col=0)

    rows = []
    for book, rule, source, key, base_key, old, old_adopted in _REVERDICT_RULES:
        tab = tables[source]
        r, b = tab.loc[key], tab.loc[base_key]
        rows.append(dict(
            book=book, rule=rule, basis="net", source=f"cesare/outputs/{source}",
            row=key, baseline_row=base_key,
            sharpe=float(r["sharpe"]), sharpe_base=float(b["sharpe"]),
            max_drawdown=float(r["max_drawdown"]), maxdd_base=float(b["max_drawdown"]),
            cvar99=float(r["CVaR_99"]), cvar99_base=float(b["CVaR_99"]),
            calmar=float(r["calmar"]), calmar_base=float(b["calmar"]),
            alpha_ann=float(r.get("alpha_vs_base_ann", np.nan)),
            t_alpha=float(r.get("t_alpha_vs_base", np.nan)),
            verdict_sharpe_old=old, adopted_on_sharpe=old_adopted))

    book, rule, source, key, base_key, old, old_adopted = _DAFU_RULE
    r, b = dafu.loc[key], dafu.loc[base_key]
    rows.append(dict(
        book=book, rule=rule, basis="net", source=source,
        row=key, baseline_row=base_key,
        sharpe=float(r["net_sharpe"]), sharpe_base=float(b["net_sharpe"]),
        max_drawdown=float(r["max_dd"]), maxdd_base=float(b["max_dd"]),
        cvar99=np.nan, cvar99_base=np.nan,
        calmar=float(r["calmar"]), calmar_base=float(b["calmar"]),
        alpha_ann=np.nan, t_alpha=np.nan,
        verdict_sharpe_old=old, adopted_on_sharpe=old_adopted))

    out = pd.DataFrame(rows)
    out["d_sharpe"] = out["sharpe"] - out["sharpe_base"]
    out["d_maxdd_pp"] = (out["max_drawdown"] - out["maxdd_base"]) * 100.0
    out["d_cvar99_rel"] = (out["cvar99"] - out["cvar99_base"]) / out["cvar99_base"]
    out["d_calmar"] = out["calmar"] - out["calmar_base"]
    out["verdict_tail_new"] = [
        _tail_verdict(s, m, c) for s, m, c
        in zip(out["d_sharpe"], out["d_maxdd_pp"], out["d_cvar99_rel"])]
    out["tail_rule"] = ~out["rule"].isin(_NOT_TAIL_RULES)
    out.loc[~out["tail_rule"], "verdict_tail_new"] = "n/a — not a tail rule"
    out["flipped"] = (out["tail_rule"]
                      & (out["adopted_on_sharpe"] != (out["verdict_tail_new"] == "ACCEPT")))
    out["note"] = out["rule"].map(_NOTES).fillna("")
    out["rule_sharpe_budget"] = TAIL_SHARPE_BUDGET
    out["rule_maxdd_gain_pp"] = TAIL_MAXDD_GAIN_PP
    out["rule_cvar_gain_rel"] = TAIL_CVAR_GAIN_REL

    cols = ["book", "rule", "basis", "tail_rule", "sharpe", "sharpe_base", "d_sharpe",
            "max_drawdown", "maxdd_base", "d_maxdd_pp", "cvar99", "cvar99_base",
            "d_cvar99_rel", "calmar", "calmar_base", "d_calmar",
            "alpha_ann", "t_alpha", "verdict_sharpe_old", "adopted_on_sharpe",
            "verdict_tail_new", "flipped", "note", "source", "row", "baseline_row",
            "rule_sharpe_budget", "rule_maxdd_gain_pp", "rule_cvar_gain_rel"]
    out = out[cols]
    out.to_csv(OUTPUTS / "p4_reverdict_tail_objective.csv", index=False)
    return out


# ---------------------------------------------------------------------------
# §14.2: the whole-sample comparison table, across all six workstreams
# ---------------------------------------------------------------------------

CANON = ["owner", "workstream", "variant", "basis", "on_base", "ann_return",
         "ann_vol", "sharpe", "sortino", "calmar", "max_drawdown", "skew",
         "hit_rate", "CVaR_99", "turnover", "cost_drag", "info_ratio",
         "alpha_ann", "t_alpha", "n_days", "start", "end", "source", "note"]


def _split_basis(label: str) -> tuple[str, str]:
    for suffix in ("_gross", "_net"):
        if label.endswith(suffix):
            return label[: -len(suffix)], suffix[1:]
    return label, "index"


def _from_stage_table(path: Path, owner: str, workstream: str, alpha: str | None,
                      t_alpha: str | None, note: str = "",
                      on_base: bool = True) -> pd.DataFrame:
    """Map one of the repo's 27-column stage tables onto the canonical schema."""
    tab = pd.read_csv(path, index_col=0)
    rows = []
    for label, r in tab.iterrows():
        variant, basis = _split_basis(str(label))
        rows.append({
            "owner": owner, "workstream": workstream, "variant": variant,
            "basis": basis, "on_base": on_base,
            "ann_return": r.get("ann_return"), "ann_vol": r.get("ann_vol"),
            "sharpe": r.get("sharpe"), "sortino": r.get("sortino"),
            "calmar": r.get("calmar"), "max_drawdown": r.get("max_drawdown"),
            "skew": r.get("skew"), "hit_rate": r.get("hit_rate"),
            "CVaR_99": r.get("CVaR_99"), "turnover": r.get("avg_monthly_turnover"),
            "cost_drag": r.get("ann_cost_drag"), "info_ratio": r.get("info_ratio"),
            "alpha_ann": r.get(alpha) if alpha else np.nan,
            "t_alpha": r.get(t_alpha) if t_alpha else np.nan,
            "n_days": r.get("n_days"), "start": r.get("start"), "end": r.get("end"),
            "source": str(path.relative_to(REPO_ROOT)), "note": note})
    return pd.DataFrame(rows)


def _blank(owner, workstream, variant, basis, on_base, source, note, **kw):
    row = {c: np.nan for c in CANON}
    row.update(owner=owner, workstream=workstream, variant=variant, basis=basis,
               on_base=on_base, source=source, note=note, **kw)
    return row


def final_comparison() -> pd.DataFrame:
    """Every named variant across all six workstreams, whole-sample.

    Assembled entirely from committed CSVs — W1 stands this up as a living
    artifact holding whatever exists today, and it is refreshed each week so the
    terminal week is assembly rather than authorship.

    `on_base` records whether a row was produced through `strategy.run()` and
    therefore reconciles to the shared baseline. Rows that do NOT reconcile are
    kept and flagged rather than dropped: that a teammate's book disagrees with
    the base is itself the §18 finding, and hiding it would defeat the point of
    the table.
    """
    c = OUTPUTS
    parts = [
        _from_stage_table(c / "stage3_dynamic_comparison.csv", "Cesare",
                          "Stage 3 dynamic carry", "alpha_vs_base_ann",
                          "t_alpha_vs_base"),
        _from_stage_table(c / "stage4_weighting_comparison.csv", "Cesare",
                          "Stage 4 portfolio construction", "alpha_vs_inv_vol_ann",
                          "t_alpha_vs_inv_vol"),
        _from_stage_table(c / "stage5_momentum_comparison.csv", "Cesare",
                          "Stage 5 momentum", "alpha_vs_carry_ann",
                          "t_alpha_vs_carry"),
        _from_stage_table(c / "stage6_regime_stats.csv", "Cesare",
                          "Stage 6 regimes", "alpha_vs_base_ann", "t_alpha_vs_base"),
        _from_stage_table(c / "skew_carry_comparison.csv", "Cesare",
                          "Phase 3 D1 skew (null)", "alpha_vs_carry_ann",
                          "t_alpha_vs_carry",
                          note="matched 21-name option universe, not the ALL-27 book"),
        _from_stage_table(c / "basis_carry_comparison.csv", "Cesare",
                          "Phase 3 D3 basis (null)", "alpha_vs_carry_ann",
                          "t_alpha_vs_carry",
                          note="matched 7-name onshore-fixing EM universe; "
                               "basis window ends 2024-09 (USD LIBOR discontinued)"),
    ]

    # D6 term structure — re-priced on the fixed cost model, so it is a live
    # measurement rather than a committed reading.
    sweep = pd.read_csv(c / "tenor_sweep.csv")
    d6 = []
    for _, r in sweep.iterrows():
        for basis in ("gross", "net"):
            d6.append(_blank("Cesare", "Phase 3 D6 term structure (null)",
                             f"tenor_{r['tenor']}", basis, True,
                             "cesare/outputs/tenor_sweep.csv",
                             "net re-priced after the F2 roll-leg fix (v1.1.0)",
                             sharpe=r[f"{basis}_sharpe"],
                             turnover=r["turnover"], cost_drag=r["cost_drag"],
                             max_drawdown=r["max_drawdown_net"] if basis == "net" else np.nan,
                             ann_return=r["ann_return_net"] if basis == "net" else np.nan,
                             ann_vol=r["ann_vol_net"] if basis == "net" else np.nan,
                             start=r["window_start"], end=r["window_end"]))
    parts.append(pd.DataFrame(d6))

    # Dafu — regime switching + the incumbent VIX gate, already on the base.
    dafu = pd.read_csv(REPO_ROOT / "dafu" / "outputs" / "headline.csv", index_col=0)
    rows = []
    for label, r in dafu.iterrows():
        rows.append(_blank("Dafu", "Regime switching / VIX gate", str(label), "net",
                           True, "dafu/outputs/headline.csv", "",
                           sharpe=r["net_sharpe"], ann_return=r["ann_return"],
                           ann_vol=r["ann_vol"], max_drawdown=r["max_dd"],
                           calmar=r["calmar"], skew=r["skew"],
                           turnover=r["turnover"], cost_drag=r["cost_drag"]))
        rows.append(_blank("Dafu", "Regime switching / VIX gate", str(label), "gross",
                           True, "dafu/outputs/headline.csv",
                           "headline.csv publishes gross Sharpe only",
                           sharpe=r["gross_sharpe"]))
    parts.append(pd.DataFrame(rows))

    # Arjun — the duration hedge, the one component that has beaten the bar.
    #
    # CORRECTED 2026-08-03 (W2). The earlier note here said his baseline was "NOT
    # the same book". That was wrong, and verifying it mattered: his `book`
    # column IS `run().net`, bit-identical (max |diff| 1.0e-16, corr 1.0) on all
    # 4,994 shared days. Both apparent discrepancies decompose exactly:
    #   * 0.4673 vs 0.4659 — he drops 7 US market holidays in the TLT inner join
    #     (2011-09-04 .. 2011-10-23). On his index the base scores 0.467288.
    #   * -33.2% vs -29.3% — a DRAWDOWN CONVENTION difference, not a different
    #     book. He uses cumsum (arithmetic); the base uses the wealth curve. His
    #     convention applied to the base's own net gives -0.3322331117648022,
    #     matching his committed figure to every digit.
    # So `on_base=True`: his delta was already measured on the shared book. What
    # does not transfer is the MaxDD, which is in different units.
    arjun = pd.read_csv(REPO_ROOT / "arjun" / "outputs" / "duration_hedge_stats.csv",
                        index_col=0)
    note_arjun = ("ON THE BASE: his `book` column is bit-identical to run().net "
                  "(1.0e-16). 0.4673 vs 0.4659 = 7 US holidays dropped by the TLT "
                  "inner join; -33.2% vs -29.3% = cumsum vs wealth-curve drawdown "
                  "convention, NOT a different book. MaxDD is therefore NOT "
                  "comparable to other rows here. Re-priced through ExternalLeg in "
                  "p4_component_standalone.csv (net 0.5145 on the base).")
    rows = []
    for label, r in arjun.iterrows():
        variant, basis = (str(label).rsplit(" ", 1) if str(label).endswith(("gross", "net"))
                          else (str(label), "net"))
        rows.append(_blank("Arjun", "Duration hedge", variant.strip(), basis, True,
                           "arjun/outputs/duration_hedge_stats.csv", note_arjun,
                           sharpe=r["sharpe"], ann_return=r["ann_return"],
                           ann_vol=r["ann_vol"], max_drawdown=r["max_dd"],
                           skew=r["skew"]))
    parts.append(pd.DataFrame(rows))

    # Phase-4 components and the combined ladder, all produced through run() on
    # this base — the first rows in this table that are directly comparable to
    # each other across owners rather than merely collected together.
    for name, workstream in (("p4_component_standalone.csv", "P4-C components"),
                             ("p4_combined_ladder.csv", "P4-C combined ladder")):
        path = c / name
        if not path.exists():
            continue
        tab = pd.read_csv(path)
        label_col = "variant" if "variant" in tab.columns else "step"
        rows = []
        for _, r in tab.iterrows():
            # The ladder file holds four ladders (add / loo / final / final_loo)
            # keyed only by `step`, and several rungs are shared between them --
            # `add`'s baseline IS `final`'s baseline. Labelling by `step` alone
            # therefore emitted 6 exact duplicate rows and double-counted the
            # baseline in any groupby. The ladder name is part of the identity.
            label = str(r[label_col])
            if "ladder" in tab.columns and pd.notna(r.get("ladder")):
                label = f"[{r['ladder']}] {label}"
            for basis in ("gross", "net"):
                key = f"{basis}_sharpe"
                if key not in tab.columns or pd.isna(r[key]):
                    continue
                rows.append(_blank(
                    r.get("owner", "Cesare"), workstream,
                    label, basis, True, f"cesare/outputs/{name}",
                    str(r.get("reconstruction", r.get("slot_rule", "")))[:300],
                    sharpe=r[key],
                    ann_return=r.get("ann_return_net") if basis == "net" else np.nan,
                    ann_vol=r.get("ann_vol_net") if basis == "net" else np.nan,
                    max_drawdown=r.get("max_drawdown") if basis == "net" else np.nan,
                    CVaR_99=r.get("CVaR_99") if basis == "net" else np.nan,
                    skew=r.get("skew") if basis == "net" else np.nan,
                    calmar=r.get("calmar") if basis == "net" else np.nan,
                    turnover=r.get("turnover"), cost_drag=r.get("cost_drag"),
                    alpha_ann=r.get("alpha_ann", r.get("alpha_vs_prev_ann")),
                    t_alpha=r.get("t_alpha", r.get("t_alpha_vs_prev")),
                    n_days=r.get("n_days")))
        parts.append(pd.DataFrame(rows))

    # Phase-3 D1 rerun — the same battery on model-free BKM skewness instead of
    # the 25d slope proxy. Both inputs are kept as separate rows: the point of
    # the rerun is the comparison, so collapsing to one would delete the result.
    bkm = c / "p3_d1_bkm_comparison.csv"
    if bkm.exists():
        tab = pd.read_csv(bkm)
        rows = []
        for _, r in tab.iterrows():
            for basis in ("gross", "net"):
                rows.append(_blank(
                    "Cesare", "Phase 3 D1 rerun (null, model-free)",
                    str(r["variant"]), basis, True,
                    "cesare/outputs/p3_d1_bkm_comparison.csv",
                    f"matched 21-name option universe, not the ALL-27 book; "
                    f"risk-neutral input = {r['input']}. The D1 null survives the "
                    f"correct construction: carry subsumes SRP (CARRY~SRP t +2.23), "
                    f"and the implied-skew sort is now significantly worse (t -2.36)",
                    sharpe=r[f"{basis}_sharpe"],
                    ann_return=r["ann_return_net"] if basis == "net" else np.nan,
                    ann_vol=r["ann_vol_net"] if basis == "net" else np.nan,
                    max_drawdown=r["max_drawdown"] if basis == "net" else np.nan,
                    CVaR_99=r["CVaR_99"] if basis == "net" else np.nan,
                    skew=r["skew"] if basis == "net" else np.nan,
                    turnover=r["turnover"], cost_drag=r["cost_drag"],
                    alpha_ann=r.get("alpha_vs_carry_ann"),
                    t_alpha=r.get("t_alpha_vs_carry"), n_days=r.get("n_days")))
        parts.append(pd.DataFrame(rows))

    # Phase-3 D2 — the volatility risk premium, the one qualified positive.
    #
    # These rows carry basis="monthly_uncosted" rather than gross/net, and that
    # is deliberate. They are MONTHLY books on the 21-name option universe with
    # NO transaction cost, because `data/raw` has option mids only. Dropping a
    # 1.69 Sharpe into the same `net` column as the daily costed books would
    # manufacture exactly the false comparability this table exists to prevent.
    d2 = c / "p3_d2_books.csv"
    if d2.exists():
        note_d2 = ("NOT COMPARABLE TO THE net ROWS: monthly, 21-name option "
                   "universe, and GROSS OF OPTION BID/ASK (mids only). Breakeven "
                   "round-trip vol spread at which it stops clearing both bars: "
                   "0.25 vol pts for short_vol and carry+short_vol, 0.10 for "
                   "vrp_xs -- inside G10 interbank. Two thirds of vrp_xs's Sharpe "
                   "is a standing short in TRY|MXN|THB|KRW|INR (1.689 -> 0.547 "
                   "demeaned, skew +1.66 -> -1.84). Report chapter 8.")
        rows = []
        for _, r in pd.read_csv(d2).iterrows():
            rows.append(_blank(
                "Cesare", "Phase 3 D2 vol risk premium (qualified positive)",
                str(r["variant"]), "monthly_uncosted", True,
                "cesare/outputs/p3_d2_books.csv", note_d2,
                sharpe=r["sharpe"], ann_return=r["ann_return"],
                ann_vol=r["ann_vol"], max_drawdown=r["max_drawdown"],
                skew=r["skew"], hit_rate=r["hit_rate"], CVaR_99=r["CVaR_99"],
                n_days=r["n_months"]))
        for _, r in pd.read_csv(c / "p3_d2_static_vs_timing.csv").iterrows():
            rows.append(_blank(
                "Cesare", "Phase 3 D2 vol risk premium (qualified positive)",
                str(r["variant"]), "monthly_uncosted", True,
                "cesare/outputs/p3_d2_static_vs_timing.csv",
                note_d2 + f" Standing shorts: {r['standing_shorts']}.",
                sharpe=r["sharpe"], ann_return=r["ann_return"],
                ann_vol=r["ann_vol"], max_drawdown=r["max_drawdown"],
                skew=r["skew"], hit_rate=r["hit_rate"], CVaR_99=r["CVaR_99"],
                n_days=r["n_months"]))
        parts.append(pd.DataFrame(rows))

    # P4-B tail forecast — a null, and it belongs in the table as one.
    tail = c / "p4_tail_overlay_stats.csv"
    if tail.exists():
        tab = pd.read_csv(tail)
        rows = []
        for _, r in tab.iterrows():
            for basis in ("gross", "net"):
                rows.append(_blank(
                    "Cesare", "P4-B tail forecast (null)", str(r["variant"]), basis,
                    True, "cesare/outputs/p4_tail_overlay_stats.csv",
                    # NOT "across 13 purged folds": 7 of the 13 contain no tail
                    # month, so AUC is undefined there and 0.4685 is the mean of
                    # the 6 that are defined. The looser phrasing overstated the
                    # evidence behind the null.
                    "REJECT: fails all three pre-registered bars; mean OOS AUC "
                    "0.4685 across the 6 of 13 purged folds that contain a tail "
                    "month (AUC is undefined in the other 7)",
                    sharpe=r[f"{basis}_sharpe"],
                    ann_return=r["ann_return"] if basis == "net" else np.nan,
                    ann_vol=r["ann_vol"] if basis == "net" else np.nan,
                    max_drawdown=r["max_drawdown"] if basis == "net" else np.nan,
                    CVaR_99=r["CVaR_99"] if basis == "net" else np.nan,
                    skew=r["skew"] if basis == "net" else np.nan,
                    calmar=r["calmar"] if basis == "net" else np.nan,
                    turnover=r["turnover"], cost_drag=r["cost_drag"],
                    alpha_ann=r.get("alpha_vs_baseline_ann"),
                    t_alpha=r.get("t_alpha_vs_baseline"), n_days=r.get("n_days")))
        parts.append(pd.DataFrame(rows))

    # Vidhi — kept and flagged. Her book's returns omit the carry accrual (§18),
    # which is exactly why the sign is wrong; dropping the row would hide that.
    vidhi = pd.read_csv(REPO_ROOT / "vidhi" / "outputs" / "adaptive_strategy_summary.csv",
                        index_col=0)
    note_vidhi = ("DOES NOT RECONCILE: monthly book whose returns are "
                  "log_return(spot) only, so it sorts on carry and harvests none "
                  "of it (§18). Sign is expected to flip once ported to the base. "
                  "Kept and flagged, not dropped.")
    rows = []
    for label, r in vidhi.iterrows():
        rows.append(_blank("Vidhi", "Macro/regime gate", str(label), "net", False,
                           "vidhi/outputs/adaptive_strategy_summary.csv", note_vidhi,
                           sharpe=r["sharpe"], sortino=r["sortino"],
                           calmar=r["calmar"], hit_rate=r["hit_rate"],
                           ann_return=r["annual_return"], ann_vol=r["annual_volatility"],
                           max_drawdown=r["maximum_drawdown"], n_days=r["observations"]))
    parts.append(pd.DataFrame(rows))

    # Theo and Oleg have no committed CSVs yet — recorded as gaps so the table
    # shows what is missing rather than silently omitting two workstreams.
    parts.append(pd.DataFrame([
        _blank("Theo", "FX options / skew filter", "(no committed CSV)", "n/a", False,
               "theo/data/processed/*.parquet",
               "results are parquet-only; spec his test as marginal over "
               "per-currency RR (0.457), not versus the raw baseline (§19.1)"),
        _blank("Oleg", "Macro event studies", "(no committed output)", "n/a", False,
               "oleg/", "no outputs committed; must consume the same frozen "
                        "windows as everyone else (§19.2)")]))

    out = pd.concat(parts, ignore_index=True)[CANON]
    before = len(out)
    out = out.drop_duplicates(subset=["owner", "workstream", "variant", "basis"],
                              keep="first")
    if before != len(out):
        print(f"  final_comparison: dropped {before - len(out)} duplicate rows")
    out = out.sort_values(["owner", "workstream", "variant", "basis"],
                          kind="stable").reset_index(drop=True)
    out.to_csv(OUTPUTS / "final_comparison.csv", index=False)
    return out


# ---------------------------------------------------------------------------
# §14.2 second artifact: the variants x episodes matrix
# ---------------------------------------------------------------------------

#: Per-episode tables that already exist, and the workstream each belongs to.
_EPISODE_SOURCES = [
    ("p4_component_by_episode.csv", "P4-C components", "daily_net"),
    ("p4_combined_by_episode.csv", "P4-C combined ladder", "daily_net"),
    ("p4_tail_overlay_by_episode.csv", "P4-B tail forecast (null)", "daily_net"),
]

#: Owner attribution for the component variants, so the matrix answers "whose
#: component was this" without the reader consulting another file.
_EPISODE_OWNER = {
    "Duration hedge (long TLT)": "Arjun",
    "VIX percentile gate (p80 / 756d)": "Dafu",
    "Macro/regime probability gate": "Vidhi",
    "Bad-skew exclusion (XS top quintile)": "Theo",
}

#: Workstreams with NO per-episode table, and why. Emitted as explicit rows so
#: the file records what is missing instead of silently omitting it.
_EPISODE_GAPS = [
    ("Arjun", "Duration hedge (own port)",
     "his own book is not ported to the base; only our re-price exists "
     "(P4-C components). A re-price is our reading of his signal, not his "
     "specification of it, and this table deliberately does not substitute one "
     "for the other"),
    ("Dafu", "Regime switching / VIX gate (own port)",
     "dafu/outputs/headline.csv publishes whole-sample stats only, no daily "
     "series, so no window table can be built from it"),
    ("Vidhi", "Macro/regime gate (own port)",
     "her committed track is monthly and its returns omit the carry accrual, so "
     "a window table from it would not be comparable to any other row here"),
    ("Theo", "FX options / skew filter (own port)",
     "results are parquet-only, no committed daily net series"),
    ("Oleg", "Macro event studies",
     "no outputs committed; must consume the same frozen windows (plan §19.2)"),
    ("Cesare", "Stages 1-6 and Phase 3 D3",
     "the per-window standard is prospective (plan §19.2) -- closed stages were "
     "deliberately not retrofitted, because re-running six stages x seven "
     "variants x seventeen windows would consume the runway and produce nothing "
     "new"),
]

_EP_CANON = ["owner", "workstream", "variant", "basis", "window_set", "window",
             "start", "end", "n_obs", "cum_return", "max_drawdown", "worst_obs",
             "hit_rate", "sharpe", "ann_return", "ann_vol", "share_pnl", "note"]


def final_comparison_by_episode() -> pd.DataFrame:
    """Every variant that has one, on the frozen windows (plan §14.2).

    The companion to `final_comparison.csv`, and the one the desk actually reads
    (guardrail §6.8). It is an **assembly**, not a re-run: the Phase-4 tables
    already carry every variant on the frozen windows, so this concatenates them
    onto one schema, adds the D1 rerun and D2, and — importantly — records what
    is *absent*.

    **Two metric conventions coexist here and must not be compared across.**
    `basis="daily_net"` rows are daily books; their `sharpe`/`ann_*` are already
    NaN below 120 trading days per guardrail §6.8. `basis="monthly_uncosted"`
    rows are D2's monthly books, which carry no annualised ratio at *any* length
    and no transaction cost at all, because option data is mids only. `n_obs` is
    trading days for the first and months for the second, which is why the column
    is not called `n_days`.
    """
    frames = []
    for name, workstream, basis_kind in _EPISODE_SOURCES:
        path = OUTPUTS / name
        if not path.exists():
            continue
        t = pd.read_csv(path)
        t = t[t["basis"] == "net"].copy()
        t["owner"] = t["variant"].map(_EPISODE_OWNER).fillna("Cesare")
        t["workstream"] = workstream
        t["basis"] = basis_kind
        t = t.rename(columns={"n_days": "n_obs", "worst_day": "worst_obs"})
        t["note"] = f"source: cesare/outputs/{name}"
        frames.append(t)

    # D1 rerun: daily books on the base, so report_windows computes them directly.
    d1 = _d1_rerun_windows()
    if d1 is not None:
        frames.append(d1)

    # D2: monthly, already written by cesare/d2_vrp.py::by_episode.
    d2_path = OUTPUTS / "p3_d2_by_episode.csv"
    if d2_path.exists():
        t = pd.read_csv(d2_path)
        t = t.rename(columns={"n_months": "n_obs", "worst_month": "worst_obs"})
        t["owner"] = "Cesare"
        t["workstream"] = "Phase 3 D2 vol risk premium (qualified positive)"
        t["basis"] = "monthly_uncosted"
        t["note"] = ("MONTHLY and GROSS OF OPTION BID/ASK (mids only); no "
                     "annualised ratio at any window length. Not comparable to "
                     "the daily_net rows. source: cesare/outputs/p3_d2_by_episode.csv")
        frames.append(t)

    out = pd.concat(frames, ignore_index=True)
    for col in _EP_CANON:
        if col not in out.columns:
            out[col] = np.nan
    out = out[_EP_CANON]

    gaps = pd.DataFrame([
        {**{c: np.nan for c in _EP_CANON}, "owner": o, "workstream": w,
         "variant": "(no per-window table)", "basis": "missing", "note": why}
        for o, w, why in _EPISODE_GAPS])
    out = pd.concat([out, gaps], ignore_index=True)

    out = out.sort_values(["owner", "workstream", "variant", "window_set", "window"],
                          kind="stable").reset_index(drop=True)
    out.to_csv(OUTPUTS / "final_comparison_by_episode.csv", index=False)
    return out


def _d1_rerun_windows() -> pd.DataFrame | None:
    """The D1 rerun variants on the frozen windows.

    These are daily books on the shared base, so `report_windows` applies
    unchanged — including its suppression of annualised ratios under 120 days.

    `d1_bkm_rerun.battery()` already builds this as its second return value, so
    this reuses it rather than reconstructing the seven variants: rebuilding them
    here would be a second definition of the same books, and the two could drift.
    The cost is that the D1 books are re-run (a few seconds), which is why it is
    wrapped — a missing optional input should not take the whole table down.
    """
    try:
        from cesare.d1_bkm_rerun import battery
        _, episodes = battery()
    except Exception as exc:                                   # pragma: no cover
        print(f"  D1 rerun windows skipped ({type(exc).__name__}: {exc})")
        return None

    out = episodes[episodes["basis"] == "net"].copy()
    out = out.rename(columns={"n_days": "n_obs", "worst_day": "worst_obs"})
    out["owner"] = "Cesare"
    out["workstream"] = "Phase 3 D1 rerun (null, model-free)"
    out["basis"] = "daily_net"
    out["note"] = ("matched 21-name option universe, not the ALL-27 book; "
                   "rebuilt live from cesare/d1_bkm_rerun.py")
    return out


# ---------------------------------------------------------------------------

def main() -> None:
    base = run()
    print(f"baseline: {base!r}")
    eras, stress = episode_tables(base)
    print(f"  p4_episode_table_baseline.csv   {len(eras)} rows")
    print(f"  p4_stress_table_baseline.csv    {len(stress)} rows")
    legs = leg_table(base)
    print(f"  p4_leg_decomposition.csv        {len(legs)} rows, "
          f"max|resid| {legs['resid'].abs().max():.2e}")
    sweep = tenor_sweep()
    print(f"  tenor_sweep.csv                 {len(sweep)} rows")
    rv = reverdict()
    print(f"  p4_reverdict_tail_objective.csv {len(rv)} rows, "
          f"{int(rv['flipped'].sum())} verdicts flip")
    fc = final_comparison()
    print(f"  final_comparison.csv            {len(fc)} rows, "
          f"{fc['owner'].nunique()} owners, {int((~fc['on_base']).sum())} not on base")
    ep = final_comparison_by_episode()
    have = ep[ep["basis"] != "missing"]
    print(f"  final_comparison_by_episode.csv {len(ep)} rows, "
          f"{have['variant'].nunique()} variants on the frozen windows, "
          f"{int((ep['basis'] == 'missing').sum())} gaps recorded")


if __name__ == "__main__":
    main()
