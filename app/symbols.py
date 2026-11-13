"""The universe: which symbols the terminal knows about, and how to name them.

This is the only place a ticker is spelled. Providers translate to their own identifiers
(`BRK.B` -> `BRK-B`) and never leak that spelling back into the UI.
"""

from __future__ import annotations

# sym -> (name, sector, exchange)
UNIVERSE: dict[str, tuple[str, str, str]] = {
    "AAPL": ("Apple Inc", "Technology", "NASDAQ"),
    "MSFT": ("Microsoft Corp", "Technology", "NASDAQ"),
    "NVDA": ("NVIDIA Corp", "Semiconductors", "NASDAQ"),
    "AMZN": ("Amazon.com Inc", "Consumer Discretionary", "NASDAQ"),
    "GOOGL": ("Alphabet Inc Class A", "Communication Services", "NASDAQ"),
    "META": ("Meta Platforms Inc", "Communication Services", "NASDAQ"),
    "TSLA": ("Tesla Inc", "Consumer Discretionary", "NASDAQ"),
    "AMD": ("Advanced Micro Devices", "Semiconductors", "NASDAQ"),
    "AVGO": ("Broadcom Inc", "Semiconductors", "NASDAQ"),
    "JPM": ("JPMorgan Chase & Co", "Financials", "NYSE"),
    "XOM": ("Exxon Mobil Corp", "Energy", "NYSE"),
    "UNH": ("UnitedHealth Group", "Health Care", "NYSE"),
    "WMT": ("Walmart Inc", "Consumer Staples", "NYSE"),
    "NFLX": ("Netflix Inc", "Communication Services", "NASDAQ"),
    "PLTR": ("Palantir Technologies", "Technology", "NASDAQ"),
    "COIN": ("Coinbase Global", "Financials", "NASDAQ"),
    "SPY": ("SPDR S&P 500 ETF", "Index ETF", "NYSE"),
    "QQQ": ("Invesco QQQ Trust", "Index ETF", "NASDAQ"),
}

ORDER: tuple[str, ...] = tuple(UNIVERSE)


def name(sym: str) -> str:
    return UNIVERSE.get(sym, (sym, "—", "—"))[0]


def sector(sym: str) -> str:
    return UNIVERSE.get(sym, (sym, "—", "—"))[1]


def exchange(sym: str) -> str:
    return UNIVERSE.get(sym, (sym, "—", "—"))[2]


def provider_id(sym: str) -> str:
    """Canonical ticker -> Yahoo ticker.

    Only class shares need translating (`BRK.B` is `BRK-B` upstream). Index, future and
    crypto symbols already contain `^`, `=` or `-` and must pass through untouched.
    """
    if any(ch in sym for ch in "^=-"):
        return sym
    return sym.replace(".", "-")


# The cross-asset strip. Free macro series (CPI, payrolls) need a FRED key; tradeable
# instruments do not, so the panel shows the market's own read on the same questions.
MACRO: tuple[tuple[str, str, str], ...] = (
    ("^VIX", "VIX", ""),
    ("^TNX", "US 10Y", "%"),
    ("^IRX", "US 3M", "%"),
    ("DX-Y.NYB", "Dollar idx", ""),
    ("^GSPC", "S&P 500", ""),
    ("GC=F", "Gold", ""),
    ("CL=F", "Crude", ""),
    ("BTC-USD", "Bitcoin", ""),
)
