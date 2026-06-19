"""Capture the accesso XHR/API calls that deliver slot prices, to assess a
   browserless (httpx) cloud path. Logs request URLs + saves JSON bodies."""
import os
from datetime import date
from playwright.sync_api import sync_playwright

CAL = "https://me-loneye.tickets.londoneye.com/calendar/Calendar?l=en-gb"
UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/126.0 Safari/537.36")
os.makedirs("data/debug/api", exist_ok=True)
hits = []

KEY = ("getdynamicpricingadjustmentcached", "getmerchantpackageeventdates")

def on_resp(r):
    u = r.url
    if "accessoticketing.com" in u or "/ecomm" in u or "static-api" in u:
        if any(x in u for x in (".js", ".css", ".woff", ".png", ".svg")):
            return
        ct = r.headers.get("content-type", "")
        hits.append((r.request.method, r.status, u, ct))
        name = u.rsplit("/", 1)[-1].split("?")[0]
        if name in KEY:
            req = r.request
            body = ""
            try:
                body = r.text()[:1200]
            except Exception:
                pass
            with open(f"data/debug/api/{name}.txt", "w") as f:
                f.write("URL: " + u + "\n\nREQUEST HEADERS:\n")
                for k, v in req.headers.items():
                    f.write(f"  {k}: {v[:120]}\n")
                f.write("\nREQUEST BODY:\n" + (req.post_data or "")[:1500])
                f.write("\n\nRESPONSE BODY (1200):\n" + body)

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
    page.wait_for_timeout(2000)
    print(f"=== {len(hits)} accesso API calls ===")
    for m, s, u, ct in hits:
        print(f"{m} {s} [{ct[:20]}] {u[:160]}")
    ctx.close()
