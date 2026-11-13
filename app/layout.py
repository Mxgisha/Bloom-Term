"""Layout presets and the panel spec string used in the URL.

A spec is `FN[:SYM[:RANGE]]`, e.g. `WATCH`, `GP:AAPL:1Y`, `DES:MSFT`. Colons are used
because tickers never contain them — unlike dots, which BRK.B would ruin.
"""

from __future__ import annotations

# preset -> (columns, panel count)
PRESETS: dict[str, tuple[int, int]] = {
    "1": (1, 1),
    "2": (2, 2),
    "4": (2, 4),
    "6": (3, 6),
}

DEFAULT_SPECS: tuple[str, ...] = ("WATCH", "GP:AAPL", "N", "DES:AAPL", "ECO", "MOV")


def spec(fn: str, sym: str = "", rng: str = "") -> str:
    if sym and rng:
        return f"{fn}:{sym}:{rng}"
    if sym:
        return f"{fn}:{sym}"
    return fn


def parse_spec(raw: str) -> tuple[str, str, str]:
    parts = raw.split(":")
    fn = (parts[0] or "WATCH").strip().upper()
    sym = parts[1].strip().upper() if len(parts) > 1 else ""
    rng = parts[2].strip().upper() if len(parts) > 2 else ""
    return fn, sym, rng
