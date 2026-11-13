# Better data, for free

What is actually available without paying, what each option costs you in complexity, and what
I would wire next. Limits change — everything below was checked in November 2026 and is cited.

## The short version

There is no free *consolidated-tape* real-time feed. The US exchanges charge for that and the
fees are passed on. What exists is a set of compromises:

| Provider | Free tier | Real-time? | Key? | Catch |
| --- | --- | --- | --- | --- |
| **Yahoo** (`yfinance`) | unlimited-ish, batch quotes | **15 min delayed** | no | unofficial, breaks silently, no SLA |
| **Alpaca** Basic | 200 REST/min, 30 websocket symbols, history since 2016 | **yes, via websocket — IEX only** | yes (free account) | IEX is a fraction of volume; historical bars are 15 min delayed |
| **Finnhub** | 60 REST/min, websocket up to 50 symbols | **yes, real-time US quotes** | yes | one symbol per REST call; personal/non-commercial |
| **Twelve Data** | 8 req/min, 800/day | delayed on free | yes | tight quota, small symbol coverage |
| **Polygon** | 5 req/min | end-of-day | yes | no intraday on free |
| **Stooq** | CSV download | EOD | no | now behind a JavaScript proof-of-work wall — unusable server-side |
| **SEC EDGAR** | 10 req/s, full XBRL | n/a (filings) | no | 10 req/s, needs a real User-Agent |
| **FRED** | generous | n/a (macro) | yes | key required; CSV endpoint timed out from here |
| **CoinGecko** | 30 req/min | crypto | no | crypto only |

Sources: [Alpaca market data docs](https://docs.alpaca.markets/docs/about-market-data-api)
(plan table) and [Alpaca data page](https://alpaca.markets/data);
[Finnhub free-tier breakdown](https://aifinhub.io/articles/finnhub-free-tier/);
Polygon and Twelve Data pricing pages; Stooq tested directly (blocked);
SEC and FRED limits are from their published API docs.

## What "better" means here — three different axes

1. **Latency.** Yahoo gives a 15-minute-delayed snapshot. A websocket from Alpaca or Finnhub
   removes the delay *and* the polling. This is the axis you feel.
2. **Accuracy.** IEX-only prices are the real trade price on one venue, not the consolidated
   last sale. For a watchlist that is usually fine; for a chart that must match everyone
   else's it is not. Finnhub's free quotes are closer to consolidated.
3. **Depth.** Fundamentals, filings, macro. Yahoo's `.info` is thin and occasionally wrong;
   SEC XBRL is authoritative and free but slow to parse.

They trade off against each other, so pick per panel rather than per app.

## Recommendation, in order

**1. A websocket stream for the watchlist — done, with Finnhub.**
`app/data/stream.py` holds one socket, subscribes to the watchlist, and pushes trades into the
shared quote cache. It is an **overlay**, not a provider: Yahoo still supplies previous close,
volume, sparkline history, descriptions and news, because a trade feed carries none of those.
A live price is re-applied after every poll so a delayed snapshot can never overwrite it.

Two things this design avoids: losing the sparklines (Finnhub's free REST quote has no
history) and hitting the 60/min REST allowance (the socket has its own 50-symbol limit).

What is still true: without a key the app is unchanged; the top bar says `YAHOO · 15M DELAY`,
and with a key it says `YAHOO · FINNHUB RT`.

**2. Keep Yahoo for everything else.**
History, descriptions, and breadth stay on Yahoo. It is free, it batches, and it is already
cached. A stream is for the 20 symbols you watch; it is not a replacement for 2 years of bars.

**3. Fill the two thin spots with authoritative sources.**
`DES` should eventually read SEC XBRL company facts (free, exact, 10 req/s) instead of
`yfinance.info`. `ECO` needs a FRED key before it can show CPI and payrolls — until then the
cross-asset strip is the honest substitute.

**4. Do not bother with Stooq or the EOD-only tiers.**
Stooq now challenges non-browser clients, and an end-of-day feed is strictly worse than the
Yahoo data already cached.

## What I would not do

- **Scrape the exchanges' own sites.** Terms-of-service problem, breaks constantly.
- **Aggregate five free tiers behind one interface.** The failure modes multiply faster than
  the coverage improves; two providers is already one more than most hobby apps can keep
  honest.
- **Claim "real-time" on a delayed feed.** The label is the product.

## If you want it, the exact change

`app/data/__init__.py` gains an optional capability:

```python
class Streamer(Protocol):
    def stream(self, syms: list[str], on_tick: Callable[[Quote], None]) -> None: ...
```

`app/data/finnhub.py` implements it with one websocket thread and writes into
`data/quotes.py`'s cache. `main.py` shows the provider's `mode` (`poll` or `stream`) in the
top bar. Everything else — panels, templates, the command line — stays exactly as it is.

The only thing that cannot be decided without your input is the key: Finnhub and Alpaca both
need a free account. Say which and I will wire it.
