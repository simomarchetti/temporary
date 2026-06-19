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
