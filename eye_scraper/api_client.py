"""Browserless client for the London Eye accesso ecomm API.

Confirmed 2026-06-19 (see TRACE_FINDINGS.md). Flow per cart session:
  getnewcartid                     -> cart_id, cart_key, session_id
  getmerchantpackageeventdates     -> available time slots per date
  getdynamicpricingadjustmentcached-> price per (date, time)

Displayed price = discounted_retail_price + discounted_tax_amount (VAT-inclusive).
"""
import os
import secrets
import time

import certifi
import httpx

# Default to certifi, but let a TLS-intercepting environment (e.g. a corporate or
# cloud proxy) point at its own CA bundle via env var without code changes.
_CA_BUNDLE = os.environ.get("EYE_CA_BUNDLE") or os.environ.get("SSL_CERT_FILE") or certifi.where()

BASE = "https://ecomm.api.meg-eu.accessoticketing.com"

HEADERS = {
    "com-accessopassport-client": "accesso26",
    "com-accessopassport-merchant-id": "304",
    "com-accessopassport-app-id": "1500",
    "com-accessopassport-language": "en-gb",
    "content-type": "application/json;charset=UTF-8",
    "accept": "application/json, text/plain, */*",
    "accept-language": "en-GB",
    "origin": "https://me-loneye.tickets.londoneye.com",
    "referer": "https://me-loneye.tickets.londoneye.com/",
    "user-agent": ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
                   "(KHTML, like Gecko) Chrome/126.0 Safari/537.36"),
}

# Static merchant config (from the accesso bootstrap / observed requests).
_BASE_BODY = {
    "_version": "6.29.7", "application_id": "1500", "merchant_id": "304",
    "machine_id": "500", "agent_id": "5", "user_id": "5",
    "device": "desktop", "language": "en-gb",
}


def _token() -> str:
    return secrets.token_hex(16).upper()


class AccessoClient:
    """One cart session against the accesso API."""

    def __init__(self, delay=0.12):
        self._http = httpx.Client(headers=HEADERS, timeout=30, verify=_CA_BUNDLE)
        self.cart_id = self.cart_key = self.session_id = None
        self._delay = delay  # politeness pause between requests (anti rate-limit)

    def __enter__(self):
        self.open_cart()
        return self

    def __exit__(self, *exc):
        self._http.close()

    def _request(self, endpoint: str, body: dict) -> dict:
        payload = {**_BASE_BODY, "request_token": _token(), **body}
        if self.cart_id:
            payload.update(cart_id=self.cart_id, cart_key=self.cart_key,
                           session_id=self.session_id)
        if self._delay:
            time.sleep(self._delay)
        r = self._http.post(f"{BASE}/api/request/{endpoint}", json=payload)
        r.raise_for_status()
        return r.json()["SERVICE"]

    def _post(self, endpoint: str, body: dict) -> dict:
        """POST with one re-bootstrap+backoff retry if Cloudflare throttles us."""
        try:
            return self._request(endpoint, body)
        except httpx.HTTPStatusError as e:
            if e.response.status_code not in (400, 403, 429):
                raise
            time.sleep(3)
            self._bootstrap()  # refresh __cf_bm cookie (cart stays valid)
            return self._request(endpoint, body)

    def _bootstrap(self):
        # Fetch bootstrap to obtain/refresh the Cloudflare __cf_bm cookie; without it
        # the api/request/* endpoints return 400.
        self._http.get(f"{BASE}/static-api/bootstrap?m=ME-LONEYE&l=en-gb")

    def open_cart(self):
        self._bootstrap()
        s = self._request("getnewcartid", {"request_type": "GetNewCartID"})
        self.cart_id, self.cart_key, self.session_id = s["cart_id"], s["cart_key"], s["session_id"]

    def event_dates(self, package_id, event_id, ct_id, start_date, end_date):
        """{date(str): [time(str), ...]} of available slots."""
        s = self._post("getmerchantpackageeventdates", {
            "P": [{"CT": [{"id": str(ct_id), "qty": 1}], "event_id": str(event_id), "id": str(package_id)}],
            "extra_movie": "date_time", "identify_customer_types": 1, "min_capacity": 1,
            "version": "2", "start_date": start_date, "end_date": end_date,
            "display_zero_capacity": "0", "include_times": True,
            "request_type": "GetMerchantPackageEventDates",
        })
        out = {}
        raw = s.get("D", [])
        items = raw.items() if isinstance(raw, dict) else ((d.get("date"), d) for d in raw)
        for date_key, d in items:
            if not isinstance(d, dict):
                continue
            date_key = d.get("date", date_key)
            times = d.get("T", [])
            times = times.values() if isinstance(times, dict) else times
            out.setdefault(date_key, [])
            for t in times:
                if isinstance(t, dict) and "time" in t:
                    out[date_key].append(t["time"])
        return out

    def keyword_calendar(self, keyword, start_date, end_date):
        """Raw getkeywordcalendar SERVICE for a calendar keyword (e.g. 'Flexi')."""
        return self._post("getkeywordcalendar", {
            "display_zero_capacity": "0", "keyword": keyword,
            "start_date": start_date, "end_date": end_date,
            "request_type": "GetKeywordCalendar",
        })

    def slot_price(self, package_id, ct_id, date_str, time_str):
        """VAT-inclusive displayed price for one slot, or None if unavailable."""
        s = self._post("getdynamicpricingadjustmentcached", {
            "customer_type": str(ct_id), "package_id": str(package_id),
            "start_date": date_str, "start_time": time_str,
            "request_type": "GetDynamicPricingAdjustmentCached",
        })
        try:
            return round(float(s["discounted_retail_price"]) + float(s["discounted_tax_amount"]), 2)
        except (KeyError, TypeError, ValueError):
            return None
