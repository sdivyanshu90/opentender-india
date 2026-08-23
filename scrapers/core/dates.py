"""Deterministic Indian date parsing. AI is never used for dates."""

from __future__ import annotations

import re
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

IST = ZoneInfo("Asia/Kolkata")

# Common formats on Indian procurement portals.
_FORMATS = (
    "%d-%b-%Y %I:%M %p",  # 05-Aug-2026 03:30 PM
    "%d-%b-%Y %H:%M",
    "%d-%b-%Y",
    "%d/%m/%Y %I:%M %p",
    "%d/%m/%Y %H:%M",
    "%d/%m/%Y",
    "%d-%m-%Y %I:%M %p",
    "%d-%m-%Y %H:%M",
    "%d-%m-%Y",
    "%d.%m.%Y %H:%M",
    "%d.%m.%Y",
    "%Y-%m-%d %H:%M:%S",
    "%Y-%m-%d %H:%M",
    "%Y-%m-%d",
    "%d %b %Y %I:%M %p",
    "%d %b %Y",
    "%d %B %Y",
)

_WS = re.compile(r"\s+")


def parse_datetime(raw: str | None) -> datetime | None:
    """Parse a portal datetime string into an IST-aware datetime.

    Naive results are assumed to be Asia/Kolkata (all target portals are).
    Returns None for empty/unparseable input - never guesses.
    """
    if not raw:
        return None
    text = _WS.sub(" ", raw.strip())
    if not text or text.lower() in {"na", "n/a", "not available", "-"}:
        return None
    for fmt in _FORMATS:
        try:
            dt = datetime.strptime(text, fmt)
        except ValueError:
            continue
        return dt.replace(tzinfo=IST)
    # ISO with offset already?
    try:
        return datetime.fromisoformat(text)
    except ValueError:
        return None


def now_ist() -> datetime:
    return datetime.now(tz=IST)


def days_until(dt: datetime, *, ref: datetime | None = None) -> int:
    ref = ref or now_ist()
    return (dt - ref).days


def month_start(dt: datetime) -> datetime:
    return dt.replace(day=1, hour=0, minute=0, second=0, microsecond=0)


def shift_days(dt: datetime, days: int) -> datetime:
    return dt + timedelta(days=days)
