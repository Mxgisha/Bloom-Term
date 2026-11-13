"""Shared quote cache: single-flight fetches, stale-while-revalidate, live tick overlay.

Three rules:
  * one upstream request at a time per symbol set (the lock is held across the fetch);
  * a stale value is served immediately and refreshed in the background, because a 10-second
    wait is worse than a 15-second-old price in a terminal;
  * a pushed trade outranks a polled price, and survives the next poll.
"""

from __future__ import annotations

import threading
import time
from dataclasses import replace

from ..models import Quote

TTL = 15.0
LIVE_HOLD = 300.0  # a tick stops overriding the polled snapshot after this long

_lock = threading.Lock()
_cache: dict[str, tuple[Quote, float]] = {}
_refreshing: set[str] = set()
_live: dict[str, tuple[float, int, float]] = {}  # sym -> (price, as_of, monotonic)


def _fetch(syms: list[str]) -> dict[str, Quote]:
    from . import get_provider

    try:
        return get_provider().quotes(syms)
    except Exception:
        return {}


def _snapshot(syms) -> dict[str, Quote]:
    return {s: _cache[s][0] for s in syms if s in _cache}


def _overlay(quote: Quote, price: float, as_of: int) -> Quote:
    """A live trade changes the price and nothing else."""
    prev = quote.prev_close or price
    spark = list(quote.spark)
    if spark:
        spark[-1] = round(price, 2)
    return replace(
        quote,
        last=round(price, 2),
        chg=round(price - prev, 2),
        pct=round((price - prev) / prev * 100.0, 2) if prev else 0.0,
        as_of=as_of,
        spark=spark,
    )


def _with_live(sym: str, quote: Quote) -> Quote:
    live = _live.get(sym)
    if live and time.monotonic() - live[2] < LIVE_HOLD:
        return _overlay(quote, live[0], live[1])
    return quote


def _store(sym: str, quote: Quote, stamp: float) -> None:
    _cache[sym] = (_with_live(sym, quote), stamp)


def ingest(sym: str, price: float, as_of: int = 0) -> None:
    """Called by the stream for every trade."""
    stamp = int(as_of or time.time())
    now = time.monotonic()
    with _lock:
        _live[sym] = (price, stamp, now)
        entry = _cache.get(sym)
        if entry is not None:
            _cache[sym] = (_overlay(entry[0], price, stamp), entry[1])


def has_live(sym: str, within: float = LIVE_HOLD) -> bool:
    live = _live.get(sym)
    return bool(live) and time.monotonic() - live[2] < within


def _refresh_in_background(syms: list[str]) -> None:
    with _lock:
        fresh = _fetch(syms)
        stamp = time.monotonic()
        for sym, quote in fresh.items():
            _store(sym, quote, stamp)
        _refreshing.difference_update(syms)


def get(syms: list[str] | tuple[str, ...], force: bool = False) -> dict[str, Quote]:
    syms = list(syms)
    to_refresh: list[str] = []

    with _lock:
        now = time.monotonic()
        stale = [s for s in syms if s not in _cache or now - _cache[s][1] > TTL]
        if not stale:
            return _snapshot(syms)

        # Cold cache, or the caller insists: block so the first paint has real numbers.
        if force or any(s not in _cache for s in syms):
            fresh = _fetch(stale)
            stamp = time.monotonic()
            for sym, quote in fresh.items():
                _store(sym, quote, stamp)
            return _snapshot(syms)

        # Warm but stale: answer now, refresh off the request path.
        to_refresh = [s for s in stale if s not in _refreshing]
        _refreshing.update(to_refresh)

    if to_refresh:
        threading.Thread(target=_refresh_in_background, args=(to_refresh,), daemon=True).start()
    return _snapshot(syms)


def oldest_age(syms) -> float:
    """Seconds since the least-recently-fetched symbol was refreshed."""
    with _lock:
        stamps = [_cache[s][1] for s in syms if s in _cache]
    return time.monotonic() - min(stamps) if stamps else 0.0


def clear() -> None:
    with _lock:
        _cache.clear()
        _refreshing.clear()
        _live.clear()
