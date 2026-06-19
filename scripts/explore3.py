"""Stage 3: try direct top-level navigation to the accesso calendar, then drive
   select-date -> Standard Buy Now -> set 1 adult -> Next -> read slots.
   Dumps element lists + screenshots at each sub-step into data/debug/."""
import os
from datetime import date
from playwright.sync_api import sync_playwright

CAL = "https://me-loneye.tickets.londoneye.com/calendar/Calendar?l=en-gb"
UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/126.0 Safari/537.36")
DBG = "data/debug"

LIST_JS = """() => {
  const out = [];
  document.querySelectorAll('button, gap-button, [role=button], input, a').forEach(el => {
    const t = (el.innerText || el.value || '').trim().replace(/\\s+/g,' ').slice(0,70);
    const r = el.getBoundingClientRect();
    if (r.width === 0 || r.height === 0) return;
    if (!t) return;
    out.push(el.tagName + ' | ' + (el.className||'').toString().slice(0,55) + ' | ' + t);
  });
  return out;
}"""


def dump(page, tag):
    page.screenshot(path=f"{DBG}/{tag}.png", full_page=True)
    try:
        items = page.evaluate(LIST_JS)
    except Exception as e:
        items = [f"EVAL FAILED {e}"]
    with open(f"{DBG}/{tag}.txt", "w") as f:
        f.write(f"url={page.url}\n" + "\n".join(items))
    print(f"[{tag}] url={page.url} elements={len(items)}")


def main():
    os.makedirs(DBG, exist_ok=True)
    today = date.today()
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        ctx = browser.new_context(user_agent=UA, viewport={"width": 1366, "height": 900},
                                  locale="en-GB")
        page = ctx.new_page()
        page.set_default_timeout(30000)
        page.goto(CAL, wait_until="domcontentloaded")
        page.wait_for_timeout(5000)
        dump(page, "30_calendar_direct")

        # select today's day cell (enabled)
        day = str(today.day)
        cell = page.locator(f"button.acso-cal__btn:not(.--disabled)", has_text=day).first
        print("today cell visible:", cell.count(), cell.is_visible() if cell.count() else None)
        cell.click()
        page.wait_for_timeout(3000)
        dump(page, "31_after_date")

        # click Standard Buy Now
        card = page.locator("gap-card", has_text="Standard Ticket").first
        card.locator("gap-button", has_text="Buy Now").first.click()
        page.wait_for_timeout(4000)
        dump(page, "32_after_buynow")

        # find the Adult rate row and dump its HTML so we can pick the + stepper
        adult_html = page.evaluate("""() => {
          const nodes = [...document.querySelectorAll('*')].filter(
            el => /Adult/i.test(el.textContent||'') &&
                  el.querySelector && el.querySelector('input'));
          // smallest such ancestor that contains exactly one input
          const rows = nodes.filter(el => el.querySelectorAll('input').length === 1);
          const row = rows[rows.length-1];
          return row ? row.outerHTML.slice(0, 2500) : 'NO ADULT ROW';
        }""")
        open(f"{DBG}/32_adult_row.html", "w").write(adult_html)
        print("ADULT ROW saved")

        # increment Adult: click the '+' control in the Adult row
        adult_row = page.locator("xpath=//*[self::div or self::gap-rate-quantity-selector][.//input][contains(.,'Adult')]").last
        plus = adult_row.locator("xpath=.//button[last()] | .//*[contains(@class,'increment') or contains(@aria-label,'ncrease') or contains(@aria-label,'dd')]")
        print("plus candidates:", plus.count())
        try:
            plus.last.click()
            page.wait_for_timeout(1200)
        except Exception as e:
            print("plus click failed:", e)
        dump(page, "33_after_adult_plus")

        # Next
        page.locator("gap-button", has_text="Next").last.click()
        page.wait_for_timeout(5000)
        dump(page, "34_upsell")

        # dismiss upsell modal(s) if present
        for _ in range(3):
            decline = page.locator("button:has-text('Not now'), gap-button:has-text('Not now')")
            if decline.count() and decline.first.is_visible():
                decline.first.click()
                page.wait_for_timeout(3000)
            else:
                break
        dump(page, "35_slots")
        open(f"{DBG}/35_slots.html", "w").write(page.content())

        # extract slot tiles heuristically: any element whose text has a time range + price
        slots = page.evaluate(r"""() => {
          const re = /\d{1,2}:\d{2}\s*(AM|PM).*?\d{1,2}:\d{2}\s*(AM|PM)/i;
          const out = [];
          document.querySelectorAll('*').forEach(el => {
            if (el.children.length > 3) return;
            const t = (el.innerText||'').replace(/\s+/g,' ').trim();
            if (re.test(t) && t.length < 60) out.push(el.tagName+' | '+(el.className||'').toString().slice(0,50)+' | '+t);
          });
          return [...new Set(out)];
        }""")
        open(f"{DBG}/35_slot_tiles.txt", "w").write("\n".join(slots))
        print("SLOT TILES:", len(slots))
        for s in slots[:20]:
            print("  ", s)
        browser.close()


if __name__ == "__main__":
    main()
