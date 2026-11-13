"""Deterministic mock provider — `BLOOMTERM_PROVIDER=mock`.

Same interface as Yahoo, no network, reproducible. Prices move with wall-clock phase so the
UI looks alive, but the same symbol at the same minute always renders the same number.
"""

from __future__ import annotations

import math
import random
import time
from datetime import datetime, timedelta
from functools import lru_cache

from .. import symbols
from ..market import NY
from ..models import Candle, NewsItem, Quote

name = "mock"
delay = "simulated"

# sym -> (reference price, average volume in millions)
_REFS: dict[str, tuple[float, float]] = {
    "AAPL": (227.40, 48.0),
    "MSFT": (418.10, 21.0),
    "NVDA": (141.02, 310.0),
    "AMZN": (201.30, 38.0),
    "GOOGL": (176.20, 26.0),
    "META": (584.00, 14.0),
    "TSLA": (248.50, 92.0),
    "AMD": (138.40, 55.0),
    "AVGO": (172.00, 24.0),
    "JPM": (243.00, 9.0),
    "XOM": (118.20, 16.0),
    "UNH": (512.00, 4.0),
    "WMT": (92.40, 18.0),
    "NFLX": (912.00, 3.0),
    "PLTR": (68.20, 62.0),
    "COIN": (296.00, 11.0),
    "SPY": (604.00, 70.0),
    "QQQ": (519.00, 42.0),
    # cross-asset strip
    "^VIX": (14.60, 0.0),
    "^TNX": (4.28, 0.0),
    "^IRX": (4.05, 0.0),
    "DX-Y.NYB": (104.20, 0.0),
    "GC=F": (2650.00, 0.0),
    "CL=F": (71.40, 0.0),
    "BTC-USD": (96000.00, 0.0),
    "^GSPC": (5980.00, 0.0),
}

SYMBOLS = symbols.ORDER


def _seed(sym: str) -> int:
    return int.from_bytes(sym.encode()[:4].ljust(4, b"_"), "big")


def _phase(sym: str) -> float:
    return (_seed(sym) % 628) / 100.0


@lru_cache(maxsize=128)
def bars(sym: str) -> tuple[Candle, ...]:
    """260 daily bars, deterministic, rescaled so the last close is the reference price."""
    if sym not in _REFS:
        raise KeyError(sym)
    ref, avg_vol = _REFS[sym]
    rnd = random.Random(_seed(sym))
    px = ref * 0.82
    out: list[Candle] = []
    for _ in range(260):
        o = px
        c = o * (1.0 + rnd.gauss(0.0007, 0.016))
        hi = max(o, c) * (1.0 + abs(rnd.gauss(0.0, 0.005)))
        lo = min(o, c) * (1.0 - abs(rnd.gauss(0.0, 0.005)))
        v = max(1, int(avg_vol * 1e6 * (1.0 + rnd.gauss(0.0, 0.45))))
        out.append(Candle(o, hi, lo, c, v))
        px = c
    k = ref / out[-1].close
    return tuple(Candle(b.open * k, b.high * k, b.low * k, b.close * k, b.volume) for b in out)


def _path(sym: str, rng: str) -> list[float]:
    """Price path for a chart range, always ending on the live quote."""
    q = quote(sym)
    if rng == "1D":
        n = 78
        rnd = random.Random(_seed(sym) + 7)
        walk = [0.0]
        for _ in range(1, n):
            walk.append(walk[-1] + rnd.gauss(0.0, 0.0011))
        target = (q.last - q.prev_close) / q.prev_close
        correction = target - walk[-1]
        return [
            round(q.prev_close * (1.0 + walk[i] + (i / (n - 1)) * correction), 2) for i in range(n)
        ]
    n = {"5D": 5, "1M": 22, "6M": 130, "1Y": 252}.get(rng, 5)
    hist = bars(sym)[-n:]
    return [round(b.close, 2) for b in hist[:-1]] + [q.last]


def quote(sym: str) -> Quote:
    if sym not in _REFS:
        raise KeyError(sym)
    hist = bars(sym)
    prev_close = hist[-1].close
    phase = _phase(sym)
    t = time.time()
    drift = 0.0045 * math.sin(t / 53.0 + phase) + 0.0012 * math.sin(t / 11.0 + phase * 1.7)
    last = round(prev_close * (1.0 + drift), 2)
    chg = round(last - prev_close, 2)
    spark = [round(b.close, 2) for b in hist[-22:-1]] + [last]
    return Quote(
        sym=sym,
        last=last,
        chg=chg,
        pct=round(chg / prev_close * 100.0, 2),
        prev_close=round(prev_close, 2),
        open=round(hist[-1].open * (1.0 + drift * 0.4), 2),
        volume=int(hist[-1].volume * 0.6),
        as_of=int(t),
        spark=spark,
    )


def quotes(syms) -> dict[str, Quote]:
    out: dict[str, Quote] = {}
    for sym in syms:
        try:
            out[sym] = quote(sym)
        except KeyError:
            continue
    return out


def candles(sym: str, rng: str) -> list[Candle]:
    if rng == "1D":
        pts = _path(sym, "1D")
        vol = _volume_series(sym, "1D")
        out = []
        for i in range(len(pts) - 1):
            o, c = pts[i], pts[i + 1]
            out.append(Candle(o, max(o, c), min(o, c), c, int(vol[i])))
        return out
    n = {"5D": 5, "1M": 22, "6M": 130, "1Y": 252}.get(rng, 5)
    return list(bars(sym)[-n:])


def _volume_series(sym: str, rng: str) -> list[float]:
    if rng == "1D":
        day = quote(sym).volume
        n = 78
        rnd = random.Random(_seed(sym) + 11)
        weights = [
            (0.6 + 1.4 * (abs(i / (n - 1) - 0.5) * 2) ** 2) * (1 + rnd.gauss(0, 0.25))
            for i in range(n)
        ]
        total = sum(weights)
        return [max(1.0, day * w / total) for w in weights]
    n = {"5D": 5, "1M": 22, "6M": 130, "1Y": 252}.get(rng, 5)
    return [float(b.volume) for b in bars(sym)[-n:]]


@lru_cache(maxsize=64)
def _fundamentals(sym: str) -> dict[str, float]:
    rnd = random.Random(_seed(sym) * 7 + 3)
    return {
        "shares": rnd.uniform(0.9e9, 15.5e9),
        "pe": round(rnd.uniform(12.0, 48.0), 1),
        "div": round(rnd.uniform(0.0, 2.4), 2),
        "beta": round(rnd.uniform(0.6, 1.9), 2),
    }


def describe(sym: str) -> dict[str, object]:
    q = quote(sym)
    hist = bars(sym)
    f = _fundamentals(sym)
    return {
        "name": symbols.name(sym),
        "sector": symbols.sector(sym),
        "exchange": symbols.exchange(sym),
        "currency": "USD",
        "cap": q.last * f["shares"],
        "pe": f["pe"],
        "div": f["div"],
        "beta": f["beta"],
        "hi52": max(b.high for b in hist),
        "lo52": min(b.low for b in hist),
        "avg_vol": 42_000_000,
        "prev_close": q.prev_close,
        "last": q.last,
    }


_NEWS: tuple[tuple[str, str], ...] = (
    ("{name} extends gains as {sector} strength broadens", "RTR"),
    ("{sym} slips after analyst trims price target", "BBG"),
    ("Fed officials signal patience; front-end yields steady", "WSJ"),
    ("{name} to report quarterly results next week", "CNBC"),
    ("Export curbs weigh on {sector} names at the open", "FT"),
    ("Options activity picks up in {sym} ahead of expiry", "RTR"),
    ("Sector rotation lifts {sector} into the close", "BBG"),
    ("Treasury auction draws soft demand; 10-year backs up", "WSJ"),
    ("{name} authorises a $10bn share repurchase", "SEC"),
    ("Oil steady as supply concerns ease; energy lags", "RTR"),
    ("{name} names new chief financial officer", "BBG"),
    ("Breadth improves as small caps outperform", "CNBC"),
)


def news(limit: int = 16) -> list[NewsItem]:
    now = datetime.now(tz=NY)
    out: list[NewsItem] = []
    for i in range(limit):
        sym = SYMBOLS[i % len(SYMBOLS)]
        tmpl, src = _NEWS[i % len(_NEWS)]
        ts = int((now - timedelta(minutes=7 * i + (i * 13) % 11)).timestamp())
        out.append(
            NewsItem(
                t=ts,
                src=src,
                headline=tmpl.format(name=symbols.name(sym), sector=symbols.sector(sym), sym=sym),
                syms=(sym,),
            )
        )
    return out
