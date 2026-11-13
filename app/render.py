"""SVG and number helpers. Pure functions so they are trivially testable."""

from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

NY = ZoneInfo("America/New_York")


def _points(values: list[float], w: float, h: float, pad: float) -> list[tuple[float, float]]:
    lo, hi = min(values), max(values)
    if hi - lo < 1e-9:
        hi = lo + 1.0
    n = len(values)
    dx = (w - 2 * pad) / max(n - 1, 1)
    span = hi - lo
    return [
        (pad + i * dx, pad + (1.0 - (v - lo) / span) * (h - 2 * pad)) for i, v in enumerate(values)
    ]


def line_path(values: list[float], w: float, h: float, pad: float = 1.0) -> str:
    if len(values) < 2:
        return ""
    pts = _points(values, w, h, pad)
    return "M" + " L".join(f"{x:.1f} {y:.1f}" for x, y in pts)


def vol_rects(values: list[float], w: float, h: float, gap: float = 1.0) -> list[dict[str, float]]:
    n = len(values)
    if not n:
        return []
    top = max(values) or 1.0
    bw = max((w - (n - 1) * gap) / n, 0.5)
    out = []
    for i, v in enumerate(values):
        bh = max(1.0, (v / top) * (h - 1.0))
        out.append(
            {
                "x": round(i * (bw + gap), 1),
                "y": round(h - bh, 1),
                "w": round(bw, 1),
                "h": round(bh, 1),
            }
        )
    return out


def price(v: float) -> str:
    return f"{v:,.2f}"


def signed(v: float) -> str:
    if abs(v) < 0.005:
        return "0.00"
    return f"{v:+,.2f}"


def signed_pct(v: float) -> str:
    if abs(v) < 0.005:
        return "0.00%"
    return f"{v:+.2f}%"


def num1(v) -> str:
    return f"{float(v):,.1f}"


def num2(v) -> str:
    return f"{float(v):,.2f}"


def compact(v: float) -> str:
    a = abs(v)
    for cut, suffix in ((1e12, "T"), (1e9, "B"), (1e6, "M"), (1e3, "K")):
        if a >= cut:
            return f"{v / cut:,.2f}{suffix}"
    return f"{v:,.0f}"


def vol_compact(v: float) -> str:
    a = abs(v)
    if a >= 1e9:
        return f"{v / 1e9:,.2f}B"
    if a >= 1e6:
        return f"{v / 1e6:,.1f}M"
    if a >= 1e3:
        return f"{v / 1e3:,.0f}K"
    return f"{v:,.0f}"


def hhmm(ts: int) -> str:
    return datetime.fromtimestamp(ts, tz=NY).strftime("%H:%M")
