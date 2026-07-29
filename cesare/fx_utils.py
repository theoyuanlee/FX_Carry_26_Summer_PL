"""Back-compatibility shim — the engine moved to `strategy/fx_utils.py`.

The engine is now team-owned and lives in the repo-root `strategy/` package, so
every teammate builds on the same base (see `strategy/README.md`). This shim
keeps the old import working unchanged for the notebooks in `cesare/` and for
anyone doing `sys.path.insert(0, "../cesare"); import fx_utils`.

New code should prefer the package import:

    import sys; sys.path.insert(0, "<repo_root>")
    from strategy import StrategyConfig, run          # the baseline backtest
    from strategy import fx_utils as fx               # the engine, if needed
"""

import sys as _sys
from pathlib import Path as _Path

_REPO_ROOT = _Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in _sys.path:
    _sys.path.insert(0, str(_REPO_ROOT))

from strategy.fx_utils import *          # noqa: F401,F403  (public API)
from strategy.fx_utils import __dict__ as _engine_dict

# `import *` skips underscore-prefixed and non-__all__ names; copy the rest so
# the shim is a true drop-in (module constants, private helpers used by tests).
globals().update({k: v for k, v in _engine_dict.items()
                  if not k.startswith("__") and k not in globals()})
