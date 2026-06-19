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
