"""Market clock and range vocabulary. Provider-agnostic, no network."""

from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

NY = ZoneInfo("America/New_York")

RANGES: tuple[str, ...] = ("1D", "5D", "1M", "6M", "1Y")


def now() -> datetime:
    return datetime.now(tz=NY)


def clock() -> str:
    return now().strftime("%H:%M:%S")


def is_open() -> bool:
    t = now()
    if t.weekday() >= 5:
        return False
    minutes = t.hour * 60 + t.minute
    return 9 * 60 + 30 <= minutes < 16 * 60


def state() -> tuple[str, str]:
    """(label, css class). Holidays are deliberately ignored."""
    t = now()
    if t.weekday() >= 5:
        return "closed", "dim"
    minutes = t.hour * 60 + t.minute
    if 4 * 60 <= minutes < 9 * 60 + 30:
        return "pre", "warn"
    if 9 * 60 + 30 <= minutes < 16 * 60:
        return "open", "up"
    if 16 * 60 <= minutes < 20 * 60:
        return "post", "warn"
    return "closed", "dim"
