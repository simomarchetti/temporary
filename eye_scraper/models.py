"""Record type and pure parsing helpers (no I/O, no browser)."""
from dataclasses import dataclass
from datetime import datetime, timezone
import re


@dataclass
class PriceRecord:
    scraped_at_utc: str
    target_date: str       # YYYY-MM-DD
    ticket_type: str
    party: str
    slot_start: str        # HH:MM (24h)
    slot_end: str          # HH:MM (24h)
    price_gbp: float | None
    sold_out: bool


_PRICE_RE = re.compile(r"£\s*([\d,]+(?:\.\d{1,2})?)")
_SPLIT_RE = re.compile(r"\s*[-–—]\s*")


def parse_price(text: str) -> float | None:
    """Extract a GBP amount from text; return None if there is no price."""
    if not text:
        return None
    m = _PRICE_RE.search(text)
    if not m:
        return None
    return float(m.group(1).replace(",", ""))


def _to_24h(token: str) -> str:
    cleaned = token.strip().upper().replace(".", "")
    return datetime.strptime(cleaned, "%I:%M %p").strftime("%H:%M")


def parse_time_slot(text: str) -> tuple[str, str]:
    """'3:00 PM - 3:30 PM' -> ('15:00', '15:30')."""
    parts = _SPLIT_RE.split(text.strip())
    if len(parts) != 2:
        raise ValueError(f"Cannot parse time slot: {text!r}")
    return _to_24h(parts[0]), _to_24h(parts[1])


def to_24h(token: str) -> str:
    """'4:30 PM' -> '16:30'."""
    return _to_24h(token)


def add_30min(hhmm: str) -> str:
    """'16:30' -> '17:00' (slots are 30 minutes)."""
    h, m = (int(x) for x in hhmm.split(":"))
    total = (h * 60 + m + 30) % (24 * 60)
    return f"{total // 60:02d}:{total % 60:02d}"


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def run_stamp() -> str:
    """Filename-safe UTC stamp for per-run output files, e.g. 20260619T152001Z."""
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
