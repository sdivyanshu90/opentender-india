"""Deterministic Indian amount parsing (₹ / lakh / crore). AI is never used.

Internally everything is stored as raw INR floats; presentation (lakh/crore)
happens in the frontend.
"""

from __future__ import annotations

import re

LAKH = 100_000.0
CRORE = 10_000_000.0

_NUM = r"(?:\d{1,3}(?:,\d{2,3})*(?:\.\d+)?|\d+(?:\.\d+)?)"

_PATTERNS: tuple[tuple[re.Pattern[str], float], ...] = (
    # "Rs 2.45 Cr", "₹ 5 crore", "INR 1.2 crores"
    (re.compile(rf"(?:rs\.?|inr|₹)\s*({_NUM})\s*(crores?|cr\.?)\b", re.I), CRORE),
    (re.compile(rf"(?:rs\.?|inr|₹)\s*({_NUM})\s*(lakhs?|lac?s\.?)\b", re.I), LAKH),
    # "2.45 Crore" without currency marker
    (re.compile(rf"\b({_NUM})\s*crores?\b", re.I), CRORE),
    (re.compile(rf"\b({_NUM})\s*lakhs?\b", re.I), LAKH),
)

_PLAIN_PREFIXED = re.compile(rf"(?:rs\.?|inr|₹)\s*({_NUM})(?![a-z])", re.I)


def parse_amount(raw: str | None) -> float | None:
    """Extract a rupee amount from free text. Returns None when absent."""
    if not raw:
        return None
    text = raw.strip()
    if not text:
        return None
    for pattern, multiplier in _PATTERNS:
        m = pattern.search(text)
        if m:
            try:
                value = float(m.group(1).replace(",", ""))
            except ValueError:
                continue
            amount = value * multiplier
            if _plausible(amount):
                return round(amount, 2)
    m = _PLAIN_PREFIXED.search(text)
    if m:
        try:
            amount = float(m.group(1).replace(",", ""))
        except ValueError:
            return None
        if _plausible(amount):
            return amount
    return None


def parse_plain_number(raw: str | None) -> float | None:
    """Parse '12,34,567.89' style numbers already known to be rupees."""
    if not raw:
        return None
    text = raw.strip().replace("₹", "").replace("Rs.", "").replace("Rs", "")
    text = text.replace("INR", "").strip()
    if not re.fullmatch(_NUM, text):
        return None
    try:
        value = float(text.replace(",", ""))
    except ValueError:
        return None
    return value if _plausible(value) else None


def _plausible(amount: float) -> bool:
    """Sanity bound to avoid garbage parses: ₹100 .. ₹10,00,00,000 Cr."""
    return 0 < amount < 1e15


def format_inr_compact(amount: float | None) -> str | None:
    """Server-side convenience for feeds; UI does its own formatting."""
    if amount is None:
        return None
    if amount >= CRORE:
        return f"₹{amount / CRORE:.2f} Cr"
    if amount >= LAKH:
        return f"₹{amount / LAKH:.2f} L"
    return f"₹{amount:,.0f}"
