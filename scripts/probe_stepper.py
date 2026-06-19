"""Probe the Adult quantity stepper HTML on the packageDetails page."""
from datetime import date
from playwright.sync_api import sync_playwright

CAL = "https://me-loneye.tickets.londoneye.com/calendar/Calendar?l=en-gb"
UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/126.0 Safari/537.36")

with sync_playwright() as p:
    ctx = p.chromium.launch(headless=True).new_context(user_agent=UA, locale="en-GB",
                                                        viewport={"width": 1366, "height": 900})
    page = ctx.new_page(); page.set_default_timeout(30000)
    page.goto(CAL, wait_until="domcontentloaded"); page.wait_for_timeout(5000)
    page.locator("button.acso-cal__btn:not(.--disabled)",
                 has_text=str(date.today().day)).first.click()
    page.wait_for_timeout(2500)
    page.locator("gap-card", has_text="Standard Ticket").first \
        .locator("gap-button", has_text="Buy Now").first.click()
    page.wait_for_timeout(4000)
    # the stepper: smallest ancestor of the first qty input that also has buttons
    html = page.evaluate(r"""() => {
      const inp = document.querySelector('input.ng-valid-number');
      if (!inp) return 'NO INPUT';
      let el = inp;
      for (let i=0;i<6;i++){ el = el.parentElement; if (el && el.querySelectorAll('button').length>=1) break; }
      return el ? el.outerHTML.slice(0,1800) : 'NONE';
    }""")
    import re
    print(re.sub(r'>\s*<', '>\n<', html))
    ctx.close()
