from app.data import quotes as cache
from app.models import Quote


def _quote(sym: str) -> Quote:
    return Quote(sym, 1.0, 0.0, 0.0, 1.0, 1.0, 0, spark=[1.0, 1.0])


def test_one_fetch_for_repeated_reads(monkeypatch):
    calls: list[list[str]] = []

    class Fake:
        def quotes(self, syms):
            calls.append(list(syms))
            return {s: _quote(s) for s in syms}

    monkeypatch.setattr("app.data.get_provider", lambda: Fake())
    cache.clear()
    cache.get(["AAPL", "MSFT"])
    cache.get(["AAPL", "MSFT"])
    assert calls == [["AAPL", "MSFT"]]


def test_a_failed_fetch_keeps_the_old_value(monkeypatch):
    class Good:
        def quotes(self, syms):
            return {s: _quote(s) for s in syms}

    class Broken:
        def quotes(self, syms):
            raise RuntimeError("upstream down")

    monkeypatch.setattr("app.data.get_provider", lambda: Good())
    cache.clear()
    cache.get(["AAPL"])
    monkeypatch.setattr("app.data.get_provider", lambda: Broken())
    got = cache.get(["AAPL"], force=True)
    assert "AAPL" in got
