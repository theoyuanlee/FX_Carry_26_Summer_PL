import pytest

from fxcarry.catalog import Catalog, TickerId


def test_quote_direction_follows_the_pair():
    cat = Catalog.default()
    assert cat["AUD"].quoted_usd_per_fcu is True      # AUDUSD
    assert cat["JPY"].quoted_usd_per_fcu is False     # USDJPY


def test_to_usd_per_fcu_inverts_only_usd_base_pairs():
    cat = Catalog.default()
    assert cat["AUD"].to_usd_per_fcu(0.65) == pytest.approx(0.65)
    assert cat["JPY"].to_usd_per_fcu(160.0) == pytest.approx(1.0 / 160.0)


def test_outright_scales_points_by_currency():
    cat = Catalog.default()
    # a yen point is a hundredth of the quote, a euro point a ten-thousandth
    assert cat["JPY"].outright(160.00, -40.85) == pytest.approx(159.5915)
    assert cat["EUR"].outright(1.0800, 25.0) == pytest.approx(1.0825)


def test_ndf_roots_survive_into_built_tickers():
    cat = Catalog.default()
    assert cat["INR"].fwd_ticker("3M") == "IRN3M Curncy"
    assert cat["TWD"].fwd_ticker("1M") == "NTN1M Curncy"


def test_vol_tickers_round_trip_through_parse():
    cat = Catalog.default()
    for iso, kind, delta in [("EUR", "atm", None), ("JPY", "rr", 25), ("JPY", "bf", 10)]:
        symbol = cat[iso].vol_ticker(kind, "1M", delta)
        got = cat.parse(symbol)
        assert (got.iso, got.kind, got.delta, got.tenor) == (iso, kind, delta, "1M")


def test_vol_ticker_rejects_a_delta_it_cannot_use():
    cat = Catalog.default()
    with pytest.raises(ValueError):
        cat["EUR"].vol_ticker("atm", "1M", delta=25)
    with pytest.raises(ValueError):
        cat["EUR"].vol_ticker("rr", "1M")


def test_parse_handles_every_ticker_shape_and_rejects_junk():
    cat = Catalog.default()
    assert cat.parse("AUD3M Curncy") == TickerId("AUD3M Curncy", "AUD", "3M", "forward")
    assert cat.parse("US0003M Index").kind == "rate"
    assert cat.parse("AUDUSD Curncy").kind == "spot"
    assert cat.parse("not a ticker") is None


def test_label_map_inverts_the_catalog():
    cat = Catalog.default().subset(["EUR", "JPY"])
    assert cat.label_map("spot") == {"EURUSD Curncy": "EUR", "USDJPY Curncy": "JPY"}
    assert cat.label_map("forward", "1M") == {"EUR1M Curncy": "EUR", "JPY1M Curncy": "JPY"}


def test_subset_is_a_catalog_and_legacy_adds_dead_currencies():
    cat = Catalog.default()
    assert "DEM" not in cat
    assert "DEM" in Catalog.with_legacy()
    small = cat.subset(["EUR", "JPY"])
    assert len(small) == 2 and set(small.isos) == {"EUR", "JPY"}


def test_unknown_currency_names_itself_in_the_error():
    with pytest.raises(KeyError, match="XXX"):
        Catalog.default()["XXX"]


def test_ticker_lists_are_deduplicated_and_ordered():
    cat = Catalog.default().subset(["EUR", "JPY"])
    got = cat.tickers("rr", tenors=["1M"], deltas=[25, 10])
    assert got == [
        "EURUSD25R1M BGN Curncy", "EURUSD10R1M BGN Curncy",
        "USDJPY25R1M BGN Curncy", "USDJPY10R1M BGN Curncy",
    ]
