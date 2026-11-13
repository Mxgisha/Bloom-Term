"""Yahoo Finance adapter.

Unofficial, free, delayed — and the only reason this app can show a real price without a key.
Two rules keep it usable: quotes are fetched for the whole watchlist in one request, and every
candle is written to SQLite so a chart never re-downloads history it already has.

When Yahoo changes shape, this is the only file that has to change.
"""

from __future__ import annotations

import json
import time

import pandas as pd
import yfinance as yf

from .. import market, store, symbols
from ..models import Candle, NewsItem, Quote
from . import news as wire

name = "yahoo"
delay = "15m delay"

_DAILY_COUNT = {"5D": 5, "1M": 22, "6M": 130, "1Y": 252}
_QUOTE_TTL_OPEN = 900
_QUOTE_TTL_CLOSED = 6 * 3600


# ------------------------------------------------------------------------ helpers


def _sub(df: pd.DataFrame, pid: str) -> pd.DataFrame | None:
    """One symbol's frame out of a batch download, whichever shape yfinance returned."""
    if df is None or len(df) == 0:
        return None
    if isinstance(df.columns, pd.MultiIndex):
        if pid in df.columns.get_level_values(0):
            return df[pid]
        return None
    return df


def _stamp(index_value) -> int:
    try:
        if getattr(index_value, "tzinfo", None) is not None:
            return int(index_value.timestamp())
        return int(index_value.tz_localize(market.NY).timestamp())
    except Exception:
        return 0


def _candles_from(df: pd.DataFrame) -> list[Candle]:
    out: list[Candle] = []
    if df is None or len(df) == 0:
        return out
    if isinstance(df.columns, pd.MultiIndex):
        df = df[df.columns.get_level_values(0)[0]]
    for ts, row in df.iterrows():
        close = row.get("Close")
        if close is None or pd.isna(close):
            continue
        volume = row.get("Volume", 0)
        out.append(
            Candle(
                open=float(row.get("Open") or close),
                high=float(row.get("High") or close),
                low=float(row.get("Low") or close),
                close=float(close),
                volume=int(0 if pd.isna(volume) else volume),
                t=_stamp(ts),
            )
        )
    return out


def _download(sym_or_list, period: str, interval: str) -> pd.DataFrame | None:
    try:
        return yf.download(
            sym_or_list,
            period=period,
            interval=interval,
            group_by="ticker",
            progress=False,
            threads=True,
            auto_adjust=False,
        )
    except Exception:
        return None


# ------------------------------------------------------------------------- quotes


def quotes(syms: list[str] | tuple[str, ...]) -> dict[str, Quote]:
    syms = [s for s in syms if s]
    if not syms:
        return {}
    ids = {symbols.provider_id(s): s for s in syms}
    # One request for one month of daily bars: enough for the quote and its sparkline.
    df = _download(list(ids), period="1mo", interval="1d")

    got: dict[str, Quote] = {}
    for pid, sym in ids.items():
        sub = _sub(df, pid)
        if sub is None:
            continue
        sub = sub.dropna(subset=["Close"])
        if len(sub) < 2:
            continue
        closes = [float(v) for v in sub["Close"].tolist()]
        last, prev = closes[-1], closes[-2]
        if prev <= 0:
            continue
        row = sub.iloc[-1]
        volume = row.get("Volume", 0)
        got[sym] = Quote(
            sym=sym,
            last=round(last, 2),
            chg=round(last - prev, 2),
            pct=round((last - prev) / prev * 100.0, 2),
            prev_close=round(prev, 2),
            open=round(float(row.get("Open") or last), 2),
            volume=int(0 if pd.isna(volume) else volume),
            as_of=int(time.time()),
            spark=[round(v, 2) for v in closes[-22:]],
        )
    return got


# ------------------------------------------------------------------------ candles


def candles(sym: str, rng: str) -> list[Candle]:
    if rng == "1D":
        return _intraday(sym)[-78:]
    return _daily(sym)[-_DAILY_COUNT.get(rng, 5) :]


def _daily(sym: str) -> list[Candle]:
    key = f"daily_at:{sym}"
    last_fetch = float(store.kv_get(key, "0") or 0)
    rows = store.read_candles(sym, "1d")
    ttl = _QUOTE_TTL_OPEN if market.is_open() else _QUOTE_TTL_CLOSED
    if rows and time.time() - last_fetch < ttl:
        return rows

    # First visit pays for two years once; later visits top up the last week.
    period = "2y" if not rows else "5d"
    df = _download(symbols.provider_id(sym), period=period, interval="1d")
    fresh = _candles_from(df)
    if fresh:
        store.upsert_candles(sym, "1d", fresh)
        store.kv_set(key, int(time.time()))
        rows = store.read_candles(sym, "1d")
    return rows


def _intraday(sym: str) -> list[Candle]:
    key = f"intraday_at:{sym}"
    last_fetch = float(store.kv_get(key, "0") or 0)
    rows = store.read_candles(sym, "5m")
    ttl = 600 if market.is_open() else _QUOTE_TTL_CLOSED
    if rows and time.time() - last_fetch < ttl:
        return rows

    df = _download(symbols.provider_id(sym), period="1d", interval="5m")
    fresh = _candles_from(df)
    if fresh:
        store.upsert_candles(sym, "5m", fresh)
        store.kv_set(key, int(time.time()))
        rows = store.read_candles(sym, "5m")
    return rows


# ----------------------------------------------------------------------- describe


def describe(sym: str) -> dict[str, object]:
    key = f"info:{sym}"
    raw = store.kv_get(key, "")
    if raw:
        try:
            blob = json.loads(raw)
            if time.time() - blob["at"] < 86400:
                return blob["data"]
        except (ValueError, KeyError):
            pass

    data = _fetch_info(sym)
    store.kv_set(key, json.dumps({"at": int(time.time()), "data": data}))
    return data


def _fetch_info(sym: str) -> dict[str, object]:
    info: dict = {}
    try:
        info = yf.Ticker(symbols.provider_id(sym)).info or {}
    except Exception:
        info = {}

    closes = [c.close for c in candles(sym, "1Y")]
    last = closes[-1] if closes else 0.0
    prev = closes[-2] if len(closes) > 1 else last

    def pick(key: str, fallback):
        value = info.get(key)
        return fallback if value in (None, "") else value

    return {
        "name": str(pick("longName", symbols.name(sym))).rstrip("."),
        "sector": pick("sector", symbols.sector(sym)),
        "exchange": pick("fullExchangeName", symbols.exchange(sym)),
        "currency": pick("currency", "USD"),
        "cap": pick("marketCap", 0.0),
        "pe": pick("trailingPE", 0.0),
        "div": pick("dividendYield", 0.0),
        "beta": pick("beta", 0.0),
        "hi52": pick("fiftyTwoWeekHigh", max(closes) if closes else 0.0),
        "lo52": pick("fiftyTwoWeekLow", min(closes) if closes else 0.0),
        "avg_vol": pick("averageVolume", 0),
        "prev_close": prev,
        "last": last,
    }


# --------------------------------------------------------------------------- news


def news(limit: int = 24) -> list[NewsItem]:
    return wire.fetch(list(symbols.ORDER), limit)
