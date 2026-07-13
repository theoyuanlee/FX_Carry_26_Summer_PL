"""fxcarry — modular, generic FX cross-sectional strategy research library."""

from . import backtest, constants, conventions, costs, io, metrics, panel, portfolio, signals
from .panel import FXPanel

__version__ = "0.0.1"

__all__ = [
    "backtest",
    "constants",
    "conventions",
    "costs",
    "io",
    "metrics",
    "panel",
    "portfolio",
    "signals",
    "FXPanel",
]
