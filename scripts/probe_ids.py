"""Drive each ticket type and log the accesso API request bodies, to extract
   package_id / event_id / customer_type for the HTTP client."""
import json
from datetime import date
from playwright.sync_api import sync_playwright

UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/126.0 Safari/537.36")
TICKETS = [
    ("Standard Ticket", "https://me-loneye.tickets.londoneye.com/calendar/Calendar?l=en-gb", "Standard Ticket"),
    ("Fast Track", "https://me-loneye.tickets.londoneye.com/calendar/Calendar?l=en-gb", "Fast Track"),
    ("Flexi Fast Track", "https://me-loneye.tickets.londoneye.com/calendarPricingWithImage/Flexi?l=en-gb", "Flexi"),
]
seen = []

def make_logger(tag):
    def on_resp(r):
        name = r.url.rsplit("/", 1)[-1].split("?")[0]
        if name in ("getmerchantpackageeventdates", "getdynamicpricingadjustmentcached"):
            try:
                b = json.loads(r.request.post_data or "{}")
                if name == "getmerchantpackageeventdates":
                    pkg = b.get("P", [{}])[0]
                    seen.append((tag, name, {"package_id": pkg.get("id"), "event_id": pkg.get("event_id"),
                                             "CT": pkg.get("CT")}))
                else:
                    seen.append((tag, name, {"package_id": b.get("package_id"),
                                             "customer_type": b.get("customer_type"),
                                             "start_time": b.get("start_time")}))
            except Exception:
                pass
    return on_resp

with sync_playwright() as p:
    ctx = p.chromium.launch(headless=True).new_context(user_agent=UA, locale="en-GB",
                                                        viewport={"width": 1366, "height": 900})
    day = str(date.today().day)
    for tag, url, card in TICKETS:
        page = ctx.new_page(); page.set_default_timeout(30000)
        page.on("response", make_logger(tag))
        try:
            page.goto(url, wait_until="domcontentloaded"); page.wait_for_timeout(5000)
            page.locator("button.acso-cal__btn:not(.--disabled)", has_text=day).first.click()
            page.wait_for_timeout(2500)
            page.locator("gap-card", has_text=card).first.locator("gap-button", has_text="Buy Now").first.click()
            page.wait_for_timeout(3500)
            inc = page.locator("button[aria-label^='Increase Adult']")
            if inc.count(): inc.first.click(); page.wait_for_timeout(800)
            page.locator("gap-button", has_text="Next").last.click()
            page.wait_for_timeout(4500)
            d = page.locator("button:has-text('Not now'), gap-button:has-text('Not now')")
            if d.count() and d.first.is_visible(): d.first.click(); page.wait_for_timeout(3000)
            page.wait_for_timeout(2500)
        except Exception as e:
            print(tag, "flow err", e)
        page.close()

    print("\n=== captured ===")
    for tag, name, data in seen:
        print(f"{tag:<18} {name:<34} {data}")
    ctx.close()
