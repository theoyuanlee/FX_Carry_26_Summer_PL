# fxcarry

Shared FX cross-sectional strategy research library.

## Modules

| Module | Docs |
|---|---|
| `constants` | [docs/constants.md](docs/constants.md) |
| `conventions` | [docs/conventions.md](docs/conventions.md) |
| `io` | [docs/io.md](docs/io.md) |
| `panel` | [docs/panel.md](docs/panel.md) |
| `signals` | [docs/signals.md](docs/signals.md) |
| `portfolio` | [docs/portfolio.md](docs/portfolio.md) |
| `costs` | [docs/costs.md](docs/costs.md) |
| `backtest` | [docs/backtest.md](docs/backtest.md) |
| `metrics` | [docs/metrics.md](docs/metrics.md) |

## Quick start

```python
import sys
sys.path.append("../src")  # from a notebook one level below the repo root

from fxcarry.panel import FXPanel
from fxcarry.signals import carry_signal, momentum_signal
from fxcarry.portfolio import ew_strategy_return

# data_dir is caller-supplied -- point it at your own data folder
panel = FXPanel.from_raw("data/raw")
currency_return = panel.currency_return("excess")  # f_t - s_{t+1}, i.e. panel.rx
carry_ew = ew_strategy_return(carry_signal(panel), panel.rx)
```

`FXPanel.from_raw` expects the raw parquet file names in `fxcarry.constants`
(`spot_daily.parquet`, `fwd_points_1m_daily.parquet`, ...). Pass `spot_file=`/`fwd_file=`
if a data pull uses different names.
