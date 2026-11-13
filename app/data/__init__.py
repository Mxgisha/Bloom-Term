"""Provider selection. One env var, one interface, no framework.

`BLOOMTERM_PROVIDER=mock` runs the whole app offline on generated data; anything else uses
Yahoo. Both expose: name, delay, quotes(), candles(), describe(), news().
"""

from __future__ import annotations

import os
from collections.abc import Sequence
from typing import Protocol

from ..models import Candle, NewsItem, Quote


class Provider(Protocol):
    name: str
    delay: str

    def quotes(self, syms: Sequence[str]) -> dict[str, Quote]: ...
    def candles(self, sym: str, rng: str) -> list[Candle]: ...
    def describe(self, sym: str) -> dict: ...
    def news(self, limit: int = 24) -> list[NewsItem]: ...


def get_provider() -> Provider:
    if os.environ.get("BLOOMTERM_PROVIDER", "yahoo").strip().lower() == "mock":
        from . import mock

        return mock
    from . import yahoo

    return yahoo
