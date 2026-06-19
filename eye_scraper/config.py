"""Configuration constants for the London Eye price monitor.

Selectors were confirmed against the live accesso booking widget on 2026-06-19.
See docs/superpowers/specs/TRACE_FINDINGS.md for how each was discovered.
"""

# The generic accesso daily-tickets calendar — reachable directly as a top-level
# page (no marketing-site iframe needed). It lists Standard / Fast Track / Champagne.
# `l=en-gb` forces English/GBP.
_CALENDAR_GENERIC = "https://me-loneye.tickets.londoneye.com/calendar/Calendar?l=en-gb"

# Per-ticket entry: which accesso calendar URL to open and which card's "Buy Now" to
# click (substring match on the gap-card). Standard & Fast Track share the generic
# calendar; Flexi Fast Track is a separate accesso product with its own calendar.
# (Confirmed live 2026-06-19; see TRACE_FINDINGS.md.)
# mode "slots": has a time-slot grid -> one record per slot.
# mode "single": flexible-entry pass, no slots -> one record per date (Adult price).
#
# Browser engine uses url/card. API engine uses package_id/event_id/ct_id (the
# accesso Adult customer-type id). Both confirmed live 2026-06-19; see TRACE_FINDINGS.md.
# API engine resolves the per-date package id from getkeywordcalendar (accesso shards
# the same product across package ids by date window), matching on `name`, then prices
# each slot with CT `ct_id`. Browser engine uses `url`/`card`.
TICKETS = {
    "Standard Ticket": {
        "url": _CALENDAR_GENERIC, "card": "Standard Ticket", "mode": "slots",
        "keyword": "Calendar", "name": "Standard Ticket", "ct_id": "331",
    },
    "Fast Track": {
        "url": _CALENDAR_GENERIC, "card": "Fast Track", "mode": "slots",
        "keyword": "Calendar", "name": "Fast Track", "ct_id": "781",
    },
    "Flexi Fast Track": {
        "url": "https://me-loneye.tickets.londoneye.com/calendarPricingWithImage/Flexi?l=en-gb",
        "card": "Flexi", "mode": "single",
        # Flat per-date price via getkeywordcalendar 'Flexi', CT 781 (Adult Fast Track),
        # using max_discounted_retail + max_discounted_tax.
        "keyword": "Flexi", "name": "The Flexi Fast Track Pass", "ct_id": "781",
    },
}

# Rolling horizon: today .. today + DAYS (inclusive) => DAYS + 1 dates.
DAYS = 7

# Which tickets to scrape each run (keys of TICKETS).
TICKET_TYPES = ["Standard Ticket", "Fast Track", "Flexi Fast Track"]

PARTY_LABEL = "1 adult"

OUTPUT_CSV = "data/london_eye_prices.csv"
SCREENSHOT_DIR = "data/debug"

NAV_TIMEOUT_MS = 45000

# DOM selectors for the accesso widget (AngularJS). Keys are stable.
SELECTORS = {
    # Calendar (Choose your date)
    "calendar_day": "button.acso-cal__btn",          # text == day number; skip class '--disabled'
    "calendar_month_label": ".acso-cal-heading .h5",  # e.g. "June 2026"
    "calendar_next_month": ".acso-cal-heading__navigate.--right",
    # Ticket list (Choose your ticket)
    "ticket_card": "gap-card",                        # filtered by has_text=<ticket title>
    "buy_now": "gap-button",                          # filtered by has_text="Buy Now"
    # Quantity page (Choose Your Tickets)
    "adult_increase": "button[aria-label^='Increase Adult']",
    "adult_qty": "input[aria-label^='Adult']",
    "next_button": "gap-button",                      # filtered by has_text="Next"
    # Upsell interstitial(s)
    "upsell_decline": "button:has-text('Not now'), gap-button:has-text('Not now')",
    # Time-slot grid (Select Time)
    "slot_tile": "gap-tile[data-cy^='dt_timeSlot']",
    "slot_time": "span[slot='title']",
    "slot_price": "span[slot='price']",
}
