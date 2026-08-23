"""Security tests for the hostile-document pipeline (ADR-011)."""

import io
import zipfile
from pathlib import Path

import pytest

from scrapers.core.parsers.documents import (
    DocumentRejected,
    chunk_extracted_text,
    extract_text,
)


def xlsx_bytes() -> bytes:
    """Minimal valid xlsx built with openpyxl."""
    import openpyxl

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "BOQ"
    ws.append(["Item", "Description", "Qty", "Unit"])
    ws.append([1, "Excavation in ordinary soil", 120.5, "cum"])
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


def extract_text_bytes(data: bytes, tmp_path: Path) -> dict:
    """tmp_path is pytest's per-test temp dir (never a shared /tmp path)."""
    p = tmp_path / "doc.bin"
    p.write_bytes(data)
    return extract_text(p)


class TestValidation:
    def test_rejects_empty_and_oversize(self, tmp_path: Path):
        with pytest.raises(DocumentRejected):
            extract_text_bytes(b"", tmp_path)
        huge = b"%PDF-1.4" + b"x" * (26 * 1024 * 1024)
        with pytest.raises(DocumentRejected):
            extract_text_bytes(huge, tmp_path)

    def test_rejects_ole_macros(self, tmp_path: Path):
        ole = b"\xd0\xcf\x11\xe0" + b"A" * 1000  # legacy OLE header: macro carrier
        with pytest.raises(DocumentRejected):
            extract_text_bytes(ole, tmp_path)

    def test_rejects_unknown_type(self, tmp_path: Path):
        with pytest.raises(DocumentRejected):
            extract_text_bytes(b"just text, not a document", tmp_path)


class TestXlsxExtraction:
    def test_values_extracted(self, tmp_path: Path):
        result = extract_text_bytes(xlsx_bytes(), tmp_path)
        assert result["kind"] == "zip"
        assert "Excavation in ordinary soil" in result["text_preview"]

    def test_zip_bomb_ratio_guard(self, tmp_path: Path):
        bomb = io.BytesIO()
        with zipfile.ZipFile(bomb, "w", zipfile.ZIP_DEFLATED) as zf:
            zf.writestr("huge.xml", b"0" * (60 * 1024 * 1024))
        data = bomb.getvalue()
        if len(data) * 200 < 60 * 1024 * 1024:
            # only assert when the expansion ratio genuinely exceeds the guard
            with pytest.raises((DocumentRejected, Exception)):
                extract_text_bytes(data, tmp_path)


class TestChunking:
    def test_page_boundaries_preserved(self):
        pages = [
            {"page": 3, "text": "Clause 4.2 Turnover\nAverage annual turnover shall be Rs 5 crore.\n\nGeneral conditions apply."},
            {"page": 4, "text": "Section 7 EMD\nEMD shall be Rs 1 lakh via bank guarantee."},
        ]
        chunks = chunk_extracted_text(pages, target_chars=50)
        pages_in_chunks = {c["page"] for c in chunks}
        assert pages_in_chunks == {3, 4}
        joined = " ".join(c["text"] for c in chunks).lower()
        assert "turnover" in joined and "emd" in joined

    def test_max_chunks_cap(self):
        pages = [{"page": i + 1, "text": f"Clause {i}.1 filler text. " * 40} for i in range(100)]
        chunks = chunk_extracted_text(pages, max_chunks=10)
        assert len(chunks) <= 10
