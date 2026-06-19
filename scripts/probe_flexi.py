"""Find where the marketing-page 'Flexi Fast Track' Book Now leads."""
from playwright.sync_api import sync_playwright

START = "https://www.londoneye.com/tickets-and-prices/"
UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/126.0 Safari/537.36")

with sync_playwright() as p:
    ctx = p.chromium.launch(headless=True).new_context(user_agent=UA, locale="en-GB",
                                                        viewport={"width": 1366, "height": 900})
    page = ctx.new_page(); page.set_default_timeout(30000)
    page.goto(START, wait_until="domcontentloaded"); page.wait_for_timeout(2500)
    for sel in ["#onetrust-accept-btn-handler"]:
        try:
            page.locator(sel).first.click(timeout=3000)
        except Exception:
            pass
    page.wait_for_timeout(1000)
    card = page.locator("a.ticket-link", has_text="Flexi").first
    print("Flexi card text:", card.inner_text().replace("\n", " ")[:80])
    book = card.locator("xpath=ancestor::*[.//button[contains(@class,'accesso')]][1]") \
               .locator("button.accesso").first
    book.click()
    page.wait_for_timeout(7000)
    for i, fr in enumerate(page.frames):
        if "tickets.londoneye.com" in fr.url and "shim" not in fr.url:
            print(f"ACCESSO FRAME [{i}]: {fr.url}")
    ctx.close()
