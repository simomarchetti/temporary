"""London Eye price monitor — scrape today..today+DAYS and append to CSV.

Usage:
    python main.py                      # headless, default 7-day horizon
    python main.py --days 1 --headed    # smoke test, visible browser
    python main.py --ticket-types "Standard Ticket" "Fast Track"
"""
import argparse
import traceback
from datetime import date, timedelta
from pathlib import Path

from eye_scraper import config
from eye_scraper.api_scrape import scrape_api
from eye_scraper.booking import scrape_ticket_type
from eye_scraper.models import run_stamp
from eye_scraper.storage import append_records, render_table

UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/126.0 Safari/537.36")


def horizon(days: int) -> list[date]:
    today = date.today()
    return [today + timedelta(days=i) for i in range(days + 1)]


def run_api(days, ticket_types, output) -> int:
    """Browserless engine: scrape all ticket types over the horizon via the API."""
    dates = horizon(days)
    records = scrape_api(ticket_types, dates)
    if records:
        append_records(output, records)
    # print grouped by (date, ticket type)
    by_key = {}
    for r in records:
        by_key.setdefault((r.target_date, r.ticket_type), []).append(r)
    for (d, tt), recs in sorted(by_key.items()):
        print(f"\n{d} / {tt}: {len(recs)} slots")
        print(render_table(recs))
    return len(records)


def main():
    ap = argparse.ArgumentParser(description="London Eye price monitor")
    ap.add_argument("--days", type=int, default=config.DAYS)
    ap.add_argument("--ticket-types", nargs="+", default=config.TICKET_TYPES)
    ap.add_argument("--output", default=config.OUTPUT_CSV)
    ap.add_argument("--timestamped", action="store_true",
                    help="Write a fresh per-run file data/london_eye_prices_<UTC>.csv "
                         "instead of appending to the default CSV.")
    ap.add_argument("--headed", action="store_true")
    ap.add_argument("--engine", choices=["browser", "api"], default="browser",
                    help="browser = Playwright (default); api = browserless accesso API.")
    args = ap.parse_args()

    output = args.output
    if args.timestamped:
        output = f"data/london_eye_prices_{run_stamp()}.csv"

    Path(config.SCREENSHOT_DIR).mkdir(parents=True, exist_ok=True)

    if args.engine == "api":
        total = run_api(args.days, args.ticket_types, output)
        print(f"\nDone. {total} records written to {output}")
        return

    # Browser engine only: import Playwright lazily so --engine api needs no browser.
    from playwright.sync_api import sync_playwright

    total = 0
    with sync_playwright() as p:
        # --no-sandbox / dev-shm flags keep Chromium working in containers (cloud runners);
        # ignore_https_errors survives a TLS-intercepting proxy.
        browser = p.chromium.launch(headless=not args.headed,
                                    args=["--no-sandbox", "--disable-dev-shm-usage"])
        ctx = browser.new_context(user_agent=UA, locale="en-GB",
                                  viewport={"width": 1366, "height": 900},
                                  ignore_https_errors=True)
        for d in horizon(args.days):
            for ticket_type in args.ticket_types:
                label = f"{d.isoformat()} / {ticket_type}"
                try:
                    recs = scrape_ticket_type(ctx, d, ticket_type, config.PARTY_LABEL)
                    append_records(output, recs)
                    total += len(recs)
                    print(f"\n{label}: {len(recs)} slots")
                    print(render_table(recs))
                except Exception:
                    safe = ticket_type.replace(" ", "_")
                    shot = f"{config.SCREENSHOT_DIR}/fail_{d.isoformat()}_{safe}.png"
                    print(f"\n!! {label}: FAILED — debug screenshot: {shot}")
                    traceback.print_exc()
        ctx.close()
        browser.close()
    print(f"\nDone. {total} records written to {output}")


if __name__ == "__main__":
    main()
