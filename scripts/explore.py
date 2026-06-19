"""Stage-by-stage explorer to discover the London Eye (accesso) booking flow.

Usage: python scripts/explore.py [stage]
  stage 1 = landing only
  stage 2 = click Standard 'Book Now', capture accesso widget + frames
"""
import os
import sys
from playwright.sync_api import sync_playwright

START = "https://www.londoneye.com/tickets-and-prices/"
UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/126.0 Safari/537.36")
DBG = "data/debug"

LIST_JS = """() => {
  const out = [];
  const sel = 'button, a, [role=button], input, [data-testid], [class*=calendar], [class*=day]';
  document.querySelectorAll(sel).forEach(el => {
    const t = (el.innerText || el.value || '').trim().replace(/\\s+/g,' ').slice(0,50);
    const r = el.getBoundingClientRect();
    if (r.width === 0 || r.height === 0) return;
    out.push({tag: el.tagName, text: t, id: el.id,
              cls: (el.className||'').toString().slice(0,70),
              testid: el.getAttribute('data-testid')});
  });
  return out;
}"""


def list_frame(frame, tag):
    try:
        items = frame.evaluate(LIST_JS)
    except Exception as e:
        print(f"  [{tag}] evaluate failed: {e}")
        return
    print(f"\n----- frame {tag} | url={frame.url} | {len(items)} elements -----")
    for it in items:
        if it["text"] or it["testid"] or "day" in it["cls"].lower() or "cal" in it["cls"].lower():
            print(it)


def accept_cookies(page):
    for sel in ["#onetrust-accept-btn-handler", "button:has-text('Accept All')"]:
        try:
            loc = page.locator(sel)
            if loc.count() and loc.first.is_visible():
                loc.first.click(timeout=3000)
                print("COOKIE clicked:", sel)
                return
        except Exception:
            pass


def main():
    stage = sys.argv[1] if len(sys.argv) > 1 else "2"
    os.makedirs(DBG, exist_ok=True)
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        ctx = browser.new_context(user_agent=UA, viewport={"width": 1366, "height": 900},
                                  locale="en-GB")
        page = ctx.new_page()
        page.on("response", lambda r: print("NET", r.status, r.request.method, r.url)
                if any(k in r.url.lower() for k in ("avail", "session", "calendar", "price", "slot", "/embed/", "accesso"))
                and not any(x in r.url for x in (".js", ".css", ".png", ".svg", ".woff"))
                else None)
        page.set_default_timeout(30000)
        page.goto(START, wait_until="domcontentloaded")
        page.wait_for_timeout(2500)
        accept_cookies(page)
        page.wait_for_timeout(1000)

        if stage == "1":
            list_frame(page, "main")
            browser.close()
            return

        # Stage 2: click the Standard Ticket "Book Now"
        card = page.locator("a.ticket-link", has_text="Standard Ticket").first
        # the Book Now button is a sibling within the same ticket card container
        book = card.locator("xpath=ancestor::*[.//button[contains(@class,'accesso')]][1]") \
                   .locator("button.accesso").first
        print("Clicking Standard Book Now; visible =", book.is_visible())
        book.click()
        page.wait_for_timeout(6000)

        page.screenshot(path=f"{DBG}/02_after_booknow.png", full_page=True)
        rep = open(f"{DBG}/frames_report.txt", "w")
        rep.write("FRAMES:\n")
        for i, fr in enumerate(page.frames):
            rep.write(f"  [{i}] {fr.url}\n")
        for i, fr in enumerate(page.frames):
            if "tickets.londoneye.com" not in fr.url and i != 0:
                continue
            try:
                items = fr.evaluate(LIST_JS)
            except Exception as e:
                rep.write(f"\n----- frame {i} {fr.url} EVAL FAILED {e}\n")
                continue
            rep.write(f"\n----- frame {i} | url={fr.url} | {len(items)} elements -----\n")
            for it in items:
                if it["text"] or it["testid"] or "day" in it["cls"].lower() or "cal" in it["cls"].lower():
                    rep.write(str(it) + "\n")
        rep.close()
        print("wrote", f"{DBG}/frames_report.txt")
        browser.close()


if __name__ == "__main__":
    main()
