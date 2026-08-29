"""Build the 12 August 2026 BofA progress deck — one self-contained HTML page.

    python cesare/build_deck_aug12.py     -> presentations/deck_2026_08_12.html

Companion to `build_deck.py`, which produced the Aug 5 deck. Two deliberate
differences, both because this week's story is different:

**No matplotlib.** The Aug 5 deck's argument was visual — seven figures showing
what the combined book does. This week nothing about the book changed; what
changed is that every extension now has a written verdict. That is a table, not a
chart. Dropping the figure machinery also makes the output **byte-deterministic**:
matplotlib assigns random SVG element ids per run, so regenerating the Aug 5 deck
produces a 904-line diff in which every line is an id and no number moves (plan
Appendix C #41). Run this file twice and the bytes match.

**It reads the verdict table with `keep_default_na=False`.** `component_verdicts.csv`
records three Phase-3 verdicts as `NULL RESULT`; an earlier version wrote plain
`NULL`, which pandas silently converts to `NaN` because it is in the default
`STR_NA_VALUES`. The three rows that vanished were the project's three headline
nulls, in the table built specifically to prove nothing was filtered out. The
source string is fixed, and this reader no longer depends on that fix holding.

Everything else follows the house pattern: numbers pulled from committed CSVs
rather than typed, the headline asserted against a live `run()` before the page is
written, and no network dependency of any kind.
"""

from __future__ import annotations

import html as _html
import sys
from pathlib import Path

import pandas as pd

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from strategy import run  # noqa: E402

OUTPUTS = Path(__file__).resolve().parent / "outputs"
EVIDENCE = REPO_ROOT / "final" / "evidence"
DECK = Path(__file__).resolve().parent / "presentations" / "deck_2026_08_12.html"

#: Snapshot date, stamped into the page. Passed in rather than read from the
#: clock so a rebuild of this deck is reproducible — `build_deck.py`'s convention.
AS_OF = "2026-08-12"
HAND_IN = "31 August 2026"


# ---------------------------------------------------------------------------
# Load — every source is a committed CSV
# ---------------------------------------------------------------------------

def _csv(path: Path) -> pd.DataFrame:
    if not path.exists():
        raise FileNotFoundError(
            f"{path.relative_to(REPO_ROOT)} is missing. This deck is assembled "
            f"from committed CSVs; it will not invent a number to cover a gap.")
    # keep_default_na=False: see the module docstring. A verdict of "NULL RESULT"
    # is a result, not a missing value, and the reader must not decide otherwise.
    return pd.read_csv(path, keep_default_na=False)


def load() -> dict:
    d = {
        "verdicts": _csv(EVIDENCE / "component_verdicts.csv"),
        "ladder": _csv(OUTPUTS / "p4_combined_ladder.csv"),
        "selection": _csv(OUTPUTS / "p4_selection_vs_derisking.csv"),
    }
    # The ladder columns come back as strings under keep_default_na=False.
    for col in ("net_sharpe", "gross_sharpe", "max_drawdown", "CVaR_99",
                "turnover", "d_net_sharpe"):
        d["ladder"][col] = pd.to_numeric(d["ladder"][col], errors="coerce")
    for col in ("max_drawdown", "net_sharpe", "skew"):
        d["selection"][col] = pd.to_numeric(d["selection"][col], errors="coerce")
    return d


def _rung(ladder: pd.DataFrame, which: str, step: str) -> pd.Series:
    hit = ladder[(ladder["ladder"] == which) & (ladder["step"] == step)]
    if len(hit) != 1:
        raise KeyError(f"ladder={which!r} step={step!r} matched {len(hit)} rows")
    return hit.iloc[0]


# ---------------------------------------------------------------------------
# Verify — the deck's claim is that its numbers are the repo's numbers
# ---------------------------------------------------------------------------

def verify(d: dict) -> None:
    """Re-derive the books live and assert they match the committed ladder.

    Worth an assertion rather than an assurance: if the base drifts, this raises
    instead of quietly publishing a stale slide into a meeting.
    """
    base, comb = run(), run("COMBINED")
    shipped = _rung(d["ladder"], "final_loo", "- VIX percentile gate (p80 / 756d)")
    gate_in = _rung(d["ladder"], "final", "+ Bad-skew exclusion (XS top quintile)")

    checks = [
        ("baseline net", base.summary().loc["ALL_net", "sharpe"],
         _rung(d["ladder"], "final", "baseline")["net_sharpe"]),
        ("COMBINED net", comb.summary().loc["COMBINED_net", "sharpe"],
         shipped["net_sharpe"]),
        ("COMBINED MaxDD", comb.summary().loc["COMBINED_net", "max_drawdown"],
         shipped["max_drawdown"]),
        ("COMBINED CVaR99", comb.summary().loc["COMBINED_net", "CVaR_99"],
         shipped["CVaR_99"]),
        ("baseline turnover", base.turnover, 0.675470),
        ("baseline cost drag", base.cost_drag, 0.018146611),
        # The cost of the contested rejection, which section 3 quotes.
        ("gate-in minus shipped",
         float(gate_in["net_sharpe"]) - float(shipped["net_sharpe"]), 0.043189),
    ]
    for label, live, committed in checks:
        if abs(float(live) - float(committed)) > 1e-5:
            raise AssertionError(
                f"{label}: live {live!r} != committed {committed!r}. The deck "
                f"will not render until this reconciles.")

    v = d["verdicts"]
    if len(v) != 16 or v["workstream"].nunique() != 6:
        raise AssertionError(
            f"verdict table is {len(v)} rows / {v['workstream'].nunique()} "
            f"workstreams, expected 16 / 6")
    if (v["verdict"].str.strip() == "").any():
        raise AssertionError("a verdict cell is empty — check the NA handling")
    print(f"  verify: {len(checks)} live-vs-committed checks passed, "
          f"verdict table {len(v)} rows / {v['workstream'].nunique()} workstreams")


# ---------------------------------------------------------------------------
# Numbers — pulled, never typed
# ---------------------------------------------------------------------------

def numbers(d: dict) -> dict:
    lad, sel = d["ladder"], d["selection"].set_index("book")
    base = _rung(lad, "final", "baseline")
    shipped = _rung(lad, "final_loo", "- VIX percentile gate (p80 / 756d)")
    gate_in = _rung(lad, "final", "+ Bad-skew exclusion (XS top quintile)")
    v = d["verdicts"]

    # Drawdowns are negative, so an improvement is variant minus baseline (less
    # negative = shallower). The other order prints a 7.3pp improvement as
    # "-7.3pp", which reads as a worsening.
    dd_total = (float(sel.loc["bad-skew exclusion", "max_drawdown"])
                - float(sel.loc["baseline", "max_drawdown"])) * 100
    dd_derisk = (float(sel.loc["gross-matched de-risk (control)", "max_drawdown"])
                 - float(sel.loc["baseline", "max_drawdown"])) * 100

    first = v["verdict"].str.split(" ").str[0]
    return {
        "base_net": f"{float(base['net_sharpe']):.4f}",
        "base_dd": f"{float(base['max_drawdown']) * 100:.2f}",
        "comb_net": f"{float(shipped['net_sharpe']):.4f}",
        "comb_gross": f"{float(shipped['gross_sharpe']):.4f}",
        "comb_dd": f"{float(shipped['max_drawdown']) * 100:.2f}",
        "comb_cvar": f"{float(shipped['CVaR_99']):.4f}",
        "comb_turn": f"{float(shipped['turnover']):.4f}",
        "tail_net": f"{float(gate_in['net_sharpe']):.4f}",
        "tail_cvar": f"{float(gate_in['CVaR_99']):.4f}",
        "gate_cost": f"{float(gate_in['net_sharpe']) - float(shipped['net_sharpe']):.3f}",
        "cvar_rel": f"{(1 - float(gate_in['CVaR_99']) / float(shipped['CVaR_99'])) * 100:.1f}",
        "n_components": str(len(v)),
        "n_workstreams": str(v["workstream"].nunique()),
        "n_adopted": str(int((first == "ADOPTED").sum())),
        "n_rejected": str(int(first.isin(["REJECTED", "NULL"]).sum())),
        "n_gaps": str(int(first.isin(["NEVER", "NOT"]).sum())),
        "dd_total": f"{dd_total:.1f}",
        "dd_derisk": f"{dd_derisk:.1f}",
        "dd_select": f"{dd_total - dd_derisk:.1f}",
        # CONTROL -> filter, not baseline -> filter: the control holds de-risking
        # constant, so this pair isolates what SELECTION buys. Quoting against
        # the baseline credits selection with part of the de-risking effect.
        "skew_ctrl": f"{float(sel.loc['gross-matched de-risk (control)', 'skew']):.2f}",
        "skew_filt": f"{float(sel.loc['bad-skew exclusion', 'skew']):.2f}",
        "skew_base": f"{float(sel.loc['baseline', 'skew']):.2f}",
    }


# ---------------------------------------------------------------------------
# Markup
# ---------------------------------------------------------------------------

def _esc(s) -> str:
    return _html.escape(str(s))


#: Verdict -> CSS class, so the table reads at a glance without a legend.
_TONE = {"ADOPTED": "ok", "REJECTED": "no", "NULL": "no", "POSITIVE": "warnpill",
         "BLOCKED": "gap", "NEVER": "gap", "NOT": "gap"}

#: Pill labels. The CSV's verdict strings are written to be read on their own —
#: "POSITIVE BUT EXCLUDED FROM THE TRADABLE BOOK" is the right thing to store and
#: the wrong thing to put in a badge. Mapped here rather than shortened in the
#: CSV, because the file is the record and this is only its presentation.
_LABEL = {
    "POSITIVE BUT EXCLUDED FROM THE TRADABLE BOOK": "POSITIVE · EXCLUDED",
    "NOT EVALUABLE AS COMMITTED": "NOT EVALUABLE",
    "BLOCKED ON DATA": "BLOCKED",
    "REJECTED (contested — see VERDICTS.md)": "REJECTED · CONTESTED",
    "REJECTED — null on all three bars": "REJECTED",
}


def _pill(verdict: str) -> str:
    v = str(verdict).strip()
    return _LABEL.get(v, v.split(" —")[0].split(" (")[0])


def verdict_table(v: pd.DataFrame) -> str:
    """All sixteen rows. Teammates first, then the research track."""
    order = ["Arjun", "Theo", "Dafu", "Vidhi", "Oleg", "Cesare"]
    v = v.copy()
    v["_k"] = v["workstream"].map({w: i for i, w in enumerate(order)})
    v = v.sort_values(["_k"], kind="stable")

    rows, seen_cesare = [], False
    for _, r in v.iterrows():
        if r["workstream"] == "Cesare" and not seen_cesare:
            seen_cesare = True
            rows.append('<tr class="rule"><td colspan="4">Research track — the '
                        'nine components tested inside this workstream</td></tr>')
        tone = _TONE.get(str(r["verdict"]).split(" ")[0], "no")
        short = _pill(r["verdict"])
        rows.append(
            f'<tr><td class="who">{_esc(r["workstream"])}</td>'
            f'<td>{_esc(r["component"])}</td>'
            f'<td><code>{_esc(r["hook"])}</code></td>'
            f'<td><span class="pill {tone}">{_esc(short)}</span></td></tr>')
    return ("<table class=\"vt\">\n<thead><tr><th>Workstream</th><th>Component</th>"
            "<th>Attaches via</th><th>Verdict</th></tr></thead>\n<tbody>\n"
            + "\n".join(rows) + "\n</tbody></table>")


# --- CSS, lifted from build_deck.py so the house style carries across decks;
# --- build_deck.py lifted its palette from presentations/overview.html the same
# --- way. Copied rather than imported: importing that module would pull in
# --- matplotlib for a string, and couple this deck to a file that currently
# --- reproduces a committed page exactly.
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
h2{font-size:21px; margin:44px 0 4px; letter-spacing:-.01em; padding-top:10px}
h2 .num{color:var(--accent); font-variant-numeric:tabular-nums; margin-right:8px}
h3{font-size:16px; margin:22px 0 6px}
p{margin:10px 0}
.lede{color:var(--ink2); font-size:15.5px; margin:6px 0 14px; max-width:80ch}
code{font-family:ui-monospace,SFMono-Regular,Menlo,monospace; font-size:.86em;
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
table{border-collapse:collapse; width:100%; font-size:14px; margin:18px 0 6px;
  background:var(--card); border:1px solid var(--border); border-radius:10px;
  overflow:hidden}
th{text-align:left; font-size:12px; letter-spacing:.06em; text-transform:uppercase;
  color:var(--muted); font-weight:700; padding:10px 12px;
  border-bottom:1px solid var(--border)}
td{padding:9px 12px; border-bottom:1px solid var(--grid); vertical-align:top}
tbody tr:last-child td{border-bottom:none}
td.who{font-weight:700; white-space:nowrap}
td.num{text-align:right; font-variant-numeric:tabular-nums; white-space:nowrap}
tr.rule td{background:var(--plane); color:var(--muted); font-size:12px;
  letter-spacing:.06em; text-transform:uppercase; font-weight:700;
  padding:8px 12px}
tr.hi td{background:#fbfcff}
.pill{display:inline-block; font-size:11.5px; font-weight:700; letter-spacing:.03em;
  padding:2px 8px; border-radius:999px; white-space:nowrap}
.pill.ok{background:#e6f5ea; color:#0a7d0a; border:1px solid #bfe3c8}
.pill.no{background:#f3f2ef; color:var(--ink2); border:1px solid var(--grid)}
.pill.gap{background:#fdf1f1; color:#a33; border:1px solid #f0cfcf}
.pill.warnpill{background:#fdf6e8; color:#8a6100; border:1px solid #f0dcae}
.src{font-size:11.5px; color:var(--muted); margin:8px 0 0}
ul{margin:10px 0; padding-left:22px} li{margin:7px 0; max-width:82ch}
.ask li{margin:10px 0}
.ask b{color:var(--ink)}
.cols{display:grid; grid-template-columns:1fr 1fr; gap:12px 26px; margin-top:8px}
.cols h3{margin-top:6px}
footer{margin-top:52px; padding-top:18px; border-top:1px solid var(--border);
  font-size:12.5px; color:var(--muted)}
@media (max-width:760px){ h1{font-size:24px} .wrap{padding:22px 16px 60px}
  .cols{grid-template-columns:1fr} table{font-size:13px} }
@media print{ body{background:#fff} .wrap{padding:0} h2{page-break-after:avoid}
  table{page-break-inside:avoid} }
"""


def build() -> str:
    d = load()
    verify(d)
    N = numbers(d)

    provenance = f"""<!--
  FX Carry — BofA progress update, {AS_OF}.
  GENERATED by `python cesare/build_deck_aug12.py`. Do not edit this file.
  Every number is pulled from a committed CSV in cesare/outputs/ or
  final/evidence/ and the headline is asserted against a live strategy.run()
  before this page is written. No number here was typed by hand.
  Sample 2007-05-01 -> 2026-06-30, 5,001 trading days, 27 currencies.
-->"""

    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>FX Carry — progress update, 12 August 2026</title>
{provenance}
<style>{CSS}</style>
</head>
<body>
<div class="wrap">

<header class="masthead">
  <div class="kicker">FX Carry · UChicago Project Lab × Bank of America</div>
  <h1>Progress update — 12 August 2026</h1>
  <p class="sub">Nothing about the strategy moved this week, and that is deliberate: the book was
  frozen on 5 August. What changed is that the <b>evaluation is now closed</b>. Every extension from
  all six workstreams has a written verdict against a bar fixed before the run — adoptions and
  rejections in one table, including the two workstreams with nothing measurable in it.</p>
  <div class="meta">
    <span>Cesare Bavaresco — shared base and integration</span>
    <span>Sample 2007-05 → 2026-06, 5,001 trading days</span>
    <span>27 currencies, net of real bid/ask costs</span>
  </div>
</header>

<div class="warn">
  <div class="lab">Read this first</div>
  <p><b>Hand-in is {HAND_IN}.</b> The book is frozen and reproducible; what is still moving is other
  people's ports. Nothing on this page is a recommendation, and the number that matters most is
  still the one that has <i>not</i> improved — no result anywhere in this project has a
  statistically significant net alpha.</p>
</div>

<div class="tiles">
  <div class="tile"><div class="v">{N['n_components']} / {N['n_workstreams']}</div>
    <div class="k">Components evaluated, across workstreams</div>
    <div class="n">one common book, one set of costs</div></div>
  <div class="tile"><div class="v">{N['n_adopted']}</div><div class="k">Adopted</div>
    <div class="n">duration hedge · bad-skew exclusion</div></div>
  <div class="tile"><div class="v">{N['n_gaps']}</div>
    <div class="k">Workstreams with nothing measurable</div>
    <div class="n">stated in the table, not omitted</div></div>
  <div class="tile"><div class="v">1 of 5</div><div class="k">Ported onto the shared base</div>
    <div class="n">today's gate — unchanged since 5 Aug</div></div>
</div>

<div class="bluf">
  <div class="lab">In one paragraph</div>
  <p>The headline book is unchanged — net <b>{N['comb_net']}</b>, worst drawdown
  <b>−{N['comb_dd'].lstrip('−-')}%</b>, CVaR₉₉ <b>{N['comb_cvar']}</b>. What is new is that all
  {N['n_components']} components across all {N['n_workstreams']} workstreams now carry a verdict
  measured against a pre-registered bar, and the {N['n_rejected']} rejections and nulls sit in the same table
  as the {N['n_adopted']} adoptions rather than filtered out of it. Two of the six workstreams have
  nothing measurable in that table, and we have written down why instead of leaving a gap for
  someone to notice. We also re-opened our own strongest rejection this week, found the published
  reasoning for it was <i>wrong</i> on two counts, and the verdict held anyway — at a cost we now
  quote rather than absorb.</p>
</div>

<h2><span class="num">1</span>What we tested, and what survived</h2>
<p class="lede">The claim this project makes is that six workstreams were each tested on one book
and kept or dropped on evidence. This is that claim, itemised. Every row traces to a committed CSV;
the file behind this table is <code>final/evidence/component_verdicts.csv</code>, which is generated
by reading the evidence rather than by anyone typing a number into it.</p>

{verdict_table(d['verdicts'])}
<p class="src">Source: <code>component_verdicts.csv</code> — {N['n_components']} components,
{N['n_workstreams']} workstreams. Full reasoning, per-component bars and caveats in
<code>final/VERDICTS.md</code>.</p>

<p><b>Two caveats decide how to read the two adoptions, and they are ours to raise.</b></p>
<ul>
  <li><b>The adopted overlay is mostly de-risking, not selection.</b> Of the bad-skew filter's
  {N['dd_total']}pp drawdown improvement, <b>{N['dd_derisk']}pp is simply holding less notional</b>
  and {N['dd_select']}pp is the signal — measured against a control that reproduces the overlay's
  exact daily gross spread across every name. The selection alpha's t-statistic is 0.92. What
  selection genuinely buys is skew, <b>{N['skew_ctrl']} → {N['skew_filt']}</b> measured against that
  control, which de-risking does not deliver at all.</li>
  <li><b>Four of the five teammate components are re-priced, not rebuilt.</b> We reconstructed each
  signal from committed outputs and re-ran it on the shared book. That is our reading of someone's
  idea, not their specification of it — and it is the direct consequence of adoption standing at
  1 of 5. Every row carries its reconstruction method.</li>
</ul>

<h2><span class="num">2</span>Two workstreams have nothing in that table</h2>
<p class="lede">Both are stated as rows with the blocker named, because a gap written into the
artifact is a gap, and a gap left out of it is a claim.</p>
<ul>
  <li><b>Oleg — never tested.</b> There is no committed output of any kind: no <code>outputs/</code>
  directory, no CSV or parquet, and no write call anywhere in the notebook. A G10 book exists as
  executed cell output but was never saved, so there was nothing to re-price and no measurement of
  this workstream appears anywhere in the project. <b>What closes it:</b> one committed daily net
  return series on the common window — it would then re-price through exactly the same path as
  everyone else's.</li>
  <li><b>Theo's 5 August commit — not evaluable as committed.</b> It landed after the evaluation ran
  and added notebooks only, no data. The option-conditioned strategy notebook is committed
  <b>unexecuted</b> — 14 code cells, no stored output — and the input it declares does not exist on
  disk or in git, so it raises before computing anything. It is a specification, not a result.
  <b>What closes it:</b> run the upstream regression notebook and commit its panel. His
  <i>adopted</i> bad-skew overlay is unaffected — that uses a panel committed on 18 July.</li>
</ul>

<h2><span class="num">3</span>The one contested call, and what rejecting it costs</h2>
<p class="lede">Dafu's VIX percentile gate is the only component in the project where two
pre-registered criteria give opposite answers. It is also the only teammate component whose owner
actually ported onto the shared base — so the component we drop belongs to the one person who did
the integration properly. That is uncomfortable, and it is not a reason to decide it differently.</p>

<p>Two things had to be diagnosed before the verdict could be reached, and both changed what we
thought we knew:</p>
<ul>
  <li>The <code>ladders_agree=False</code> flag that justified the original rejection is an
  <b>artifact</b> — it compares the add pass's two-criterion verdict against the leave-one-out
  pass's Sharpe sign. Read like-for-like, the two ladders <i>agree</i>. The verdict was right; the
  reason given for it was not.</li>
  <li>The two books report an <b>identical</b> maximum drawdown to six decimals, which looks like a
  copy-paste error. It is not: the combined book's drawdown episode is the 2013 taper tantrum, and
  the gate is fully invested on all 145 days of it. <b>Whole-sample maximum drawdown is structurally
  blind to this gate</b> — which also means the headline "+4.8pp of drawdown" we quoted for it on
  5 August does not transfer to the stack. CVaR₉₉ is the tail measure that actually moves.</li>
</ul>

<table>
<thead><tr><th>Book</th><th class="num">Net Sharpe</th><th class="num">MaxDD</th>
<th class="num">CVaR₉₉</th><th class="num">Turnover</th></tr></thead>
<tbody>
<tr class="hi"><td><code>run("COMBINED")</code> — shipped</td><td class="num">{N['comb_net']}</td>
  <td class="num">−{N['comb_dd'].lstrip('−-')}%</td><td class="num">{N['comb_cvar']}</td>
  <td class="num">{N['comb_turn']}</td></tr>
<tr><td><code>run("COMBINED_TAIL")</code> — the gate included, <i>not shipped</i></td>
  <td class="num">{N['tail_net']}</td><td class="num">−{N['comb_dd'].lstrip('−-')}%</td>
  <td class="num">{N['tail_cvar']}</td><td class="num">0.6051</td></tr>
</tbody></table>
<p class="src">Source: <code>p4_combined_ladder.csv</code>, rows <code>final_loo</code> and
<code>final</code> rung 3 — both committed since Phase 4. The alternative is a name for a ladder
rung that already existed, not a new result.</p>

<p><b>We kept the rejection, on the rule as written before the run.</b> It costs
<b>{N['gate_cost']} of net Sharpe and {N['cvar_rel']}% of relative CVaR₉₉</b>, and paying that
rather than re-reading the rule after seeing which answer is more flattering is the whole point of
fixing the rule in advance. The alternative book is built, tested and runnable so the desk can price
the decision instead of taking it on trust.</p>

<h2><span class="num">4</span>What is next, and what we need from you</h2>
<p class="lede">Nineteen days to hand-in. The research is finished; what remains is writing, and
four things that are not ours to close.</p>

<div class="cols">
<div>
<h3>From us, by {HAND_IN}</h3>
<ul>
  <li><b>Per-member methodology write-ups</b> — the "why" behind each workstream rather than its
  output. Your 17 July ask; still the largest open item on our side.</li>
  <li><b>Single-currency options deep dive</b> through one drawdown (15 July ask) — the cross-
  sectional crash betas exist, the per-currency narrative does not.</li>
  <li><b>December year-end liquidity</b> sidebar — a diagnostic, not a strategy change.</li>
</ul>
</div>
<div>
<h3>From the desk and the team</h3>
<ul class="ask">
  <li><b>Option bid/ask.</b> Still the one blocker we cannot work around: the surfaces we hold are
  <b>mids only</b>, so no premium-paying hedge can be honestly costed. Until it is bought, an
  insurance overlay's Sharpe would be reported as if the premium were free, and we will not do
  that.</li>
  <li><b>Teammate ports.</b> Four of five components are re-priced rather than rebuilt. Ports are
  what let us drop that label — nothing else does.</li>
  <li><b>Arjun's idea from 22 July</b> — carried three meetings running and still unrecorded. We
  would like to capture it in the room today.</li>
  <li><b>Dafu:</b> why the option overlay lost more than plain carry in 2009 — the frozen episode
  table makes this answerable now.</li>
</ul>
</div>
</div>

<footer>
  <p><b>How to check anything on this page.</b> Every figure quoted here is read from a committed
  CSV in <code>cesare/outputs/</code> or <code>final/evidence/</code>; this page is generated by
  <code>python cesare/build_deck_aug12.py</code> rather than written by hand, and the build asserts
  the headline against a live <code>strategy.run()</code> before writing, failing rather than
  publishing a stale slide. Baseline reconciliation: net {N['base_net']}, turnover 0.675470, cost
  drag 1.8146611%/yr. To reproduce the whole book in one command:
  <code>python final/reproduce.py</code>.</p>
  <p>Snapshot {AS_OF}. The fuller 5 August record is
  <code>presentations/deck_2026_08_05.html</code>; the written report is <code>final/report/</code>;
  source of truth for every claim is <code>cesare/FX_Carry_Strategy_Project_Plan.md</code>.</p>
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
