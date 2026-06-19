# London Eye Price Monitor Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** A standalone Python + Playwright script that scrapes London Eye Standard Ticket / 1-Adult time-slot prices for today through today+7 days, prints them, and appends them to a CSV with a scrape timestamp.

**Architecture:** Headless Chromium drives the JS booking SPA (date → Buy Now → 1 Adult → Next → slot grid). Pure logic (price/time parsing, CSV) is isolated in `models.py`/`storage.py` and unit-tested offline against a saved HTML fixture; the live browser flow in `booking.py` is verified by a manual smoke run. `main.py` owns the browser lifecycle and the date-horizon loop.

**Tech Stack:** Python 3.11+, Playwright (sync API, Chromium), pytest, stdlib `csv`/`dataclasses`/`argparse`.

## Global Constraints

- **No git.** This project is not a git repository and must not become one. Every task ends with a **Checkpoint** (run tests / verify output), never a commit. No `git` commands anywhere.
- **Python 3.11+** (uses `X | None` type syntax).
- **Playwright sync API** only (no asyncio).
- **Ticket types are config-driven.** Ship with `["Standard Ticket"]`; the flow must work unchanged when `"Fast Track"` / `"Flexi Fast Track"` are added to the list.
- **Date horizon:** today through today + `DAYS` (default 7) → 8 dates per run.
- **Party:** fixed at 1 adult.
- **CSV is append-only**, header written once, columns exactly: `scraped_at_utc, target_date, ticket_type, party, slot_start, slot_end, price_gbp, sold_out`.
- **Times stored 24h `HH:MM`; timestamps UTC ISO `YYYY-MM-DDTHH:MM:SSZ`; prices numeric GBP (no `£`).**
- The monitor must survive partial failures: one bad `(date, ticket_type)` iteration logs + screenshots + continues.

---

### Task 1: Project scaffold and dependencies

**Files:**
- Create: `requirements.txt`
- Create: `eye_scraper/__init__.py` (empty)
- Create: `eye_scraper/config.py`
- Create: `tests/__init__.py` (empty)
- Create: `tests/fixtures/.gitkeep` (empty placeholder — fixtures land here in Task 4)
- Create: `README.md`

**Interfaces:**
- Consumes: nothing.
- Produces: `eye_scraper/config.py` exposing module-level constants — `BOOKING_URL: str`, `DAYS: int = 7`, `TICKET_TYPES: list[str]`, `PARTY_LABEL: str = "1 adult"`, `OUTPUT_CSV: str = "data/london_eye_prices.csv"`, `NAV_TIMEOUT_MS: int = 30000`, `SCREENSHOT_DIR: str = "data/debug"`, and a `SELECTORS: dict[str, str]` placeholder dict (filled in Task 4).

- [ ] **Step 1: Write `requirements.txt`**

```
playwright>=1.44
pytest>=8.0
```

- [ ] **Step 2: Create the package and test directories**

Create empty `eye_scraper/__init__.py`, `tests/__init__.py`, and `tests/fixtures/.gitkeep`.

- [ ] **Step 3: Write `eye_scraper/config.py`**

```python
"""Configuration constants for the London Eye price monitor."""

# Booking entry URL — CONFIRMED/UPDATED in Task 4 from the live trace.
# Start with the marketing page; Task 4 replaces this with the real booking SPA URL.
BOOKING_URL = "https://www.londoneye.com/tickets-and-prices/"

# Rolling horizon: today .. today + DAYS (inclusive) => DAYS + 1 dates.
DAYS = 7

# Ship with Standard only; add "Fast Track" / "Flexi Fast Track" once proven.
TICKET_TYPES = ["Standard Ticket"]

PARTY_LABEL = "1 adult"

OUTPUT_CSV = "data/london_eye_prices.csv"
SCREENSHOT_DIR = "data/debug"

NAV_TIMEOUT_MS = 30000

# DOM selectors — POPULATED in Task 4 from the live trace. Keys are stable;
# values are placeholders until then.
SELECTORS = {
    "cookie_accept": "",      # cookie-consent accept button
    "calendar_day": "",       # a selectable day cell, formatted with {day}
    "calendar_next_month": "",
    "ticket_card": "",        # a ticket card, located by its title text
    "buy_now": "",            # Buy Now button within a ticket card
    "adult_plus": "",         # the "+" stepper for the Adult row
    "adult_qty": "",          # the Adult quantity input/display
    "next_button": "",        # Next button on the quantity page
    "slot_tile": "",          # one time-slot tile in the grid
    "slot_time": "",          # time-range text within a tile
    "slot_price": "",         # price text within a tile
}
```

- [ ] **Step 4: Write a minimal `README.md`**

```markdown
# London Eye Price Monitor

Scrapes London Eye Standard Ticket (1 adult) time-slot prices for today..today+7
and appends them to `data/london_eye_prices.csv`.

## Setup
    pip install -r requirements.txt
    playwright install chromium

## Run
    python main.py                 # headless, default 7-day horizon
    python main.py --days 1 --headed   # smoke test, visible browser

See `docs/superpowers/specs/2026-06-19-london-eye-price-monitor-design.md`.
```

- [ ] **Step 5: Install and verify**

Run:
```bash
pip install -r requirements.txt && playwright install chromium && python -c "import eye_scraper.config as c; print(c.DAYS, c.TICKET_TYPES, c.OUTPUT_CSV)"
```
Expected: prints `7 ['Standard Ticket'] data/london_eye_prices.csv` with no import error.

- [ ] **Step 6: Checkpoint**

Confirm `playwright install chromium` finished and the import line printed the expected values. No git.

---

### Task 2: `models.py` — record type and pure parsers

**Files:**
- Create: `eye_scraper/models.py`
- Test: `tests/test_models.py`

**Interfaces:**
- Consumes: nothing.
- Produces:
  - `PriceRecord` dataclass with fields `scraped_at_utc: str, target_date: str, ticket_type: str, party: str, slot_start: str, slot_end: str, price_gbp: float | None, sold_out: bool`.
  - `parse_price(text: str) -> float | None` — `"£37.00" -> 37.0`; no match -> `None`.
  - `parse_time_slot(text: str) -> tuple[str, str]` — `"3:00 PM - 3:30 PM" -> ("15:00", "15:30")`; raises `ValueError` if not two times.
  - `utc_now_iso() -> str` — current UTC as `YYYY-MM-DDTHH:MM:SSZ`.

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_models.py
import pytest
from eye_scraper.models import PriceRecord, parse_price, parse_time_slot, utc_now_iso


def test_parse_price_basic():
    assert parse_price("£37.00") == 37.0

def test_parse_price_with_thousands_and_spaces():
    assert parse_price("Online from £1,234.50") == 1234.5

def test_parse_price_no_price_returns_none():
    assert parse_price("Sold out") is None
    assert parse_price("") is None

def test_parse_time_slot_pm():
    assert parse_time_slot("3:00 PM - 3:30 PM") == ("15:00", "15:30")

def test_parse_time_slot_am_and_endash():
    assert parse_time_slot("10:30 AM – 11:00 AM") == ("10:30", "11:00")

def test_parse_time_slot_bad_input_raises():
    with pytest.raises(ValueError):
        parse_time_slot("whenever")

def test_utc_now_iso_format():
    s = utc_now_iso()
    assert s.endswith("Z") and "T" in s and len(s) == 20

def test_price_record_fields():
    r = PriceRecord("2026-06-19T15:00:00Z", "2026-06-19", "Standard Ticket",
                    "1 adult", "15:00", "15:30", 37.0, False)
    assert r.price_gbp == 37.0 and r.sold_out is False
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_models.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'eye_scraper.models'`.

- [ ] **Step 3: Write `eye_scraper/models.py`**

```python
"""Record type and pure parsing helpers (no I/O, no browser)."""
from dataclasses import dataclass
from datetime import datetime, timezone
import re


@dataclass
class PriceRecord:
    scraped_at_utc: str
    target_date: str       # YYYY-MM-DD
    ticket_type: str
    party: str
    slot_start: str        # HH:MM (24h)
    slot_end: str          # HH:MM (24h)
    price_gbp: float | None
    sold_out: bool


_PRICE_RE = re.compile(r"£\s*([\d,]+(?:\.\d{1,2})?)")
_SPLIT_RE = re.compile(r"\s*[-–—]\s*")


def parse_price(text: str) -> float | None:
    """Extract a GBP amount from text; return None if there is no price."""
    if not text:
        return None
    m = _PRICE_RE.search(text)
    if not m:
        return None
    return float(m.group(1).replace(",", ""))


def _to_24h(token: str) -> str:
    cleaned = token.strip().upper().replace(".", "")
    return datetime.strptime(cleaned, "%I:%M %p").strftime("%H:%M")


def parse_time_slot(text: str) -> tuple[str, str]:
    """'3:00 PM - 3:30 PM' -> ('15:00', '15:30')."""
    parts = _SPLIT_RE.split(text.strip())
    if len(parts) != 2:
        raise ValueError(f"Cannot parse time slot: {text!r}")
    return _to_24h(parts[0]), _to_24h(parts[1])


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_models.py -v`
Expected: all 8 tests PASS.

- [ ] **Step 5: Checkpoint**

All `tests/test_models.py` green. No git.

---

### Task 3: `storage.py` — CSV append and console table

**Files:**
- Create: `eye_scraper/storage.py`
- Test: `tests/test_storage.py`

**Interfaces:**
- Consumes: `PriceRecord` from Task 2.
- Produces:
  - `FIELDNAMES: list[str]` — the CSV column order (matches Global Constraints).
  - `append_records(path: str, records: list[PriceRecord]) -> None` — creates parent dirs, writes header only when the file is new, appends one row per record. `price_gbp` written as empty string when `None`; `sold_out` written as `true`/`false`.
  - `render_table(records: list[PriceRecord]) -> str` — a plain-text table for one date's slots.

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_storage.py
import csv
from eye_scraper.models import PriceRecord
from eye_scraper.storage import FIELDNAMES, append_records, render_table


def _rec(slot_start="15:00", slot_end="15:30", price=37.0, sold_out=False):
    return PriceRecord("2026-06-19T15:00:00Z", "2026-06-19", "Standard Ticket",
                       "1 adult", slot_start, slot_end, price, sold_out)


def test_append_creates_file_with_header(tmp_path):
    path = tmp_path / "sub" / "prices.csv"
    append_records(str(path), [_rec()])
    rows = list(csv.DictReader(path.open()))
    assert list(rows[0].keys()) == FIELDNAMES
    assert rows[0]["price_gbp"] == "37.0"
    assert rows[0]["sold_out"] == "false"
    assert rows[0]["slot_start"] == "15:00"


def test_append_is_additive_without_duplicate_header(tmp_path):
    path = tmp_path / "prices.csv"
    append_records(str(path), [_rec()])
    append_records(str(path), [_rec(slot_start="15:30", slot_end="16:00")])
    lines = path.read_text().strip().splitlines()
    assert len(lines) == 3                 # 1 header + 2 data rows
    assert lines[0].startswith("scraped_at_utc")


def test_sold_out_record_has_empty_price(tmp_path):
    path = tmp_path / "prices.csv"
    append_records(str(path), [_rec(price=None, sold_out=True)])
    rows = list(csv.DictReader(path.open()))
    assert rows[0]["price_gbp"] == ""
    assert rows[0]["sold_out"] == "true"


def test_render_table_contains_values():
    out = render_table([_rec()])
    assert "15:00" in out and "37.0" in out
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_storage.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'eye_scraper.storage'`.

- [ ] **Step 3: Write `eye_scraper/storage.py`**

```python
"""CSV append + console rendering for price records."""
import csv
from pathlib import Path

from .models import PriceRecord

FIELDNAMES = [
    "scraped_at_utc", "target_date", "ticket_type", "party",
    "slot_start", "slot_end", "price_gbp", "sold_out",
]


def _row(r: PriceRecord) -> dict:
    return {
        "scraped_at_utc": r.scraped_at_utc,
        "target_date": r.target_date,
        "ticket_type": r.ticket_type,
        "party": r.party,
        "slot_start": r.slot_start,
        "slot_end": r.slot_end,
        "price_gbp": "" if r.price_gbp is None else r.price_gbp,
        "sold_out": "true" if r.sold_out else "false",
    }


def append_records(path: str, records: list[PriceRecord]) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    is_new = not p.exists()
    with p.open("a", newline="") as f:
        w = csv.DictWriter(f, fieldnames=FIELDNAMES)
        if is_new:
            w.writeheader()
        for r in records:
            w.writerow(_row(r))


def render_table(records: list[PriceRecord]) -> str:
    if not records:
        return "  (no slots)"
    lines = []
    for r in records:
        price = "SOLD OUT" if r.sold_out or r.price_gbp is None else f"£{r.price_gbp:.2f}"
        lines.append(f"  {r.slot_start}-{r.slot_end}  {price}")
    return "\n".join(lines)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_storage.py -v`
Expected: all 4 tests PASS.

- [ ] **Step 5: Checkpoint**

`tests/test_storage.py` green. No git.

---

### Task 4: Live trace — discover booking URL, selectors, and capture a fixture

This is an **exploratory** task (no TDD). Its deliverables unblock Tasks 5–7.

**Files:**
- Create: `scripts/trace_flow.py` (throwaway helper to drive the live site headed)
- Create: `tests/fixtures/slot_grid.html` (saved HTML of the time-slot grid)
- Create: `docs/superpowers/specs/TRACE_FINDINGS.md`
- Modify: `eye_scraper/config.py` (set real `BOOKING_URL` and fill `SELECTORS`)

**Interfaces:**
- Consumes: `eye_scraper/config.py` from Task 1.
- Produces: a populated `SELECTORS` dict, a real `BOOKING_URL`, and `tests/fixtures/slot_grid.html` (the exact DOM Task 5 parses).

- [ ] **Step 1: Write `scripts/trace_flow.py`**

```python
"""Headed walkthrough to discover the booking flow. Run manually, watch console.
   Logs every network response URL so the pricing endpoint can be spotted."""
from playwright.sync_api import sync_playwright

START = "https://www.londoneye.com/tickets-and-prices/"

with sync_playwright() as p:
    browser = p.chromium.launch(headless=False, slow_mo=300)
    page = browser.new_page()
    page.on("response", lambda r: print("NET", r.status, r.url))
    page.goto(START, wait_until="domcontentloaded")
    print("\n>>> Manually click: Standard Ticket -> Book/Buy Now -> set 1 Adult"
          " -> Next, until the time-slot grid is visible. Then press Enter here.\n")
    input()
    # Once the slot grid is on screen, dump the page so we can pick selectors.
    page.screenshot(path="data/debug/trace_slots.png", full_page=True)
    print("BOOKING URL NOW:", page.url)
    print(page.content()[:200])
    open("tests/fixtures/slot_grid.html", "w").write(page.content())
    print("\nSaved tests/fixtures/slot_grid.html and data/debug/trace_slots.png")
    input("Press Enter to close browser...")
    browser.close()
```

- [ ] **Step 2: Run the trace and record findings**

Run: `mkdir -p data/debug tests/fixtures && python scripts/trace_flow.py`
Then manually walk the flow (Standard Ticket → Buy Now → 1 Adult → Next → slot grid) and press Enter.
Expected: `tests/fixtures/slot_grid.html` written; console prints the booking URL and the `NET` lines.

- [ ] **Step 3: Inspect the saved HTML and identify selectors**

Open `tests/fixtures/slot_grid.html` and `data/debug/trace_slots.png`. For each `SELECTORS` key, find a stable selector (prefer `get_by_text` / `get_by_role` semantics, then stable `data-*`/class). Note from the console `NET` log any JSON endpoint whose response contained the slot prices.

- [ ] **Step 4: Write `docs/superpowers/specs/TRACE_FINDINGS.md`**

Record verbatim: the real booking-entry URL (the URL that lands on the date+ticket page, if reachable directly), the chosen selector string for every `SELECTORS` key, how a sold-out slot renders (greyed tile? "Sold out" text? missing price?), and any pricing JSON endpoint URL + a one-line note on its response shape.

- [ ] **Step 5: Update `eye_scraper/config.py`**

Set `BOOKING_URL` to the deepest reliably-reachable entry URL, and replace every empty string in `SELECTORS` with the real selector found in Step 3. For `calendar_day`, use a `{day}` placeholder (e.g. `'[role=gridcell]:has-text("{day}")'`) so the flow can format in the day number.

- [ ] **Step 6: Checkpoint**

Confirm `tests/fixtures/slot_grid.html` exists and is non-trivial (`wc -c tests/fixtures/slot_grid.html` > 1000), `TRACE_FINDINGS.md` documents every selector, and `config.SELECTORS` has no empty values. No git.

---

### Task 5: `booking.py` — slot extraction (tested against the fixture)

**Files:**
- Create: `eye_scraper/booking.py` (extraction function only in this task)
- Test: `tests/test_extract.py`

**Interfaces:**
- Consumes: `PriceRecord` (Task 2), `parse_price`/`parse_time_slot`/`utc_now_iso` (Task 2), `SELECTORS` (Task 4), and `tests/fixtures/slot_grid.html` (Task 4).
- Produces: `extract_slots(page, *, scraped_at: str, target_date: str, ticket_type: str, party: str) -> list[PriceRecord]` — reads every slot tile on the given Playwright page and returns one `PriceRecord` per tile. A tile with no price → `sold_out=True, price_gbp=None`.

- [ ] **Step 1: Write the failing test (loads the fixture into a real page via `set_content`)**

> Adjust the two asserted numbers only if the captured fixture differs from the screenshots; the structure of the test does not change.

```python
# tests/test_extract.py
from pathlib import Path
import pytest
from playwright.sync_api import sync_playwright
from eye_scraper.booking import extract_slots

FIXTURE = Path("tests/fixtures/slot_grid.html").read_text()


@pytest.fixture(scope="module")
def page():
    with sync_playwright() as p:
        browser = p.chromium.launch()
        pg = browser.new_page()
        pg.set_content(FIXTURE)
        yield pg
        browser.close()


def test_extract_returns_records(page):
    recs = extract_slots(page, scraped_at="2026-06-19T15:00:00Z",
                         target_date="2026-06-19", ticket_type="Standard Ticket",
                         party="1 adult")
    assert len(recs) >= 1
    first = recs[0]
    assert first.target_date == "2026-06-19"
    assert first.ticket_type == "Standard Ticket"
    assert first.slot_start.count(":") == 1            # HH:MM
    # every record is either priced or explicitly sold out
    for r in recs:
        assert (r.price_gbp is not None) ^ r.sold_out
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `pytest tests/test_extract.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'eye_scraper.booking'`.

- [ ] **Step 3: Implement `extract_slots` in `eye_scraper/booking.py`**

> Selector strings come from `config.SELECTORS` (Task 4). The loop logic below does not change regardless of the exact selectors.

```python
"""Playwright booking flow + slot extraction for the London Eye monitor."""
from .config import SELECTORS
from .models import PriceRecord, parse_price, parse_time_slot


def extract_slots(page, *, scraped_at, target_date, ticket_type, party):
    """Read every time-slot tile currently rendered on `page`."""
    tiles = page.locator(SELECTORS["slot_tile"])
    records = []
    for i in range(tiles.count()):
        tile = tiles.nth(i)
        time_text = tile.locator(SELECTORS["slot_time"]).inner_text().strip()
        price_loc = tile.locator(SELECTORS["slot_price"])
        price_text = price_loc.inner_text().strip() if price_loc.count() else ""
        try:
            start, end = parse_time_slot(time_text)
        except ValueError:
            continue  # not a slot tile
        price = parse_price(price_text)
        records.append(PriceRecord(
            scraped_at_utc=scraped_at, target_date=target_date,
            ticket_type=ticket_type, party=party,
            slot_start=start, slot_end=end,
            price_gbp=price, sold_out=price is None,
        ))
    return records
```

- [ ] **Step 4: Run the test to verify it passes**

Run: `pytest tests/test_extract.py -v`
Expected: PASS. If a selector mismatch makes `tiles.count()` 0, fix the selector in `config.SELECTORS` (Task 4) against the fixture, then rerun.

- [ ] **Step 5: Checkpoint**

`tests/test_extract.py` green against the real captured fixture. No git.

---

### Task 6: `booking.py` — drive the live flow for one date + ticket type

**Files:**
- Modify: `eye_scraper/booking.py` (add navigation functions)

**Interfaces:**
- Consumes: `SELECTORS`, `BOOKING_URL`, `NAV_TIMEOUT_MS` (config); `extract_slots`, `utc_now_iso`.
- Produces:
  - `accept_cookies(page) -> None` — clicks the consent button if present (no-op otherwise).
  - `scrape_ticket_type(context, target_date: "datetime.date", ticket_type: str, party: str) -> list[PriceRecord]` — opens a fresh page, runs the full flow (cookies → select date → Buy Now on the matching card → set Adult to 1 → Next → `extract_slots`) and returns the records. Closes its page before returning.

- [ ] **Step 1: Add the navigation code to `eye_scraper/booking.py`**

> The exact click targets use `config.SELECTORS` from Task 4. Steps below describe the canonical flow from the screenshots; adjust only the selector values, not the sequence.

```python
from .config import BOOKING_URL, NAV_TIMEOUT_MS
from .models import utc_now_iso


def accept_cookies(page) -> None:
    sel = SELECTORS["cookie_accept"]
    btn = page.locator(sel)
    if sel and btn.count():
        try:
            btn.first.click(timeout=5000)
        except Exception:
            pass


def _select_date(page, target_date):
    """Click the calendar cell for target_date, advancing months if needed."""
    for _ in range(13):  # at most ~1 year of forward navigation
        cell = page.locator(SELECTORS["calendar_day"].format(day=target_date.day))
        if cell.count() and cell.first.is_enabled():
            cell.first.click()
            return
        page.locator(SELECTORS["calendar_next_month"]).first.click()
        page.wait_for_timeout(400)
    raise RuntimeError(f"Date {target_date} not selectable")


def _buy_now_for(page, ticket_type):
    card = page.locator(SELECTORS["ticket_card"], has_text=ticket_type).first
    card.locator(SELECTORS["buy_now"]).first.click()


def _set_one_adult(page):
    # Default Adult quantity is 1 in the screenshots; ensure it is exactly 1.
    qty = page.locator(SELECTORS["adult_qty"]).first
    current = (qty.input_value() if qty.count() else "1").strip() or "0"
    while int(current) < 1:
        page.locator(SELECTORS["adult_plus"]).first.click()
        current = qty.input_value().strip()


def scrape_ticket_type(context, target_date, ticket_type, party):
    page = context.new_page()
    page.set_default_timeout(NAV_TIMEOUT_MS)
    try:
        page.goto(BOOKING_URL, wait_until="domcontentloaded")
        accept_cookies(page)
        _select_date(page, target_date)
        _buy_now_for(page, ticket_type)
        _set_one_adult(page)
        page.locator(SELECTORS["next_button"]).first.click()
        page.wait_for_selector(SELECTORS["slot_tile"], timeout=NAV_TIMEOUT_MS)
        return extract_slots(
            page,
            scraped_at=utc_now_iso(),
            target_date=target_date.isoformat(),
            ticket_type=ticket_type,
            party=party,
        )
    finally:
        page.close()
```

- [ ] **Step 2: Smoke-test the live flow for today, visible browser**

Add a temporary bottom block (or run from a Python REPL):
```python
# scripts/smoke.py
from datetime import date
from playwright.sync_api import sync_playwright
from eye_scraper.booking import scrape_ticket_type

with sync_playwright() as p:
    ctx = p.chromium.launch(headless=False, slow_mo=200).new_context()
    recs = scrape_ticket_type(ctx, date.today(), "Standard Ticket", "1 adult")
    for r in recs:
        print(r.slot_start, r.slot_end, r.price_gbp, r.sold_out)
    ctx.close()
```
Run: `python scripts/smoke.py`
Expected: prints the same time slots and £ prices visible on screen (e.g. `15:00 15:30 37.0 False`). If a step misclicks, refine that step's selector in `config.SELECTORS` (re-confirm against the live page) and rerun.

- [ ] **Step 3: Checkpoint**

Live smoke run prints correct slots/prices for today. Delete or keep `scripts/smoke.py` (not imported by the package). No git.

---

### Task 7: `main.py` — orchestrate the date horizon

**Files:**
- Create: `main.py`

**Interfaces:**
- Consumes: `config` (DAYS, TICKET_TYPES, PARTY_LABEL, OUTPUT_CSV, SCREENSHOT_DIR); `scrape_ticket_type` (Task 6); `append_records`, `render_table` (Task 3).
- Produces: a CLI entry point.

- [ ] **Step 1: Write `main.py`**

```python
"""London Eye price monitor — scrape today..today+DAYS and append to CSV."""
import argparse
import traceback
from datetime import date, timedelta
from pathlib import Path

from playwright.sync_api import sync_playwright

from eye_scraper import config
from eye_scraper.booking import scrape_ticket_type
from eye_scraper.storage import append_records, render_table


def horizon(days: int) -> list[date]:
    today = date.today()
    return [today + timedelta(days=i) for i in range(days + 1)]


def main():
    ap = argparse.ArgumentParser(description="London Eye price monitor")
    ap.add_argument("--days", type=int, default=config.DAYS)
    ap.add_argument("--ticket-types", nargs="+", default=config.TICKET_TYPES)
    ap.add_argument("--output", default=config.OUTPUT_CSV)
    ap.add_argument("--headed", action="store_true")
    args = ap.parse_args()

    Path(config.SCREENSHOT_DIR).mkdir(parents=True, exist_ok=True)
    total = 0
    with sync_playwright() as p:
        ctx = p.chromium.launch(headless=not args.headed).new_context()
        for d in horizon(args.days):
            for ticket_type in args.ticket_types:
                label = f"{d.isoformat()} / {ticket_type}"
                try:
                    recs = scrape_ticket_type(ctx, d, ticket_type, config.PARTY_LABEL)
                    append_records(args.output, recs)
                    total += len(recs)
                    print(f"\n{label}: {len(recs)} slots")
                    print(render_table(recs))
                except Exception:
                    shot = f"{config.SCREENSHOT_DIR}/fail_{d.isoformat()}_{ticket_type.replace(' ', '_')}.png"
                    print(f"\n!! {label}: FAILED — see {shot}")
                    traceback.print_exc()
                    try:
                        ctx.pages and ctx.pages[-1].screenshot(path=shot)
                    except Exception:
                        pass
        ctx.close()
    print(f"\nDone. {total} records appended to {args.output}")


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Run a 1-day headless smoke of the full entry point**

Run: `python main.py --days 1`
Expected: console prints two per-date tables (today and tomorrow), then `Done. N records appended to data/london_eye_prices.csv`; the CSV exists with a header + N rows.

- [ ] **Step 3: Verify the CSV**

Run: `head -3 data/london_eye_prices.csv`
Expected: line 1 is the header `scraped_at_utc,target_date,...,sold_out`; lines 2–3 are data rows with a 24h `slot_start` and numeric `price_gbp`.

- [ ] **Step 4: Verify resilience**

Confirm that when one date fails it prints `!! ... FAILED`, writes a screenshot under `data/debug/`, and the run still completes the remaining dates (the `Done.` line prints).

- [ ] **Step 5: Checkpoint**

Full `python main.py --days 7` produces 8 dates of Standard-Ticket slots in the CSV. No git.

---

## Extending to Fast Track / Flexi Fast Track (post-MVP, not part of this plan's tasks)

Once the Standard flow is green: set `config.TICKET_TYPES = ["Standard Ticket", "Fast Track", "Flexi Fast Track"]` (use the exact card titles from `TRACE_FINDINGS.md`) and re-run the Task 6 smoke for each new type to confirm the `ticket_card` `has_text` match selects the right card. No code changes expected.

## Self-Review Notes

- **Spec coverage:** scope/monitor → Task 7 horizon + append; print+CSV → Tasks 3/7; Standard-first + config-extensible → `TICKET_TYPES`, "Extending" section; horizon today..+7 → `horizon()`; Playwright SPA flow → Tasks 4/6; DOM extraction + opportunistic API logging → Tasks 4 (NET log) /5; CSV schema → Task 3 `FIELDNAMES`; error handling/survive failures → Task 7 try/except + screenshots; testing (pure logic + fixture + manual smoke) → Tasks 2/3/5 + smoke in 6/7; known-unknown live trace → Task 4. No gaps found.
- **Placeholders:** none — selector *values* are intentionally discovered in Task 4 and consumed by stable `SELECTORS` keys; every code step is complete.
- **Type consistency:** `PriceRecord` field names identical across Tasks 2/3/5; `extract_slots`/`scrape_ticket_type`/`append_records`/`render_table` signatures match between definition and call sites.
