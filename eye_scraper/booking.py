"""Playwright booking flow + slot extraction for the London Eye (accesso widget).

Flow (all on the accesso storefront, no marketing-site iframe needed):
  calendar  -> pick date
            -> Buy Now on the ticket card
  quantity  -> set Adult = 1 -> Next
  upsell    -> dismiss "Not now, thanks" (0..n interstitials)
  dateTime  -> read every time-slot tile
"""
import re

from .config import NAV_TIMEOUT_MS, SCREENSHOT_DIR, SELECTORS, TICKETS
from .models import PriceRecord, parse_price, parse_time_slot, utc_now_iso

# Adult price on the quantity page, for flexible-entry passes with no slot grid.
_ADULT_PRICE_JS = """() => {
  for (const r of document.querySelectorAll('.customer-info')) {
    const lbl = (r.querySelector('[ng-bind-html*=cusTypeName]') || {}).innerText || '';
    if (/Adult/i.test(lbl)) return (r.querySelector('.gap-text--currency') || {}).innerText || '';
  }
  return '';
}"""


# ---- extraction (pure DOM read; unit-tested against a fixture) --------------

def extract_slots(page, *, scraped_at, target_date, ticket_type, party):
    """Read every time-slot tile currently rendered on `page`."""
    tiles = page.locator(SELECTORS["slot_tile"])
    records = []
    for i in range(tiles.count()):
        tile = tiles.nth(i)
        try:
            time_text = tile.locator(SELECTORS["slot_time"]).first.inner_text().strip()
            start, end = parse_time_slot(time_text)
        except Exception:
            continue  # not a parseable slot tile
        price_loc = tile.locator(SELECTORS["slot_price"])
        price_text = price_loc.first.inner_text().strip() if price_loc.count() else ""
        price = parse_price(price_text)
        aria = (tile.get_attribute("aria-disabled") or "").lower()
        records.append(PriceRecord(
            scraped_at_utc=scraped_at, target_date=target_date,
            ticket_type=ticket_type, party=party,
            slot_start=start, slot_end=end,
            price_gbp=price, sold_out=(price is None or aria == "true"),
        ))
    return records


def extract_adult_price(page, *, scraped_at, target_date, ticket_type, party):
    """For flexible-entry passes (no slot grid): one record with the Adult price."""
    page.wait_for_selector(".customer-info")
    price = parse_price(page.evaluate(_ADULT_PRICE_JS))
    return [PriceRecord(
        scraped_at_utc=scraped_at, target_date=target_date,
        ticket_type=ticket_type, party=party,
        slot_start="any", slot_end="any",
        price_gbp=price, sold_out=(price is None),
    )]


# ---- live flow --------------------------------------------------------------

def _select_date(page, target_date):
    """Advance the calendar to target_date's month, then click its day cell."""
    want = target_date.strftime("%B %Y")            # e.g. "June 2026"
    label_loc = page.locator(SELECTORS["calendar_month_label"])
    for _ in range(13):
        try:
            label = label_loc.first.inner_text(timeout=3000).strip()
        except Exception:
            label = ""
        if not label or label == want:
            break
        page.locator(SELECTORS["calendar_next_month"]).first.click()
        page.wait_for_timeout(600)

    day_re = re.compile(rf"^\s*{target_date.day}\s*$")
    cells = page.locator(SELECTORS["calendar_day"], has_text=day_re)
    for i in range(cells.count()):
        cell = cells.nth(i)
        if "--disabled" in (cell.get_attribute("class") or ""):
            continue
        cell.click()
        return
    raise RuntimeError(f"Date {target_date} not selectable (sold out / out of range)")


def _set_one_adult(page):
    page.wait_for_selector(SELECTORS["adult_increase"])
    qty = page.locator(SELECTORS["adult_qty"]).first
    for _ in range(3):
        val = (qty.input_value() or "0").strip() or "0"
        if int(val) >= 1:
            return
        page.locator(SELECTORS["adult_increase"]).first.click()
        page.wait_for_timeout(600)


def _dismiss_upsells(page):
    """Click 'Not now, thanks' on any upsell interstitial(s) until none remain."""
    page.wait_for_timeout(3000)
    for _ in range(3):
        decline = page.locator(SELECTORS["upsell_decline"])
        try:
            if decline.count() and decline.first.is_visible():
                decline.first.click()
                page.wait_for_timeout(2500)
                continue
        except Exception:
            pass
        break


def scrape_ticket_type(context, target_date, ticket_type, party):
    """Run the full flow for one (date, ticket type) and return its slot records."""
    entry = TICKETS.get(ticket_type, {"url": None, "card": ticket_type})
    if not entry["url"]:
        raise ValueError(f"Unknown ticket type {ticket_type!r}; add it to config.TICKETS")
    page = context.new_page()
    page.set_default_timeout(NAV_TIMEOUT_MS)
    try:
        page.goto(entry["url"], wait_until="domcontentloaded")
        page.wait_for_selector(SELECTORS["calendar_day"])
        page.wait_for_timeout(2000)
        _select_date(page, target_date)
        page.wait_for_timeout(1500)
        card = page.locator(SELECTORS["ticket_card"], has_text=entry["card"]).first
        card.locator(SELECTORS["buy_now"], has_text="Buy Now").first.click()
        page.wait_for_url("**/packageDetails/**")
        _set_one_adult(page)

        common = dict(scraped_at=utc_now_iso(), target_date=target_date.isoformat(),
                      ticket_type=ticket_type, party=party)
        if entry.get("mode") == "single":
            return extract_adult_price(page, **common)

        page.locator(SELECTORS["next_button"], has_text="Next").last.click()
        _dismiss_upsells(page)
        page.wait_for_selector(SELECTORS["slot_tile"])
        return extract_slots(page, **common)
    except Exception:
        try:
            safe = ticket_type.replace(" ", "_")
            page.screenshot(path=f"{SCREENSHOT_DIR}/fail_{target_date.isoformat()}_{safe}.png")
        except Exception:
            pass
        raise
    finally:
        page.close()
