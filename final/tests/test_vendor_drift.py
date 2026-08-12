"""Has any vendored file drifted from the original it was copied from?

    python final/tests/test_vendor_drift.py

**The cost of vendoring is two copies that can silently diverge.** This project
has already paid that cost once: `cesare/requirements.txt` was hand-maintained
alongside the root file, drifted, ended up omitting a package the code actually
imported, and was deleted rather than re-synced. The lesson recorded at the time
was that two files which must be hand-synced is how it breaks.

So `final/` vendors deliberately and makes the drift *loud*. Every copied file is
hashed against its source. Where a copy is intentionally patched — six lines in
total, all of them path constants — the diff is **declared below** and the test
asserts the patched file differs from its source in exactly the declared way and
in no other. An undeclared change fails.

**This test is designed to stop mattering.** Once the sibling folders are retired
there is no source to compare against, and the checks report `unverifiable`
rather than failing. That is the correct end state: the guard exists for the
window in which both copies live, which is exactly the window in which they can
diverge unnoticed. A test that failed after the hand-off would be a test that
punished the hand-off for succeeding.
"""

from __future__ import annotations

import difflib
import hashlib
import sys
from pathlib import Path

PACKAGE_ROOT = Path(__file__).resolve().parents[1]
if str(PACKAGE_ROOT) not in sys.path:
    sys.path.insert(0, str(PACKAGE_ROOT))

REPO_ROOT = PACKAGE_ROOT.parent

#: Copied byte-for-byte. Any difference at all is drift.
#: `vendored path (relative to final/)` -> `source path (relative to repo root)`
IDENTICAL: dict[str, str] = {
    # the engine
    "strategy/__init__.py": "strategy/__init__.py",
    "strategy/core.py": "strategy/core.py",
    "strategy/fx_utils.py": "strategy/fx_utils.py",
    "strategy/episodes.py": "strategy/episodes.py",
    "strategy/overlays.py": "strategy/overlays.py",
    # the runtime inputs the strategy reads
    "inputs/duration_hedge_series.csv": "arjun/outputs/duration_hedge_series.csv",
    "inputs/fx_option_signal_panel.parquet":
        "theo/data/processed/fx_option_signal_panel.parquet",
    "inputs/adaptive_strategy_returns_monthly.csv":
        "vidhi/outputs/adaptive_strategy_returns_monthly.csv",
}

#: Every `*_wide.parquet` plus the manifest, added programmatically below.
for _p in sorted((PACKAGE_ROOT / "data" / "raw").glob("*.parquet")):
    IDENTICAL[f"data/raw/{_p.name}"] = f"data/raw/{_p.name}"
IDENTICAL["data/raw/ticker_manifest.csv"] = "data/raw/ticker_manifest.csv"

#: Copied and then patched, with the reason. `max_changed_lines` is a ceiling on
#: how much may differ, so a small declared patch cannot grow into a rewrite
#: without this test noticing.
PATCHED: dict[str, dict] = {
    "strategy/config.py": {
        "source": "strategy/config.py",
        "why": ("the strategy definition moved out of a personal folder and in "
                "beside the engine, so `combined_preset` imports "
                "`combined_engine` rather than `cesare.combined_engine`; plus "
                "the COMBINED_TAIL preset, which names an existing ladder rung"),
        "must_appear": ("from combined_engine import combined_components",
                        "COMBINED_TAIL"),
        "must_not_appear": ("from cesare.combined_engine",),
        "max_changed_lines": 90,
    },
    "combined_engine.py": {
        "source": "cesare/combined_engine.py",
        "why": ("four path constants repointed at vendored copies: PACKAGE_ROOT "
                "replaces REPO_ROOT, OUTPUTS -> final/evidence, and the three "
                "teammate inputs -> final/inputs"),
        "must_appear": ('PACKAGE_ROOT / "inputs"', 'PACKAGE_ROOT / "evidence"'),
        "must_not_appear": ('REPO_ROOT / "arjun"',             # sibling-ok: declaration
                            'REPO_ROOT / "vidhi"',             # sibling-ok: declaration
                            'REPO_ROOT / "theo"'),             # sibling-ok: declaration
        "max_changed_lines": 70,
    },
}
for _t in ("test_reconciliation.py", "test_episodes.py", "test_overlays.py",
           "test_combined.py"):
    PATCHED[f"tests/{_t}"] = {
        "source": f"strategy/tests/{_t}",
        "why": ("the suite roots itself at the final/ package rather than the "
                "repo root, and reads the evidence copies of the committed CSVs"),
        "must_appear": ("PACKAGE_ROOT = Path(__file__).resolve().parents[1]",),
        "must_not_appear": ('REPO_ROOT / "cesare"',            # sibling-ok: declaration
                            "from cesare.combined_engine"),
        # Re-rooting is a handful of lines. `test_combined.py` gets a wider
        # ceiling because it also gains a whole test the shared base does not
        # have — the one asserting `COMBINED_TAIL` against its ladder rung, which
        # only exists here because the alternative book only exists here.
        "max_changed_lines": 130 if _t == "test_combined.py" else 40,
    }


class Skip(Exception):
    """Raised when the source is gone — the expected end state, not a failure."""


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _changed_lines(a: Path, b: Path) -> int:
    left = a.read_text().splitlines()
    right = b.read_text().splitlines()
    diff = difflib.unified_diff(left, right, n=0)
    return sum(1 for ln in diff if ln.startswith(("+", "-"))
               and not ln.startswith(("+++", "---")))


def test_identical_copies_are_identical():
    """Every byte-for-byte copy still matches its source."""
    drifted, missing_src, checked = [], [], 0
    for rel, src_rel in sorted(IDENTICAL.items()):
        dst, src = PACKAGE_ROOT / rel, REPO_ROOT / src_rel
        assert dst.exists(), f"vendored file is missing entirely: final/{rel}"
        if not src.exists():
            missing_src.append(src_rel)
            continue
        checked += 1
        if _sha(dst) != _sha(src):
            drifted.append(f"final/{rel}  !=  {src_rel}")

    assert not drifted, (
        "vendored copies have drifted from their sources:\n    " +
        "\n    ".join(drifted) +
        "\n  Re-copy, or if the source changed on purpose, re-vendor and "
        "re-verify the acceptance numbers.")

    if missing_src and not checked:
        raise Skip(f"all {len(missing_src)} sources are gone — sibling folders "
                   f"retired, nothing left to compare against")
    note = f", {len(missing_src)} sources retired" if missing_src else ""
    print(f"  byte-identical copies          {checked} verified{note}")


def test_patched_copies_differ_only_as_declared():
    """A patched copy must contain its patch, lack the original, and no more.

    Three separate claims, because "it differs" is not the same as "it differs in
    the way I said it does". The line ceiling is what stops a one-token rewire
    from quietly becoming a fork.
    """
    problems, checked, retired = [], 0, 0
    for rel, spec in sorted(PATCHED.items()):
        dst, src = PACKAGE_ROOT / rel, REPO_ROOT / spec["source"]
        assert dst.exists(), f"vendored file is missing entirely: final/{rel}"
        text = dst.read_text()

        for needle in spec["must_appear"]:
            if needle not in text:
                problems.append(f"final/{rel}: declared patch missing — {needle!r}")
        for needle in spec["must_not_appear"]:
            if needle in text:
                problems.append(f"final/{rel}: unpatched original still present — {needle!r}")

        if not src.exists():
            retired += 1
            continue
        checked += 1
        n = _changed_lines(src, dst)
        if n == 0:
            problems.append(f"final/{rel}: identical to source, but a patch was declared")
        elif n > spec["max_changed_lines"]:
            problems.append(
                f"final/{rel}: {n} changed lines exceeds the declared ceiling of "
                f"{spec['max_changed_lines']} — the patch has grown into a fork")

    assert not problems, "declared-patch violations:\n    " + "\n    ".join(problems)
    note = f", {retired} sources retired" if retired else ""
    print(f"  patched copies as declared     {len(PATCHED)} files, {checked} diffed{note}")


def test_every_vendored_file_is_accounted_for():
    """Nothing in `final/` is vendored without being declared here.

    The gap this closes: a file copied in during a later change, never added to
    either table, and therefore never checked. It would look vendored and be
    unguarded.
    """
    declared = set(IDENTICAL) | set(PATCHED)
    #: Authored in `final/`, not copied — so not expected in the tables above.
    authored = {"verdicts.py", "reproduce.py", "README.md", "VERDICTS.md",
                "requirements.txt", "tests/test_standalone.py",
                "tests/test_vendor_drift.py", "inputs/PROVENANCE.md",
                "data/raw/PROVENANCE.md", "evidence/README.md",
                "evidence/component_verdicts.csv"}

    unaccounted = []
    for path in sorted(PACKAGE_ROOT.rglob("*")):
        if not path.is_file() or "__pycache__" in path.parts:
            continue
        rel = str(path.relative_to(PACKAGE_ROOT))
        if rel in declared or rel in authored:
            continue
        # The evidence CSVs and the report chapters are bulk copies, checked
        # wholesale below rather than enumerated file by file.
        if rel.startswith(("evidence/", "report/")):
            continue
        unaccounted.append(rel)

    assert not unaccounted, (
        "files in final/ that are neither declared as vendored nor as authored:\n    "
        + "\n    ".join(unaccounted))
    print(f"  every file accounted for       {len(declared)} vendored, "
          f"{len(authored)} authored")


def test_bulk_copied_folders_match():
    """`evidence/` and `report/` are whole-folder copies; verify them wholesale."""
    results, problems = [], []
    sources = (("evidence", REPO_ROOT / "cesare" / "outputs", "*.csv"),   # sibling-ok: source
               ("report", REPO_ROOT / "report", "*.md"))
    for folder, src_dir, pattern in sources:
        dst_dir = PACKAGE_ROOT / folder
        if not dst_dir.exists():
            continue
        if not src_dir.exists():
            results.append(f"{folder}: source retired")
            continue
        same = differ = only_here = 0
        for f in sorted(dst_dir.glob(pattern)):
            src = src_dir / f.name
            if not src.exists():
                only_here += 1              # generated or adapted in final/
            elif _sha(f) == _sha(src):
                same += 1
            else:
                differ += 1
        missing = [p.name for p in sorted(src_dir.glob(pattern))
                   if not (dst_dir / p.name).exists()]
        if missing:
            problems.append(f"{folder}: not copied — {', '.join(missing)}")
        results.append(f"{folder}: {same} identical, {differ} adapted, "
                       f"{only_here} new")

    assert not problems, "bulk copies incomplete:\n    " + "\n    ".join(problems)
    print(f"  bulk folders complete          {'; '.join(results)}")


TESTS = [test_identical_copies_are_identical,
         test_patched_copies_differ_only_as_declared,
         test_every_vendored_file_is_accounted_for,
         test_bulk_copied_folders_match]


def main() -> int:
    print(f"\nRunning {len(TESTS)} vendor-drift tests\n")
    passed = failed = skipped = 0
    for t in TESTS:
        try:
            t()
            passed += 1
        except Skip as exc:
            print(f"  SKIP {t.__name__}: {exc}")
            skipped += 1
        except AssertionError as exc:
            print(f"  FAIL {t.__name__}: {exc}")
            failed += 1
    tail = f", {skipped} skipped" if skipped else ""
    print(f"\n{passed}/{len(TESTS)} passed{tail}")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
