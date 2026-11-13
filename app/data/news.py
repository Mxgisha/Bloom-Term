"""Headlines from RSS, deduped and cached.

RSS is unglamorous but it is the only free wire that works without a key. Two consequences
shape this module: headlines carry no ticker tags (so we subscribe per symbol), and the same
story appears in several feeds (so we dedupe on the title).
"""

from __future__ import annotations

import hashlib
import re
import time
import urllib.request
import xml.etree.ElementTree as ET
from concurrent.futures import ThreadPoolExecutor
from email.utils import parsedate_to_datetime

from .. import store
from ..models import NewsItem

UA = "Mozilla/5.0 (compatible; bloomterm/0.1; personal market dashboard)"

# One general feed for things that are not about a single company.
GENERAL = [
    ("CNBC", "https://www.cnbc.com/id/100003114/device/rss/rss.html"),
    ("WSJ", "https://feeds.a.dj.com/rss/RSSMarketsMain.xml"),
]

CACHE_TTL = 300
KEEP_SECONDS = 3 * 24 * 3600


def _feed_url(sym: str) -> str:
    return f"https://feeds.finance.yahoo.com/rss/2.0/headline?s={sym}&region=US&lang=en-US"


def _get(url: str) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=8) as resp:
        return resp.read()


def _parse(raw: bytes, src: str, sym: str = "") -> list[NewsItem]:
    out: list[NewsItem] = []
    try:
        root = ET.fromstring(raw)
    except ET.ParseError:
        return out
    for item in root.findall(".//item"):
        title = (item.findtext("title") or "").strip()
        link = (item.findtext("link") or "").strip()
        if not title:
            continue
        stamp = item.findtext("pubDate") or ""
        try:
            ts = int(parsedate_to_datetime(stamp).timestamp())
        except (TypeError, ValueError):
            ts = int(time.time())
        out.append(NewsItem(t=ts, src=src, headline=title, syms=(sym,) if sym else (), url=link))
    return out


def _key(item: NewsItem) -> str:
    norm = re.sub(r"[^a-z0-9]+", "", item.headline.lower())[:90]
    return hashlib.sha1(norm.encode()).hexdigest()


def fetch(symbols: list[str], limit: int = 24) -> list[NewsItem]:
    """Cached wire. Returns [] when every feed is down and nothing is cached."""
    fresh = float(store.kv_get("news_at", "0") or 0)
    if time.time() - fresh < CACHE_TTL:
        cached = store.read_news(limit)
        if cached:
            return cached[:limit]

    jobs = [(src, url, "") for src, url in GENERAL]
    for sym in symbols[:6]:
        jobs.append(("YH", _feed_url(sym), sym))

    def run(job: tuple[str, str, str]) -> list[NewsItem]:
        src, url, sym = job
        try:
            return _parse(_get(url), src, sym)
        except Exception:
            return []

    items: list[NewsItem] = []
    with ThreadPoolExecutor(max_workers=6) as pool:
        for part in pool.map(run, jobs):
            # no single feed should drown the rest
            items.extend(sorted(part, key=lambda i: i.t, reverse=True)[:8])

    if not items:
        return store.read_news(limit)[:limit]

    seen: set[str] = set()
    unique: list[NewsItem] = []
    for item in sorted(items, key=lambda i: i.t, reverse=True):
        key = _key(item)
        if key in seen:
            continue
        seen.add(key)
        unique.append(item)

    store.upsert_news(unique)
    store.prune_news(int(time.time()) - KEEP_SECONDS)
    store.kv_set("news_at", int(time.time()))
    return unique[:limit]
