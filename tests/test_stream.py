"""The Finnhub overlay, tested without a socket or a key."""

import json

from app.data import quotes, stream
from app.models import Quote


class FakeProvider:
    def quotes(self, syms):
        return {
            s: Quote(s, 100.0, 1.0, 1.01, 99.0, 99.5, 1_000, spark=[98.0, 99.0, 100.0])
            for s in syms
        }


def _use_fake(monkeypatch):
    monkeypatch.setattr("app.data.get_provider", lambda: FakeProvider())
    quotes.clear()


def test_trade_frame_is_ingested(monkeypatch):
    _use_fake(monkeypatch)
    quotes.get(["AAPL"])

    frame = json.dumps(
        {"type": "trade", "data": [{"s": "AAPL", "p": 105.5, "t": 1_700_000_000_000, "v": 10}]}
    )
    assert stream._handle(frame) == 1
    assert quotes.get(["AAPL"])["AAPL"].last == 105.5


def test_other_frames_are_ignored(monkeypatch):
    _use_fake(monkeypatch)
    quotes.get(["AAPL"])
    assert stream._handle(json.dumps({"type": "ping"})) == 0
    assert stream._handle("not json") == 0
    assert stream._handle(json.dumps({"type": "trade", "data": [{"s": "AAPL"}]})) == 0
    assert quotes.get(["AAPL"])["AAPL"].last == 100.0


def test_tick_survives_the_next_poll(monkeypatch):
    _use_fake(monkeypatch)
    quotes.get(["AAPL"])
    quotes.ingest("AAPL", 105.0, 1_700_000_000)

    # a forced poll returns the provider's 100.0 — the live price must win
    after_poll = quotes.get(["AAPL"], force=True)["AAPL"]
    assert after_poll.last == 105.0
    assert after_poll.chg == 6.0
    assert after_poll.spark[-1] == 105.0
    # context from the poll survives
    assert after_poll.volume == 1_000


def test_old_tick_stops_overriding(monkeypatch):
    _use_fake(monkeypatch)
    quotes.get(["AAPL"])
    quotes.ingest("AAPL", 105.0, 1_700_000_000)
    assert quotes.has_live("AAPL", within=-1) is False


def test_stream_is_off_without_a_key(monkeypatch):
    monkeypatch.delenv("FINNHUB_API_KEY", raising=False)
    assert stream.enabled() is False
    stream.start(["AAPL"])
    assert stream.state() == "off"
