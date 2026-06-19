# London Eye Price Monitor — Design

**Date:** 2026-06-19
**Status:** Approved

## Goal

A standalone Python script that, on each run, walks the London Eye online booking
flow for **today through today + 7 days** (8 dates), reads **all time-slot prices**
for the **Standard Ticket / 1 Adult**, prints them to the console, and **appends**
them to a CSV with a scrape timestamp so price movements can be tracked over time.

Built so that adding **Fast Track** and **Flexi Fast Track** later is a one-line
config change.

Source flow (from user screenshots):
`https://www.londoneye.com/tickets-and-prices/` → Standard Ticket → "Book Online
and Save" / Daily Tickets → *Buy Now* (Standard) → set 1 Adult → *Next* →
time-slot grid with per-slot prices.

## Decisions (from brainstorming)

- **Scope:** scheduled monitor (reusable, appends over time). Scheduling wired up
  later — for now, a solid standalone script.
- **Output:** print to console **and** append to CSV.
- **Ticket types:** start with **Standard** only; extend to Fast Track / Flexi
  Fast Track once Standard works.
- **Date horizon:** rolling, today through today + 7 days (8 dates per run).

## Approach

- **Python 3 + Playwright (sync API), headless Chromium.** Drives the real
  JavaScript SPA exactly like the manual flow: select date → *Buy Now* on the
  ticket card → set Adult = 1 → *Next* → read the time-slot grid.
- **Primary extraction:** read the rendered DOM tiles (each tile = time range +
  £ price + sold-out state).
- **Secondary (no commitment):** log any pricing JSON API endpoint observed in the
  network tab. If it proves clean, it gives a faster lightweight (`httpx`) path
  later. Not built now.
- Handle the cookie-consent banner; use a realistic user-agent. Structured so
  `playwright-stealth` can be dropped in if anti-bot blocks us.

### Rejected alternative

- **Pure HTTP / API reverse-engineering up front** — rejected because discovering
  the endpoint requires running a browser anyway, and it is more fragile against
  anti-bot. We capture the endpoint opportunistically instead.

## Flow control

- One browser/context reused across all dates (fast); a fresh page per date for
  clean state.
- For each `(date, ticket_type)`: navigate to the booking entry → pick date →
  *Buy Now* on the card whose title matches the ticket label → set Adult to 1 →
  *Next* → scrape every slot tile.
- A ticket type is just a card-title string. Config starts as
  `["Standard Ticket"]`; later `["Standard Ticket", "Fast Track", "Flexi Fast Track"]`.
  The per-type flow function is identical.

## Output

### CSV (append mode), e.g. `data/london_eye_prices.csv`

| Column          | Example                | Notes                                    |
|-----------------|------------------------|------------------------------------------|
| scraped_at_utc  | 2026-06-19T15:20:01Z   | UTC timestamp of the scrape run          |
| target_date     | 2026-06-19             | The date being priced                    |
| ticket_type     | Standard Ticket        | Card title                               |
| party           | 1 adult                | Party composition                        |
| slot_start      | 15:00                  | 24h local time                           |
| slot_end        | 15:30                  | 24h local time                           |
| price_gbp       | 37.00                  | Numeric; empty if sold out               |
| sold_out        | false                  | Boolean                                  |

- The CSV grows over time (one file). Header written once on creation.
- Console prints a per-date table on each run.

## Project structure

```
eye_scraper/
  models.py     # PriceRecord dataclass + price/time parsing helpers (pure, testable)
  booking.py    # Playwright flow: navigate, select date/ticket/party, extract slots
  storage.py    # CSV append + console table rendering
  config.py     # horizon days, ticket types, URLs, timeouts, output path
main.py         # orchestrates the date horizon, owns the browser lifecycle
requirements.txt
README.md
data/           # CSV output (gitignored)
```

CLI (argparse) on `main.py`: `--days` (default 7), `--ticket-types`, `--headed`,
`--output`.

## Error handling

The monitor must survive partial failures:

- Each `(date, ticket_type)` iteration wrapped in try/except → log the error, save
  a debug screenshot, continue to the next. One failure never kills the run.
- Retry with backoff on navigation timeouts.
- Sold-out / no-availability dates recorded explicitly (rows with `sold_out=true`
  or a clear no-slots marker) rather than silently skipped.

## Testing

- **Unit tests** for the pure logic in `models.py`: price-string `"£37.00" → 37.00`,
  time-slot parsing (`"3:00 PM - 3:30 PM" → ("15:00", "15:30")`), and the CSV
  append behaviour in `storage.py`, using saved HTML fixtures of the slot grid.
- **Manual smoke run**: `python main.py --days 1 --headed` for the live
  end-to-end flow (network-dependent; not in CI).

## Known unknown (resolved in step 1 of implementation)

The exact booking-entry URL and the live DOM selectors are not yet known — the
booking page is JS-rendered, so static fetching can't see them. **The first
implementation step is an exploratory live trace**: run a headed browser, capture
the real booking URL, the network calls, and the selectors for date picker /
ticket card / adult stepper / Next button / slot tiles. Build the real flow
against what that trace finds, and save a slot-grid HTML fixture for the unit tests.
