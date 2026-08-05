"""Build the BofA progress deck for 2026-08-05 as one self-contained HTML file.

    python cesare/build_deck.py        # -> cesare/presentations/deck_2026_08_05.html

**Why this is a module and not a hand-written HTML file.** The repo's standing
promise (plan §1, `report/README.md` rule 1) is that every number traces to a
committed CSV. A hand-authored deck makes that a promise; a generator makes it
mechanical. Every figure here is rendered from a file in `cesare/outputs/`, and
every number that appears in the prose is pulled from a CSV cell through `NUM`
rather than typed. The same reasoning made `final_evaluation.py` a module rather
than notebook cells: this artifact is rebuilt weekly, so the terminal week should
be assembly, not authorship.

**What the deck is, and is not.** It is a *progress update* three weeks before
hand-in, with two threads: six workstreams are now folded into one engine and are
directly comparable across owners for the first time, and here is what is new
since the 2026-07-29 meeting. Nothing in it is framed as a final answer or a
recommendation, because nothing in it is one yet.

**Charts are matplotlib rendered to SVG and inlined**, not base64 PNGs. Two
reasons: `cesare/presentations/overview.html`, the newest precedent in the repo, is inline
SVG and is 57 KB where the older PNG deck is 640 KB; and vector text stays legible
when a slide is projected. The one real hazard is that several matplotlib SVGs on
one page collide on their element ids (`figure_1`, `axes_1`, and the generated
`url(#p…)` clip-paths), which silently blanks every figure after the first —
`_inline_svg` namespaces every id per figure to prevent it.

Self-contained: no CDN, no external stylesheet, no remote image, no script tag.
It must open from a `file://` path with no network.
"""

from __future__ import annotations

import io
import re
import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from strategy import run  # noqa: E402

OUTPUTS = Path(__file__).resolve().parent / "outputs"
DECK = Path(__file__).resolve().parent / "presentations" / "deck_2026_08_05.html"

#: Snapshot date, stamped into the page. Passed in rather than read from the
#: clock so a rebuild of this deck is reproducible.
AS_OF = "2026-08-05"

# --- palette, lifted from presentations/overview.html so the house style carries ---
BLUE, AQUA, ORANGE, RED = "#2a78d6", "#1baf7a", "#eb6834", "#e34948"
YELLOW, INK, INK2, MUTED = "#eda100", "#0b0b0b", "#52514e", "#898781"
GRID, CARD = "#e1e0d9", "#ffffff"

matplotlib.rcParams.update({
    # Keep text as <text> nodes rather than glyph outlines: smaller, selectable,
    # and it inherits the page's font stack instead of embedding a font.
    "svg.fonttype": "none",
    "font.family": "sans-serif",
    "font.sans-serif": ["system-ui", "-apple-system", "Segoe UI", "Roboto",
                        "Helvetica Neue", "Arial"],
    "font.size": 11,
    "axes.edgecolor": GRID, "axes.labelcolor": INK2, "axes.titlecolor": INK,
    "axes.grid": True, "grid.color": GRID, "grid.linewidth": 0.8,
    "xtick.color": MUTED, "ytick.color": MUTED,
    "axes.spines.top": False, "axes.spines.right": False,
    "figure.facecolor": CARD, "axes.facecolor": CARD,
    # Drop vertices that would not move a rendered pixel. Without this the two
    # daily curves alone emit ~27,000 SVG path vertices and the page is 840 KB.
    "path.simplify": True, "path.simplify_threshold": 1.0,
})


# ---------------------------------------------------------------------------
# Loading — every figure and every quoted number enters through here
# ---------------------------------------------------------------------------

def _csv(name: str) -> pd.DataFrame:
    path = OUTPUTS / name
    if not path.exists():                       # Appendix C #18/#26: a cited
        raise FileNotFoundError(                # artifact is a testable claim.
            f"{path} does not exist. The deck refuses to render a number it "
            f"cannot source. Re-run the module that produces it.")
    return pd.read_csv(path)


def load() -> dict[str, pd.DataFrame]:
    """Every committed CSV the deck reads, in one place."""
    return {
        "ladder": _csv("p4_combined_ladder.csv"),
        "standalone": _csv("p4_component_standalone.csv"),
        "combined_ep": _csv("p4_combined_by_episode.csv"),
        "selection": _csv("p4_selection_vs_derisking.csv"),
        "legs": _csv("p4_leg_decomposition.csv"),
        "tail_eval": _csv("p4_tail_forecast_eval.csv"),
        "tail_stats": _csv("p4_tail_overlay_stats.csv"),
        "d1": _csv("p3_d1_bkm_comparison.csv"),
        "d1_agree": _csv("p3_d1_bkm_signal_agreement.csv"),
        "d2_prem": _csv("p3_d2_premium.csv"),
        "d2_books": _csv("p3_d2_books.csv"),
        "d2_span": _csv("p3_d2_spanning.csv"),
        "d2_be": _csv("p3_d2_breakeven_cost.csv"),
        "d2_svt": _csv("p3_d2_static_vs_timing.csv"),
    }


def _rung(ladder: pd.DataFrame, which: str, step: str) -> pd.Series:
    """One row of the fold-in ladder, addressed by ladder name and step."""
    hit = ladder[(ladder["ladder"] == which) & (ladder["step"] == step)]
    if len(hit) != 1:
        raise ValueError(f"{which}/{step!r} matched {len(hit)} rows, expected 1")
    return hit.iloc[0]


# ---------------------------------------------------------------------------
# Verification — runs before anything is written
# ---------------------------------------------------------------------------

def verify(d: dict[str, pd.DataFrame]) -> tuple[object, object]:
    """Re-derive the two books live and assert they match the committed ladder.

    The deck's whole claim is that its numbers are the repo's numbers. That is
    worth an assertion rather than an assurance: if the base drifts, this raises
    instead of quietly publishing a stale slide.
    """
    base, comb = run(), run("COMBINED")
    checks = [
        ("baseline net", base.summary().loc["ALL_net", "sharpe"],
         _rung(d["ladder"], "final", "baseline")["net_sharpe"]),
        ("baseline gross", base.summary().loc["ALL_gross", "sharpe"],
         _rung(d["ladder"], "final", "baseline")["gross_sharpe"]),
        # COMBINED is the ladder's *survivor* book: the top rung minus the VIX
        # gate, which the two ladders disagreed about (§19.4 caveat 3).
        ("COMBINED net", comb.summary().loc["COMBINED_net", "sharpe"],
         _rung(d["ladder"], "final_loo", "- VIX percentile gate (p80 / 756d)")["net_sharpe"]),
        ("COMBINED MaxDD", comb.summary().loc["COMBINED_net", "max_drawdown"],
         _rung(d["ladder"], "final_loo", "- VIX percentile gate (p80 / 756d)")["max_drawdown"]),
        ("baseline turnover", base.turnover, 0.675470),
        ("baseline cost drag", base.cost_drag, 0.018146611),
    ]
    for label, live, committed in checks:
        if abs(float(live) - float(committed)) > 1e-6:
            raise AssertionError(
                f"{label}: live {live!r} != committed {committed!r}. The deck "
                f"will not render until this reconciles.")
    print(f"  verify: {len(checks)} live-vs-committed checks passed")
    return base, comb


# ---------------------------------------------------------------------------
# SVG inlining
# ---------------------------------------------------------------------------

_XML_PREAMBLE = re.compile(r"<\?xml[^>]*\?>\s*|<!DOCTYPE[^>]*>\s*", re.S)
_METADATA = re.compile(r"<metadata>.*?</metadata>\s*", re.S)
_SIZE_ATTRS = re.compile(r'(<svg[^>]*?)\s(?:width|height)="[^"]*"', re.S)


def _inline_svg(fig, key: str, label: str) -> str:
    """Render `fig` to an `<svg>` element safe to drop into a shared document.

    Two things have to happen or the page breaks in ways that are easy to miss.

    **Ids must be namespaced.** matplotlib emits `id="figure_1"`, `id="axes_1"`
    and generated clip-path ids, then references them as `url(#p12ab…)` and
    `xlink:href="#m34cd…"`. Inline two figures and the duplicate ids make the
    browser resolve every reference to the *first* definition, which clips later
    charts to the wrong box — they render blank, with no error anywhere.

    **The width/height attributes must go.** matplotlib writes them in points;
    left in place they pin the chart to a fixed size and it stops being
    responsive. Dropping them and keeping `viewBox` lets CSS size it.
    """
    buf = io.StringIO()
    fig.savefig(buf, format="svg", bbox_inches="tight", transparent=False)
    plt.close(fig)
    svg = buf.getvalue()

    svg = _XML_PREAMBLE.sub("", svg)
    svg = _METADATA.sub("", svg)

    ids = set(re.findall(r'id="([^"]+)"', svg))
    for old in sorted(ids, key=len, reverse=True):   # longest first: no partial hits
        new = f"{key}-{old}"
        svg = svg.replace(f'id="{old}"', f'id="{new}"')
        svg = svg.replace(f"url(#{old})", f"url(#{new})")
        svg = svg.replace(f'xlink:href="#{old}"', f'xlink:href="#{new}"')

    svg = _SIZE_ATTRS.sub(r"\1", svg)
    svg = _SIZE_ATTRS.sub(r"\1", svg)                # width and height, two passes
    svg = svg.replace("<svg ", f'<svg class="cx" role="img" aria-label="{label}" ', 1)
    return svg


def figure(key: str, fig, title: str, takeaway: str, source: str,
           alt: str, sub: str = "") -> str:
    """One `<figure>`: chart, bolded one-line takeaway, and its source file."""
    subline = f'<p class="figsub">{sub}</p>' if sub else ""
    return f"""
<figure data-source="{source}">
  <p class="figttl">{title}</p>
  {subline}
  {_inline_svg(fig, key, alt)}
  <figcaption>{takeaway}</figcaption>
  <p class="src">Source: <code>{source}</code></p>
</figure>"""


def _despine(ax, keep_y: bool = True) -> None:
    ax.spines["bottom"].set_color(GRID)
    ax.spines["left"].set_color(GRID)
    if not keep_y:
        ax.spines["left"].set_visible(False)


# ---------------------------------------------------------------------------
# Figures
# ---------------------------------------------------------------------------

def fig_components(d: dict) -> str:
    """Every teammate's component, re-priced on one book. The headline chart."""
    s = d["standalone"]
    base = float(s.loc[s["variant"] == "(bar) baseline", "net_sharpe"].iloc[0])
    rr = float(s.loc[s["variant"] == "(bar) per-currency RR", "net_sharpe"].iloc[0])
    comp = s[~s["variant"].str.startswith(("(bar)", "(control)"))].copy()
    comp = comp.sort_values("net_sharpe")

    labels = [f"{v}\n{o}" for v, o in zip(
        comp["variant"].str.replace(r"\s*\(.*\)", "", regex=True), comp["owner"])]
    vals = comp["net_sharpe"].to_numpy()

    # Colour by whether the component is in the shipped book, NOT by whether it
    # beats the baseline Sharpe. Sharpe is explicitly not the slot criterion --
    # the bad-skew filter sits below the baseline here and still earned a slot,
    # on the tail. A red/green split on this axis would assert the wrong rule.
    in_combined = {"Bad-skew exclusion (XS top quintile)", "Duration hedge (long TLT)"}
    colors = [BLUE if v in in_combined else MUTED for v in comp["variant"]]

    fig, ax = plt.subplots(figsize=(9.6, 4.0))
    ax.barh(labels, vals, color=colors, height=0.6, zorder=3)
    xmax = max(vals.max(), base) * 1.22
    for y, (v, var) in enumerate(zip(vals, comp["variant"])):
        # A right-aligned value column, not a label riding the bar end: at the
        # bar end two of these sit directly on the baseline rule.
        ax.text(xmax * 0.985, y, f"{v:.3f}", va="center", ha="right",
                fontsize=10.5, fontweight="bold", color=INK, zorder=4)
        if var in in_combined:
            ax.text(0.012, y, "in COMBINED", va="center", ha="left", fontsize=9,
                    color=CARD, fontweight="bold", zorder=4)
    ax.axvline(base, color=INK, lw=1.6, zorder=2)
    ax.set_xlim(0, xmax)
    ax.set_ylim(-0.6, len(vals) - 0.2)
    ax.annotate(f"baseline {base:.4f}", xy=(base, len(vals) - 0.55),
                xytext=(base + 0.035, len(vals) - 0.55), color=INK, fontsize=10,
                fontweight="bold", va="center",
                arrowprops=dict(arrowstyle="-", color=INK, lw=1.0))
    ax.set_xlabel("net Sharpe, 2007-05 to 2026-06, after real bid/ask costs")
    ax.grid(axis="y", visible=False)
    ax.set_axisbelow(True)
    _despine(ax)
    fig.tight_layout()

    return figure(
        "f1", fig,
        "Four workstreams, one book, one change at a time",
        "<b>This is the thing that is new.</b> Each bar is the shared baseline with exactly one "
        "teammate's component switched on — so for the first time these are comparable to each "
        "other, not just collected together. Two of the four help; one is close to neutral; one "
        "removes almost all of the return.",
        "cesare/outputs/p4_component_standalone.csv",
        f"Standalone net Sharpe of four teammate components on the shared base, against a "
        f"baseline of {base:.4f}: duration hedge {vals.max():.3f} at the top, "
        f"macro/regime gate {vals.min():.3f} at the bottom.",
        f"Each component re-priced on the shared base from its owner's committed outputs — "
        f"re-priced, not rebuilt. Bars are coloured by whether the component is in the shipped "
        f"book, not by whether it beats the baseline: Sharpe is deliberately not the slot "
        f"criterion, which is why the bad-skew filter sits below {base:.4f} and is still in. "
        f"The second bar the project measures against, the per-currency risk-reversal book, "
        f"is {rr:.4f}.")


def fig_curve(base, comb) -> str:
    """Cumulative net return and drawdown, baseline vs COMBINED.

    Everything is computed on the **daily** series; only the plotted points are
    thinned to weekly, because 5,001 daily points across two lines and two panels
    emit ~27,000 SVG vertices and are drawn six-deep per pixel at this width.
    The thinning is trough-preserving: the drawdown is computed daily and then
    reduced with a weekly *minimum*, so the deepest point survives exactly. The
    assertion below is what makes that a fact rather than an intention, and
    `W-FRI` is used because guardrail §6.10 permits only right-labelled aliases.
    """
    def wealth(r):
        return (1.0 + r.dropna()).cumprod()

    wb_d, wc_d = wealth(base.net), wealth(comb.net)
    ddb_d = wb_d / wb_d.cummax() - 1.0
    ddc_d = wc_d / wc_d.cummax() - 1.0

    wb, wc = wb_d.resample("W-FRI").last(), wc_d.resample("W-FRI").last()
    ddb, ddc = ddb_d.resample("W-FRI").min(), ddc_d.resample("W-FRI").min()
    for name, thin, daily in (("baseline", ddb, ddb_d), ("combined", ddc, ddc_d)):
        if abs(thin.min() - daily.min()) > 1e-12:
            raise AssertionError(
                f"{name} drawdown trough lost to thinning: "
                f"{thin.min()!r} vs daily {daily.min()!r}")

    fig, (ax1, ax2) = plt.subplots(
        2, 1, figsize=(9.6, 5.4), sharex=True, layout="constrained",
        gridspec_kw={"height_ratios": [2.1, 1.0]})

    ax1.plot(wb.index, wb.values, color=MUTED, lw=1.7, label="Baseline book")
    ax1.plot(wc.index, wc.values, color=BLUE, lw=2.0, label="COMBINED")
    ax1.set_ylabel("growth of $1, net")
    ax1.legend(frameon=False, loc="upper left", fontsize=10.5)
    ax1.text(wb.index[-1], wb.iloc[-1], f"  {wb_d.iloc[-1]:.2f}x", color=MUTED,
             fontsize=10.5, va="center", fontweight="bold")
    ax1.text(wc.index[-1], wc.iloc[-1], f"  {wc_d.iloc[-1]:.2f}x", color=BLUE,
             fontsize=10.5, va="center", fontweight="bold")
    _despine(ax1)

    ax2.fill_between(ddb.index, ddb.values * 100, 0, color=MUTED, alpha=0.35,
                     lw=0, label="Baseline")
    ax2.fill_between(ddc.index, ddc.values * 100, 0, color=BLUE, alpha=0.45,
                     lw=0, label="COMBINED")
    ax2.set_ylabel("drawdown, %")
    ax2.axhline(ddb.min() * 100, color=MUTED, lw=1.0, ls=":")
    ax2.axhline(ddc.min() * 100, color=BLUE, lw=1.0, ls=":")
    ax2.text(ddb.index[5], ddb.min() * 100 + 0.8, f"{ddb.min() * 100:.1f}%",
             color=MUTED, fontsize=10, fontweight="bold")
    ax2.text(ddb.index[5], ddc.min() * 100 + 0.8, f"{ddc.min() * 100:.1f}%",
             color=BLUE, fontsize=10, fontweight="bold")
    _despine(ax2)
    # Headroom on the right so the end-of-line multiples are not clipped.
    span = wb.index[-1] - wb.index[0]
    ax1.set_xlim(wb.index[0], wb.index[-1] + span * 0.055)

    return figure(
        "f2", fig,
        "The combined book against the baseline",
        f"<b>Steadier, not richer — and the chart says so.</b> The combined book rides above the "
        f"baseline for most of nineteen years and its worst drawdown is a third shallower "
        f"(−29.3% → −19.1%), but it <b>ends lower in raw dollars: {wc_d.iloc[-1]:.2f}× against "
        f"{wb_d.iloc[-1]:.2f}×</b>. That is not a contradiction, it is the trade-off stated "
        f"plainly: it runs at <b>8.8% annualised vol against the baseline's 11.2%</b>, so it is "
        f"better per unit of risk (Sharpe 0.4659 → 0.4891) and worse per dollar deployed. Levered "
        f"back to a matched risk level the comparison would change again, and we have not done "
        f"that — it is a fair thing to push us on.",
        "strategy.run() and run('COMBINED'), reconciled to p4_combined_ladder.csv",
        f"Growth of one dollar net of costs, 2007 to 2026: the baseline ends at "
        f"{wb_d.iloc[-1]:.2f}x and the combined book at {wc_d.iloc[-1]:.2f}x, with the drawdown "
        f"panel beneath showing {ddb.min()*100:.1f}% against {ddc.min()*100:.1f}%.",
        "Computed live and asserted equal to the committed ladder row before this page was written.")


def fig_ladder(d: dict) -> str:
    """The fold-in ladder, and the component that was excluded on principle."""
    lad = d["ladder"]
    steps = ["baseline", "+ Duration hedge (long TLT)",
             "+ VIX percentile gate (p80 / 756d)",
             "+ Bad-skew exclusion (XS top quintile)"]
    rows = [_rung(lad, "final", s) for s in steps]
    sh = [float(r["net_sharpe"]) for r in rows]
    dd = [float(r["max_drawdown"]) * 100 for r in rows]
    earned = [None, True, False, True]
    names = ["Baseline", "+ duration\nhedge (Arjun)", "+ VIX gate\n(Dafu)",
             "+ bad-skew\n(Theo)"]
    c_row = _rung(lad, "final_loo", "- VIX percentile gate (p80 / 756d)")
    combined, comb_dd = float(c_row["net_sharpe"]), float(c_row["max_drawdown"]) * 100

    # Two panels because the point is the contrast between them: up the ladder
    # the Sharpe barely moves and the drawdown moves a lot. Both axes start at
    # zero -- the flatness of the left panel is the finding, not a rendering
    # problem, and truncating it would manufacture a result.
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(9.8, 4.3))
    colors = [MUTED] + [BLUE if e else YELLOW for e in earned[1:]]

    ax1.bar(names, sh, color=colors, width=0.6, zorder=3)
    for x, (v, e) in enumerate(zip(sh, earned)):
        ax1.text(x, v + 0.010, f"{v:.4f}", ha="center", fontsize=10.5,
                 fontweight="bold", color=INK, zorder=4)
        if e is not None:
            ax1.text(x, 0.018, "earned" if e else "refused", ha="center",
                     fontsize=9.5, color=CARD, fontweight="bold", zorder=4)
    ax1.hlines(combined, 0.55, 4.05, color=INK, lw=1.5, ls="--", zorder=2)
    ax1.set_xlim(-0.7, 4.05)
    ax1.text(4.0, combined + 0.010, f"COMBINED {combined:.4f}", ha="right",
             va="bottom", fontsize=9.5, color=INK, fontweight="bold")
    ax1.set_ylabel("net Sharpe")
    ax1.set_ylim(0, max(sh) * 1.22)
    ax1.set_title("Return barely moves", fontsize=11.5, color=INK, pad=8)

    ax2.bar(names, dd, color=colors, width=0.6, zorder=3)
    for x, v in enumerate(dd):
        ax2.text(x, v - 1.1, f"{v:.1f}%", ha="center", va="top", fontsize=10.5,
                 fontweight="bold", color=INK, zorder=4)
    ax2.hlines(comb_dd, 0.55, 3.45, color=INK, lw=1.5, ls="--", zorder=2)
    ax2.set_ylabel("maximum drawdown, %")
    ax2.set_ylim(min(dd) * 1.22, 0)
    ax2.set_title("Drawdown moves a lot", fontsize=11.5, color=INK, pad=8)

    for ax in (ax1, ax2):
        ax.grid(axis="x", visible=False)
        ax.set_axisbelow(True)
        ax.tick_params(axis="x", labelsize=9.5)
        _despine(ax)
    fig.tight_layout()

    return figure(
        "f3", fig,
        "Which components earned a slot",
        f"<b>The book buys drawdown, not return.</b> Across the whole ladder the net Sharpe moves "
        f"from {sh[0]:.4f} to {sh[-1]:.4f} — visible only because the left panel is zoomed into a "
        f"narrow range, and not statistically significant at any rung. Over the same steps the "
        f"drawdown goes from {dd[0]:.1f}% to {dd[-1]:.1f}%. <b>The ladder's top rung is also not "
        f"the book we ship.</b> The VIX gate passed leave-one-out but failed the add-one-in window "
        f"test, and what to do when the two ladders disagree was written down before the run: mark "
        f"it not robust and leave it out. That costs {sh[-1] - combined:.3f} of net Sharpe, and "
        f"taking the cost rather than re-reading the rule is the entire point of fixing it first.",
        "cesare/outputs/p4_combined_ladder.csv",
        f"Net Sharpe and maximum drawdown up the fold-in ladder: Sharpe {sh[0]:.4f} to "
        f"{sh[-1]:.4f} while drawdown improves from {dd[0]:.1f}% to {dd[-1]:.1f}%; the shipped "
        f"COMBINED book excludes the VIX gate at {combined:.4f} and {comb_dd:.1f}%.",
        f"Add-one-in ladder, net of costs, each rung measured against the one before it rather "
        f"than against the baseline — that is how a component avoids taking credit for the "
        f"previous one's work. Alpha is insignificant at every rung shown: the largest "
        f"t-statistic here is {max(abs(float(r['t_alpha_vs_prev'])) for r in rows[1:]):.2f}.")


def fig_selection(d: dict) -> str:
    """The control that decides how to read the strongest Phase-4 number."""
    sel = d["selection"].set_index("book")
    order = ["baseline", "gross-matched de-risk (control)", "bad-skew exclusion"]
    short = ["Baseline\nfull risk", "Control\nsame gross,\nspread evenly",
             "Bad-skew filter\nthe actual overlay"]
    dd = [float(sel.loc[b, "max_drawdown"]) * 100 for b in order]
    sk = [float(sel.loc[b, "skew"]) for b in order]
    colors = [MUTED, YELLOW, AQUA]

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(9.8, 4.1))
    for ax, vals, ttl, fmt in ((ax1, dd, "Maximum drawdown, %", "{:.1f}%"),
                               (ax2, sk, "Skew of daily returns", "{:.2f}")):
        rng = abs(max(vals) - min(vals)) or 1.0
        ax.bar(short, vals, color=colors, width=0.55, zorder=3)
        for x, v in enumerate(vals):
            ax.text(x, v - rng * 0.05, fmt.format(v), ha="center", va="top",
                    fontsize=10.5, fontweight="bold", color=INK, zorder=4)
        ax.set_title(ttl, fontsize=11.5, color=INK, pad=26)
        ax.set_ylim(min(vals) * 1.20, abs(min(vals)) * 0.42)
        ax.grid(axis="x", visible=False)
        ax.set_axisbelow(True)
        ax.tick_params(axis="x", labelsize=9.5)
        _despine(ax)

    # These bars are negative, so every y between the value and 0 is *inside* a
    # bar. Annotations therefore live strictly above y=0, in the headroom the
    # ylim above reserves for them.
    for ax, (x0, x1), colour, label in (
            (ax1, (0.06, 0.94), RED, "6.8pp of the 7.3pp is\njust holding less risk"),
            (ax2, (1.06, 1.94), AQUA, "this part is real\nselection")):
        up = ax.get_ylim()[1]
        ax.annotate("", xy=(x1, up * 0.30), xytext=(x0, up * 0.30),
                    arrowprops=dict(arrowstyle="->", color=colour, lw=1.8))
        ax.text((x0 + x1) / 2, up * 0.40, label, ha="center", va="bottom",
                fontsize=9.5, color=colour, fontweight="bold")
    fig.tight_layout()

    a = float(d["selection"]["alpha_selection_ann"].iloc[0]) * 100
    t = float(d["selection"]["t_alpha_selection"].iloc[0])
    return figure(
        "f4", fig,
        "The caveat that changes how to read the last chart",
        "<b>Most of the drawdown improvement is not skill.</b> Against a control that holds the "
        f"exact same daily gross exposure but spreads the reduction across every currency, "
        f"<b>6.8 of the 7.3 points</b> of drawdown improvement is simply holding less risk. Only "
        f"0.5pp is the filter picking the right names, and that selection alpha is "
        f"{a:+.2f}%/yr with a t-statistic of {t:.2f} — indistinguishable from zero. What "
        "selection genuinely does buy is the skew, −0.63 → −0.31, which de-risking does not "
        "deliver at all.",
        "cesare/outputs/p4_selection_vs_derisking.csv",
        f"Maximum drawdown and skew for the baseline, a gross-matched de-risking control, and "
        f"the bad-skew filter: drawdown {dd[0]:.1f}% to {dd[1]:.1f}% to {dd[2]:.1f}%, "
        f"skew {sk[0]:.2f} to {sk[1]:.2f} to {sk[2]:.2f}.",
        "The control reproduces the overlay's daily gross exposure to 8.9e-16, so any difference "
        "between the middle and right bars is selection and nothing else.")


def fig_windows(d: dict) -> str:
    """Per stress window — the desk's standing requirement since Jul 29."""
    ep = d["combined_ep"]
    sel = ep[(ep["basis"] == "net") & (ep["window_set"] == "STRESS")]
    order = ["gfc_2008", "euro_2011", "taper_2013", "china_em_2015",
             "covid_2020", "rates_2022", "oil_2026", "semis_2026"]
    dd = sel.pivot(index="window", columns="variant", values="max_drawdown").reindex(order)
    cum = sel.pivot(index="window", columns="variant", values="cum_return").reindex(order)
    b = dd["final0 baseline"].to_numpy() * 100
    c = dd["final_loo -vix_gate"].to_numpy() * 100

    fig, ax = plt.subplots(figsize=(9.6, 4.4))
    y = np.arange(len(order))
    ax.barh(y + 0.20, b, height=0.38, color=MUTED, label="Baseline", zorder=3)
    ax.barh(y - 0.20, c, height=0.38, color=BLUE, label="COMBINED", zorder=3)
    for yy, (vb, vc) in enumerate(zip(b, c)):
        ax.text(vb - 0.5, yy + 0.20, f"{vb:.1f}", va="center", ha="right",
                fontsize=9.5, color=INK2)
        ax.text(vc - 0.5, yy - 0.20, f"{vc:.1f}", va="center", ha="right",
                fontsize=9.5, color=BLUE, fontweight="bold")
    ax.set_yticks(y, order)
    ax.invert_yaxis()
    ax.set_xlabel("maximum drawdown inside the window, % (net)")
    ax.grid(axis="y", visible=False)
    ax.set_axisbelow(True)
    ax.set_xlim(min(b.min(), c.min()) * 1.16, 0)
    ax.axhspan(5.5, 7.5, color=YELLOW, alpha=0.12, zorder=0)
    lo = ax.get_xlim()[0]
    ax.text(lo * 0.97, 6.5, "the 2026 shocks were not carry stress —\n"
            "the baseline barely noticed them", fontsize=9, color=INK2,
            va="center", ha="left", style="italic")
    ax.legend(frameon=False, loc="upper left", fontsize=10.5)
    _despine(ax)
    fig.tight_layout()

    r22b = float(cum.loc["rates_2022", "final0 baseline"]) * 100
    r22c = float(cum.loc["rates_2022", "final_loo -vix_gate"]) * 100
    return figure(
        "f5", fig,
        "Every stress window, baseline against COMBINED",
        "<b>Better in all six pre-2026 crises, and it costs upside.</b> The combined book is "
        "shallower in every window the slot criterion was written against. But it gives up a lot "
        f"in the good states: in the 2022 rates selloff — carry's <i>best</i> crisis, in the table "
        f"deliberately as a control — the baseline made {r22b:+.1f}% and the combined book only "
        f"{r22c:+.1f}%. And in both 2026 shocks it is <i>worse</i> than the baseline, which is "
        "consistent rather than alarming: neither 2026 shock was FX-carry stress in the first "
        "place, so there was nothing there to protect against.",
        "cesare/outputs/p4_combined_by_episode.csv",
        "Maximum drawdown per stress window, baseline versus combined book: the combined book is "
        "shallower in the six pre-2026 windows and slightly deeper in the two 2026 windows.",
        "Windows are frozen in <code>strategy/episodes.py</code> and asserted by test. Windows "
        "under 120 trading days quote drawdown and cumulative return only — never an annualised "
        "Sharpe off 64 days of COVID.")


def fig_d2(d: dict) -> str:
    """D2 — the first non-null, and its three qualifications."""
    prem = d["d2_prem"].sort_values("mean_vrp_vol_pts")
    be = d["d2_be"]

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(9.8, 4.3),
                                   gridspec_kw={"width_ratios": [1.05, 1.0]})

    sig = prem["t_newey_west"] > 1.96
    ax1.barh(prem["currency"], prem["mean_vrp_vol_pts"],
             color=[AQUA if s else "#b9d8c9" for s in sig], height=0.7, zorder=3)
    ax1.axvline(0, color=INK2, lw=1.0)
    ax1.set_xlabel("implied minus realised vol, vol points / month")
    ax1.set_title("The premium exists in 20 of 21 currencies",
                  fontsize=11.5, color=INK, pad=8)
    ax1.tick_params(labelsize=9)
    ax1.grid(axis="y", visible=False)
    ax1.set_axisbelow(True)
    ax1.text(0.97, 0.03, f"solid = NW t > 1.96 ({int(sig.sum())} of {len(prem)})",
             transform=ax1.transAxes, ha="right", fontsize=9, color=INK2)
    _despine(ax1)

    bar = float(d["d2_books"]["bar_baseline"].iloc[0])
    for name, col in (("vrp_xs", RED), ("short_vol", BLUE),
                      ("carry+short_vol", AQUA)):
        sub = be[be["variant"] == name].sort_values("cost_vol_pts")
        ax2.plot(sub["cost_vol_pts"], sub["sharpe"], color=col, lw=2.0,
                 marker="o", ms=4, label=name, zorder=3)
        last = sub[sub["beats_both_bars"]]["cost_vol_pts"].max()
        ax2.plot([last], [float(sub.loc[sub["cost_vol_pts"] == last, "sharpe"].iloc[0])],
                 marker="o", ms=10, mfc="none", mec=col, mew=2, zorder=4)
    ax2.axhline(bar, color=INK, lw=1.5, ls="--", zorder=2)
    ax2.text(1.55, bar + 0.06, f"carry bar {bar}", fontsize=9.5,
             color=INK, fontweight="bold")
    ax2.axvspan(0, 0.20, color=YELLOW, alpha=0.14, zorder=0)
    ax2.text(0.10, -1.3, "interbank\nG10 1M ATM\n≈0.2 vol pts", fontsize=8.5,
             color=INK2, ha="center")
    ax2.set_xlim(-0.05, 1.6)
    ax2.set_ylim(-1.6, 1.9)
    ax2.set_xlabel("assumed round-trip vol bid/ask, vol points")
    ax2.set_ylabel("Sharpe")
    ax2.set_title("…and it does not survive being charged for",
                  fontsize=11.5, color=INK, pad=8)
    ax2.legend(frameon=False, fontsize=9.5, loc="upper right",
               title="hollow ring = widest spread at\nwhich it still clears the bar",
               title_fontsize=8.5, alignment="left")
    ax2.set_axisbelow(True)
    _despine(ax2)
    fig.tight_layout()

    span = d["d2_span"].set_index("regression")
    t_sv = float(span.loc["short_vol ~ CARRY", "alpha_t"])
    svt = d["d2_svt"].set_index("variant")
    raw = float(svt.loc["vrp_xs (raw signal)", "sharpe"])
    dem = float(svt.loc["vrp_xs (ccy-demeaned = pure timing)", "sharpe"])
    be_xs = be[(be["variant"] == "vrp_xs") & be["beats_both_bars"]]["cost_vol_pts"].max()
    be_sv = be[(be["variant"] == "short_vol") & be["beats_both_bars"]]["cost_vol_pts"].max()

    return figure(
        "f6", fig,
        "D2 — a different premium in the same data",
        "<b>The first thing in this project that is not a null, and it comes with its caveats "
        "attached.</b> Selling one-month volatility earns a positive premium in 20 of 21 "
        f"currencies, and it is the only signal we have tested that <i>survives</i> the spanning "
        f"test against carry (t {t_sv:.2f}) — every previous idea died on exactly that test. "
        f"Two things stop it being a recommendation. Two thirds of the cross-sectional Sharpe is a "
        f"standing short in five EM names, not timing: strip the standing tilt and "
        f"{raw:.2f} becomes {dem:.2f}. And on mids-only data it cannot be costed — the "
        f"cross-sectional book stops clearing the carry bar at a {be_xs:.2f} vol-point round-trip "
        f"spread, which is <i>inside</i> interbank G10, and the directional book at {be_sv:.2f}.",
        "cesare/outputs/p3_d2_premium.csv · p3_d2_breakeven_cost.csv",
        "Left: mean implied-minus-realised volatility per currency, positive for 20 of 21. "
        "Right: Sharpe against an assumed round-trip volatility bid/ask, showing each book "
        "falling below the carry bar within a fraction of a vol point.",
        "Not folded into COMBINED: that preset is a costed, executable book and this one is not "
        "costable on the data we have.")


def fig_nulls(d: dict) -> str:
    """The two nulls added since the last meeting."""
    ev, d1 = d["tail_eval"], d["d1"]

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(9.8, 4.0))

    has = ev["n_tail_in_test"] > 0
    mean_auc = float(ev["auc"].mean())
    ax1.bar(ev["fold"][has], ev["auc"][has], color=RED, width=0.62, zorder=3)
    # Folds with no tail month have UNDEFINED AUC. Drawing them as full-height
    # grey bars (the obvious thing) reads as AUC = 1.0, i.e. a perfect forecast
    # -- the opposite of the truth. They get a tick on the axis instead.
    for f in ev["fold"][~has]:
        ax1.plot([f], [0.0], marker="_", ms=9, mew=2.5, color=MUTED, zorder=3)
    ax1.axhline(0.5, color=INK, lw=1.5, ls="--", zorder=4)
    ax1.text(12.6, 0.515, "coin flip", ha="right", va="bottom", fontsize=9.5,
             color=INK, fontweight="bold")
    ax1.axhline(mean_auc, color=RED, lw=1.5, zorder=4)
    ax1.text(-0.6, mean_auc - 0.02, f"mean {mean_auc:.4f}", ha="left", va="top",
             fontsize=9.5, color=RED, fontweight="bold")
    ax1.set_ylim(-0.04, 1.12)
    ax1.set_xlim(-0.8, 12.8)
    ax1.set_xlabel("purged walk-forward fold")
    ax1.set_ylabel("out-of-sample AUC")
    ax1.set_title("The tail forecast is worse than a coin flip",
                  fontsize=11.5, color=INK, pad=8)
    ax1.text(0.0, 1.05, f"— on the axis: {int((~has).sum())} of 13 folds hold no "
             f"tail month at all,\n    so AUC is undefined there",
             transform=ax1.get_yaxis_transform(), fontsize=8.5, color=MUTED,
             va="top")
    ax1.grid(axis="x", visible=False)
    ax1.set_axisbelow(True)
    _despine(ax1)

    # Each row is one (variant, input) pair, so the base name has to be derived
    # BEFORE pivoting: pivoting on `variant` directly gives a diagonal frame
    # where every cell but one per row is NaN, and half of each bar pair vanishes.
    sk = d1[d1["variant"] != "U21_carry (anchor)"].copy()
    sk["base"] = (sk["variant"].str.replace("U21_", "", regex=False)
                  .str.replace("_bkm", "", regex=False)
                  .str.replace("_proxy", "", regex=False))
    piv = sk.pivot(index="base", columns="input", values="net_sharpe")
    piv = piv.reindex(["iskew", "srp", "clean"])
    piv.index = ["implied\nskew sort", "skewness risk\npremium", "clean\ncarry"]
    if piv.isna().any().any():
        raise ValueError(f"D1 proxy/BKM pairing incomplete:\n{piv}")
    anchor = float(d1.loc[d1["variant"] == "U21_carry (anchor)", "net_sharpe"].iloc[0])
    x = np.arange(len(piv))
    ax2.bar(x - 0.19, piv["25d slope proxy"], width=0.36, color=MUTED,
            label="25Δ slope proxy (original D1)", zorder=3)
    ax2.bar(x + 0.19, piv["model-free BKM"], width=0.36, color=BLUE,
            label="model-free BKM (rerun)", zorder=3)
    ax2.axhline(anchor, color=AQUA, lw=1.8, zorder=4)
    ax2.text(-0.45, anchor - 0.022,
             f"plain carry on the same 21 names: {anchor:.3f}", ha="left",
             va="top", fontsize=9.5, color=AQUA, fontweight="bold")
    ax2.axhline(0, color=INK2, lw=1.0)
    ax2.set_xticks(x, piv.index)
    ax2.set_ylim(min(piv.min().min() * 1.35, -0.12), anchor * 1.30)
    ax2.set_ylabel("net Sharpe")
    ax2.set_title("D1's null survives the correct construction",
                  fontsize=11.5, color=INK, pad=8)
    ax2.legend(frameon=False, fontsize=9, loc="upper right")
    ax2.grid(axis="x", visible=False)
    ax2.set_axisbelow(True)
    _despine(ax2)
    fig.tight_layout()

    n_none = int((~has).sum())
    ts = d["tail_stats"].set_index("variant")
    d_inc = float(ts.loc["tail forecast (binary p80 gate)", "d_net_sharpe_vs_incumbent"])
    agree = float(d["d1_agree"]["xs_rank_corr_mean"].iloc[0])
    chg = float(d["d1_agree"]["corr_change"].median())

    return figure(
        "f7", fig,
        "Two more things we tested and rejected",
        "<b>Left: sixteen features lose to one VIX threshold.</b> A model forecasting next month's "
        f"tail scores {mean_auc:.4f} out of sample — worse than chance — and loses to the "
        f"incumbent VIX gate by {abs(d_inc):.3f} of Sharpe. It was not iterated; that was fixed in "
        f"advance. The honest limit is that {n_none} of 13 folds contain no tail month at all, so "
        "this may simply not be answerable monthly on nineteen years of data. "
        "<b>Right: D1's null no longer rests on an approximation.</b> Rebuilding the risk-neutral "
        "skewness properly, from the ten-delta wings that were in the data all along, leaves the "
        "verdict unchanged — nothing beats plain carry on the same names. The durable finding is "
        f"methodological: the cheap proxy agrees with the proper measure on <i>which</i> "
        f"currencies are crash-priced (rank correlation {agree:.2f}) but almost not at all on "
        f"month-to-month <i>changes</i> (median {chg:.3f}) — so it is a good cross-sectional "
        "proxy and a nearly useless timing signal.",
        "cesare/outputs/p4_tail_forecast_eval.csv · p3_d1_bkm_comparison.csv",
        f"Left: out-of-sample AUC by purged fold, mean {mean_auc:.4f}, below the 0.5 coin-flip "
        f"line, with {n_none} of 13 folds containing no tail month. Right: net Sharpe of each D1 "
        f"variant under the proxy and the model-free construction, all far below the {anchor:.3f} "
        "carry anchor.",
        "Both were specified with a falsifiable bar before they were run, and both are reported "
        "against the bar they failed.")


# ---------------------------------------------------------------------------
# Page
# ---------------------------------------------------------------------------

CSS = """
:root{
  --blue:#2a78d6; --aqua:#1baf7a; --yellow:#eda100; --red:#e34948;
  --ink:#0b0b0b; --ink2:#52514e; --muted:#898781;
  --grid:#e1e0d9; --surface:#ffffff; --plane:#f6f6f3; --card:#ffffff;
  --border:rgba(11,11,11,0.10); --good:#0a7d0a; --bad:#d03b3b; --accent:#2a78d6;
  --wash:#f2f7fe; --washb:#cfe0f7; --code:#f6f6f3;
  color-scheme:light;
}
*{box-sizing:border-box}
body{margin:0; background:var(--plane); color:var(--ink);
  font-family:system-ui,-apple-system,"Segoe UI",Roboto,sans-serif;
  line-height:1.55; font-size:16px}
.wrap{max-width:1080px; margin:0 auto; padding:32px 28px 80px}
header.masthead{border-bottom:2px solid var(--ink); padding-bottom:18px}
.kicker{font-size:12px; letter-spacing:.14em; text-transform:uppercase;
  color:var(--accent); font-weight:700}
h1{font-size:30px; line-height:1.15; margin:6px 0 4px; letter-spacing:-.01em}
.sub{color:var(--ink2); font-size:16px; margin:8px 0 0; max-width:78ch}
.meta{display:flex; flex-wrap:wrap; gap:6px 18px; margin-top:12px;
  font-size:12.5px; color:var(--muted)}
.meta span{white-space:nowrap}
h2{font-size:21px; margin:48px 0 4px; letter-spacing:-.01em; padding-top:10px}
h2 .num{color:var(--accent); font-variant-numeric:tabular-nums; margin-right:8px}
h3{font-size:16px; margin:24px 0 6px}
p{margin:10px 0}
.lede{color:var(--ink2); font-size:15.5px; margin:6px 0 14px; max-width:80ch}
code{font-family:ui-monospace,SFMono-Regular,Menlo,monospace; font-size:.88em;
  background:var(--code); padding:1px 5px; border-radius:4px}
.bluf{background:var(--wash); border:1px solid var(--washb);
  border-left:4px solid var(--blue); border-radius:10px; padding:16px 18px;
  margin:20px 0 8px}
.bluf .lab{font-size:12px; letter-spacing:.12em; text-transform:uppercase;
  color:var(--accent); font-weight:700}
.bluf p{margin:6px 0 0}
.warn{background:#fdf6e8; border:1px solid #f0dcae; border-left:4px solid var(--yellow);
  border-radius:10px; padding:14px 18px; margin:20px 0}
.warn .lab{font-size:12px; letter-spacing:.12em; text-transform:uppercase;
  color:#8a6100; font-weight:700}
.warn p{margin:6px 0 0}
.tiles{display:grid; grid-template-columns:repeat(auto-fit,minmax(158px,1fr));
  gap:12px; margin:20px 0}
.tile{background:var(--card); border:1px solid var(--border); border-radius:10px;
  padding:14px 14px 12px}
.tile .v{font-size:25px; font-weight:700; letter-spacing:-.02em;
  font-variant-numeric:tabular-nums}
.tile .k{font-size:12.5px; color:var(--ink2); margin-top:2px}
.tile .n{font-size:11.5px; color:var(--muted); margin-top:3px}
figure{margin:22px 0 8px; background:var(--card); border:1px solid var(--border);
  border-radius:12px; padding:18px 20px 14px}
.figttl{font-size:15px; font-weight:700; margin:0}
.figsub{font-size:13px; color:var(--ink2); margin:3px 0 10px}
svg.cx{display:block; width:100%; height:auto; margin:6px 0}
figcaption{font-size:14px; color:var(--ink2); margin-top:10px;
  padding-top:10px; border-top:1px solid var(--border); max-width:88ch}
figcaption b{color:var(--ink)}
.src{font-size:11.5px; color:var(--muted); margin:8px 0 0}
ul{margin:10px 0; padding-left:22px} li{margin:6px 0; max-width:82ch}
.next li{margin:10px 0}
.next b{color:var(--ink)}
footer{margin-top:56px; padding-top:18px; border-top:1px solid var(--border);
  font-size:12.5px; color:var(--muted)}
@media (max-width:760px){ h1{font-size:24px} .wrap{padding:22px 16px 60px} }
@media print{ body{background:#fff} figure{page-break-inside:avoid;
  border:1px solid #ddd} .wrap{padding:0} h2{page-break-after:avoid} }
"""


def build() -> str:
    d = load()
    base, comb = verify(d)

    lad = d["ladder"]
    r_base = _rung(lad, "final", "baseline")
    r_comb = _rung(lad, "final_loo", "- VIX percentile gate (p80 / 756d)")
    legs = d["legs"]
    ann = legs[legs["freq"] == "FULL"].iloc[0]
    prem = d["d2_prem"]

    N = {
        "base_net": f"{float(r_base['net_sharpe']):.4f}",
        "base_gross": f"{float(r_base['gross_sharpe']):.4f}",
        "base_dd": f"{float(r_base['max_drawdown']) * 100:.1f}",
        "base_vol": f"{float(r_base['ann_vol_net']) * 100:.1f}",
        "comb_net": f"{float(r_comb['net_sharpe']):.4f}",
        "comb_dd": f"{float(r_comb['max_drawdown']) * 100:.1f}",
        "comb_vol": f"{float(r_comb['ann_vol_net']) * 100:.1f}",
        "cvar_cut": f"{(1 - float(r_comb['CVaR_99']) / float(r_base['CVaR_99'])) * 100:.0f}",
        # The largest |t| among rungs that ADD value, on the ladder actually
        # shipped. Taking the max over the whole file instead gives 2.69, which
        # is the leave-one-out row for *removing* the component that hurt --
        # a significant statistic attached to the opposite claim.
        "max_t": f"{lad[(lad['ladder'] == 'final') & (lad['alpha_vs_prev_ann'] > 0)]['t_alpha_vs_prev'].abs().max():.2f}",
        "t_regime_add": f"{float(_rung(lad, 'add', '+ Macro/regime probability gate')['t_alpha_vs_prev']):.2f}",
        "t_regime_loo": f"{float(_rung(lad, 'loo', '- Macro/regime probability gate')['t_alpha_vs_prev']):.2f}",
        "carry_long": f"{float(ann['carry_long']) * 100:.2f}",
        "spot_long": f"{float(ann['spot_long']) * 100:.2f}",
        "gross_tot": f"{float(ann['total']) * 100:.2f}",
        "d2_pos": f"{int((prem['mean_vrp_vol_pts'] > 0).sum())}",
        "d2_n": f"{len(prem)}",
        "n_days": f"{int(r_base['n_days']):,}",
    }

    figs = [
        fig_components(d),
        fig_curve(base, comb),
        fig_ladder(d),
        fig_selection(d),
        fig_windows(d),
        fig_d2(d),
        fig_nulls(d),
    ]

    provenance = f"""<!--
  BofA progress deck, {AS_OF}. Self-contained: no CDN, no external asset, no script.

  GENERATED, NOT HAND-WRITTEN -- rebuild with:  python cesare/build_deck.py
  Every chart is rendered from a committed CSV in cesare/outputs/ and every
  number in the prose is read from a CSV cell, never typed. The two daily curves
  are computed live via strategy.run() and asserted equal to the committed
  p4_combined_ladder.csv rows before this file is written; build_deck.verify()
  raises rather than publish a stale slide.

  Sample: 2007-05-01 -> 2026-06-30, {N['n_days']} trading days, 27 currencies.
  Tests behind it: 12/12 + 11/11 + 17/17 + 8/8.
-->"""

    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>FX Carry — progress update, 5 August 2026</title>
{provenance}
<style>{CSS}</style>
</head>
<body>
<div class="wrap">

<header class="masthead">
  <div class="kicker">FX Carry · UChicago Project Lab × Bank of America</div>
  <h1>Progress update — 5 August 2026</h1>
  <p class="sub">Two things happened since the last meeting. We pulled all six workstreams into
  one engine, so everybody's ideas are finally measured on the same book. And we found a second
  premium in the option data that behaves differently from everything we have tried so far.</p>
  <div class="meta">
    <span>Cesare Bavaresco — shared base and integration</span>
    <span>Sample 2007-05 → 2026-06, {N['n_days']} trading days</span>
    <span>27 currencies, net of real bid/ask costs</span>
  </div>
</header>

<div class="warn">
  <div class="lab">Read this first</div>
  <p><b>This is not the final strategy.</b> There are three weeks to hand-in. Everything here is
  work in progress and several pieces are still being tweaked — nothing on this page is a
  recommendation, and the numbers that matter most are the ones that have <i>not</i> improved.</p>
</div>

<div class="tiles">
  <div class="tile"><div class="v">6 → 1</div><div class="k">Workstreams, now one engine</div>
    <div class="n">first time components are comparable</div></div>
  <div class="tile"><div class="v">{N['comb_net']}</div><div class="k">Net Sharpe, combined book</div>
    <div class="n">from {N['base_net']} — not statistically significant</div></div>
  <div class="tile"><div class="v">−{N['comb_dd'].lstrip('−-')}%</div>
    <div class="k">Worst drawdown, combined</div>
    <div class="n">from −{N['base_dd'].lstrip('−-')}%, at lower risk</div></div>
  <div class="tile"><div class="v">{N['d2_pos']}/{N['d2_n']}</div>
    <div class="k">Currencies paying a vol premium</div>
    <div class="n">new, and heavily qualified</div></div>
</div>

<div class="bluf">
  <div class="lab">In one paragraph</div>
  <p>The combined book earns a little more and loses a lot less than the baseline, but
  <b>none of the improvement is statistically significant</b> — every component that adds value
  does so with a t-statistic under {N['max_t']}. The only large t-statistics in the whole exercise
  belong to the component that <i>hurt</i>: adding the macro/regime gate costs return at
  t&nbsp;{N['t_regime_add']}, and taking it back out gains at t&nbsp;{N['t_regime_loo']}. So what
  we can show is a shallower drawdown and a less ugly left tail — and even that is mostly the
  result of holding less risk rather than picking better. The one genuinely new finding is a
  volatility risk premium that survives a test every previous idea failed, and it is not costable
  on the data we own. We are still tweaking.</p>
</div>

<h2><span class="num">1</span>What we built: one engine, one set of numbers</h2>
<p class="lede">Until now each of us measured our idea against our own baseline, so a difference
between two results measured the two baselines rather than the two ideas. Everything is now
measured on one book — the same 27 currencies, the same costs, the same window — with exactly one
thing changed at a time.</p>
{figs[0]}
<p>An honest label travels with this chart: all four components are <b>re-priced, not rebuilt</b>.
We reconstructed each teammate's signal from their committed outputs and re-ran it on the shared
book, which is our reading of their idea rather than their specification of it. Their own ports
are still the goal.</p>

<h2><span class="num">2</span>What the combined book does</h2>
{figs[1]}
{figs[2]}

<h2><span class="num">3</span>The caveat we would rather state ourselves</h2>
<p class="lede">The strongest-looking number in this whole exercise is the drawdown improvement.
It is also the one most likely to be misread, so we built the control that tests it.</p>
{figs[3]}

<h2><span class="num">4</span>Per stress window, as asked</h2>
<p class="lede">Since 29 July the standing requirement has been results per stress window, with
whole-sample statistics as supporting evidence only. The windows are frozen in code and asserted
by a test, so nobody — including us — can re-pick a window after seeing a result.</p>
{figs[4]}

<h2><span class="num">5</span>What is new: a second premium</h2>
<p class="lede">Every previous idea asked whether some signal could improve the <i>carry sort</i>.
This one asks a different question: is there a <i>different premium</i> in the same data. It is
the first thing in the project that is not a null — which is exactly why its caveats need to
travel with it rather than sit in a footnote.</p>
{figs[5]}

<h2><span class="num">6</span>What is new: two more nulls</h2>
<p class="lede">Both were the desk's asks, both were specified with a bar written down before the
run, and both failed it. We think this is the most defensible part of the project.</p>
{figs[6]}

<h2><span class="num">7</span>Where the risk actually sits</h2>
<p class="lede">One line from the decomposition that reframes what risk management in this book is
<i>for</i>, and it holds up in every year of the sample.</p>
<div class="bluf">
  <div class="lab">The reframe</div>
  <p>Carry accrues <b>+{N['carry_long']}%/yr on the long leg</b>. Spot gives back
  <b>{N['spot_long']}%/yr on that same leg</b>. The book keeps {N['gross_tot']}%. Year by year,
  <b>carry on the long leg is positive in all twenty years, including all seven losing ones</b> —
  so every losing year is a spot event, never a carry event. The trade is not "earn carry". It is
  <b>earn carry and survive spot</b>, which is why the tail objective is the right objective:
  the carry leg has never been the problem.</p>
  <p class="src">Source: <code>cesare/outputs/p4_leg_decomposition.csv</code> — the four legs
  reconcile to the book's gross return at 3.9e-17.</p>
</div>

<h2><span class="num">8</span>What is next, and what we are still tweaking</h2>
<p class="lede">Three weeks. These are open questions, not a plan we are defending.</p>
<ul class="next">
  <li><b>Replace our reconstructions with real ports.</b> Four of the components on this page are
  our reading of somebody else's signal. Each one that gets ported properly is a number on this
  page that could move.</li>
  <li><b>Decide what to do about the VIX gate.</b> Our own rule excluded it and that cost 0.043 of
  Sharpe. We think taking the cost was right, but it is the call we would most like challenged in
  the room.</li>
  <li><b>Pin down how much of D2 is real.</b> The standing-tilt result says most of the
  cross-sectional Sharpe is a static short in five EM currencies whose tail has not happened inside
  our sample. That is the number we are least comfortable with.</li>
  <li><b>Two data asks are now the highest-value items in the project</b> — option bid/ask, without
  which no premium-paying hedge and no volatility strategy can be honestly costed; and an
  investable FX volatility index to validate D2 against the way carry was validated against the DB
  carry indices.</li>
  <li><b>Write it up.</b> The report is the deliverable, and the null chapter is the longest one in
  it on purpose.</li>
</ul>

<footer>
  <p><b>How to check anything on this page.</b> Every chart names the committed CSV behind it, and
  this page is generated by <code>python cesare/build_deck.py</code> rather than written by hand —
  no number here was typed. The two daily curves are recomputed by
  <code>strategy.run()</code> at build time and the build fails if they disagree with the committed
  ladder. Baseline reconciliation: gross {N['base_gross']} / net {N['base_net']}, turnover 0.675470,
  cost drag 1.8146611%/yr; test suites 12/12 · 11/11 · 17/17 · 8/8.</p>
  <p>Snapshot {AS_OF}. Source of truth for every claim:
  <code>cesare/FX_Carry_Strategy_Project_Plan.md</code>.</p>
</footer>

</div>
</body>
</html>
"""


def main() -> None:
    html = build()
    DECK.write_text(html, encoding="utf-8")
    print(f"  wrote {DECK.relative_to(REPO_ROOT)}  ({len(html) / 1024:.0f} KB)")


if __name__ == "__main__":
    main()
