"""A modular FX cross-sectional strategy research library."""

from fxcarry import (
    catalog,
    compare,
    curves,
    options,
    quotes,
    reference,
    regimes,
    registry,
    stats,
    strategy,
    vol,
)
from fxcarry.catalog import Catalog, Currency, TickerId
from fxcarry.compare import Comparison
from fxcarry.curves import SpotForward
from fxcarry.options import (
    Black76,
    Combination,
    Forward,
    Instrument,
    MarketState,
    NoOverlay,
    Overlay,
    PricingModel,
    SingleWing,
    Vanilla,
    VerticalSpread,
)
from fxcarry.quotes import DataNotPulled, FrameSource, ParquetSource, Quotes, QuoteSource
from fxcarry.regimes import (
    INFORMATION_SETS,
    LogisticRegime,
    MarkovSwitching,
    RegimeModel,
    RegimeSeries,
    TrailingPercentile,
    binary_gate,
    linear_gate,
    power_gate,
)
from fxcarry.stats import HAC, FactorModel, LinearSDF, Performance, Realized, Shrinkage
from fxcarry.strategy import (
    BidAskCost,
    Book,
    Bucket,
    Carry,
    CostModel,
    EqualLong,
    HalfSpreadCost,
    Momentum,
    Signal,
    SignEqualWeight,
    SpreadWeighted,
    TopBottom,
    Weighting,
    ZeroCost,
)
from fxcarry.vol import Smile, VolSurface

__version__ = "0.1.0"

__all__ = [
    # modules
    "catalog", "compare", "curves", "options", "quotes", "reference", "regimes",
    "registry", "stats", "strategy", "vol",
    # market identity and data
    "Catalog", "Currency", "TickerId",
    "Quotes", "QuoteSource", "ParquetSource", "FrameSource", "DataNotPulled",
    "SpotForward", "Smile", "VolSurface",
    # options
    "PricingModel", "Black76", "MarketState",
    "Instrument", "Forward", "Vanilla", "Combination",
    "Overlay", "NoOverlay", "SingleWing", "VerticalSpread",
    # strategy
    "Signal", "Carry", "Momentum",
    "Weighting", "TopBottom", "Bucket", "SignEqualWeight", "SpreadWeighted", "EqualLong",
    "CostModel", "ZeroCost", "BidAskCost", "HalfSpreadCost",
    "Book",
    # estimation
    "Performance", "HAC", "Realized", "FactorModel", "LinearSDF", "Shrinkage",
    # regimes and comparison
    "RegimeModel", "RegimeSeries", "MarkovSwitching", "TrailingPercentile", "LogisticRegime",
    "INFORMATION_SETS", "linear_gate", "binary_gate", "power_gate",
    "Comparison",
]
