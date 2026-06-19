"""Match UI-displayed slot prices against the accesso dynamic-pricing API
   responses, in one session, to derive the displayed-price formula."""
import json
from datetime import date
from playwright.sync_api import sync_playwright

CAL = "https://me-loneye.tickets.londoneye.com/calendar/Calendar?l=en-gb"
UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/126.0 Safari/537.36")
api = {}  # start_time -> dict of price fields

def on_resp(r):
    if "getdynamicpricingadjustmentcached" in r.url:
        try:
            body = r.json()["SERVICE"]
            api[body["start_time"]] = {
                "retail": body.get("retail_price"),
                "disc": body.get("discounted_retail_price"),
                "tax": body.get("tax_amount"),
                "disc_tax": body.get("discounted_tax_amount"),
                "disc_pct": body.get("discount_percentage"),
            }
        except Exception:
            pass

with sync_playwright() as p:
    ctx = p.chromium.launch(headless=True).new_context(user_agent=UA, locale="en-GB",
                                                        viewport={"width": 1366, "height": 900})
    page = ctx.new_page(); page.set_default_timeout(30000)
    page.on("response", on_resp)
    page.goto(CAL, wait_until="domcontentloaded"); page.wait_for_timeout(5000)
    page.locator("button.acso-cal__btn:not(.--disabled)", has_text=str(date.today().day)).first.click()
    page.wait_for_timeout(2500)
    page.locator("gap-card", has_text="Standard Ticket").first \
        .locator("gap-button", has_text="Buy Now").first.click()
    page.wait_for_timeout(3500)
    inc = page.locator("button[aria-label^='Increase Adult']")
    if inc.count(): inc.first.click(); page.wait_for_timeout(800)
    page.locator("gap-button", has_text="Next").last.click()
    page.wait_for_timeout(4000)
    d = page.locator("button:has-text('Not now'), gap-button:has-text('Not now')")
    if d.count() and d.first.is_visible(): d.first.click(); page.wait_for_timeout(3000)
    page.wait_for_selector("gap-tile[data-cy^='dt_timeSlot']")
    page.wait_for_timeout(2000)
    # read displayed prices per slot
    tiles = page.locator("gap-tile[data-cy^='dt_timeSlot']")
    print(f"{'slot':<16}{'displayed':<11}{'api_retail':<11}{'api_disc':<10}{'disc_pct'}")
    for i in range(tiles.count()):
        t = tiles.nth(i)
        title = t.locator("span[slot=title]").inner_text().strip()
        disp = t.locator("span[slot=price]").inner_text().strip()
        start = title.split("-")[0].strip()
        a = api.get(start, {})
        print(f"{start:<16}{disp:<11}{str(a.get('retail')):<11}{str(a.get('disc')):<10}{a.get('disc_pct')}")
    ctx.close()
