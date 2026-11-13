"""SQLite: one file, thread-local connections, no ORM.

Candles are the expensive thing to fetch, so they are the thing worth keeping. Everything
here is idempotent — a re-run of the app, or a second process, cannot corrupt the cache.
"""

from __future__ import annotations

import sqlite3
import threading
from pathlib import Path

from .models import Candle, NewsItem

DB_PATH = Path(__file__).resolve().parent.parent / "data" / "bloomterm.db"

SCHEMA = """
create table if not exists candles (
    sym      text    not null,
    interval text    not null,
    ts       integer not null,
    open     real    not null,
    high     real    not null,
    low      real    not null,
    close    real    not null,
    volume   integer not null default 0,
    primary key (sym, interval, ts)
);

create table if not exists news (
    id       text primary key,
    ts       integer not null,
    src      text    not null,
    headline text    not null,
    url      text    not null default '',
    syms     text    not null default ''
);
create index if not exists news_ts on news (ts desc);

create table if not exists kv (
    k text primary key,
    v text not null
);
"""

_local = threading.local()


def use(path: str | Path) -> None:
    """Point the store at another file (tests, or a throwaway cache)."""
    global DB_PATH
    DB_PATH = Path(path)
    existing = getattr(_local, "c", None)
    if existing is not None:
        existing.close()
        del _local.c
    conn()


def conn() -> sqlite3.Connection:
    c = getattr(_local, "c", None)
    if c is None:
        DB_PATH.parent.mkdir(parents=True, exist_ok=True)
        c = sqlite3.connect(DB_PATH, timeout=10)
        c.row_factory = sqlite3.Row
        c.execute("pragma journal_mode=wal")
        c.execute("pragma synchronous=normal")
        c.executescript(SCHEMA)
        _local.c = c
    return c


# --------------------------------------------------------------------- candles


def upsert_candles(sym: str, interval: str, rows: list[Candle]) -> None:
    if not rows:
        return
    conn().executemany(
        "insert or replace into candles (sym, interval, ts, open, high, low, close, volume)"
        " values (?, ?, ?, ?, ?, ?, ?, ?)",
        [(sym, interval, c.t, c.open, c.high, c.low, c.close, c.volume) for c in rows],
    )
    conn().commit()


def read_candles(sym: str, interval: str, limit: int = 2000) -> list[Candle]:
    rows = (
        conn()
        .execute(
            "select ts, open, high, low, close, volume from candles"
            " where sym = ? and interval = ? order by ts asc limit ?",
            (sym, interval, limit),
        )
        .fetchall()
    )
    return [Candle(r["open"], r["high"], r["low"], r["close"], r["volume"], r["ts"]) for r in rows]


# ------------------------------------------------------------------------- news


def upsert_news(items: list[NewsItem]) -> None:
    if not items:
        return
    conn().executemany(
        "insert or replace into news (id, ts, src, headline, url, syms) values (?, ?, ?, ?, ?, ?)",
        [
            (n.url or n.headline, n.t, n.src, n.headline, getattr(n, "url", ""), ",".join(n.syms))
            for n in items
        ],
    )
    conn().commit()


def read_news(limit: int = 40) -> list[NewsItem]:
    rows = (
        conn()
        .execute("select ts, src, headline, syms, url from news order by ts desc limit ?", (limit,))
        .fetchall()
    )
    return [
        NewsItem(
            r["ts"],
            r["src"],
            r["headline"],
            tuple(filter(None, r["syms"].split(","))),
            r["url"],
        )
        for r in rows
    ]


def prune_news(before_ts: int) -> None:
    conn().execute("delete from news where ts < ?", (before_ts,))
    conn().commit()


# --------------------------------------------------------------------------- kv


def kv_get(key: str, default: str = "") -> str:
    row = conn().execute("select v from kv where k = ?", (key,)).fetchone()
    return row["v"] if row else default


def kv_set(key: str, value: str) -> None:
    conn().execute(
        "insert into kv (k, v) values (?, ?) on conflict(k) do update set v = excluded.v",
        (key, str(value)),
    )
    conn().commit()
