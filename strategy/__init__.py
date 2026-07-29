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
    fx_utils                                                          (the engine)
"""

from . import fx_utils
from .config import (ALL_BASELINE, DEFAULT_EXCLUDE, EM_BASELINE, G10_BASELINE,
                     G10_TRADABLE, PRESETS, StrategyConfig)
from .core import (OverlayContext, Panels, StrategyResult, load_panels,
                   resolve_universe, run)

__all__ = [
    "StrategyConfig", "ALL_BASELINE", "G10_BASELINE", "EM_BASELINE", "PRESETS",
    "DEFAULT_EXCLUDE", "G10_TRADABLE",
    "run", "StrategyResult", "Panels", "OverlayContext", "load_panels",
    "resolve_universe", "fx_utils",
]

__version__ = "1.0.0"
