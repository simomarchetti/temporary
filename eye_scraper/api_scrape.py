"""High-level browserless scrape: drive the accesso API into PriceRecords.

Two pricing models (see config.TICKETS):
  slots  (Standard, Fast Track) -> event_dates + per-slot dynamic pricing
  single (Flexi Fast Track)     -> one getkeywordcalendar call, flat per-date price
"""
from datetime import date, timedelta

from .api_client import AccessoClient
from .config import PARTY_LABEL, TICKETS
from .models import PriceRecord, add_30min, to_24h, utc_now_iso


def _resolve_packages(client, keyword, name, wanted):
    """{date_iso: (package_id, event_id)} for the named package, per date.

    accesso shards a product across package ids by date window, so the package
    must be resolved per date from the calendar.
    """
    # end is padded +1 day: a zero-width range (e.g. a 1-date horizon) returns nothing.
    end = (date.fromisoformat(max(wanted)) + timedelta(days=1)).isoformat()
    svc = client.keyword_calendar(keyword, min(wanted), end)
    out = {}
    for day in svc.get("DATES", {}).get("D", []):
        iso = day.get("date")
        if iso not in wanted:
            continue
        P = day.get("PS", {}).get("P", [])
        for pk in (P if isinstance(P, list) else [P]):
            if pk.get("name") == name:
                out[iso] = (pk.get("id"), pk.get("event_id"))
    return out


def _slot_records(client, ticket_type, cfg, dates):
    wanted = {d.isoformat() for d in dates}
    try:
        pkgs = _resolve_packages(client, cfg["keyword"], cfg["name"], wanted)
    except Exception:
        return []
    # Group dates by their package, then fetch event dates once per package over its
    # whole range (accesso only serves a date if the query START is near it, so a
    # per-date start= call misses boundary dates — a range call from the package's
    # earliest date returns them all, like the browser's initial load).
    by_pkg = {}
    for iso, (package_id, event_id) in pkgs.items():
        by_pkg.setdefault((package_id, event_id), []).append(iso)

    records = []
    for (package_id, event_id), isos in by_pkg.items():
        start, end = min(isos), max(isos)
        end_excl = (date.fromisoformat(end) + timedelta(days=1)).isoformat()
        try:
            slots_by_date = client.event_dates(package_id, event_id, cfg["ct_id"], start, end_excl)
        except Exception:
            continue
        for iso in isos:
            for time_str in slots_by_date.get(iso, []):
                price = client.slot_price(package_id, cfg["ct_id"], iso, time_str)
                start_24 = to_24h(time_str)
                records.append(PriceRecord(
                    scraped_at_utc=utc_now_iso(), target_date=iso, ticket_type=ticket_type,
                    party=PARTY_LABEL, slot_start=start_24, slot_end=add_30min(start_24),
                    price_gbp=price, sold_out=(price is None),
                ))
    return records


def _single_records(client, ticket_type, cfg, dates):
    wanted = {d.isoformat() for d in dates}
    start = min(wanted)
    end = (date.fromisoformat(max(wanted)) + timedelta(days=1)).isoformat()
    records = []
    try:
        svc = client.keyword_calendar(cfg["keyword"], start, end)
    except Exception:
        return records
    done = set()
    for day in svc.get("DATES", {}).get("D", []):
        iso = day.get("date")
        if iso not in wanted or iso in done:
            continue
        P = day.get("PS", {}).get("P", [])
        for pk in (P if isinstance(P, list) else [P]):
            if iso in done:
                break
            CT = pk.get("CT", [])
            for ct in (CT if isinstance(CT, list) else [CT]):
                if ct.get("id") != str(cfg["ct_id"]) or iso in done:
                    continue
                done.add(iso)
                dp = ct.get("DYNAMIC_PRICING") or {}
                try:
                    price = round(float(dp["max_discounted_retail_amount"])
                                  + float(dp["max_discounted_tax_amount"]), 2)
                except (KeyError, TypeError, ValueError):
                    try:
                        price = round(float(ct["retail_amount"]) + float(ct["tax_amount"]), 2)
                    except (KeyError, TypeError, ValueError):
                        price = None
                records.append(PriceRecord(
                    scraped_at_utc=utc_now_iso(), target_date=iso, ticket_type=ticket_type,
                    party=PARTY_LABEL, slot_start="any", slot_end="any",
                    price_gbp=price, sold_out=(price is None),
                ))
    return records


def scrape_api(ticket_types, dates):
    """Scrape the given ticket types over `dates` (list[date]) via the API."""
    records = []
    with AccessoClient() as client:
        for ticket_type in ticket_types:
            cfg = TICKETS[ticket_type]
            if cfg.get("mode") == "single":
                records += _single_records(client, ticket_type, cfg, dates)
            else:
                records += _slot_records(client, ticket_type, cfg, dates)
    return records
