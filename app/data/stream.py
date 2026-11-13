"""Finnhub trade stream, overlaid on the cached Yahoo snapshot.

Why an overlay and not a provider: Yahoo already gives us the things a websocket does not —
previous close, volume, a month of closes for the sparkline — and Finnhub gives us the one
thing Yahoo cannot: the price right now.

The two never fight. A tick updates `last`, `chg`, `pct` and `as_of` and leaves the rest of
the row alone. Yahoo's next refresh restores the context but the live price is re-applied on
top, so a poll can never drag the price backwards.

No key, no socket, no change: the app runs exactly as before on Yahoo alone.
"""

from __future__ import annotations

import contextlib
import json
import logging
import os
import threading
import time

from .. import symbols
from . import quotes

LIVE_HOLD = 300.0  # a tick older than this stops overriding the polled snapshot

log = logging.getLogger("bloomterm.stream")

_state = "off"  # off | connecting | live
_thread: threading.Thread | None = None


def enabled() -> bool:
    return bool(os.environ.get("FINNHUB_API_KEY", "").strip())


def state() -> str:
    return _state


def _set(state: str) -> None:
    global _state
    _state = state


def start(syms: list[str] | None = None) -> None:
    global _thread
    if not enabled() or _thread is not None:
        return
    targets = list(syms or symbols.ORDER)
    _thread = threading.Thread(target=_run, args=(targets,), daemon=True, name="finnhub-stream")
    _thread.start()


def _run(syms: list[str]) -> None:
    import websocket  # imported here so the app works without the dependency

    token = os.environ.get("FINNHUB_API_KEY", "").strip()
    base = os.environ.get("FINNHUB_WS_URL", "wss://ws.finnhub.io").rstrip("/")
    url = f"{base}?token={token}"
    backoff = 2.0

    while True:
        _set("connecting")
        try:
            ws = websocket.create_connection(url, timeout=30)
            try:
                for sym in syms:
                    ws.send(json.dumps({"type": "subscribe", "symbol": sym}))
                _set("live")
                backoff = 2.0
                while True:
                    try:
                        raw = ws.recv()
                    except websocket.WebSocketTimeoutException:
                        ws.ping()  # quiet market: keep the connection honest
                        continue
                    if not raw:
                        raise ConnectionError("socket closed")
                    _handle(raw)
            finally:
                with contextlib.suppress(Exception):
                    ws.close()
        except Exception as exc:
            log.debug("stream reconnect in %.0fs: %s", backoff, exc)
            _set("connecting")
            time.sleep(backoff)
            backoff = min(backoff * 2, 60.0)


def _handle(raw: str) -> int:
    """Apply one websocket frame. Returns how many trades were ingested."""
    try:
        message = json.loads(raw)
    except (TypeError, ValueError):
        return 0
    if not isinstance(message, dict):
        return 0
    if message.get("type") == "error":
        log.warning("finnhub: %s", message.get("msg", "stream error"))
        return 0
    if message.get("type") != "trade":
        return 0
    applied = 0
    for trade in message.get("data") or []:
        sym = trade.get("s")
        price = trade.get("p")
        if not sym or price is None:
            continue
        try:
            quotes.ingest(str(sym), float(price), int(trade.get("t") or 0) // 1000)
        except (TypeError, ValueError):
            continue
        applied += 1
    return applied
