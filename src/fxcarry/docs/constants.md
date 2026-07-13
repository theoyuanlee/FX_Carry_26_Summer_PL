# fxcarry.constants

Single source of truth for hard-coded values used across the library: Bloomberg field
names, currency universes, quote-inversion flags, forward-point scale factors, file
names, and annualization/lag defaults.

## Contents

- `PX_LAST`, `PX_BID`, `PX_ASK`, `FIELDS` — Bloomberg field names.
- `FIELD_TO_KEY`, `KEY_TO_FIELD` — map Bloomberg field names to/from the `{"mid","bid","ask"}` keys used by `fxcarry.io`.
- `BER20_TICKERS`, `LRV_EXTRA_TICKERS`, `LEGACY_EURO_TICKERS` — currency universes (ISO code -> `(spot ticker, 1M forward-points ticker)`).
- `DEFAULT_TICKERS` — universe used by default; point at a different dict to change coverage everywhere.
- `TBILL_TICKER` — risk-free proxy ticker for NAV compounding.
- `INVERTED` — currencies Bloomberg quotes USD-per-FCU instead of FCU-per-USD.
- `POINT_SCALE`, `point_scale()` — forward-point scale factor by currency.
- `DEFAULT_START_DATE`, `DEFAULT_END_DATE` — pull window defaults.
- `DEFAULT_FREQ`, `RESAMPLE_ALIAS`, `PERIODS_PER_YEAR`, `DEFAULT_ANNUALIZATION`, `DEFAULT_NW_LAGS` — resampling/analytics defaults.
- `SPOT_FILE`, `FWD_FILE`, `TBILL_FILE` — expected raw parquet file names.

## Convention

To extend the currency universe, add a pull source, or change a convention, edit this
file only. No other module hard-codes any of the values listed above.
