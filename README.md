# London Eye Price Monitor

Scrapes London Eye ticket prices from the official accesso booking widget for a
rolling horizon (today through today + 7 days), prints them, and **appends** them
to `data/london_eye_prices.csv` with a UTC scrape timestamp so price movements can
be tracked over time.

Party is fixed at **1 adult**. Ticket types scraped by default:

- **Standard Ticket** — per-30-minute time-slot prices
- **Fast Track** — per-30-minute time-slot prices
- **Flexi Fast Track** — flexible-entry pass; single price per date (`slot=any`)

## Setup

    pip install -r requirements.txt
    playwright install chromium

## Run

    python main.py                          # headless, 7-day horizon, all 3 ticket types
    python main.py --days 1 --headed        # smoke test, visible browser, today + tomorrow
    python main.py --ticket-types "Standard Ticket"     # one type only
    python main.py --output data/eye.csv    # custom CSV path

Each `(date, ticket type)` is independent: if one fails it logs, saves a debug
screenshot to `data/debug/`, and the run continues.

## Output

`data/london_eye_prices.csv` (append-only, header written once):

| column | example |
|--------|---------|
| scraped_at_utc | 2026-06-19T15:04:25Z |
| target_date | 2026-06-19 |
| ticket_type | Standard Ticket |
| party | 1 adult |
| slot_start | 15:30  *(or `any` for Flexi)* |
| slot_end | 16:00  *(or `any` for Flexi)* |
| price_gbp | 39.0  *(empty if sold out)* |
| sold_out | false |

## Scheduling

Currently a standalone script (run it whenever). To make it a real monitor, wrap
it in cron/launchd, e.g. daily:

    0 9 * * *  cd /path/to/eye-scraper && /usr/bin/python3 main.py >> data/run.log 2>&1

## How it works / extending

See `docs/superpowers/specs/TRACE_FINDINGS.md` for the full booking-flow trace
(platform = accesso, selectors, the two pricing models, anti-bot notes). To add or
adjust a ticket type, edit `eye_scraper/config.py` → `TICKETS`.

## Project layout

    eye_scraper/
      models.py    # PriceRecord + price/time parsing (pure, unit-tested)
      storage.py   # CSV append + console table (unit-tested)
      booking.py   # Playwright flow: navigate, select, extract (slots + single)
      config.py    # horizon, ticket entries, selectors, timeouts, output path
    main.py        # CLI orchestrator over the date horizon
    scripts/       # throwaway exploration helpers used to trace the site
    tests/         # pytest unit tests + tests/fixtures/slot_grid.html

## Tests

    python -m pytest -q
