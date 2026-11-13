# bloomterm — a minimal terminal-style market display

**One sentence:** a keyboard-first, single-screen dashboard that puts quotes, one chart,
news, and a handful of macro numbers in front of you with no hunting through menus.

> **Status:** P0–P3 are built, plus a latency pass and an optional Finnhub trade stream.
> Six panels, command line, URL state, delayed quotes by default, live ticks with a key,
> a SQLite candle cache, and the RSS wire. `BLOOMTERM_PROVIDER=mock` runs it offline.
> Free data alternatives: [docs/DATA.md](docs/DATA.md).

**Design test for every decision below:** *does it make the screen denser, faster, and more
predictable under the keyboard?* If not, it is out of scope.

---

## 0. The job to be done

A Bloomberg Terminal is ~$30k/seat/year and is really four products: a data terminal, a
messaging network, an order router, and a news wire. You want one of them: **centralised
information display**. That means the entire product is:

1. **Composition** — arrange 4–6 panels on one screen, saved between sessions.
2. **Navigation** — reach any panel with a mnemonic from the keyboard in <1s.
3. **Density** — maximum signal per pixel, no scrolling for the thing you check daily.
4. **Trust** — you can always tell how fresh each number is.

Notice what is *not* in that list: features. A terminal with 6 excellent panels beats one
with 30 half-working ones, because each panel is a data feed with a maintenance tail.

---

## 1. v1 feature set — frozen at six functions

```
+-------------------------------+----------------------------------------------+
| bloomterm   [ AAPL GP          ]  * DELAY 15M  16:04 ET  FRI OPEN  v0.1      |
+-------------------------------+----------------------------------------------+
| WATCH                         | AAPL  GP           1D 5D 1M 6M 1Y 5Y         |
| AAPL   227.52  +1.84  +0.82%  |                                              |
|  .:=+*%#%*+=:.                |                                              |
| MSFT   418.10  -2.20  -0.52%  |            /\      /\                        |
|  .:-+*#%*+-:.                 |       /\  /  \/\  /  \/\                     |
| NVDA   141.02  +3.10  +2.25%  |  /\/  \/            \/                       |
|  :=*#%@@%*+=-                 | -------------------------------- vol -----   |
|                               | .:-=+*#%@@%*+=-:.  .:-=+*#%@@%*+=-:.         |
+-------------------------------+----------------------------------------------+
| N  NEWS                       | DES  APPLE INC                               |
| 16:02  Apple unveils ...      | Price    227.52    Mkt cap   3.44T           |
| 15:47  Fed officials ...      | P/E      35.1      Div yld   0.44%           |
| 14:30  Chip export rules ..   | 52w      164.08-260.10  Beta 1.24            |
| 13:55  ...                    | Sector   Technology     Vol  48.2M           |
+-------------------------------+----------------------------------------------+
| ECO  US MACRO                                               quotes 14/60 rpm |
| CPI 3.0% ^  UNRATE 4.1%  DGS10 4.28%  10Y-2Y +0.12   PAYEMS +148k            |
+------------------------------------------------------------------------------+
```

| Code    | Panel                  | Ticker | Answers the question            | Build cost |
| ------- | ---------------------- | ------ | ------------------------------- | ---------- |
| `WATCH` | watchlist + sparklines | no     | "what am I tracking today?"     | S          |
| `GP`    | price chart + volume   | yes    | "what is it doing?"             | M          |
| `DES`   | description / key stats | yes   | "what even is this thing?"      | S          |
| `N`     | news headlines         | opt.   | "why is it moving?"             | M          |
| `ECO`   | cross-asset strip      | no     | "what is the backdrop?"         | S          |
| `MOV`   | movers (fixed universe)| no     | "what is alive today?"          | S          |

**Cap: six.** Adding a seventh means deleting one. This rule is the whole "minimise
complexity" brief; write it in the README so future-you argues with it.

Deliberately excluded from v1: portfolio/P&L, options, fixed income, FX, screener,
comparables, alerts, chat, order entry, mobile.

> **Variant if your real use case is your own portfolio:** swap `ECO` + `MOV` for a `PORT`
> panel (positions, P&L, weight, day change) and make `WATCH` the same table with quantity
> columns. If you mostly want to watch *your money*, this is the correct v1 and the macro
> panel is decoration. Decide this before you build; it changes the data model.

---

## 2. Interaction model

### 2.1 Command grammar

The part of Bloomberg worth copying is the **noun + mnemonic** command line. Keep that,
drop everything else.

```
AAPL GP        → open GP panel for AAPL
AAPL           → open the default function (DES) for AAPL
N              → news panel
?              → help overlay listing every function
```

```ts
type Command = { fn: FunctionCode; sym?: string }

// Resolution rule, in order:
// 1. two tokens        → [symbol, function]   (no ambiguity)
// 2. one token, is a known function code → function
// 3. one token, is a known symbol       → default function
// 4. otherwise          → show suggestions, never silently do nothing
```

Collisions are real (`F` = Ford, `T` = AT&T, `V` = Visa, `N`, `C`, `K`). Rule 1 handles most;
for single tokens, **function codes win only if the panel needs no ticker**. Keep a
`COLLISIONS` set and prefer the symbol. Command history via `↑` / `↓`.

### 2.2 Keyboard map

Single-letter shortcuts must be inert whenever a text input has focus — that is a scope
stack, not an afterthought (`useKeys(scope)`).

| Key                 | Action                                  |
| ------------------- | --------------------------------------- |
| `Ctrl/Cmd+K` or `/` | focus command line                      |
| `Enter`             | execute                                 |
| `Esc`               | clear input → then blur → then close overlay |
| `Tab` / `Shift+Tab` | next / previous panel (focus ring)      |
| `Alt+1..6`          | focus panel n                           |
| `[` / `]`           | chart range shorter / longer (focused)  |
| `r`                 | force refresh focused panel             |
| `w`                 | toggle focused symbol in watchlist      |
| `?`                 | help / mnemonic cheat-sheet             |

Only one panel is "active" at a time and it must be *obvious* (2px accent border + header
inversion). Every action targets the active panel. This single piece of state is what makes
it feel like a terminal instead of a web page.

### 2.3 Layout

CSS Grid with **fixed presets only** — `1`, `2-col`, `3-col`, `2×2`, `3×2`. No drag-resize,
no arbitrary splits; resizable panes are a week of fiddly code for zero information gain.

```ts
type Layout = { preset: '2x2'; panels: Array<{ fn: FunctionCode; sym?: string }> }
```

Persisted in `localStorage` (`bloomterm.v1`). Panels mount lazily; offscreen panels stop
polling (Page Visibility + IntersectionObserver).

### 2.4 Visual contract — technical, not showy

The look is the product. Every rule below exists to stop it drifting into a SaaS dashboard.

- **Chrome does not exist.** No cards, shadows, gradients, blur, rounded corners over 2px, or
  hover lift. The only ornament is a 1px hairline between panels.
- **Three type sizes, one family.** 10px uppercase labels, 12px data, 13px panel titles.
  `ui-monospace` stack, `tabular-nums`, no italics, no bold except the active panel title.
- **Colour is data.** Four greys plus up/down and one accent. The accent appears only on focus
  and errors — never on a button, never on a heading.
- **Labels uppercase, tracked +0.08em, muted; values never uppercase.** Numbers right-aligned
  in columns with fixed decimals, so the eye can scan a magnitude without reading it.
- **No icons, no logo, no illustration.** Empty state is one muted sentence. Errors are inline
  text in the panel header, never a modal, never a toast.
- **No spinners.** A refreshing panel keeps its last values, dims to 60%, and shows the age.
- **Density floor:** at least 18 data rows visible at 900px height. If a panel needs a scroll
  to show the thing you check daily, the panel is designed wrong.
- **Motion:** a single 160ms background flash when a value changes, and nothing else. Kill it
  under `prefers-reduced-motion`.
- **Legible in greyscale.** Up/down always carries `+`/`-` or `▲`/`▼`; colour is redundant.
- **No settings page.** Every preference is a command (`?` lists them), so there is one input
  in the whole application.
- **A permanent status line.** Provider, data delay, clock (ET), market state, poll interval,
  quota used. It is the only place the app admits what it is doing, so it always exists.
- **Keyboard first, click second.** Anything clickable is reachable by key; the mouse is a
  fallback, not the design target.

---

## 3. Architecture

### Stack (small on purpose)

| Layer        | Choice                          | Why                                                      |
| ------------ | ------------------------------- | -------------------------------------------------------- |
| Language     | Python 3.12+                    | one language for routes, data, and templates              |
| Server       | FastAPI + uvicorn               | typed routes, async providers, ~30 lines of bootstrap     |
| Templating   | Jinja2 (server-rendered)        | a panel is HTML, not a component tree                     |
| Interactivity| ~280 lines of vanilla JS        | command bar, focus, polling — no framework, no build      |
| Charts       | inline SVG, generated in Python | zero dependencies, crisp at any DPI, no canvas            |
| Validation   | pydantic + per-panel try/except | provider data is garbage; fail at the edge, not in Jinja  |
| Storage      | stdlib `sqlite3`                | candle cache + news + kv: one file, no ORM                |
| Data         | `yfinance` + RSS                | free, no key, 15m delayed, unofficial                    |
| Tests        | `pytest` + 2 Playwright flows   | formatter/parser drift is the real risk                   |

No npm, no Vite, no bundler, no Node. `uvicorn app.main:app --reload` and a browser is the
whole dev loop. That is the single biggest complexity saving available here, and it is why
Python is the right call for this application specifically.

**Why not React:** every panel is a table or a chart that replaces itself on a timer. Server
rendering gives that for free, and the SPA would add a build step, a state store, and
hydration to reproduce work the browser already does. The escape hatch: the day a panel needs
genuinely interactive client state (crosshair dragging, cross-filtering, a streaming book),
add a small React island for *that panel only* — do not rewrite the shell.

**Why not HTMX:** it would replace the ~40-line `fetch + swap` helper, but we need custom
keyboard scoping, active-panel tracking, and URL sync anyway, so it buys little. If you would
rather not own the swap helper, drop htmx in and delete those 40 lines; nothing else changes.

**Why SVG charts:** a terminal chart is a line, bars, and a price scale. Canvas buys
interactivity we do not have yet, and a chart library is a dependency plus a CDN. When the
crosshair arrives it is a 20-line JS overlay on the same coordinates.

### State lives in the URL

There is one piece of mutable state — the layout — and it belongs in the query string:

```
/?l=4&p0=WATCH&p1=GP:AAPL&p2=N&p3=DES:AAPL
```

`l` is the preset, `p{n}` is a `FUNCTION[:SYMBOL[:RANGE]]` panel — colons because tickers can
contain dots (`BRK.B`). Reload restores exactly what you saw,
the back button works, and the server is stateless, so there is no session store, no cookie,
and no hydration mismatch. Command execution is a client `fetch` to replace one panel plus
`history.replaceState`.

### Directory layout

```
bloomterm/
├─ run.py                     # uvicorn entry
├─ README.md                  # how to run, keys, rules
├─ pyproject.toml             # deps, pytest, ruff
├─ PLAN.md                    # this file
├─ data/bloomterm.db          # candle cache + news + kv (gitignored)
├─ tests/                     # pytest, no network
└─ app/
   ├─ main.py                 # routes; renders a panel from a spec; error boundary
   ├─ functions.py            # the registry: the only list of functions
   ├─ command.py              # "AAPL GP" -> Command, with suggestions on error
   ├─ layout.py               # presets and the URL spec format
   ├─ symbols.py              # the universe, ticker spelling, cross-asset list
   ├─ market.py               # market clock and range vocabulary
   ├─ render.py               # SVG paths + number formatting
   ├─ models.py               # Quote, Candle, NewsItem
   ├─ store.py                # SQLite: candles, news, kv
   ├─ data/
   │  ├─ __init__.py          # provider selection (BLOOMTERM_PROVIDER)
   │  ├─ yahoo.py             # quotes, candles, descriptions
   │  ├─ mock.py              # deterministic offline provider
   │  ├─ news.py              # RSS fetch, dedupe, cache
   │  └─ quotes.py            # shared TTL cache with single-flight fetch
   ├─ templates/
   │  ├─ base.html            # shell: top bar, grid, footer, help overlay
   │  ├─ panel.html           # the frame every panel shares
   │  └─ panels/              # watch, gp, des, n, eco, mov, error
   └─ static/
      ├─ app.css              # the whole design system, ~420 lines
      └─ app.js               # command line, focus, polling, URL sync
```

### Provider interface

Every panel talks to this, never to `yfinance` directly. `BLOOMTERM_PROVIDER=mock` swaps
the implementation and the app runs with no network at all; `tests/conftest.py` sets it.

```python
class Provider(Protocol):
    def quotes(self, syms: list[str]) -> dict[str, Quote]: ...      # MUST batch
    def candles(self, sym: str, rng: Range) -> list[Candle]: ...
    def describe(self, sym: str) -> Describe: ...
    def news(self, syms: list[str], limit: int) -> list[NewsItem]: ...
    def search(self, q: str) -> list[Hit]: ...
```

---

## 4. Data layer

### What is wired

| Need        | Source                                  | Reality                                                |
| ----------- | --------------------------------------- | ------------------------------------------------------ |
| Quotes      | Yahoo via `yfinance`, one batched call  | unofficial, ~15 min delayed, one request for 18 symbols |
| Live ticks  | Finnhub websocket (optional)            | 50 symbols, free, needs a key; overlays Yahoo's price   |
| Candles     | Yahoo daily + 5m bars                   | written to SQLite; closed bars never refetched          |
| Description | `yfinance` `.info`, cached 24h          | slow (~0.4s) and occasionally missing fields            |
| News        | Yahoo per-symbol RSS, CNBC, WSJ         | no ticker tags; dedupe on title; headlines only         |
| Cross-asset | `^VIX`, `^TNX`, `DX-Y.NYB`, `GC=F`, …   | same batch quote path, so no extra requests             |

**Deferred, with reasons.** Finnhub was the fallback plan, but its free tier is one symbol per
call — useless for a watchlist. FRED needs a key, so `ECO` shows tradeable macro proxies
instead of CPI and payrolls. SEC XBRL is authoritative but slow and only worth it if `DES`
grows real financial statements. Stooq remains a cheap backup for daily bars if Yahoo breaks.

**The constraint that shaped this:** 18 symbols every 15s is 72 requests/minute if the API
takes one symbol per call. Yahoo's batch endpoint plus a 15s cache plus one poll loop means
the app costs about **4 upstream requests a minute**.

**The stream is built, as an overlay rather than a provider.** Yahoo keeps the snapshot —
previous close, volume, sparkline history — and Finnhub supplies the price. A trade updates
`last`, `chg`, `pct` and `as_of` only; Yahoo's next poll restores the context and the live
price is re-applied on top, so a poll can never drag the price backwards. No key: no socket,
no change, `15M DELAY` in the top bar. With a key: `FINNHUB RT`.

### Refresh tiers (enforced server-side, not per panel)

| Tier         | Interval | Applies to                                  |
| ------------ | -------- | ------------------------------------------- |
| quote cache  | 15s      | shared by every panel and `/api/watch`      |
| watch poll   | 15s      | browser asks; usually lands on the cache    |
| candles      | 15m open / 6h closed | daily bars; 5m bars 10m open      |
| news         | 5m       | RSS fetch, dedupe, SQLite                   |
| description  | 24h      | `.info` per symbol                          |
| closed bars  | never    | immutable once the session ends             |

Because the feed is 15 minutes delayed, refreshing faster than 15s only re-fetches a number
that has not changed. 15s is the honest floor: the UI still feels live because *ticking UI*
and *fresh data* are different things.

Target budget: **≤ 20 req/min** steady state. The footer shows the age of the oldest quote in
the cache, so staleness is visible rather than assumed.

### Caching

- **Quotes** — in-memory `Map<sym, {quote, fetchedAt}>` with single-flight (concurrent callers
  share one upstream request). Never poll from the browser; the browser asks the proxy.
- **Candles** — SQLite, keyed `(sym, interval, bucket_start)`, upsert on read. Closed bars are
  immutable, so backfill once and never refetch. This is what makes charts instant.
- **News / macro / fundamentals** — SQLite with `fetched_at`; serve stale-while-revalidate.
- **Layout / watchlist** — `localStorage` only. They are UI state; syncing devices is a
  feature, not a requirement.

### Symbols

Never pass raw strings around. `canonicalise()` returns `{ sym, exch }`; adapters own the
mapping (`BRK.B` → Yahoo `BRK-B`, `VOD.L` unchanged). Keep an `aliases` table for ticker
changes (FB→META); one row per rename, no cleverness.

### Failure model

One shape, used by every panel:

```ts
type PanelData<T> = {
  data: T | null;
  asOf: number | null;
  state: 'loading' | 'ok' | 'stale' | 'error';
  error?: string;
};
```

`PanelFrame` renders a dot: green ok, amber when `now - asOf > 2× interval`, red on error.
**Keep the last good data forever**; never blank a panel because a refresh failed. Add a
provider circuit breaker (3 consecutive failures → open 60s) and per-provider exponential
backoff with jitter.

---

## 5. Build order

Each phase ends in something you can look at. Estimates are evenings for one person.

| Phase | Deliverable                                                        | Exit criterion                          |
| ----- | ------------------------------------------------------------------ | --------------------------------------- |
| **P0** ✓ | FastAPI + Jinja shell, grid presets, command bar, mock provider, all six panels | type `AAPL GP`, see a panel, reload, layout persists |
| **P1** ✓ | `yfinance` quotes, quote cache + single-flight, real watchlist, status line | 18 symbols update for an hour inside quota |
| **P2** ✓ | candles endpoint + SQLite backfill + chart ranges                  | 1Y chart loads <300ms from cache        |
| **P3** ✓ | `N` news, dedupe, per-symbol feeds                                 | no duplicate headlines across sources   |
| **P4** ✓ | `DES` key stats + profile                                          | correct for 3 sectors + 1 ETF           |
| **P5** ~ | `ECO` as a cross-asset strip (FRED needs a key)                     | 8 instruments, real quotes              |
| **P6** | Playwright flows, per-panel staleness dots, alerts                 | all six functions via keyboard only     |

P0 is the vertical slice — do it in one sitting and resist adding panels until P1 is done.

---

## 6. What you didn't bring up

Ordered by *when it will hurt you*.

### 6.1 Will bite in week one

1. **Your quota sets the architecture, not your feature list.** A naive per-panel poller
   burns the free tier in minutes. Decide batching + refresh tiers before writing panel #2.
2. **"Real-time" is not really on the free menu.** Free quotes are delayed, unofficial, or
   quota-limited, and scraped endpoints break without notice. Every number needs an `asOf`, and a second provider
   should be a config flag, not a refactor.
3. **Symbols are not strings.** `BRK.B`/`BRK-B`, `.L`/`.TO`/`.DE`, ETFs, crypto, ADRs,
   renamed tickers. One `canonicalise()` used by *everything*.
4. **API keys cannot go in the browser.** Even on localhost — it is the habit that decides
   whether this can ever be hosted. The proxy is 30 lines.
5. **Charts need history you don't have yet.** Free intraday data is shallow. Backfill into
   SQLite once; also means charts work when the API is down.
6. **The market clock is a real module.** Pre/regular/post, half-days, holidays, DST, ET vs
   local, and the fact that after-hours prints make `% change` look wrong. One
   `marketState()` function, tested.

### 6.2 Will bite in month one

7. **Focus is the product.** A terminal is a keyboard state machine. If the active panel,
   the focus ring, and the typing-vs-shortcut boundary are mushy, no feature count saves it.
   Build `useKeys` with a scope stack early.
8. **Stale data that looks fresh is worse than an error.** Silent staleness destroys trust in
   the whole screen.
9. **You will build UI while rate-limited.** Record provider responses to fixtures and make
   `MOCK=1` the default in dev; otherwise every reload costs you a real API call and your
   tests are non-deterministic.
10. **Re-render storms.** Six panels ticking every 5s will feel janky if the whole tree
    re-renders. Subscribe per row (`useSyncExternalStore`) and memoise.
11. **News is the hardest "simple" panel.** RSS has no ticker tags, entity matching is fuzzy,
    sources duplicate each other, links rot. Store `headline + url + source + ts` only —
    never the article body (also a licensing matter).
12. **Movers need a universe.** "Top gainers" is meaningless without a fixed list, and index
    membership changes. Freeze a JSON list; refresh quarterly; label it.
13. **The maintenance tail.** Every panel is a feed that can break. Six is the cap for a
    reason; budget an hour a month for scraper repairs.

### 6.3 Product questions you haven't asked

14. **What is the actual job?** "Portfolio tracking" and "market browsing" produce different
    v1s. If you check your own positions daily, `PORT` belongs in v1 and `ECO` does not.
15. **You have no muscle memory.** Mnemonics are fast *after* you learn them. A fuzzy command
    palette with descriptions must sit alongside the command line, or the terminal feel is
    just friction for you, its only user.
16. **Alerts, sharing, mobile** are the three requests that always follow. Decide now:
    in-app alerts only (no email/push), copy-panel-as-image optional, no mobile layout.
17. **One screen vs one window.** A dedicated always-on-top window (Tauri) and a global
    hotkey change how often you actually use this far more than another panel would.

### 6.4 Legal / ethical

18. **Don't ship the Bloomberg name, logo, or trade dress.** "Terminal-inspired", your own
    palette and your own name. Personal project looks fine; a public clone with their marks
    does not.
19. **Free tiers are personal, non-commercial, non-redistributable.** Do not host a public
    instance with your key. Do not store or republish article text — headline + link only.
20. **No order entry, no P&L promises, no "advice".** A one-line disclaimer is free; a broker
    integration turns a display into a regulated, money-losing surface. Keep it out.

### 6.5 Explicit non-goals

Auth/multi-user · order entry/OMS · Level 2 book · options chains · fixed income/FX depth ·
chat · mobile app · real-time streaming at scale · drag-resize panes · plugin system ·
portfolio backtesting.

---

## 7. Decisions — settled

| Question            | Answer                                                      |
| ------------------- | ----------------------------------------------------------- |
| Job                 | General market browsing — no portfolio, no `PORT` panel     |
| Freshness           | 15-minute delayed data is fine; label it everywhere         |
| Hosting             | Local only; bind `127.0.0.1`, no auth, keys in `.env`       |
| Stack               | Python on the server; server-rendered panels, no build step |

What those answers removed from the plan: portfolio/P&L data model, authentication, user
accounts, deployment hardening, and the entire npm toolchain. What they did **not** remove:
the provider abstraction, the URL-as-state model, or the staleness contract — those are cheap
now and expensive to retrofit.

Remaining choice, deliberately deferred: whether `ECO` or `MOV` earns the fourth panel slot
alongside `WATCH` / `GP` / `N`. Build `DES` for P0, then decide from use.

P0–P3 are built: `.venv/bin/python run.py`, then open <http://127.0.0.1:8420>.

What is left, in the order it would actually matter:

1. **Per-panel staleness dots.** The footer shows the cache age globally; each panel should
   show its own state (ok / stale / error) in its header, per the failure model above.
2. **Search.** The command line only accepts the 18 known tickers. `AAPL` works; `brk.b`
   does not, and there is no way to discover a symbol you have not hardcoded.
3. **Alerts.** Price thresholds evaluated server-side against the quote cache; in-app only.
4. **Playwright flows.** Two tests: command replaces the active panel; reload restores layout.
5. **True macro.** A FRED key would let `ECO` show CPI and payrolls instead of proxies.

