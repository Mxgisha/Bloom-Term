import pytest

from app import store
from app.models import Candle


@pytest.fixture()
def db(tmp_path, monkeypatch):
    store.use(tmp_path / "test.db")
    yield


def test_candle_roundtrip(db):
    rows = [Candle(1.0, 2.0, 0.5, 1.5, 100, 1000), Candle(1.5, 2.5, 1.0, 2.0, 200, 2000)]
    store.upsert_candles("AAPL", "1d", rows)
    got = store.read_candles("AAPL", "1d")
    assert [c.close for c in got] == [1.5, 2.0]
    assert [c.t for c in got] == [1000, 2000]


def test_upsert_is_idempotent(db):
    row = Candle(1.0, 1.0, 1.0, 1.0, 10, 1000)
    store.upsert_candles("AAPL", "1d", [row])
    store.upsert_candles("AAPL", "1d", [row])
    assert len(store.read_candles("AAPL", "1d")) == 1


def test_kv(db):
    assert store.kv_get("missing", "fallback") == "fallback"
    store.kv_set("k", "v")
    assert store.kv_get("k") == "v"
    store.kv_set("k", "w")
    assert store.kv_get("k") == "w"


def test_symbols_are_isolated(db):
    store.upsert_candles("AAPL", "1d", [Candle(1, 1, 1, 1, 1, 1000)])
    assert store.read_candles("MSFT", "1d") == []
