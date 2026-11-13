"""Plain data shapes. No behaviour, no provider imports — panels only ever see these."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(slots=True)
class Candle:
    open: float
    high: float
    low: float
    close: float
    volume: int
    t: int = 0


@dataclass(slots=True)
class Quote:
    sym: str
    last: float
    chg: float
    pct: float
    prev_close: float
    open: float
    volume: int
    as_of: int = 0
    spark: list[float] = field(default_factory=list)

    @property
    def direction(self) -> str:
        if abs(self.chg) < 0.005:
            return "flat"
        return "up" if self.chg > 0 else "down"


@dataclass(slots=True)
class NewsItem:
    t: int
    src: str
    headline: str
    syms: tuple[str, ...] = ()
    url: str = ""
