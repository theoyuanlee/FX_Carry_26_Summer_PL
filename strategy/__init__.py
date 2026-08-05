"""The team's base FX carry strategy.

One construction, one set of conventions, one set of numbers — so that a regime
gate, an option hedge, a robustness sweep and a crisis study are all measured
against the same book. Read `strategy/README.md` before extending anything.

    import sys; sys.path.insert(0, "<repo_root>")
    from strategy import run

    base = run()                       # the baseline: ALL 27 names, net Sharpe 0.4659
    mine = run(exposure=my_signal)     # my extension, same base
    print(base.summary(), mine.summary(), sep="\\n")

Public API:
    StrategyConfig, ALL_BASELINE, G10_BASELINE, EM_BASELINE, PRESETS   (config)
    run, StrategyResult, Panels, OverlayContext, load_panels, resolve_universe (core)
    ERAS, STRESS, report_windows, compare_windows, leg_decomposition  (episodes)
    ExternalLeg, compose_exposure, compose_overlays                   (overlays)
    fx_utils                                                          (the engine)
"""

from . import episodes, fx_utils, overlays
from .config import (ALL_BASELINE, DEFAULT_EXCLUDE, EM_BASELINE, G10_BASELINE,
                     G10_TRADABLE, PRESETS, StrategyConfig)
from .core import (OverlayContext, Panels, StrategyResult, load_panels,
                   resolve_universe, run)
from .episodes import (ERAS, STRESS, compare_windows, leg_decomposition,
                       report_windows)
from .overlays import ExternalLeg, compose_exposure, compose_overlays

__all__ = [
    "StrategyConfig", "ALL_BASELINE", "G10_BASELINE", "EM_BASELINE", "PRESETS",
    "DEFAULT_EXCLUDE", "G10_TRADABLE",
    "run", "StrategyResult", "Panels", "OverlayContext", "load_panels",
    "resolve_universe", "fx_utils",
    "episodes", "ERAS", "STRESS", "report_windows", "compare_windows",
    "leg_decomposition",
    "overlays", "ExternalLeg", "compose_exposure", "compose_overlays",
]

#: 1.2.0 — the `overlays` module (plan §19.4): `compose_exposure`,
#: `compose_overlays` with its gross-non-increasing contract, and `ExternalLeg`
#: + `StrategyConfig.external_legs` for instruments the two hooks cannot express.
#: All three are exact no-ops at their neutral settings, so every v1.1.0
#: reconciliation target is unchanged.
#:
#: 1.1.0 — F1 `summary(min_obs=)` passthrough, F2 tenor-indexed roll leg,
#: and the `episodes` module (plan §19.2). Both fixes are exact no-ops at the
#: committed baseline; the reconciliation targets are unchanged.
__version__ = "1.2.0"
