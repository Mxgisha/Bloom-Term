"""Keeps the quote cache hot while somebody is actually looking at the screen.

Polling from the browser means every page load is one cold request. A tiny daemon does the
same fetch in the background instead, so the request path reads from cache. It stops on its
own after two minutes without traffic — no browser open, no upstream calls.
"""

from __future__ import annotations

import contextlib
import threading
import time

from . import symbols
from .data import quotes

IDLE_AFTER = 120.0
_started = False
_last_seen = 0.0


def touch() -> None:
    global _last_seen
    _last_seen = time.time()


def start() -> None:
    global _started
    if _started:
        return
    _started = True
    threading.Thread(target=_prewarm, daemon=True, name="prewarm").start()
    threading.Thread(target=_loop, daemon=True, name="warmer").start()


def _prewarm() -> None:
    """First paint should never wait on Yahoo."""
    with contextlib.suppress(Exception):
        quotes.get(list(symbols.ORDER), force=True)


def _loop() -> None:
    while True:
        time.sleep(2)
        if time.time() - _last_seen > IDLE_AFTER:
            continue
        try:
            if quotes.oldest_age(symbols.ORDER) >= quotes.TTL * 0.9:
                quotes.get(list(symbols.ORDER), force=True)
        except Exception:
            continue
