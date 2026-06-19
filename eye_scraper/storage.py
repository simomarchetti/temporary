"""CSV append + console rendering for price records."""
import csv
from pathlib import Path

from .models import PriceRecord

FIELDNAMES = [
    "scraped_at_utc", "target_date", "ticket_type", "party",
    "slot_start", "slot_end", "price_gbp", "sold_out",
]


def _row(r: PriceRecord) -> dict:
    return {
        "scraped_at_utc": r.scraped_at_utc,
        "target_date": r.target_date,
        "ticket_type": r.ticket_type,
        "party": r.party,
        "slot_start": r.slot_start,
        "slot_end": r.slot_end,
        "price_gbp": "" if r.price_gbp is None else r.price_gbp,
        "sold_out": "true" if r.sold_out else "false",
    }


def append_records(path: str, records: list[PriceRecord]) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    is_new = not p.exists()
    with p.open("a", newline="") as f:
        w = csv.DictWriter(f, fieldnames=FIELDNAMES)
        if is_new:
            w.writeheader()
        for r in records:
            w.writerow(_row(r))


def render_table(records: list[PriceRecord]) -> str:
    if not records:
        return "  (no slots)"
    lines = []
    for r in records:
        price = "SOLD OUT" if r.sold_out or r.price_gbp is None else f"£{r.price_gbp:.2f}"
        lines.append(f"  {r.slot_start}-{r.slot_end}  {price}")
    return "\n".join(lines)
