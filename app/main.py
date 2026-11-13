"""FastAPI app: two HTML routes and three JSON routes. No state on the server.

Every panel is rendered from a spec on request, so a reload reproduces the screen exactly
and the URL is the whole application state.
"""

from __future__ import annotations

import logging
import time
from concurrent.futures import ThreadPoolExecutor
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from markupsafe import Markup
from pydantic import BaseModel

from . import command, layout, market, render, symbols, warm
from .config import load_env
from .data import get_provider, stream
from .data.quotes import get as get_quotes
from .data.quotes import oldest_age
from .functions import ALIASES, FUNCTIONS
from .market import RANGES
from .models import Candle, Quote

BASE = Path(__file__).resolve().parent

load_env()
log = logging.getLogger("bloomterm")
provider = get_provider()


@asynccontextmanager
async def lifespan(_: FastAPI):
    warm.start()  # keep the quote cache hot while the tab is open
    stream.start()  # live ticks when FINNHUB_API_KEY is set; a no-op otherwise
    yield


app = FastAPI(title="bloomterm", docs_url=None, redoc_url=None, lifespan=lifespan)
app.add_middleware(GZipMiddleware, minimum_size=500)


@app.middleware("http")
async def observe(request: Request, call_next):
    warm.touch()
    started = time.perf_counter()
    response = await call_next(request)
    response.headers["x-render-ms"] = f"{(time.perf_counter() - started) * 1000:.0f}"
    if request.url.path.startswith("/static/"):
        response.headers["cache-control"] = "public, max-age=3600"
    return response


app.mount("/static", StaticFiles(directory=BASE / "static"), name="static")

templates = Jinja2Templates(directory=str(BASE / "templates"))
templates.env.filters.update(
    price=render.price,
    signed=render.signed,
    pct=render.signed_pct,
    compact=render.compact,
    num1=render.num1,
    num2=render.num2,
    vol=render.vol_compact,
    hhmm=render.hhmm,
)

STATIC_VERSION = "0.3"


class FeedError(RuntimeError):
    """A provider could not supply what a panel needs."""


# --------------------------------------------------------------------------- context


def _normalise(fn: str, sym: str, rng: str) -> tuple[str, str, str]:
    if fn not in FUNCTIONS:
        fn = "WATCH"
    f = FUNCTIONS[fn]
    if f.needs_ticker and sym not in symbols.UNIVERSE:
        sym = "AAPL"
    if not f.needs_ticker:
        sym = ""
    rng = rng if rng in RANGES else f.default_range
    return fn, sym, rng


def _spark(values: list[float]) -> str:
    return render.line_path(values, 54, 16, 1) if len(values) > 1 else ""


def _row(sym: str, q: Quote) -> dict[str, object]:
    return {
        "sym": sym,
        "name": symbols.name(sym),
        "q": q,
        "dir": q.direction,
        "spark": _spark(q.spark),
    }


def _quote_from_bars(bars: list[Candle], sym: str) -> Quote:
    """Last resort when the quote batch fails but we have history."""
    closes = [b.close for b in bars]
    last, prev = closes[-1], closes[-2] if len(closes) > 1 else closes[-1]
    return Quote(
        sym=sym,
        last=last,
        chg=round(last - prev, 2),
        pct=round((last - prev) / prev * 100.0, 2) if prev else 0.0,
        prev_close=prev,
        open=bars[-1].open,
        volume=bars[-1].volume,
        spark=closes[-22:],
    )


def _title_meta(fn: str, sym: str, rng: str) -> tuple[str, str]:
    if fn == "WATCH":
        return "us equities", f"{len(symbols.ORDER)} sym · {FUNCTIONS['WATCH'].poll}s"
    if fn == "GP":
        return f"{sym} · {symbols.name(sym)}", rng
    if fn == "DES":
        return f"{sym} · {symbols.name(sym)}", "usd"
    if fn == "N":
        return "wire", "delayed"
    if fn == "ECO":
        return "cross-asset", "delayed"
    if fn == "MOV":
        return "universe", f"{len(symbols.ORDER)} sym"
    return fn.lower(), ""


def _context(fn: str, sym: str, rng: str) -> dict[str, object]:
    ctx: dict[str, object] = {"fn": fn, "sym": sym, "range": rng, "ranges": RANGES}

    if fn == "WATCH":
        qs = get_quotes(symbols.ORDER)
        rows = [_row(s, qs[s]) for s in symbols.ORDER if s in qs]
        if not rows:
            raise FeedError("no quotes available")
        ctx["rows"] = rows

    elif fn == "GP":
        bars = provider.candles(sym, rng)
        closes = [b.close for b in bars]
        if len(closes) < 2:
            raise FeedError(f"no chart data for {sym}")
        q = get_quotes([sym]).get(sym) or _quote_from_bars(bars, sym)
        ctx.update(
            q=q,
            path=render.line_path(closes, 600, 150, 2),
            rects=render.vol_rects([float(b.volume) for b in bars], 600, 34, 1),
            hi=max(closes),
            lo=min(closes),
            volume=sum(b.volume for b in bars),
        )

    elif fn == "DES":
        d = provider.describe(sym)
        q = get_quotes([sym]).get(sym)
        if q is None:
            q = Quote(
                sym=sym,
                last=float(d.get("last") or 0),
                chg=round(float(d.get("last") or 0) - float(d.get("prev_close") or 0), 2),
                pct=0.0,
                prev_close=float(d.get("prev_close") or 0),
                open=float(d.get("last") or 0),
                volume=0,
            )
        ctx.update(q=q, d=d)

    elif fn == "N":
        items = provider.news(16)
        if not items:
            raise FeedError("wire unavailable")
        ctx["items"] = items

    elif fn == "ECO":
        qs = get_quotes([m[0] for m in symbols.MACRO])
        rows = [
            {
                "label": label,
                "unit": unit,
                "q": qs[s],
                "dir": qs[s].direction,
                "spark": _spark(qs[s].spark),
            }
            for s, label, unit in symbols.MACRO
            if s in qs
        ]
        if not rows:
            raise FeedError("cross-asset feed unavailable")
        ctx["rows"] = rows

    elif fn == "MOV":
        qs = get_quotes(symbols.ORDER)
        if not qs:
            raise FeedError("no quotes available")
        ordered = sorted(qs.values(), key=lambda q: q.pct)
        ctx["gainers"] = [_row(q.sym, q) for q in ordered[-6:][::-1]]
        ctx["losers"] = [_row(q.sym, q) for q in ordered[:6]]

    return ctx


def render_panel(index: int, fn: str, sym: str, rng: str, active: bool = False) -> str:
    fn, sym, rng = _normalise(fn, sym, rng)
    try:
        body = templates.get_template(f"panels/{fn.lower()}.html").render(**_context(fn, sym, rng))
    except Exception as exc:  # a broken feed must not take the screen down
        log.warning("panel %s %s: %s", fn, sym, exc)
        message = str(exc) if isinstance(exc, FeedError) else f"feed error — {type(exc).__name__}"
        body = templates.get_template("panels/error.html").render(message=message)

    title, meta = _title_meta(fn, sym, rng)
    return templates.get_template("panel.html").render(
        i=index,
        fn=fn,
        sym=sym,
        range=rng,
        active=active,
        title=title,
        meta=meta,
        poll=FUNCTIONS[fn].poll,
        body=Markup(body),
    )


# --------------------------------------------------------------------------- routes


@app.get("/", response_class=HTMLResponse)
def index(request: Request) -> HTMLResponse:
    q = request.query_params
    preset = q.get("l", "4")
    cols, count = layout.PRESETS.get(preset, layout.PRESETS["4"])

    jobs = []
    for i in range(count):
        fallback = layout.DEFAULT_SPECS[i] if i < len(layout.DEFAULT_SPECS) else "N"
        fn, sym, rng = layout.parse_spec(q.get(f"p{i}", fallback))
        jobs.append((i, fn, sym, rng, i == 0))

    # Panels are independent fetches; render them at the same time, not one after another.
    with ThreadPoolExecutor(max_workers=min(6, count)) as pool:
        panels = [Markup(html) for html in pool.map(lambda job: render_panel(*job), jobs)]

    state, state_class = market.state()
    tick_age = int(oldest_age(symbols.ORDER))
    return templates.TemplateResponse(
        request,
        "base.html",
        {
            "panels": panels,
            "preset": preset if preset in layout.PRESETS else "4",
            "cols": cols,
            "provider": provider.name,
            "delay": provider.delay,
            "clock": market.clock(),
            "tick_age": tick_age,
            "stream_live": stream.state() == "live",
            "mkt": state,
            "mkt_class": state_class,
            "functions": list(FUNCTIONS.values()),
            "aliases": ALIASES,
            "version": STATIC_VERSION,
        },
    )


@app.get("/api/panel", response_class=HTMLResponse)
def api_panel(fn: str, sym: str = "", range: str = "", i: int = 0) -> HTMLResponse:
    return HTMLResponse(render_panel(i, fn.upper(), sym.upper(), range.upper(), active=True))


class Cmd(BaseModel):
    q: str
    index: int = 0
    sym: str = ""


@app.post("/api/command")
def api_command(cmd: Cmd) -> JSONResponse:
    parsed = command.parse(cmd.q, current_sym=cmd.sym or "AAPL")
    if not parsed.ok:
        return JSONResponse({"ok": False, "error": parsed.error, "candidates": parsed.candidates})

    rng = FUNCTIONS[parsed.fn].default_range
    html = render_panel(cmd.index, parsed.fn, parsed.sym, rng, active=True)
    return JSONResponse({"ok": True, "html": html, "fn": parsed.fn, "sym": parsed.sym})


@app.get("/api/watch")
def api_watch() -> JSONResponse:
    qs = get_quotes(symbols.ORDER)
    rows = []
    for sym in symbols.ORDER:
        q = qs.get(sym)
        if q is None:
            continue
        rows.append(
            {
                "sym": sym,
                "last": render.price(q.last),
                "chg": render.signed(q.chg),
                "pct": render.signed_pct(q.pct),
                "dir": q.direction,
            }
        )
    return JSONResponse(rows)


@app.get("/api/health")
def api_health() -> dict[str, object]:
    return {"status": "ok", "provider": provider.name, "symbols": len(symbols.ORDER)}
