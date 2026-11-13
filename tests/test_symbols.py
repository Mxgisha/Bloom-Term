from app import symbols


def test_class_shares_map_to_dashes():
    assert symbols.provider_id("BRK.B") == "BRK-B"


def test_index_and_futures_symbols_pass_through():
    assert symbols.provider_id("^VIX") == "^VIX"
    assert symbols.provider_id("DX-Y.NYB") == "DX-Y.NYB"
    assert symbols.provider_id("BTC-USD") == "BTC-USD"
    assert symbols.provider_id("CL=F") == "CL=F"


def test_every_macro_symbol_is_named():
    for sym, label, _unit in symbols.MACRO:
        assert sym and label


def test_universe_lookups():
    assert symbols.name("AAPL") == "Apple Inc"
    assert symbols.exchange("AAPL") == "NASDAQ"
    assert symbols.name("NOPE") == "NOPE"
