from app import layout


def test_spec_roundtrip():
    assert layout.spec("GP", "AAPL") == "GP:AAPL"
    assert layout.spec("GP", "AAPL", "1Y") == "GP:AAPL:1Y"
    assert layout.parse_spec("GP:AAPL:1Y") == ("GP", "AAPL", "1Y")
    assert layout.parse_spec("WATCH") == ("WATCH", "", "")


def test_spec_handles_dotted_ticker():
    fn, sym, _rng = layout.parse_spec("GP:BRK.B")
    assert (fn, sym) == ("GP", "BRK.B")


def test_presets_are_consistent():
    for name, (cols, count) in layout.PRESETS.items():
        assert cols >= 1 and count >= cols
        assert name.isdigit()
