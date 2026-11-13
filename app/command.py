"""Command grammar.

    AAPL GP     -> GP panel for AAPL
    AAPL        -> default panel for AAPL (DES)
    N           -> news panel
    MOV         -> movers panel

Resolution order matters and is deliberate: an exact function code beats a ticker, because
the function list is tiny and the ticker list is not. Two tokens are never ambiguous.
"""

from __future__ import annotations

import difflib
from dataclasses import dataclass, field

from .functions import FUNCTIONS, resolve
from .symbols import ORDER as SYMBOLS
from .symbols import UNIVERSE


@dataclass(slots=True)
class Parsed:
    ok: bool
    fn: str = ""
    sym: str = ""
    error: str = ""
    candidates: list[str] = field(default_factory=list)


def _suggest(token: str) -> list[str]:
    pool = list(FUNCTIONS) + list(SYMBOLS)
    return difflib.get_close_matches(token, pool, n=4, cutoff=0.45)


def parse(raw: str, current_sym: str = "AAPL") -> Parsed:
    tokens = raw.strip().upper().split()

    if not tokens:
        return Parsed(False, error="type a ticker, a function, or both")

    if len(tokens) > 2:
        return Parsed(False, error="too many words — try `AAPL GP`")

    if len(tokens) == 2:
        sym, fn_token = tokens
        fn = resolve(fn_token)
        if fn is None:
            return Parsed(
                False,
                error=f"unknown function `{fn_token}`",
                candidates=_suggest(fn_token) + list(FUNCTIONS)[:3],
            )
        if sym not in UNIVERSE:
            return Parsed(False, error=f"unknown ticker `{sym}`", candidates=_suggest(sym))
        if not fn.needs_ticker:
            return Parsed(False, error=f"`{fn.code}` does not take a ticker")
        return Parsed(True, fn=fn.code, sym=sym)

    token = tokens[0]
    fn = resolve(token)
    if fn is not None:
        return Parsed(True, fn=fn.code, sym=current_sym if fn.needs_ticker else "")

    if token in UNIVERSE:
        return Parsed(True, fn="DES", sym=token)

    return Parsed(False, error=f"no match for `{token}`", candidates=_suggest(token))
