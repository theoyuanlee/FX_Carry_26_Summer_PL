"""Does `final/` still run if every other folder is deleted?

    python final/tests/test_standalone.py

**This is the acceptance test for the whole package.** A green strategy test
suite proves the numbers are right; it does not prove the package is
self-contained, because a test that reads a teammate's file passes perfectly well
right up until that teammate's folder is retired. The failure would surface at the
worst possible moment — after the hand-off, on someone else's machine — and it
would surface as `FileNotFoundError`, which reads like a broken deliverable rather
than a missing dependency.

So the question is not "do the tests pass". It is **"would this run if every
sibling folder were deleted"**, and the only honest way to answer it is to watch
what the code actually opens.

Five tests, in increasing order of how hard they are to fool:

1.  every module resolves under `final/` — no import leaks to a repo-root twin
2.  **every file opened during a full run lives under `final/`** — traced, not
    reasoned about. This is the one that matters
3.  the strategy runs with `final/` as the only entry on `sys.path`
4.  the strategy runs from a working directory outside the repo entirely
5.  no source file names a sibling folder in a path expression

Test 2 catches what code review does not. `run("COMBINED")` reaches through
`config.combined_preset` -> `combined_engine` -> three input files -> the engine
-> thirteen parquets, and a single stale constant anywhere in that chain is
invisible until you trace the opens.
"""

from __future__ import annotations

import builtins
import os
import subprocess
import sys
import tempfile
from pathlib import Path

import pandas as pd

PACKAGE_ROOT = Path(__file__).resolve().parents[1]
if str(PACKAGE_ROOT) not in sys.path:
    sys.path.insert(0, str(PACKAGE_ROOT))

REPO_ROOT = PACKAGE_ROOT.parent

#: Folders that go away when `final/` becomes the repo. Nothing here may be read.
SIBLINGS = ("arjun", "theo", "dafu", "vidhi", "oleg", "cesare",
            "strategy", "src", "notebooks", "papers", "proposal", "docs")


class Skip(Exception):
    """Raised when a check cannot run in this environment."""


def _under_package(path) -> bool:
    try:
        return Path(path).resolve().is_relative_to(PACKAGE_ROOT)
    except (TypeError, ValueError, OSError):
        return False


def test_every_module_resolves_inside_final():
    """`import strategy` must find the vendored engine, not the repo-root twin.

    Both are importable when the repo root is on `sys.path`, and whichever comes
    first wins. `final/` inserts itself at position 0 precisely so this is not a
    coin flip — but "precisely so" is an intention, and this is the check.
    """
    import combined_engine
    import strategy
    import verdicts
    from strategy import config, core, episodes, fx_utils, overlays

    checked = {"strategy": strategy, "strategy.config": config,
               "strategy.core": core, "strategy.fx_utils": fx_utils,
               "strategy.episodes": episodes, "strategy.overlays": overlays,
               "combined_engine": combined_engine, "verdicts": verdicts}
    for name, mod in checked.items():
        assert _under_package(mod.__file__), (
            f"{name} resolved to {mod.__file__}, outside final/. The vendored "
            f"copy is being shadowed — check sys.path ordering")

    assert _under_package(fx_utils.RAW_DIR), (
        f"the engine's RAW_DIR is {fx_utils.RAW_DIR}, outside final/")
    print(f"  all modules inside final/      {len(checked)} modules + RAW_DIR")


def test_no_file_outside_final_is_opened():
    """Trace every open during a full run. This is the real acceptance test.

    Wraps `builtins.open`, `pd.read_csv` and `pd.read_parquet` and records every
    path. Anything resolving outside `final/` is a latent dependency on a folder
    that is being retired.

    `run("COMBINED")` is deliberately the traced call rather than plain `run()`:
    it is the one that pulls the teammate inputs, and it is the one that used to
    raise `FileNotFoundError` when a teammate's folder went away.
    """
    from strategy import run

    opened: list[str] = []
    real_open, real_csv, real_pq = builtins.open, pd.read_csv, pd.read_parquet

    def spy(fn):
        def wrapped(path, *a, **kw):
            try:
                opened.append(str(path))
            except Exception:
                pass
            return fn(path, *a, **kw)
        return wrapped

    builtins.open, pd.read_csv, pd.read_parquet = spy(real_open), spy(real_csv), spy(real_pq)
    try:
        run()
        run("COMBINED")
        run("COMBINED_TAIL")
        import verdicts
        verdicts.build()
    finally:
        builtins.open, pd.read_csv, pd.read_parquet = real_open, real_csv, real_pq

    # Only judge paths that actually point into this repo. Python opens plenty of
    # site-packages files during a run and those are the environment, not us.
    ours, outside = [], []
    for p in opened:
        try:
            rp = Path(p).resolve()
        except (TypeError, ValueError, OSError):
            continue
        if not rp.is_relative_to(REPO_ROOT):
            continue
        ours.append(rp)
        if not rp.is_relative_to(PACKAGE_ROOT):
            outside.append(rp)

    assert ours, "traced no repo files at all — the spy is not wired up"
    assert not outside, (
        "these files were read from OUTSIDE final/, so the package is not "
        "self-contained:\n    " +
        "\n    ".join(sorted({str(p.relative_to(REPO_ROOT)) for p in outside})))
    print(f"  every read inside final/       {len(set(ours))} distinct files, 0 outside")


def test_runs_with_final_as_the_only_path_entry():
    """No reliance on the repo root being importable.

    A subprocess whose `sys.path` starts with `final/` and nothing else from this
    repo. If anything still needs the repo root, this is where it says so.
    """
    code = (
        "import sys, json;"
        f"sys.path.insert(0, {str(PACKAGE_ROOT)!r});"
        "from strategy import run;"
        "r = run('COMBINED');"
        "s = r.summary(benchmark=None).loc['COMBINED_net'];"
        "print(json.dumps({'sharpe': float(s['sharpe'])}))"
    )
    env = dict(os.environ)
    env.pop("PYTHONPATH", None)
    out = subprocess.run([sys.executable, "-c", code], capture_output=True,
                         text=True, env=env, cwd=str(PACKAGE_ROOT))
    assert out.returncode == 0, f"subprocess failed:\n{out.stderr[-2000:]}"
    sharpe = float(out.stdout.strip().splitlines()[-1].split(":")[1].strip(" }"))
    assert abs(sharpe - 0.4891) < 5e-4, f"net Sharpe {sharpe:.6f} != 0.4891"
    print(f"  final/ alone on sys.path       COMBINED net {sharpe:.4f}")


def test_runs_from_a_working_directory_outside_the_repo():
    """cwd must not matter. Nine notebooks in this project depend on cwd; this
    package must not.
    """
    with tempfile.TemporaryDirectory() as tmp:
        code = (
            "import sys;"
            f"sys.path.insert(0, {str(PACKAGE_ROOT)!r});"
            "from strategy import run;"
            "print(round(float(run().summary(benchmark=None).loc['ALL_net']['sharpe']), 6))"
        )
        env = dict(os.environ)
        env.pop("PYTHONPATH", None)
        out = subprocess.run([sys.executable, "-c", code], capture_output=True,
                            text=True, env=env, cwd=tmp)
        assert out.returncode == 0, f"failed from cwd={tmp}:\n{out.stderr[-2000:]}"
        sharpe = float(out.stdout.strip().splitlines()[-1])
        assert abs(sharpe - 0.465923) < 5e-4, f"net Sharpe {sharpe} != 0.4659"
    print(f"  runs from an external cwd      baseline net {sharpe:.4f}")


#: Tokens that make a line a *path expression* rather than prose. A sibling
#: folder's name is only a problem when it is being turned into a path — the
#: provenance docstrings name `arjun/outputs/...` on purpose and must keep doing
#: so, because a vendored file with no stated origin is worse than no file.
_PATH_TOKENS = ("Path(", "open(", "read_csv(", "read_parquet(", "to_csv(",
                "to_parquet(", "glob(", "rglob(", "os.path", "/ \"", "/ '")


def _sibling_path_hits(line: str) -> bool:
    """True if `line` builds a filesystem path naming a retired sibling folder."""
    if not any(tok in line for tok in _PATH_TOKENS):
        return False
    return any(f'"{s}"' in line or f"'{s}'" in line or f'"{s}/' in line
               or f"'{s}/" in line or f"/{s}/" in line for s in SIBLINGS)


def test_no_source_file_names_a_sibling_folder():
    """A static backstop for the paths test 2 cannot reach.

    Tracing only covers code that actually executes. A stale constant on a branch
    nobody took would slip through, so also scan for sibling-folder names that are
    being *built into a path*. Prose is deliberately allowed: `inputs/PROVENANCE.md`
    and the verdict table have to say which folder each vendored file came from.

    The detector self-checks first. A grep that has never been shown to catch
    anything is not evidence — it is a test that passes because it is broken.
    """
    canary = ('ARJUN = REPO_ROOT / "arjun" / "outputs" / '   # sibling-ok: fixture
              '"duration_hedge_series.csv"')
    assert _sibling_path_hits(canary), "the detector does not detect; fix it before trusting it"
    prose = '"Impossible. oleg/ holds four files, and theo/data/processed is empty"'
    assert not _sibling_path_hits(prose), "the detector flags prose; it will be ignored"

    offenders, scanned = [], 0
    for py in sorted(PACKAGE_ROOT.rglob("*.py")):
        scanned += 1
        for i, line in enumerate(py.read_text().splitlines(), start=1):
            stripped = line.strip()
            if not stripped or stripped.startswith("#"):
                continue
            # `sibling-ok:` marks the few lines that must name a retired
            # folder: this detector's own fixture, and test_vendor_drift.py's
            # declaration of what each vendored file was copied FROM. Both are
            # bookkeeping about the sources, not reads from them.
            if "sibling-ok:" in line:
                continue
            if _sibling_path_hits(line):
                offenders.append(f"{py.relative_to(PACKAGE_ROOT)}:{i}: {stripped[:90]}")
    assert not offenders, (
        "sibling-folder paths found in executable code:\n    " + "\n    ".join(offenders))
    print(f"  no sibling paths in code       {scanned} .py files, detector self-checked")


TESTS = [test_every_module_resolves_inside_final,
         test_no_file_outside_final_is_opened,
         test_runs_with_final_as_the_only_path_entry,
         test_runs_from_a_working_directory_outside_the_repo,
         test_no_source_file_names_a_sibling_folder]


def main() -> int:
    print(f"\nRunning {len(TESTS)} standalone-package tests\n")
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
