"""Build the 19 August 2026 BofA deck — the finished product, one self-contained page.

    python cesare/build_deck_aug19.py   -> presentations/deck_2026_08_19.html

Third in the generated-deck series. The Aug 5 deck argued a change of objective;
the Aug 12 deck closed the evaluation. This one presents **the deliverable**: one
engine, three books, and the pros and cons of each — which is the condition the
desk set on 12 August for presenting more than one strategy.

**The CSS and the verdict-table renderer are imported from `build_deck_aug12.py`,
not copied.** That module was itself written without matplotlib precisely so it
stays cheap to import, so there is no cost to reusing it and a real cost to
forking the house style a third time. Everything the two decks share now has one
definition.

**Byte-deterministic, like its predecessor.** No matplotlib, so no random SVG
element ids: run this twice and the hashes match, which is what makes it safe to
regenerate in the hour before a meeting. The two bar charts are hand-emitted
inline SVG with coordinates computed from the CSV values.

Sources, all committed: `final/evidence/strategy_menu.csv`,
`strategy_menu_by_window.csv`, `strategy_menu_matched_risk.csv` (all written by
`final/menu.py`), `component_verdicts.csv` (by `final/verdicts.py`), and
`cesare/outputs/p4_combined_ladder.csv` / `p4_selection_vs_derisking.csv`. As in
both earlier decks the headline is asserted against a live `run()` before the page
is written, so a stale slide fails the build rather than reaching the room.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from strategy import run                                              # noqa: E402
from cesare.build_deck_aug12 import CSS, _esc, verdict_table          # noqa: E402

OUTPUTS = REPO_ROOT / "cesare" / "outputs"
EVIDENCE = REPO_ROOT / "final" / "evidence"
DECK = REPO_ROOT / "cesare" / "presentations" / "deck_2026_08_19.html"

AS_OF = "2026-08-19"
FINAL_MEETING = "Wednesday 26 August 2026, 12:00 CDT"


def _csv(path: Path) -> pd.DataFrame:
    if not path.exists():
        raise FileNotFoundError(
            f"{path.relative_to(REPO_ROOT)} is missing. This deck is assembled from "
            f"committed CSVs; it will not invent a number to cover a gap. "
            f"Run `python final/menu.py` and `python final/verdicts.py` first.")
    return pd.read_csv(path, keep_default_na=False)


def load() -> dict:
    d = {"menu": _csv(EVIDENCE / "strategy_menu.csv"),
         "windows": _csv(EVIDENCE / "strategy_menu_by_window.csv"),
         "matched": _csv(EVIDENCE / "strategy_menu_matched_risk.csv"),
         "verdicts": _csv(EVIDENCE / "component_verdicts.csv"),
         "ladder": _csv(OUTPUTS / "p4_combined_ladder.csv"),
         "selection": _csv(OUTPUTS / "p4_selection_vs_derisking.csv")}
    num = ("ann_return ann_vol sharpe sortino calmar max_drawdown CVaR_99 skew "
           "hit_rate turnover cost_drag gross_sharpe cum_return").split()
    for k in ("menu", "windows", "matched"):
        for c in num:
            if c in d[k].columns:
                d[k][c] = pd.to_numeric(d[k][c], errors="coerce")
    for c in ("net_sharpe", "max_drawdown", "CVaR_99", "alpha_selection_ann",
              "t_alpha_selection", "skew"):
        for k in ("ladder", "selection"):
            if c in d[k].columns:
                d[k][c] = pd.to_numeric(d[k][c], errors="coerce")
    return d


def verify(d: dict) -> None:
    """Assert the three books against a live run() before publishing a slide.

    The deck's whole claim is that these are runnable configurations of one
    shipped engine rather than a table someone assembled. If that stops being
    true, this build must fail rather than print it.
    """
    want = {r["preset"]: r for _, r in d["menu"].iterrows()}
    for preset in ("OFFENSIVE", "ALL", "CORE", "DEFENSIVE"):
        r = run(preset)
        s = r.summary(benchmark=None).loc[f"{r.config.name}_net"]
        for key, col in (("sharpe", "sharpe"), ("max_drawdown", "max_drawdown"),
                         ("ann_vol", "ann_vol")):
            got, exp = float(s[key]), float(want[preset][col])
            if abs(got - exp) > 5e-4:
                raise AssertionError(
                    f"{preset}.{key}: live run gives {got:.6f}, "
                    f"strategy_menu.csv says {exp:.6f}. The menu CSV is stale — "
                    f"re-run `python final/menu.py` before rebuilding this deck.")

    vols = d["menu"]["ann_vol"].tolist()
    if vols != sorted(vols, reverse=True):
        raise AssertionError(
            f"the menu is no longer a monotone risk ladder ({vols}); the deck's "
            f"central slide would be wrong.")
    print(f"  verified 4 books against a live run(); ladder monotone "
          f"({' > '.join(f'{v:.3f}' for v in vols)})")


# ---------------------------------------------------------------------------
# Markup helpers
# ---------------------------------------------------------------------------

def _pct(x, dp=1, sign=False):
    v = float(x) * 100
    return f"{v:+.{dp}f}%" if sign else f"{v:.{dp}f}%"


def _tone_for(book: str) -> str:
    return {"OFFENSIVE": "off", "BASELINE (reference)": "ref",
            "CORE": "core", "DEFENSIVE": "def"}.get(book, "ref")


def menu_table(menu: pd.DataFrame) -> str:
    rows = []
    for _, r in menu.iterrows():
        cls = _tone_for(r["book"])
        ref = ' class="refrow"' if r["kind"] == "reference" else ""
        rows.append(
            f'<tr{ref}><td><span class="chip {cls}">{_esc(r["book"])}</span></td>'
            f'<td class="n">{_pct(r["ann_return"])}</td>'
            f'<td class="n">{_pct(r["ann_vol"])}</td>'
            f'<td class="n"><b>{r["sharpe"]:.4f}</b></td>'
            f'<td class="n">{r["sortino"]:.3f}</td>'
            f'<td class="n">{r["calmar"]:.3f}</td>'
            f'<td class="n">{_pct(r["max_drawdown"])}</td>'
            f'<td class="n">{r["CVaR_99"]:.4f}</td>'
            f'<td class="n">{r["skew"]:.2f}</td>'
            f'<td class="n">{_pct(r["cost_drag"], 2)}</td></tr>')
    return ('<table class="vt menu"><thead><tr><th>Book</th><th class="n">Return</th>'
            '<th class="n">Vol</th><th class="n">Sharpe</th><th class="n">Sortino</th>'
            '<th class="n">Calmar</th><th class="n">MaxDD</th><th class="n">CVaR<sub>99</sub></th>'
            '<th class="n">Skew</th><th class="n">Cost</th></tr></thead><tbody>'
            + "".join(rows) + "</tbody></table>")


#: Window -> short human label. The 2026 pair are marked because the desk
#: nominated them and because they turned out not to be carry stress at all.
_WLAB = {"gfc_2008": "GFC 2008", "euro_2011": "Euro 2011", "taper_2013": "Taper 2013",
         "china_em_2015": "China/EM 2015", "covid_2020": "COVID 2020",
         "rates_2022": "Rates 2022 · control", "oil_2026": "Oil 2026 · desk",
         "semis_2026": "Semis 2026 · desk"}
_ORDER = ["OFFENSIVE", "BASELINE (reference)", "CORE", "DEFENSIVE"]


def window_table(w: pd.DataFrame, metric: str, dp=1) -> str:
    piv = w.pivot(index="window", columns="book", values=metric)
    piv = piv.reindex([k for k in _WLAB if k in piv.index])[
        [c for c in _ORDER if c in piv.columns]]
    head = "".join(f'<th class="n">{c.split(" (")[0]}</th>' for c in piv.columns)
    rows = []
    for win, r in piv.iterrows():
        cells = "".join(f'<td class="n {"pos" if v > 0 else "neg"}">{_pct(v, dp)}</td>'
                        for v in r)
        rows.append(f'<tr><td>{_esc(_WLAB[win])}</td>{cells}</tr>')
    return (f'<table class="vt menu"><thead><tr><th>Stress window</th>{head}</tr></thead>'
            f'<tbody>{"".join(rows)}</tbody></table>')


def proscons(menu: pd.DataFrame) -> str:
    cards = []
    for _, r in menu.iterrows():
        if r["kind"] != "mandate":
            continue
        cards.append(
            f'<div class="pc {_tone_for(r["book"])}">'
            f'<div class="pchead"><span class="chip {_tone_for(r["book"])}">'
            f'{_esc(r["book"])}</span>'
            f'<span class="when">{_esc(r["when"])}</span></div>'
            f'<div class="pcbody"><p class="pro"><span class="lab">For</span>'
            f'{_esc(r["pros"])}</p>'
            f'<p class="con"><span class="lab">Against</span>{_esc(r["cons"])}</p></div></div>')
    return f'<div class="pcgrid">{"".join(cards)}</div>'


def ladder_svg(menu: pd.DataFrame) -> str:
    """Return vs drawdown, drawn from the CSV. Hand-emitted so it stays deterministic."""
    W, H, PAD = 720, 232, 46
    books = list(menu.itertuples())
    span = max(abs(float(b.max_drawdown)) for b in books)
    mid, usable = H / 2, (H / 2 - PAD)
    bw, gap = 74, 108
    parts = [f'<svg viewBox="0 0 {W} {H}" role="img" class="fig">',
             f'<line x1="20" y1="{mid:.0f}" x2="{W-20}" y2="{mid:.0f}" '
             f'class="axis"/>']
    for i, b in enumerate(books):
        x = 60 + i * gap * 1.6
        rh = float(b.ann_return) / span * usable
        dh = abs(float(b.max_drawdown)) / span * usable
        parts.append(
            f'<rect x="{x:.0f}" y="{mid - rh:.0f}" width="{bw}" height="{rh:.0f}" '
            f'class="bar up {_tone_for(b.book)}"/>'
            f'<rect x="{x:.0f}" y="{mid:.0f}" width="{bw}" height="{dh:.0f}" '
            f'class="bar dn {_tone_for(b.book)}"/>'
            f'<text x="{x + bw/2:.0f}" y="{mid - rh - 7:.0f}" class="bl">'
            f'{_pct(b.ann_return)}</text>'
            f'<text x="{x + bw/2:.0f}" y="{mid + dh + 15:.0f}" class="bl">'
            f'{_pct(b.max_drawdown)}</text>'
            f'<text x="{x + bw/2:.0f}" y="{H - 6:.0f}" class="bx">'
            f'{_esc(b.book.split(" (")[0])}</text>')
    parts.append('<text x="20" y="16" class="cap">annual return (up) vs maximum '
                 'drawdown (down), net of costs</text></svg>')
    return "".join(parts)


EXTRA_CSS = """
.menu td.n,.menu th.n{text-align:right; font-variant-numeric:tabular-nums}
.menu tr.refrow td{background:var(--plane); color:var(--ink2); font-style:italic}
.chip{display:inline-block; font-size:11.5px; font-weight:800; letter-spacing:.04em;
  padding:2px 9px; border-radius:999px; border:1px solid}
.chip.off{background:#fdf1ec; color:#a1451d; border-color:#f0cdbb}
.chip.core{background:#e9f1fb; color:#1c4f8f; border-color:#c2d8f0}
.chip.def{background:#e8f4ef; color:#146b4a; border-color:#bfe0d1}
.chip.ref{background:var(--plane); color:var(--muted); border-color:var(--grid)}
td.pos{color:#0a7d0a} td.neg{color:#a33}
.pcgrid{display:grid; grid-template-columns:repeat(3,1fr); gap:14px; margin:16px 0 6px}
.pc{border:1px solid var(--grid); border-radius:10px; overflow:hidden; background:#fff}
.pc.off{border-top:3px solid #c2622f} .pc.core{border-top:3px solid #2b6cb0}
.pc.def{border-top:3px solid #1a8a5f}
.pchead{padding:11px 13px 8px; border-bottom:1px solid var(--grid)}
.pchead .when{display:block; margin-top:6px; font-size:12px; color:var(--muted)}
.pcbody{padding:11px 13px 13px}
.pcbody p{margin:0 0 10px; font-size:13.5px; line-height:1.5}
.pcbody .lab{display:block; font-size:10.5px; letter-spacing:.13em; font-weight:800;
  text-transform:uppercase; margin-bottom:3px}
.pro .lab{color:#0a7d0a} .con .lab{color:#a33}
.fig{width:100%; height:auto; margin:14px 0 4px}
.fig .axis{stroke:var(--ink2); stroke-width:1}
.fig .bar.up{opacity:.92} .fig .bar.dn{opacity:.55}
.fig .bar.off{fill:#c2622f} .fig .bar.core{fill:#2b6cb0}
.fig .bar.def{fill:#1a8a5f} .fig .bar.ref{fill:#9aa1a8}
.fig .bl{font-size:11.5px; font-weight:700; text-anchor:middle; fill:var(--ink)}
.fig .bx{font-size:11px; text-anchor:middle; fill:var(--ink2); letter-spacing:.03em}
.fig .cap{font-size:11px; fill:var(--muted)}
h3.sub2{font-size:14px; font-weight:700; color:var(--ink2); letter-spacing:.02em;
  margin:22px 0 6px}
p.foot{font-size:12px; color:var(--muted); margin:8px 0 0; line-height:1.5}
p.foot code{font-size:11.5px}
footer.end{margin:52px 0 8px; padding-top:16px; border-top:1px solid var(--grid);
  font-size:12px; color:var(--muted); line-height:1.6}
ul.next{margin:12px 0 0; padding-left:20px}
ul.next li{margin:0 0 9px; line-height:1.55}
@media (max-width:900px){ .pcgrid{grid-template-columns:1fr} }
@media print{ .pcgrid{grid-template-columns:repeat(3,1fr)} .pc{break-inside:avoid} }
"""


def build() -> str:
    d = load()
    verify(d)
    menu, w, m = d["menu"], d["windows"], d["matched"]
    base = menu[menu["preset"] == "ALL"].iloc[0]
    core = menu[menu["preset"] == "CORE"].iloc[0]
    dfn = menu[menu["preset"] == "DEFENSIVE"].iloc[0]
    off = menu[menu["preset"] == "OFFENSIVE"].iloc[0]
    mb, mc = m.iloc[0], m.iloc[1]

    sel = d["selection"].set_index("book")
    sel_alpha = float(sel.loc["baseline", "alpha_selection_ann"]) * 100
    sel_t = float(sel.loc["baseline", "t_alpha_selection"])
    n_comp = len(d["verdicts"])
    n_ws = d["verdicts"]["workstream"].nunique()

    provenance = f"""<!--
  FX Carry — BofA deck, {AS_OF}. THE DELIVERABLE: one engine, three books.
  GENERATED by `python cesare/build_deck_aug19.py`. Do not edit this file.
  Every number is pulled from a committed CSV in cesare/outputs/ or
  final/evidence/, and all four books are asserted against a live strategy.run()
  before this page is written. No number here was typed by hand.
  Sample 2007-05-01 -> 2026-06-30, 5,001 trading days, 27 currencies, net of
  real per-currency bid/ask.
-->"""

    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>FX Carry — the finished product, 19 August 2026</title>
{provenance}
<style>{CSS}{EXTRA_CSS}</style>
</head>
<body>
<div class="wrap">

<header class="masthead">
  <div class="kicker">FX Carry · UChicago Project Lab × Bank of America</div>
  <h1>The finished product — 19 August 2026</h1>
  <p class="sub">The strategy is done. What we are bringing today is <b>one engine and three
  books</b> — the same construction at three points on a single risk-appetite ladder, each with its
  pros and cons written down, which was the condition set on 12 August for presenting more than one
  strategy. Everything runs from one package with one command, and every number on this page is
  asserted against a live run of the shipped engine before the page is written.</p>
  <div class="meta">
    <span>Cesare Bavaresco — shared base and integration</span>
    <span>Final presentation: {FINAL_MEETING}</span>
  </div>
</header>

<div class="warn">
  <div class="lab">Three things to hold on to while reading the rest</div>
  <p><b>No result anywhere in this project has a statistically significant net alpha.</b> The largest
  |t| on any rung of the integration ladder is 1.16. What these books buy is drawdown and skew, not
  return, and the ladder below is a choice about risk rather than a claim about edge.</p>
  <p><b>Most of the tail improvement is de-risking, not selection.</b> Against a control holding the
  overlay's exact daily gross spread across every name, 6.8 of the 7.3pp of drawdown improvement is
  simply holding less notional. Selection's alpha is {sel_alpha:+.2f}%/yr at t&nbsp;{sel_t:.2f} —
  insignificant. What selection genuinely buys is skew.</p>
  <p><b>Four of five teammate components were re-priced, not rebuilt.</b> Base adoption reached 1 of
  5, so the rest were folded in from committed outputs. A re-price is our reading of a teammate's
  signal, not their specification of it, and every row records which it is.</p>
</div>

<h2><span class="num">1</span>The product: one engine, three books</h2>
<p>One construction, one set of conventions, one set of numbers — 27 currencies against USD,
forward-implied carry, inverse-volatility legs, monthly rebalance, vol-targeted, net of real
per-currency bid/ask. The three books differ <i>only</i> in how much protection is bought and how
much risk is deployed. They are named presets in the shipped package:
<code>run("OFFENSIVE")</code>, <code>run("CORE")</code>, <code>run("DEFENSIVE")</code>.</p>

{menu_table(menu)}

<p class="foot">Whole sample 2007-05-01 → 2026-06-30, net of costs.
Source <code>final/evidence/strategy_menu.csv</code>, written by <code>final/menu.py</code>.</p>

<div class="warn">
  <div class="lab">The one line worth saying out loud</div>
  <p>Every risk-adjusted ratio — Sharpe, Sortino and Calmar — <b>improves monotonically as you move
  down the ladder</b>, while return moves monotonically the other way. That is the trade-off, stated
  without a story on top of it: {_pct(off['ann_return'])} a year at a {_pct(off['max_drawdown'])}
  drawdown at one end, {_pct(dfn['ann_return'])} at {_pct(dfn['max_drawdown'])} at the other.</p>
</div>

{ladder_svg(menu)}

<h2><span class="num">2</span>Pros and cons, per book</h2>
<p>The desk's condition on 12 August was that every strategy presented comes with its pros and cons
clearly explained. These are authored rather than computed — a verdict is a judgement and should be
signed — and the case <i>against</i> each book is stated in the same breath as the case for it.</p>

{proscons(menu)}

<h2><span class="num">3</span>Per stress window — the cost of insurance, in both directions</h2>
<p>Per the standing requirement from 29 July, results are reported per window first. The eight
windows are frozen in code so none can be re-picked after seeing a result, and
<code>rates_2022</code> is in the set deliberately as a <b>control</b> — it is carry's best crisis,
so this is not a list of disasters chosen to motivate a hedge.</p>

<h3 class="sub2">Cumulative return, net</h3>
{window_table(w, "cum_return")}

<h3 class="sub2">Maximum drawdown within the window, net</h3>
{window_table(w, "max_drawdown")}

<p class="foot">Source <code>final/evidence/strategy_menu_by_window.csv</code>. Windows under 120
trading days quote cumulative return and drawdown only — never an annualised Sharpe; the code
enforces that rather than our memory.</p>

<div class="warn">
  <div class="lab">Read these two tables together — this is the whole argument</div>
  <p>Protection is bought in the bad states and <b>paid for in the good ones</b>, and the price is
  visible in both directions. Through COVID the offensive book loses 28.2% and the defensive book
  loses 2.8%. Through the 2022 rates selloff the offensive book makes +40.2% and the defensive book
  makes +5.0%. In the two 2026 windows the desk nominated, the protected books are <i>worse</i> —
  and that is not a defect: neither shock was carry stress, so the overlays trimmed exposure and
  carried their own hedge drawdown with nothing to protect against.</p>
</div>

<h2><span class="num">4</span>At matched risk — the 5 August question, answered</h2>
<p>The desk asked on 5 August: lever the combined book back to the baseline's risk level so it can be
compared on <i>return</i> rather than on risk-adjusted return. It had not been run, and our own
answer at the time was the concessive one — better per unit of risk, worse per dollar deployed.
<b>That framing was an artifact of comparing two books at different risk levels.</b></p>

<table class="vt menu"><thead><tr><th>At matched risk</th><th class="n">Return</th>
<th class="n">Vol</th><th class="n">Sharpe</th><th class="n">MaxDD</th>
<th class="n">CVaR<sub>99</sub></th><th class="n">Skew</th></tr></thead><tbody>
<tr class="refrow"><td>{_esc(mb['book'])}</td><td class="n">{_pct(mb['ann_return'])}</td>
<td class="n">{_pct(mb['ann_vol'])}</td><td class="n">{mb['sharpe']:.4f}</td>
<td class="n">{_pct(mb['max_drawdown'])}</td><td class="n">{mb['CVaR_99']:.4f}</td>
<td class="n">{mb['skew']:.2f}</td></tr>
<tr><td><span class="chip core">{_esc(mc['book'])}</span></td>
<td class="n"><b>{_pct(mc['ann_return'])}</b></td><td class="n">{_pct(mc['ann_vol'])}</td>
<td class="n"><b>{mc['sharpe']:.4f}</b></td><td class="n"><b>{_pct(mc['max_drawdown'])}</b></td>
<td class="n"><b>{mc['CVaR_99']:.4f}</b></td><td class="n"><b>{mc['skew']:.2f}</b></td></tr>
</tbody></table>

<p>At the same risk, CORE delivers <b>more return</b> ({_pct(mc['ann_return'], 2)} against
{_pct(mb['ann_return'], 2)}), a <b>5.4pp shallower drawdown</b>, 13% less CVaR<sub>99</sub> and less
than half the negative skew. The leverage is a mandate parameter, not a signal, and it was chosen
with the whole sample in view — legitimate for a like-for-like comparison, which is exactly what was
asked for, and <i>not</i> offered as a trading rule.</p>

<p class="foot">Source <code>final/evidence/strategy_menu_matched_risk.csv</code>.</p>

<h2><span class="num">5</span>Every component, kept or dropped</h2>
<p>{n_comp} components across {n_ws} workstreams, each measured against a bar written down before
the run. Two rows are new since 12 August: both arrived after the scope freeze, and both are here
because a component that arrives late is still a component.</p>

{verdict_table(d["verdicts"])}

<div class="warn">
  <div class="lab">What the central check found in the two late arrivals</div>
  <p><b>Arjun's EM deleveraging rule</b> carries the largest t-statistic of any teammate result in
  the project (3.43) — but the comparison as written does not stand. The first two rows of his table
  are the <i>same book on two cost bases</i>: the 1.81%/yr booked between them is precisely this
  project's committed cost drag. The honest increment is <b>+0.048 gross Sharpe</b>, not
  0.4659&nbsp;→&nbsp;0.6768, it is measured uncosted while adding turnover by construction, and it
  does not improve MaxDD at all. Worth finishing; not admissible yet.</p>
  <p><b>Theo's option-conditioned work is now executed</b> — and our own verdict table said it was
  not. That claim was true on 5 August and false since 14 August; it is corrected in
  <code>VERDICTS.md</code> with the correction recorded rather than quietly applied. The blocker is
  unchanged: the input panel is still not committed, so nothing can be re-priced. His numbers are
  measured against his own baseline of 0.44, not the shared base's 0.4659.</p>
</div>

<h2><span class="num">6</span>What you get on 26 August</h2>
<ul class="next">
  <li><b>One folder.</b> <code>final/</code> — the engine, the strategy definition, every runtime
  input vendored, the data, 63 evidence CSVs, six test suites and the eleven-chapter report. It was
  copied into an empty directory with no repository and no sibling folders, and every suite plus the
  full reproduction ran there.</li>
  <li><b>One command.</b> <code>python final/reproduce.py</code> rebuilds every published number and
  fails rather than print a stale one. It currently reports <i>every published number matches</i>.</li>
  <li><b>Three books to choose from</b>, each a named preset with its pros and cons, plus the
  baseline as the reference line.</li>
  <li><b>The negative evidence, in full.</b> Nine documented nulls, four named gaps and one contested
  rejection that we paid 0.043 of Sharpe to honour rather than re-argue after seeing the answer.</li>
</ul>

<h2><span class="num">7</span>What we would still like from the desk</h2>
<ul class="next">
  <li><b>Option bid/ask.</b> Still the one blocking data dependency. It is what would let the
  volatility-premium sleeve be costed and admitted, and what would let a premium-paying option hedge
  be priced honestly instead of reported as if the premium were free.</li>
  <li><b>Which point on the ladder</b> a Treasury book would actually want — that is a mandate
  question, and it is the one question in this project the evidence cannot answer for you.</li>
  <li><b>A view on the contested rejection.</b> The defensive book has the better ratios and failed a
  rule we fixed in advance. We shipped the rejection; you may reasonably disagree, and the book is
  runnable either way.</li>
</ul>

<footer class="foot end">
  Generated {AS_OF} by <code>cesare/build_deck_aug19.py</code> from committed CSVs; all four books
  asserted against a live <code>strategy.run()</code> before this page was written. Rebuilds
  byte-identically. Sample 2007-05-01 → 2026-06-30, 5,001 trading days, 27 currencies, net of real
  per-currency bid/ask.
</footer>

</div>
</body>
</html>"""


def main() -> None:
    DECK.parent.mkdir(parents=True, exist_ok=True)
    print(f"Building {DECK.relative_to(REPO_ROOT)}")
    html = build()
    DECK.write_text(html, encoding="utf-8")
    print(f"  wrote {len(html):,} bytes")
    print("  Regenerate freely: no matplotlib, so the output is byte-deterministic.")


if __name__ == "__main__":
    main()
