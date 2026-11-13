from app import command


def test_symbol_then_function():
    p = command.parse("AAPL GP")
    assert p.ok and p.fn == "GP" and p.sym == "AAPL"


def test_lowercase_and_whitespace():
    p = command.parse("  nvda   gp ")
    assert p.ok and p.fn == "GP" and p.sym == "NVDA"


def test_bare_symbol_opens_description():
    p = command.parse("MSFT")
    assert p.ok and p.fn == "DES" and p.sym == "MSFT"


def test_bare_function():
    p = command.parse("N")
    assert p.ok and p.fn == "N" and p.sym == ""


def test_alias_resolves():
    assert command.parse("TOP").fn == "N"
    assert command.parse("WEI").fn == "ECO"


def test_ticker_function_uses_current_symbol():
    p = command.parse("GP", current_sym="TSLA")
    assert p.ok and p.fn == "GP" and p.sym == "TSLA"


def test_tickerless_function_rejects_ticker():
    p = command.parse("AAPL N")
    assert not p.ok and "does not take a ticker" in p.error


def test_unknown_symbol_suggests():
    p = command.parse("NVDIA")
    assert not p.ok and "NVDA" in p.candidates


def test_empty_and_too_long():
    assert not command.parse("").ok
    assert not command.parse("a b c").ok


def test_unknown_function_lists_options():
    p = command.parse("AAPL XYZZY")
    assert not p.ok and p.candidates
