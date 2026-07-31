"""Build the regime-switching notebook.

Writes the same notebook to both places it needs to live: this repository's own
`notebooks/`, and the personal folder of the team project where the shared base book and the
raw panels are. One builder, so the two copies cannot drift apart.

    python scripts/notebooks/build_regime_switching.py

The notebook itself locates both repositories at run time rather than assuming a working
directory, so either copy executes from wherever it sits.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _nb import code, md, write  # noqa: E402

FXCARRY_ROOT = Path(__file__).resolve().parents[2]
TEAM_ROOT = FXCARRY_ROOT.parent / "FX_Carry_26_Summer_PL"

DESTINATIONS = [
    FXCARRY_ROOT / "notebooks" / "05_regime_switching_carry.ipynb",
    TEAM_ROOT / "dafu" / "regime_switching_carry.ipynb",
]

cells = []


cells.append(md(r"""
# Regime switching on the carry book

A carry book spends most of its life being boring. The interest differential accrues, the spot
rates wander, and the monthly return lands somewhere near a percent. Then, every few years,
every position turns over at once and the book gives back two years of accrual in a quarter.
The 27-currency book underneath this notebook has a monthly return skew of about $-0.65$ and a
worst drawdown near 29%. That asymmetry is the whole reason carry pays anything: you are being
compensated for holding a position that occasionally detonates.

It also makes regime switching almost impossible to resist. If the bad months arrive in
clusters, and if something observable marks the clusters while they are happening, then a
model that recognises the cluster and stands aside should collect the accrual without the
detonation. The literature is full of versions of this, most of them reporting that it works.

What follows is an attempt to find out whether it works here, under the constraint that
matters most and is easiest to break: at every date, the model may only use what a person
sitting at that date could have known. That turns out to be the entire story. Five different
regime models, spanning latent-state estimators, a rule on an observable, and a supervised
classifier, all improve the book when they are allowed a peek at the future, and all fail to
improve it when they are not.

The second half of the notebook puts the same question to the instrument built for the job.
A carry crash is what an FX put is for, and the option market has been quoting a price for it
throughout. That turns out to change the problem rather than solve it: the obstacle there is a
premium rather than a model, and knowing the regime does not buy the premium down.

This notebook needs two repositories side by side. The estimators come from `fxcarry`, and the
book, the raw panels and the data plumbing come from the team project `FX_Carry_26_Summer_PL`.
The setup cell below finds both from wherever it is being run, so the same file executes
unchanged out of either checkout. Point `FX_CARRY_PL_ROOT` at the team repository if it does
not sit beside this one.
"""))


cells.append(md(r"""
## The book everything is measured against

Every variant here differs from one shared baseline by exactly one thing: a monthly exposure
multiplier. The baseline is the project's team book, and using it rather than building another
one is deliberate. A gate measured against its author's own private construction tells you
nothing about the gate, only about the pair.

The base is a quintile sort on forward-implied carry across 27 currencies, inverse-volatility
weighted within each leg, targeted to 10% annualised volatility, rebalanced monthly, and
charged real bid/ask half-spreads with maintained notional rolled at the points spread. It
runs from May 2007 to June 2026. Its net Sharpe is 0.4659 against 0.6284 gross, so roughly a
sixth of a Sharpe point is eaten by costs before any overlay exists.

The exposure hook matters more than it looks. It scales *weights*, not returns, which means a
gate pays the transaction costs of the trades it triggers. Applying a multiplier to a finished
return series instead is free, and free de-risking makes every risk rule look better than it
is.
"""))


cells.append(code(r"""
import os
import sys
import warnings
from pathlib import Path

warnings.filterwarnings("ignore")


def locate_repositories():
    # Both checkouts, found from the working directory rather than assumed. The team project
    # holds the base strategy, the raw panels and the `regime_lab` plumbing; the library holds
    # the estimators. Whichever library checkout this notebook is sitting inside wins, so
    # running the copy in fxcarry tests fxcarry's own source.
    here = Path.cwd().resolve()
    candidates = [here, *here.parents]

    override = os.environ.get("FX_CARRY_PL_ROOT")
    team = Path(override).resolve() if override else None
    if team is None:
        team = next((p for p in candidates if (p / "strategy" / "core.py").is_file()), None)
    if team is None:
        for parent in candidates:
            guess = parent / "FX_Carry_26_Summer_PL"
            if (guess / "strategy" / "core.py").is_file():
                team = guess.resolve()
                break
    if team is None:
        raise RuntimeError(
            "Could not find FX_Carry_26_Summer_PL. Put it beside this repository, or set "
            "FX_CARRY_PL_ROOT to its path."
        )

    library = next(
        (p / "src" for p in candidates if (p / "src" / "fxcarry" / "__init__.py").is_file()),
        None,
    )
    if library is None:
        library = team / "dafu" / "fxcarry" / "src"
    if not (library / "fxcarry" / "__init__.py").is_file():
        raise RuntimeError(f"No fxcarry source at {library}.")
    return team, library.resolve()


TEAM, LIBRARY = locate_repositories()
for path in (TEAM, LIBRARY, TEAM / "dafu"):
    sys.path.insert(0, str(path))

print(f"team project : {TEAM}")
print(f"fxcarry      : {LIBRARY}")
"""))


cells.append(code(r"""
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from fxcarry.compare import Comparison
from fxcarry.regimes import (
    LogisticRegime,
    MarkovSwitching,
    TrailingPercentile,
    binary_gate,
    linear_gate,
    power_gate,
)
from fxcarry.stats import HAC
from strategy import fx_utils as fx, run

import regime_lab as lab

pd.set_option("display.width", 200)
pd.set_option("display.max_columns", 40)

# Okabe-Ito, the standard colour-blind-safe qualitative set. Assigned in a fixed order and
# never recycled, so a series keeps its colour when the chart it appears in changes.
INK = "#111111"
PALETTE = ["#000000", "#0072B2", "#D55E00", "#009E73", "#CC79A7", "#E69F00", "#56B4E9"]
plt.rcParams.update({
    "figure.figsize": (11, 4.5), "figure.dpi": 110,
    "axes.spines.top": False, "axes.spines.right": False,
    "axes.edgecolor": "#999999", "axes.labelcolor": INK, "axes.titlesize": 11,
    "axes.titlelocation": "left", "axes.titlepad": 10,
    "text.color": INK, "xtick.color": "#666666", "ytick.color": "#666666",
    "grid.color": "#DDDDDD", "grid.linewidth": 0.6, "axes.grid": True,
    "axes.axisbelow": True, "legend.frameon": False, "lines.linewidth": 1.6,
    "font.size": 9.5,
})

# Derived tables land beside whichever copy of the notebook is running, never in the other
# repository.
OUT = Path.cwd() / "outputs"
OUT.mkdir(exist_ok=True)
"""))


cells.append(code(r"""
base = run(name="baseline")
monthly = base.monthly("net")

print(f"universe        {len(base.universe)} currencies")
print(f"window          {base.window[0].date()} to {base.window[1].date()}")
print(f"months          {len(monthly)}")
base.summary(benchmark=None).round(4).T
"""))


cells.append(md(r"""
## Three ways to answer the same question

Most of the difficulty in this exercise is not estimation. It is that nearly every convenient
way to report a regime probability quietly looks backwards, and the resulting numbers are
better than anything you could have traded.

Take a two-state Markov model fitted to the book's monthly returns. The smoothed probability
for September 2008 is the model's opinion having read every month through 2026. The filtered
probability at that date only reads the past, which sounds fixed, except the parameters
driving the filter were still estimated on the whole sample, so the filter already knows how
volatile the volatile state is going to turn out to be. Only re-estimating the parameters on
an expanding window removes both problems.

`fxcarry.regimes` makes that choice explicit rather than implicit. Every estimator takes an
`information` argument with three values:

`insample` uses the whole sample for parameters and for state inference. Nobody could trade
it. It is here so the size of the illusion can be measured instead of argued about.

`filtered` takes parameters from the whole sample and infers states recursively. This is the
halfway house, and in my experience it is the one that gets published without comment.

`realtime` re-estimates parameters on an expanding window and infers states recursively. At
date $t$ nothing has touched data after $t$.

The module tests this rather than asserting it. Truncating the sample and recomputing must
leave every earlier `realtime` probability bit-identical, and the same check is run against
`insample` and required to *fail*, because a no-lookahead test that passes under every
configuration is not testing anything.
"""))


cells.append(code(r"""
features = lab.build_features(monthly, base.signal)
labels = lab.loss_labels(monthly)
fxvol = lab.fx_volatility()
fxvol_change = np.log(fxvol).diff().dropna().rename("d_log_fx_vol")
equity = lab.month_end(fx.load_wide("global_risk")["MXWO"]).pct_change().dropna()

print(f"conditioning features : {features.shape[1]} series, {features.shape[0]} months")
print(f"losing months         : {int(labels.sum())} of {len(labels)} ({labels.mean():.1%})")
print()
print(features.tail(3).round(3).T.to_string())
"""))


cells.append(md(r"""
## Five models, and why the stressed state is named before anything is run

The models differ in what they read and how much structure they assume.

`MS-book` is a two-state Markov switching model on the book's own monthly net return. It is
the textbook version and also the most self-referential: it conditions on the very series it
is trying to protect.

`MS-equity` is the same estimator on world equity monthly returns, which removes the
circularity by looking outside the book entirely.

`MS-fxvol` is the same estimator again on the monthly change in log FX implied volatility.
A carry book is short FX volatility rather than short equity volatility, and the two have
disagreed about which was happening more than once.

`Vol-rank` is not a model at all. It is where FX implied volatility sits in its own trailing
five-year distribution. It exists as the bar the estimators have to clear, because most of
what a regime model knows about a crisis is that volatility was high, and a percentile rank
knows that too.

`Logit` is a ridge logistic regression on twelve macro and market features, trained to predict
whether next month loses money. Standardisation happens inside each fold and the classifier
only ever trains on labels that have already resolved.

There is one decision that has to be made before any of these is run, and getting it wrong
costs more than any tuning parameter. A two-state model does not know which of its states is
the bad one; the likelihood is unchanged if you swap the labels. So the stressed state has to
be identified from the fitted parameters, and the rule has to come from what the series *is*.
For a profit and loss series the bad state is the one that loses money. For a series of
volatility changes it is the one where volatility jumps. Picking the rule that backtests best
is a second helping of exactly the hindsight this whole exercise is trying to measure, and
there is a section below showing what that costs.
"""))


cells.append(code(r"""
SPECS = {
    "MS-book":   dict(kind="markov", data=monthly,      stressed="low_mean",
                      sets=("insample", "filtered", "realtime")),
    "MS-equity": dict(kind="markov", data=equity,       stressed="low_mean",
                      sets=("insample", "filtered", "realtime")),
    "MS-fxvol":  dict(kind="markov", data=fxvol_change, stressed="high_mean",
                      sets=("insample", "filtered", "realtime")),
    "Vol-rank":  dict(kind="percentile", data=fxvol,    sets=("insample", "realtime")),
    "Logit":     dict(kind="logit", data=features,      sets=("insample", "realtime")),
}


def model_for(label, spec, information):
    # The estimator for one model under one information set.
    if spec["kind"] == "markov":
        return MarkovSwitching(information=information, stressed=spec["stressed"],
                               min_periods=60, refit_every=12, name=f"{label} [{information}]")
    if spec["kind"] == "percentile":
        return TrailingPercentile(information=information, window=60, min_periods=36,
                                  name=f"{label} [{information}]")
    return LogisticRegime(labels, information=information, ridge=1.0, min_periods=60,
                          refit_every=3, name=f"{label} [{information}]")


paths = {}
for label, spec in SPECS.items():
    for information in spec["sets"]:
        paths[(label, information)] = model_for(label, spec, information).probabilities(spec["data"])
    print(f"{label:10s} " + "  ".join(
        f"{i}: {paths[(label, i)].stressed_share:.3f}" for i in spec["sets"]))
"""))


cells.append(md(r"""
## What the switching models actually found

Before trusting a probability path it is worth looking at the states behind it. The table below
reports the last fitted parameter set for each Markov model in per-month percent, alongside the
persistence of each state.

Two things stand out. On the book's own returns the full-sample fit separates a normal state
averaging $+0.74\%$ a month from a crash state averaging $-8.2\%$, and the crash state is
transient: once in it, the model expects to leave with probability 0.67 the following month.
That is a sensible description of a carry unwind. The standard deviations of the two states,
however, are 2.91% and 3.42%, barely different. The states here are separated by their means,
not their variances, which is precisely why identifying the stressed state by variance is the
wrong call on this series.

On FX volatility changes the separation is enormous and in the other direction: a quiet state
drifting at $-0.79\%$ a month against a spike state averaging $+34\%$. That model knows exactly
what it is looking for. Whether the book cares is a different question.
"""))


cells.append(code(r"""
fitted = {}
for label, spec in SPECS.items():
    if spec["kind"] != "markov":
        continue
    for information in ("insample", "realtime"):
        row = paths[(label, information)].parameters.iloc[-1]
        fitted[(label, information)] = {
            "mean_0_%": 100 * row["const[0]"], "sd_0_%": 100 * np.sqrt(row["sigma2[0]"]),
            "mean_1_%": 100 * row["const[1]"], "sd_1_%": 100 * np.sqrt(row["sigma2[1]"]),
            "P(stay in 0)": row["p[0->0]"], "P(leave 1)": row["p[1->0]"],
            "refits": len(paths[(label, information)].parameters),
        }

fitted = pd.DataFrame(fitted).T
fitted.index = pd.MultiIndex.from_tuples(fitted.index, names=["model", "information"])
fitted.round(3)
"""))


cells.append(md(r"""
## Nobody is armed for the crisis

The next table is the one that reframed this project for me. It reports the first date each
model produces a probability at all.

A Markov switching model needs a few years of monthly data before its parameters mean
anything, and the shared panel begins in 2007. Five years of burn-in therefore puts the first
honest `realtime` probability in 2012. The models fitted on the whole sample, by contrast,
start producing opinions in early 2007, because they were estimated on data that includes
everything they are opining about.

The consequence is blunt. Not one of the real-time models was operating during the 2008
unwind, which is the largest carry drawdown in the sample and the event the entire idea of a
crisis gate exists to handle. They arm somewhere between 2010 and 2012 and are then evaluated
on a period whose worst episode is COVID. Anyone reporting a regime gate that "would have
avoided 2008" on a panel starting in 2007 has fitted the model on 2008 and then tested it on
2008.

This is a data problem before it is a modelling problem, and it has a price tag: risk-factor
history reaching back to the 1990s would let a model be armed *for* a crisis rather than
calibrated *after* one.
"""))


cells.append(code(r"""
activity = {}
for (label, information), series in paths.items():
    prob = series.probability
    activity[f"{label} [{information}]"] = {
        "armed from": str(prob.index[0].date()),
        "months": len(prob),
        "mean P(stress)": prob.mean(),
        "months P>0.5": float((prob > 0.5).mean()),
        "months P>0.9": float((prob > 0.9).mean()),
    }
pd.DataFrame(activity).T
"""))


cells.append(code(r"""
realtime_probs = pd.DataFrame({k: paths[(k, "realtime")].probability for k in SPECS}).dropna()

fig, axes = plt.subplots(len(SPECS), 1, figsize=(11, 9), sharex=True)
for ax, (label, colour) in zip(axes, zip(SPECS, PALETTE[1:])):
    series = paths[(label, "realtime")].probability
    ax.fill_between(series.index, 0, series.values, color=colour, alpha=0.30, lw=0)
    ax.plot(series.index, series.values, color=colour, lw=1.3)
    ax.set_ylim(0, 1)
    ax.set_yticks([0, 0.5, 1])
    ax.set_ylabel(label, rotation=0, ha="right", va="center", labelpad=42)
axes[0].set_title("Probability the book is in the stressed state, using only data available at the time")
axes[-1].set_xlabel("")
fig.tight_layout()
plt.show()
"""))


cells.append(md(r"""
Those five paths are supposed to be measuring the same thing. They are not. `MS-fxvol` fires on
0.9% of months and is close to a no-op; `MS-equity` and `Vol-rank` sit near 40%; `Logit`
hovers around a coin flip without ever committing past 0.9.

Their correlations make the disagreement precise. The largest positive pairing is `MS-equity`
with `Vol-rank` at 0.46, which is unsurprising since equity drawdowns and volatility spikes
are close cousins. `Logit` is *negatively* correlated with both, around $-0.5$ and $-0.42$.
The supervised model, having been told what a bad outcome looks like, has concluded that
something other than high volatility predicts it.

I do not think that is a bug. It is a warning that "regime" is not one thing. These models are
answering different questions and there is no reason their answers should agree, which also
means picking the one whose answer you like is a choice with consequences.
"""))


cells.append(code(r"""
agreement = realtime_probs.corr()
print(f"overlapping window: {realtime_probs.index[0].date()} to {realtime_probs.index[-1].date()}"
      f"  ({len(realtime_probs)} months)")
agreement.round(3)
"""))


cells.append(md(r"""
## The headline

Each real-time probability is mapped to exposure by the gentlest available rule: hold the full
book when the stressed state is impossible, hold nothing when it is certain, and interpolate
in between. Nothing is tuned. The last row is the rule already sitting in the shared codebase,
which halves exposure when VIX is in the top fifth of its trailing three years, carried along
because a new model that cannot beat the rule you already have has not earned its parameters.
"""))


cells.append(code(r"""
runs = {"baseline": base}
for label in SPECS:
    runs[label] = run(exposure=linear_gate(paths[(label, "realtime")].probability), name=label)
runs["VIX-rule (incumbent)"] = run(exposure=lab.vix_percentile_gate(), name="VIX-rule")

headline = lab.variant_table(runs, benchmark=None)
headline["avg notional"] = [lab.average_exposure(r) for r in runs.values()]
headline.round(4)
"""))


cells.append(md(r"""
Not one of them improves the book.

The baseline nets 0.4659. `MS-fxvol` lands at 0.4629 and the incumbent VIX rule at 0.4653, and
both of those are dead heats rather than results: `MS-fxvol` barely trades, and its gross
notional of 3.216 against the baseline's 3.232 tells you it is the same book. The three models
that actually take a view all lose. `Logit` gives up 0.08 of Sharpe, `Vol-rank` 0.15,
`MS-book` 0.16, and `MS-equity`, the only one with no connection at all to FX, 0.20.

Turnover explains part of it but not most of it. The gates raise cost drag by at most a few
basis points a year, and `Logit` and `Vol-rank` actually trade *less* than the baseline
because the de-risked months need smaller rebalances. The gross Sharpe column moves almost as
much as the net one, which is the giveaway: these gates are not being killed by transaction
costs, they are getting the timing wrong.
"""))


cells.append(code(r"""
comparison = Comparison({k: v.net for k, v in runs.items()}, periods_per_year=252.0,
                        baseline="baseline")
comparison.save(OUT / "returns_net_daily.parquet")
Comparison({k: v.gross for k, v in runs.items()}, 252.0, "baseline").save(
    OUT / "returns_gross_daily.parquet")

fig, (top, bottom) = plt.subplots(2, 1, figsize=(11, 8), sharex=True,
                                  gridspec_kw={"height_ratios": [1.4, 1]})
nav, drawdown = comparison.nav(), comparison.drawdown()
for (name, colour) in zip(nav.columns, PALETTE):
    width = 2.4 if name == "baseline" else 1.3
    top.plot(nav.index, nav[name], color=colour, lw=width, label=name)
    bottom.plot(drawdown.index, drawdown[name], color=colour, lw=width)
top.set_yscale("log")
top.set_ylabel("growth of 1")
top.set_title("Every gate on the same book, net of costs")
top.legend(ncol=4, loc="upper left")
bottom.set_ylabel("drawdown")
bottom.axhline(0, color="#999999", lw=0.8)
fig.tight_layout()
plt.show()
"""))


cells.append(md(r"""
## How much of a regime gate is hindsight

This is the result I would keep if I could keep only one.

The table re-runs every model under every information set it supports, changing nothing else.
Same estimator, same data, same gate, same book. The only thing that varies is how much of the
future the model was allowed to see while forming its opinion.
"""))


cells.append(code(r"""
ladder_rows = {}
for label, spec in SPECS.items():
    for information in spec["sets"]:
        result = run(exposure=linear_gate(paths[(label, information)].probability),
                     name=f"{label}|{information}")
        summary = result.summary(benchmark=None)
        net = summary.loc[[i for i in summary.index if i.endswith("_net")][0]]
        gross = summary.loc[[i for i in summary.index if i.endswith("_gross")][0]]
        ladder_rows[(label, information)] = {
            "net_sharpe": net["sharpe"], "gross_sharpe": gross["sharpe"],
            "max_dd": net["max_drawdown"], "ann_return": net["ann_return"],
            "turnover": result.turnover,
        }

ladder = pd.DataFrame(ladder_rows).T
ladder.index = pd.MultiIndex.from_tuples(ladder.index, names=["model", "information"])
ladder["vs baseline"] = ladder["net_sharpe"] - headline.loc["baseline", "net_sharpe"]
ladder.round(4)
"""))


cells.append(code(r"""
order = ["insample", "filtered", "realtime"]
positions = {name: i for i, name in enumerate(order)}
bar = headline.loc["baseline", "net_sharpe"]

fig, ax = plt.subplots(figsize=(9, 5))
ax.axhline(bar, color=PALETTE[0], lw=2.0, zorder=1)
ax.annotate(f"ungated baseline  {bar:.3f}", xy=(-0.22, bar + 0.006), va="bottom", ha="left",
            fontsize=9, color=PALETTE[0])
for (label, colour) in zip(SPECS, PALETTE[1:]):
    sub = ladder.loc[label]
    x = [positions[i] for i in sub.index]
    y = sub["net_sharpe"].to_numpy(float)
    ax.plot(x, y, color=colour, marker="o", markersize=7, lw=1.8, zorder=2)
    ax.annotate(label, xy=(x[-1] + 0.06, y[-1]), va="center", fontsize=9, color=colour)
ax.set_xticks(range(3))
ax.set_xticklabels(["in sample\n(sees everything)", "filtered\n(parameters see everything)",
                    "real time\n(sees nothing ahead)"])
ax.set_xlim(-0.25, 2.9)
ax.set_ylabel("net Sharpe")
ax.set_title("Take the future away and every regime model falls below the book it was gating")
ax.grid(axis="x", visible=False)
fig.tight_layout()
plt.show()
"""))


cells.append(md(r"""
Every line slopes down, without exception, and the ordering is the same for all five models.

In sample, four of the five beat the baseline, two of them by more than a tenth of a Sharpe
point. `Logit` reaches 0.599 against 0.466 and cuts the worst drawdown from 29% to 17%. Written
up on its own, with a plot of the probability path shaded over the drawdowns, it would look
like a good piece of work.

Filtering the states while keeping full-sample parameters removes between a third and a half of
the gain. `MS-book` falls from $+0.12$ to $+0.04$ relative to the baseline. So even the
halfway house, which many people would describe as out of sample because the state inference is
recursive, is carrying most of the advantage in its parameters.

Re-estimating the parameters honestly removes the rest, and then some. Every model ends below
the baseline. The sign of the conclusion is set by the information set, not by the model, the
data, or the gate. That is uncomfortable, because the information set is the part of a
published backtest you usually cannot check.
"""))


cells.append(md(r"""
## A second, quieter channel of hindsight

Parameter estimation is not the only place the future gets in. The choice of specification is
another, and it does not show up in any out-of-sample test, because by the time you run the
test you have already made the choice.

The identification rule is the cleanest example I found. Below, the same estimator runs on the
same data under the same real-time information set. The only difference is which fitted state
gets called "stressed".
"""))


cells.append(code(r"""
trap_rows = {}
for label, data, rules in (("MS-book", monthly, ("low_mean", "high_variance")),
                           ("MS-fxvol", fxvol_change, ("high_mean", "high_variance"))):
    for rule in rules:
        series = MarkovSwitching(information="realtime", stressed=rule,
                                 min_periods=60, refit_every=12).probabilities(data)
        result = run(exposure=linear_gate(series.probability), name=f"{label}|{rule}")
        summary = result.summary(benchmark=None)
        net = summary.loc[[i for i in summary.index if i.endswith("_net")][0]]
        trap_rows[(label, rule)] = {
            "mean P(stress)": series.probability.mean(), "net_sharpe": net["sharpe"],
            "max_dd": net["max_drawdown"], "ann_vol": net["ann_vol"],
            "avg notional": lab.average_exposure(result),
        }

trap = pd.DataFrame(trap_rows).T
trap.index = pd.MultiIndex.from_tuples(trap.index, names=["model", "stressed state rule"])
trap.round(4)
"""))


cells.append(md(r"""
Calling the higher-variance state stressed produces a net Sharpe of 0.605 on `MS-fxvol`, which
beats the baseline by 0.14 and would be the best number in this notebook by a distance. It is
also meaningless. That configuration flags 55% of all months as stressed, which is not a
description of a crisis, and there is no story under which "the state where volatility moves
erratically in either direction" is the state a carry book should sit out.

The `MS-book` row shows the same failure from the other side. Identifying by variance flags
83% of months. The reason is visible in the fitted parameters from earlier: on short expanding
windows the high-variance state is ordinary trading, and the low-variance state is doing the
work of catching a handful of outlier months. Labelling the ordinary state "stressed" leaves
the gate de-risked almost permanently, which drops volatility from 11.2% to 6.5% and drags the
Sharpe down with it.

So one identification rule halves the book for no reason and the other clears the baseline for
no reason, and neither has anything to do with whether regimes exist. If the rule that names
the bad state is chosen after seeing the equity curve, the backtest is measuring the choice,
not the model.
"""))


cells.append(md(r"""
## Does anything survive a sweep over the gate

The gate is a separate decision from the model, so pairing every real-time path with ten
mappings from probability to exposure asks whether the failure lies in the state estimates or
in how aggressively they were acted on. The sweep spans a linear rule at three floors, two
convex rules that only de-risk on strong conviction, and five threshold rules.
"""))


cells.append(code(r"""
GATES = {
    "linear, floor 0.00": lambda p: linear_gate(p, floor=0.0),
    "linear, floor 0.25": lambda p: linear_gate(p, floor=0.25),
    "linear, floor 0.50": lambda p: linear_gate(p, floor=0.50),
    "power 2, floor 0.00": lambda p: power_gate(p, exponent=2.0, floor=0.0),
    "power 3, floor 0.00": lambda p: power_gate(p, exponent=3.0, floor=0.0),
    "cut to 0.0 above 0.50": lambda p: binary_gate(p, 0.50, floor=0.0),
    "cut to 0.5 above 0.50": lambda p: binary_gate(p, 0.50, floor=0.5),
    "cut to 0.0 above 0.70": lambda p: binary_gate(p, 0.70, floor=0.0),
    "cut to 0.5 above 0.70": lambda p: binary_gate(p, 0.70, floor=0.5),
    "cut to 0.5 above 0.90": lambda p: binary_gate(p, 0.90, floor=0.5),
}

sweep_rows = {}
for label in SPECS:
    prob = paths[(label, "realtime")].probability
    for gate_name, gate in GATES.items():
        result = run(exposure=gate(prob), name=f"{label}|{gate_name}")
        summary = result.summary(benchmark=None)
        net = summary.loc[[i for i in summary.index if i.endswith("_net")][0]]
        sweep_rows[(label, gate_name)] = {"net_sharpe": net["sharpe"],
                                          "max_dd": net["max_drawdown"],
                                          "avg notional": lab.average_exposure(result)}

sweep = pd.DataFrame(sweep_rows).T
sweep.index = pd.MultiIndex.from_tuples(sweep.index, names=["model", "gate"])
sharpe_grid = sweep["net_sharpe"].unstack(0)
sharpe_grid.round(4)
"""))


cells.append(code(r"""
fig, ax = plt.subplots(figsize=(10, 5))
ax.axvline(bar, color=PALETTE[0], lw=2.0, zorder=1)
rows = list(sharpe_grid.index)[::-1]
ax.set_ylim(-0.8, len(rows) - 0.2)
ax.annotate(f"ungated baseline {bar:.3f}", xy=(bar - 0.004, -0.7), fontsize=9,
            color=PALETTE[0], va="bottom", ha="right")
for (label, colour) in zip(SPECS, PALETTE[1:]):
    ax.scatter(sharpe_grid.loc[rows, label], range(len(rows)), s=46, color=colour,
               label=label, zorder=3, edgecolor="white", linewidth=0.8)
ax.set_yticks(range(len(rows)))
ax.set_yticklabels(rows)
ax.set_xlabel("net Sharpe")
ax.set_title("Fifty gate and model pairs, none of them above the line")
ax.legend(ncol=3, loc="lower center", bbox_to_anchor=(0.5, -0.28))
ax.grid(axis="y", visible=False)
fig.tight_layout()
plt.show()

print(sharpe_grid.agg(["min", "median", "max"]).round(4).to_string())
"""))


cells.append(md(r"""
Fifty combinations, and the highest value anywhere in the grid is 0.4659. It occurs four times,
three of them in the `MS-book` column and one in `Logit`, and in every case it is a threshold
the model's stress probability never actually crosses. Those cells are the baseline to four
decimal places because the gate attached to them never fires once. The optimum of this sweep is
the configuration in which the gate does nothing at all.

The pattern within each column says the same thing more gently. Sharpe rises monotonically
with the floor, from 0.302 to 0.394 on `MS-book` as the floor goes from zero to a half, and
rises again as the threshold moves from 0.50 to 0.90. Every direction that makes a gate less
active makes it better. There is no interior plateau, which is what a real effect would look
like.

The spread across gates is worth quoting next to any single cell. `MS-book` ranges from 0.302
to 0.466 depending only on how the same probabilities are acted on, and `Vol-rank` from 0.174
to 0.463.
"""))


cells.append(md(r"""
## Is the burn-in the problem

If the real-time models fail mainly because they arm too late, shortening the burn-in should
help. It does, a little, and in a way that argues against the models rather than for them.
"""))


cells.append(code(r"""
burn_rows = {}
for min_periods in (36, 60, 84):
    estimators = (
        ("MS-book", MarkovSwitching(information="realtime", stressed="low_mean",
                                    min_periods=min_periods, refit_every=12)),
        ("Logit", LogisticRegime(labels, information="realtime", ridge=1.0,
                                 min_periods=min_periods, refit_every=3)),
    )
    for label, estimator in estimators:
        series = estimator.probabilities(SPECS[label]["data"])
        result = run(exposure=linear_gate(series.probability), name=f"{label}|{min_periods}")
        summary = result.summary(benchmark=None)
        net = summary.loc[[i for i in summary.index if i.endswith("_net")][0]]
        burn_rows[(label, min_periods)] = {
            "armed from": str(series.probability.index[0].date()),
            "net_sharpe": net["sharpe"], "max_dd": net["max_drawdown"],
        }

burn = pd.DataFrame(burn_rows).T
burn.index = pd.MultiIndex.from_tuples(burn.index, names=["model", "burn-in months"])
burn
"""))


cells.append(md(r"""
Three years of burn-in arms the models in 2010 and lifts `Logit` to 0.462, within a whisker of
the baseline, and `MS-book` to 0.329. Seven years pushes them to 2014 and drops both. So
shorter is better, monotonically, across the range.

The natural reading is that more live history helps. The less flattering reading, which I think
is the right one, is that shorter burn-in simply means fewer months of gating, and a gate that
does less does better. It is the sweep result again in a different costume. Either way, none of
the three arms in time for 2008, and the best of them still only draws level with doing
nothing.
"""))


cells.append(md(r"""
## The drawdown argument, and why it does not hold

There is a defence available at this point, and it is a reasonable one. Sharpe is not why
anyone runs a crisis gate. You run it so the bad quarter is survivable, and the headline table
does show `Logit` cutting the worst drawdown from 29.3% to 23.6% and the VIX rule to 24.5%.

The problem is that all of these books hold less risk than the baseline, and a smaller position
has a smaller drawdown whether or not it was ever timed well. Separating the two means putting
every book on the same realised volatility and looking again. That rescaling is not a portfolio
anyone could run, since the scale factor is a full-sample number, but it isolates the question
of whether the risk was held at better moments.
"""))


cells.append(code(r"""
rescaled = Comparison(comparison.rescaled(), 252.0, "baseline").table()
rescaled = rescaled[["mean", "volatility", "sharpe", "max_drawdown"]]
observed = headline[["ann_vol", "max_dd"]].rename(
    columns={"ann_vol": "vol as run", "max_dd": "drawdown as run"})
observed.join(rescaled[["max_drawdown"]].rename(
    columns={"max_drawdown": "drawdown at equal vol"})).round(4)
"""))


cells.append(md(r"""
At equal volatility the drawdown improvement does not survive. `Logit` goes from 23.6% to
31.9%, worse than the baseline's 29.3%. `MS-book` goes to 38.5% and `Vol-rank` to 36.6%. The
apparent tail protection was the de-leveraging, and once you give the money back to the book to
maintain the same risk, these gates have you carrying it into worse moments than the ungated
version would have.

One book breaks the pattern. The incumbent VIX rule holds 25.8% at equal volatility against the
baseline's 29.3%, with Sharpe essentially unchanged at 0.4653. It is the only construction in
this notebook that improves anything after the risk budget is held fixed, and what it improves
is the shape of the tail rather than the return.

The statistical picture is consistent with all of this. The active return of each gate against
the baseline, with Newey-West standard errors, is negative for every model. It is significantly
negative for the four that take real positions, with $t$ statistics between $-2$ and $-4$, and
indistinguishable from zero for the two that barely trade. Nothing anywhere is significantly
positive.
"""))


cells.append(code(r"""
relative = comparison.relative(hac=HAC(lags=10))
relative[["sharpe", "sharpe_delta", "active_return", "tracking_error", "info_ratio",
          "active_t", "corr_to_baseline"]].round(4)
"""))


cells.append(code(r"""
episodes = comparison.subperiods(lab.EPISODES, field="sharpe")
episodes.round(3)
"""))


cells.append(md(r"""
The episode table shows why single-crisis anecdotes are so persuasive and so useless. The first
three rows are identical across every column because the real-time models had not started yet.
After that the gates trade wins for losses with no pattern: `MS-equity` softens COVID, going
$-0.70$ against the baseline's $-1.26$, then gives it all back through 2021 to 2023 at 0.20
against 0.70. `Logit` is the best book of any through the tightening period and the worst
through the euro crisis.

Pick your episode and you can support any conclusion you like, which is a good reason to
distrust anyone who leads with one.
"""))


cells.append(md(r"""
## The instrument actually designed for this

Everything so far hedges by holding less. That is a strange way to buy crash protection when
there is an instrument built for it, and when the option market has been quoting a price for
the exact risk these models are trying to dodge the whole time.

The quoted surface gives three points per currency and tenor: the at-the-money volatility, the
risk reversal, and the butterfly, at the 25 and 10 delta wings. The team panel carries every
point for 21 of the book's 27 currencies, missing the six EM names whose options were never
downloaded. `vol_surface_panel` returns the risk reversal already sign-normalised so that
positive means FX puts are rich against calls, which is the direction that hurts a long carry
position, so the volatility at a put wing is the at-the-money level plus the butterfly plus half
the risk reversal.

Turning that into a price takes a model, because a delta is a coordinate rather than a
moneyness. `fxcarry.options.Black76` does both halves: `strike_from_delta` inverts the quoted
delta into a strike, and `value` prices the option on the forward. Writing the option on the
forward rather than on spot is what keeps the two interest rates out of it, since the outright
forward has already priced their difference. The one rate that survives is the base currency's,
which enters the delta, and under covered interest parity that is the dollar rate plus the
carry the panel already reports.

Two things to hold on to about what follows. Everything is priced at mid, because the panel
carries option mids and no bid/ask, so every premium below is a floor on what it would really
cost. And a premium paid cannot go through the base's exposure hook, which moves weights rather
than returns, so this section prices the hedge rather than backtesting it.
"""))


cells.append(code(r"""
from fxcarry.options import Black76

TENOR_YEARS = 1 / 12
MODEL = Black76()
ATM = fx.vol_surface_panel("ATM", "1M")


def wing_vol(delta):
    # Volatility at a put wing: at-the-money, plus the butterfly, plus half the risk reversal.
    # The panel's risk reversal is already crash-positive, so the put wing takes +RR/2 where
    # the raw market convention would write -RR/2.
    rr = fx.vol_surface_panel("RR", "1M", delta)
    bf = fx.vol_surface_panel("BF", "1M", delta)
    shared = ATM.columns.intersection(rr.columns).intersection(bf.columns)
    return (ATM[shared] + bf[shared] + rr[shared] / 2.0) / 100.0


spot, carry = base.panels.spots, base.panels.carry
forward = spot * np.exp(-carry * TENOR_YEARS)              # carry is ln(S/F), annualised
usd_rate = (fx.load_wide("usd_riskfree")["USGG3M"] / 100.0).reindex(spot.index).ffill()
base_rate = carry.add(usd_rate, axis=0)                    # parity: foreign = dollar + carry
HEDGED = [c for c in base.weights.columns if c in wing_vol(25).columns]
print(f"option coverage: {len(HEDGED)} of {base.weights.shape[1]} currencies")
print("no quotes for:", sorted(set(base.weights.columns) - set(HEDGED)))


def put_premium(delta):
    # Premium of one out-of-the-money put, per unit of capital deployed. A unit of capital
    # buys 1/F of face at the forward, so the price divides by the same forward.
    vol = wing_vol(delta)[HEDGED].reindex(spot.index).ffill()
    fwd = forward[HEDGED]
    strike = MODEL.strike_from_delta(delta / 100.0, "put", fwd, vol, TENOR_YEARS,
                                     base_rate=base_rate[HEDGED])
    discount = pd.DataFrame(
        np.repeat(np.exp(-usd_rate * TENOR_YEARS).to_numpy()[:, None], len(HEDGED), axis=1),
        index=spot.index, columns=HEDGED)
    price = MODEL.value("put", fwd, strike, vol, TENOR_YEARS, discount=discount)
    return price / fwd, strike, vol


premium_25, strike_25, vol_25 = put_premium(25)
premium_10, _, _ = put_premium(10)
STRUCTURES = {"outright 25d put": premium_25, "25/10 put spread": premium_25 - premium_10}
"""))


cells.append(code(r"""
# The strike has to reprice to the delta it came from, or the inversion is wrong.
recovered = MODEL.delta("put", forward[HEDGED], strike_25, vol_25, TENOR_YEARS,
                        base_rate=base_rate[HEDGED])
print(f"delta recovered from the fitted strike: "
      f"min {recovered.stack().min():.4f}, max {recovered.stack().max():.4f} (target -0.25)")

pd.DataFrame({
    "forward": forward[HEDGED].iloc[-1],
    "put vol": vol_25.iloc[-1],
    "strike": strike_25.iloc[-1],
    "strike / forward": (strike_25 / forward[HEDGED]).iloc[-1],
    "premium %": 100 * premium_25.iloc[-1],
    "spread premium %": 100 * (premium_25 - premium_10).iloc[-1],
}).dropna().round(4).head(12)
"""))


cells.append(md(r"""
## What it costs, and whether the regime models buy it any cheaper

The premium below is charged against the long leg of the book, rolled monthly, sized to whatever
the leg actually holds. `always` pays it every month. The other rows pay it in proportion to
each real-time regime probability, which is the natural way to make a hedge conditional on a
state rather than on a calendar.

The last column is the one to read. It divides what a policy paid by what the same number of
months would have cost bought blind, so it asks whether the model is picking cheap moments to
insure or merely insuring less often.
"""))


cells.append(code(r"""
long_leg = base.weights[HEDGED].clip(lower=0.0).resample("ME").last()
book_return = headline.loc["baseline", "ann_return"]

drag_rows = {}
for structure, premium in STRUCTURES.items():
    cost = (long_leg * premium.resample("ME").last()).sum(axis=1, min_count=1).dropna()
    drag_rows[(structure, "always")] = {"drag": 12 * cost.mean(), "months paid": 1.0}
    for label in SPECS:
        prob = paths[(label, "realtime")].probability.reindex(cost.index).fillna(0.0)
        drag_rows[(structure, f"when {label} says so")] = {
            "drag": 12 * (cost * prob).mean(), "months paid": prob.mean()}

drag = pd.DataFrame(drag_rows).T
drag.index = pd.MultiIndex.from_tuples(drag.index, names=["structure", "timing"])
always_cost = drag.xs("always", level="timing")["drag"]
drag["% of capital a year"] = 100 * drag["drag"]
drag["share of book return"] = drag["drag"] / book_return
drag["unit cost vs always"] = [
    row["drag"] / (row["months paid"] * always_cost[structure]) if row["months paid"] > 0 else np.nan
    for (structure, _), row in drag.iterrows()]

print(f"the book earns {100 * book_return:.2f}% a year")
drag[["% of capital a year", "months paid", "share of book return", "unit cost vs always"]].round(3)
"""))


cells.append(code(r"""
fig, ax = plt.subplots(figsize=(10, 4.2))
ax.axvline(100 * book_return, color=PALETTE[0], lw=2.0, zorder=1)
ax.annotate(f"what the book earns, {100 * book_return:.1f}%", xy=(100 * book_return + 0.15, -0.45),
            fontsize=9, color=PALETTE[0], va="bottom")
labels = list(drag.xs("outright 25d put", level="structure").index)[::-1]
for (structure, colour, marker) in (("outright 25d put", PALETTE[2], "o"),
                                    ("25/10 put spread", PALETTE[3], "D")):
    values = drag.xs(structure, level="structure").loc[labels, "% of capital a year"]
    ax.scatter(values, range(len(labels)), s=52, color=colour, marker=marker, label=structure,
               zorder=3, edgecolor="white", linewidth=0.8)
ax.set_ylim(-0.9, len(labels) - 0.3)
ax.set_yticks(range(len(labels)))
ax.set_yticklabels(labels)
ax.set_xlabel("premium paid, % of capital a year, at mid")
ax.set_title("Crash insurance on the long leg, against what the book makes")
ax.legend(loc="lower right")
ax.grid(axis="y", visible=False)
fig.tight_layout()
plt.show()
"""))


cells.append(md(r"""
Hedging the long leg outright, every month, costs 9.2% of capital a year against a book that
earns 5.2%. The insurance is roughly twice the strategy. Selling the 10 delta wing back to fund
part of it brings that to 5.7%, which is still more than the book makes. At mid, with no bid,
no offer and no slippage. Whatever else is true, continuously buying this protection is not a
strategy, it is a way of donating the carry to the option market.

Making the hedge conditional does cut the bill, and roughly in proportion to how often it pays.
`Vol-rank` insures a third of the months and pays about a third as much. That is the arithmetic
of buying less, not of buying better.

The last column separates those two. For four of the five models it sits just above one, between
1.01 and 1.04, meaning a month of protection bought on the model's say-so costs a few percent
more than a month bought at random. This is not a defect in the models. It is what they are
selecting on. The states they identify as stressed are the states where implied volatility is
already elevated, and elevated implied volatility is the price of the option going up. You
cannot time your way into cheap crash insurance, because the option market is reading the same
volatility the regime model is, and it repriced first.

`Logit` is the exception at 0.95, and consistently with its negative correlation to every
volatility measure earlier, it is the one model whose stress signal is not simply high
volatility. A five percent discount on insurance is not a strategy either, but it is the only
sign anywhere in this notebook that a regime model saw something the option market had not
already charged for.

`MS-fxvol` shows 1.77, which I would not read into: it pays in 0.7% of months, so the number
rests on barely more than a dozen observations.
"""))


cells.append(md(r"""
## The version that is actually affordable

If the premium cannot be paid, the remaining option is to use what the option market is saying
without buying anything from it. Trimming a long position is a crude substitute for owning a put
on it: it gives up the upside as well as the downside and it protects nothing below the trim,
but it costs a bid/ask spread on the forward instead of a volatility premium, and the panel can
price that honestly.

This goes through the base's `weight_overlay` hook, so it is a real book rather than a costing
exercise. The rule halves long positions in currencies whose crash insurance is in the top
quintile of its own trailing three years, judged only against data available at the time. The
conditional versions do the same thing with a depth that follows each regime probability,
rescaled so the average trim matches the static rule's. Without that rescaling the comparison
would once again be measuring how much each rule hedges rather than when.
"""))


cells.append(code(r"""
RISK_REVERSAL = fx.vol_surface_panel("RR", "1M", 25)


def expensive_longs(weights, ctx):
    # Where crash insurance sits in its own trailing three years, month-end and lagged one day,
    # the same no-lookahead convention the signal uses.
    rank = RISK_REVERSAL.reindex(weights.index).ffill().rolling(756, min_periods=378).rank(pct=True)
    rank = rank.resample(ctx.config.rebal).last().reindex(weights.index, method="ffill").shift(1)
    return (rank.reindex(columns=weights.columns) > 0.80).fillna(False) & (weights > 0)


def static_trim(weights, ctx):
    scale = pd.DataFrame(1.0, index=weights.index, columns=weights.columns)
    scale[expensive_longs(weights, ctx)] = 0.5
    return weights * scale


def timed_trim(probability, depth=0.5):
    # Same rule, depth following the regime probability, normalised to the static rule's
    # average so the difference reads as timing rather than as hedging more.
    scaled = (probability / probability.mean()).clip(upper=1.0 / depth)

    def overlay(weights, ctx):
        daily = scaled.reindex(weights.index, method="ffill").shift(1).fillna(0.0)
        cut = pd.DataFrame(np.repeat((depth * daily).to_numpy()[:, None], weights.shape[1], axis=1),
                           index=weights.index, columns=weights.columns)
        scale = pd.DataFrame(1.0, index=weights.index, columns=weights.columns)
        return weights * scale.mask(expensive_longs(weights, ctx), 1.0 - cut)

    return overlay


option_runs = {"baseline": base,
               "static option trim": run(weight_overlay=static_trim, name="static_trim")}
for label in SPECS:
    option_runs[f"trim timed by {label}"] = run(
        weight_overlay=timed_trim(paths[(label, "realtime")].probability), name=f"trim_{label}")

option_table = lab.variant_table(option_runs, benchmark=None)
option_comparison = Comparison({k: v.net for k, v in option_runs.items()}, 252.0, "baseline")
option_comparison.save(OUT / "option_returns_net_daily.parquet")
option_table["dd at equal vol"] = Comparison(option_comparison.rescaled(), 252.0,
                                             "baseline").table()["max_drawdown"]
option_table["avg notional"] = [lab.average_exposure(r) for r in option_runs.values()]
option_table[["gross_sharpe", "net_sharpe", "ann_return", "ann_vol", "max_dd",
              "dd at equal vol", "skew", "cvar_95", "avg notional"]].round(4)
"""))


cells.append(md(r"""
The static rule is the first thing in this notebook that buys a better tail without simply
holding less. It gives up 0.010 of Sharpe, which is a tenth of what the cheapest regime gate
cost, and in exchange the worst drawdown goes from 29.3% to 27.6%, the skew improves from
$-0.648$ to $-0.605$, and the 5% conditional loss falls. Most of that survives the equal
volatility test, at 28.9% against 29.3%, and it should, because the rule barely changes the size
of the book: average gross notional is 3.13 against 3.23. It is trimming specific currencies at
specific times rather than standing down.

Timing it by regime makes it worse in every case. The five conditional versions run from 0.368
to 0.460 in net Sharpe, all below the static rule's 0.456 except `MS-fxvol`, which is a near
no-op and lands at 0.460. The spread across the five is wider than the effect being measured,
which is the same pattern as the gate sweep and it means the same thing: the choice of timing
model is doing more work than the timing.

There is one honest complication. `MS-equity` timing gives the deepest drawdown improvement of
anything here, 26.6% as run and 27.3% at equal volatility, better than the static rule, at a
cost of 0.030 more Sharpe. If drawdown is what you are buying, that trade exists. I would not
lead with it off one cell of a five-cell table.
"""))


cells.append(md(r"""
## Where this leaves the book

Regime gating does not improve this carry book on this sample, and the failure is not marginal.
Five models covering three quite different families all land below the ungated baseline, the
best gate in a fifty-cell sweep is the one that never fires, and the drawdown protection
disappears the moment you control for how much risk was actually held.

The more useful finding is *why* published versions of this look better. Four of the five
models beat the baseline in sample and one of them by a lot, so the difference between a
positive and a negative write-up here is entirely the information set. Filtering the states
while leaving parameters fitted on the full sample, which is a very easy thing to do without
noticing, recovers about half of the illusion. A second and quieter channel runs through
specification: choosing which fitted state to call stressed swings `MS-fxvol` from 0.463 to
0.605, and that choice leaves no trace in any out-of-sample statistic.

Moving from exposure to options does not rescue it, and the reason is a price rather than a
model. Buying the 25 delta put on the long leg every month costs 9.2% of capital a year against
a book earning 5.2%, and funding it with the 10 delta wing only brings that to 5.7%. Both at
mid. Conditioning the purchase on a regime state cuts the bill roughly in proportion to how
often it pays, and the protection it buys costs a few percent more per month than protection
bought blind, because the states these models call stressed are the states where implied
volatility has already risen. The option market reads the same volatility and reprices first.
Whatever a regime model knows about crashes, it is not something it can buy cheaply.

Three things are worth carrying forward. The first is a data constraint with a price attached.
The shared panel starts in 2007, a regime model needs three to seven years of burn-in, and so
no honest gate in this notebook was armed during the 2008 unwind. Risk-factor history back to
the 1990s would let a model face a crisis it had not already been fitted on, and until that
exists any claim about regime models and carry crashes rests on two events, one of which is
inside the training window.

The second is that every option number here is a floor. The panel carries option mids with no
bid or offer, so a premium-paying hedge cannot yet be charged what it would really cost. That
does not change the conclusion, since a hedge already costing more than the book earns only
looks worse with a spread on it, but it does mean the affordable structures cannot be ranked
against each other properly until that data exists.

The third is what to run. The two constructions that improve anything are both simple and
neither estimates a state. Halving exposure when FX volatility is in the top fifth of its
trailing three years keeps the baseline's Sharpe and cuts the equal-risk drawdown from 29.3% to
25.8%. Halving the position in currencies whose crash insurance is in the top fifth of its own
trailing three years costs 0.010 of Sharpe and improves the drawdown, the skew and the
conditional loss together, while barely changing the size of the book. Both read the same
thing the Markov chains were estimating, both arm from the first day there is enough history to
rank against, and between them they have two parameters. On this evidence that is where I would
put the risk budget.
"""))


cells.append(code(r"""
summary_note = pd.concat([
    pd.DataFrame({
        "net sharpe": headline["net_sharpe"],
        "drawdown as run": headline["max_dd"],
        "drawdown at equal vol": rescaled["max_drawdown"],
        "avg notional": headline["avg notional"],
    }),
    pd.DataFrame({
        "net sharpe": option_table["net_sharpe"],
        "drawdown as run": option_table["max_dd"],
        "drawdown at equal vol": option_table["dd at equal vol"],
        "avg notional": option_table["avg notional"],
    }).drop("baseline"),
]).round(4)
summary_note.to_csv(OUT / "notebook_summary.csv")
summary_note
"""))


for destination in DESTINATIONS:
    written = write(cells, destination)
    print(f"wrote {written}  ({len(cells)} cells)")
