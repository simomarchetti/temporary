# Live Trace Findings — London Eye booking flow

**Traced:** 2026-06-19 (autonomously, via headless Playwright + screenshots).

## Platform

The booking is powered by **accesso** (ticketing platform), an AngularJS widget
served from `me-loneye.tickets.londoneye.com`. The marketing page
(`www.londoneye.com/tickets-and-prices/`) embeds it via `embed/accesso.js` +
`shim.html` and opens it as an iframe modal on "Book Now".

**Key shortcut:** the accesso storefront is reachable **directly as a top-level
page** — no marketing site, no iframe, no "Book Now" click needed. The scraper
navigates straight to the calendar URL.

- Generic daily-tickets calendar: `https://me-loneye.tickets.londoneye.com/calendar/Calendar?l=en-gb`
  (lists Standard / Fast Track / Champagne cards)
- Flexi Fast Track (separate product): `https://me-loneye.tickets.londoneye.com/calendarPricingWithImage/Flexi?l=en-gb`
- `l=en-gb` forces English / GBP.

## Anti-bot

- **Cloudflare** + **queue-it** virtual waiting room (`accessoar.queue-it.net`)
  sit in front of the storefront. During tracing, direct navigation passed
  without challenge (no queue, no CAPTCHA) on a plain headless Chromium with a
  desktop user-agent. **Risk:** under high demand / heavy automation, queue-it
  may interpose a waiting-room page. Not handled yet — see "Future".
- No bot block observed on the marketing page either.

## Flow (per date + ticket type)

1. `goto` the ticket's calendar URL.
2. Calendar ("Choose your date"): click the day cell.
3. Ticket list ("Choose your ticket"): click "Buy Now" on the matching card →
   navigates to `packageDetails/<id>/...`.
4. Quantity page ("Choose Your Tickets"): increase **Adult** to 1 → "Next".
5. **Upsell interstitial** (e.g. "Upgrade with Madame Tussauds") → dismiss with
   "Not now, thanks". May appear 0..n times.
6. Time-slot grid ("Select Time", `dateTime/<id>`): read every tile.

## Selectors (confirmed live; in `eye_scraper/config.py SELECTORS`)

| Purpose            | Selector |
|--------------------|----------|
| Calendar day cell  | `button.acso-cal__btn` (text = day number; skip class `--disabled`) |
| Month label        | `.acso-cal-heading .h5` (e.g. "June 2026") |
| Next month         | `.acso-cal-heading__navigate.--right` |
| Ticket card        | `gap-card` (filtered by `has_text` = card title) |
| Buy Now            | `gap-button` with text "Buy Now" |
| Adult increment    | `button[aria-label^='Increase Adult']` |
| Adult quantity     | `input[aria-label^='Adult']` |
| Next               | `gap-button` with text "Next" |
| Upsell decline     | `button:has-text('Not now'), gap-button:has-text('Not now')` |
| Slot tile          | `gap-tile[data-cy^='dt_timeSlot']` |
| Slot time          | `span[slot='title']` (e.g. "3:30 PM - 4:00 PM") |
| Slot price         | `span[slot='price']` (e.g. "£39.00" or sold-out label) |

A sold-out tile has `aria-disabled="true"` and the title gets a `strike-through`
class; the price span shows the sold-out label instead of a `£` amount.

## Ticket types — two pricing models

| Ticket            | Card title in widget        | Entry                              | Model    |
|-------------------|-----------------------------|-------------------------------------|----------|
| Standard Ticket   | "Standard Ticket"           | generic calendar                    | **slots** |
| Fast Track        | "Fast Track Ticket"         | generic calendar                    | **slots** |
| Champagne         | "Champagne Experience"      | generic calendar                    | hosted experience — different flow, **not scraped** |
| Flexi Fast Track  | "The Flexi Fast Track Pass" | `calendarPricingWithImage/Flexi`    | **single** |

- **slots**: per-30-minute time slot, each with its own dynamic price. One CSV row
  per slot.
- **single**: Flexi is a *flexible-entry* pass — no time-slot grid. It has one
  dynamic Adult price per date (read from the quantity page, customer type
  "Adult Fast Track (16+)"). Recorded as one CSV row per date with
  `slot_start=slot_end="any"`. Example: 2026-06-19 Adult = £59.00.
- **Champagne** uses a different flow (no standard slot grid); the monitor logs it
  as a failure and continues. Out of scope.

## Pricing JSON API (opportunistic, not used)

A clean accesso ecomm API exists (`ecomm.api.meg-eu.accessoticketing.com/static-api/...`,
`m=ME-LONEYE`). It could power a faster `httpx`-only scraper later, but it sits
behind Cloudflare/queue-it and was not reverse-engineered. The browser flow is the
current source of truth.

## Future

- **queue-it handling:** detect a `queue-it` URL/interstitial and wait/retry, or
  back off the schedule, to keep scheduled runs reliable under demand.
- **accesso API path:** reverse-engineer `static-api` for a lightweight scraper.
- **Champagne:** map its (different) flow if its pricing is ever wanted.
