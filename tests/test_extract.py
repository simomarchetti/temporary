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


def test_extract_returns_all_tiles(page):
    recs = extract_slots(page, scraped_at="2026-06-19T15:00:00Z",
                         target_date="2026-06-19", ticket_type="Standard Ticket",
                         party="1 adult")
    assert len(recs) == 4


def test_extract_parses_times_and_prices(page):
    recs = extract_slots(page, scraped_at="2026-06-19T15:00:00Z",
                         target_date="2026-06-19", ticket_type="Standard Ticket",
                         party="1 adult")
    first = recs[0]
    assert (first.slot_start, first.slot_end) == ("15:30", "16:00")
    assert first.price_gbp == 39.0
    assert first.sold_out is False
    assert first.ticket_type == "Standard Ticket"


def test_extract_flags_sold_out(page):
    recs = extract_slots(page, scraped_at="2026-06-19T15:00:00Z",
                         target_date="2026-06-19", ticket_type="Standard Ticket",
                         party="1 adult")
    sold = recs[-1]
    assert sold.slot_start == "19:30"
    assert sold.price_gbp is None
    assert sold.sold_out is True


def test_every_record_is_priced_xor_sold_out(page):
    recs = extract_slots(page, scraped_at="2026-06-19T15:00:00Z",
                         target_date="2026-06-19", ticket_type="Standard Ticket",
                         party="1 adult")
    for r in recs:
        assert (r.price_gbp is not None) ^ r.sold_out
