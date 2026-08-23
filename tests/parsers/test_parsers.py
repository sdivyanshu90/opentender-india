"""Unit tests: deterministic parsers (dates, amounts, text hygiene)."""

from datetime import datetime

import pytest

from scrapers.core.amounts import format_inr_compact, parse_amount, parse_plain_number
from scrapers.core.dates import parse_datetime
from scrapers.core.textutil import clean_text, safe_filename


class TestDates:
    @pytest.mark.parametrize("raw,expected", [
        ("05-Aug-2026 03:30 PM", datetime(2026, 8, 5, 15, 30)),
        ("05-Aug-2026", datetime(2026, 8, 5)),
        ("05/08/2026 15:30", datetime(2026, 8, 5, 15, 30)),
        ("05-08-2026", datetime(2026, 8, 5)),
        ("2026-08-05", datetime(2026, 8, 5)),
        ("5 Aug 2026", datetime(2026, 8, 5)),
    ])
    def test_formats(self, raw, expected):
        got = parse_datetime(raw)
        assert got is not None
        assert (got.year, got.month, got.day) == (expected.year, expected.month, expected.day)
        assert got.tzinfo is not None  # always IST-aware

    @pytest.mark.parametrize("raw", ["", None, "NA", "N/A", "not available", "garbage date ??"])
    def test_missing(self, raw):
        assert parse_datetime(raw) is None


class TestAmounts:
    @pytest.mark.parametrize("raw,expected", [
        ("Rs. 2.45 Cr", 24_500_000.0),
        ("₹ 2.45 crore", 24_500_000.0),
        ("INR 5 crores", 50_000_000.0),
        ("Rs 4.9 Lakhs", 490_000.0),
        ("₹ 4,90,000", 490_000.0),
        ("Estimated value: Rs.12,34,567 only", 1_234_567.0),
        ("Tender Value in Rupees 24,500,000", None),  # no currency marker -> plain parser's job
    ])
    def test_parse_amount(self, raw, expected):
        assert parse_amount(raw) == expected

    def test_plain_number_indian_format(self):
        assert parse_plain_number("24,50,000") == 2_450_000.0
        assert parse_plain_number("24500000") == 24_500_000.0

    def test_compact_formatting(self):
        assert format_inr_compact(24_500_000) == "₹2.45 Cr"
        assert format_inr_compact(490_000) == "₹4.90 L"


class TestText:
    def test_clean_text(self):
        assert clean_text(None) is None
        assert clean_text("  Hello&nbsp;&nbsp;world \n\n\n\nx ") == "Hello world\n\nx"
        long = clean_text("a" * 9000, max_len=100)
        assert len(long) == 101  # truncation marker appended

    @pytest.mark.parametrize("raw,expected", [
        ("../../etc/passwd", "passwd"),  # basename only: traversal neutralized
        ("NIT Document (final).pdf", "NIT_Document_final.pdf"),
        ("..", "download.bin"),
        ("", "download.bin"),
    ])
    def test_safe_filename(self, raw, expected):
        assert safe_filename(raw) == expected
