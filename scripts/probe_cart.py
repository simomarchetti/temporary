"""Capture getnewcartid + getcartsummary request/response and where session_id /
   cart_key / request_token come from, to replicate cart bootstrap over HTTP."""
import json
from playwright.sync_api import sync_playwright

CAL = "https://me-loneye.tickets.londoneye.com/calendar/Calendar?l=en-gb"
UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/126.0 Safari/537.36")
SHOW = ("getnewcartid", "getcartsummary", "getkeywordcalendar")

def on_resp(r):
    name = r.url.rsplit("/", 1)[-1].split("?")[0]
    if name in SHOW:
        try:
            req = r.request.post_data or ""
            body = r.text()[:700]
            print(f"\n##### {name} #####")
            print("REQ:", req[:700])
            print("RESP:", body)
        except Exception as e:
            print(name, "err", e)

with sync_playwright() as p:
    ctx = p.chromium.launch(headless=True).new_context(user_agent=UA, locale="en-GB",
                                                        viewport={"width": 1366, "height": 900})
    page = ctx.new_page(); page.set_default_timeout(30000)
    page.on("response", on_resp)
    page.goto(CAL, wait_until="domcontentloaded"); page.wait_for_timeout(6000)
    ctx.close()
