"""The function registry: the only list of things this terminal can display.

Adding a feature = one entry here, one template in templates/panels/, one branch in
main.build_context. Nothing else in the app needs to know it exists.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class Function:
    code: str
    title: str
    needs_ticker: bool
    default_range: str = ""
    poll: int = 0  # seconds; 0 disables polling for this panel type


FUNCTIONS: dict[str, Function] = {
    f.code: f
    for f in (
        Function("WATCH", "watchlist", needs_ticker=False, poll=15),
        Function("GP", "graph", needs_ticker=True, default_range="1D"),
        Function("DES", "description", needs_ticker=True),
        Function("N", "news", needs_ticker=False),
        Function("ECO", "cross-asset", needs_ticker=False),
        Function("MOV", "movers", needs_ticker=False, poll=15),
    )
}

# What a person actually types, versus what we call it internally.
ALIASES: dict[str, str] = {
    "TOP": "N",
    "Q": "DES",
    "G": "GP",
    "WEI": "ECO",
    "MOST": "MOV",
}


def resolve(token: str) -> Function | None:
    """Function code or alias -> Function. None if it is not a function."""
    return FUNCTIONS.get(ALIASES.get(token, token))
