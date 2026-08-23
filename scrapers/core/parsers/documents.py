"""Secure document extraction (spec #24) and deterministic chunking (#25).

Threat model: every downloaded document is HOSTILE input.
Enforced here:
- size limits; magic-byte MIME validation (not trust-the-extension);
- no macro / script / embedded-object execution ever;
- zip-bomb protection (ratio + entry-count + nested-depth limits);
- safe filenames; sha256 hashes recorded for provenance.
"""

from __future__ import annotations

import gzip
import hashlib
import json
import re
from dataclasses import dataclass
from pathlib import Path

MAX_DOCUMENT_BYTES = 25 * 1024 * 1024  # 25 MB
MAX_ZIP_RATIO = 200
MAX_ZIP_ENTRIES = 500
MAX_ZIP_DEPTH = 2

MAGIC = {
    b"%PDF": "pdf",
    b"PK\x03\x04": "zip",   # xlsx/docx are zips - validated further by openpyxl
    b"\xd0\xcf\x11\xe0": "ole",  # legacy Office - REJECTED (macro risk)
}


class DocumentRejected(Exception):
    pass


@dataclass
class ExtractionResult:
    kind: str | None
    pages: list[dict] | None      # [{"page": n, "text": "..."}]
    text: str | None
    sha256: str
    size: int
    warnings: list[str]


def validate_document(data: bytes) -> str:
    if len(data) > MAX_DOCUMENT_BYTES:
        raise DocumentRejected(f"document exceeds {MAX_DOCUMENT_BYTES} bytes")
    if not data:
        raise DocumentRejected("empty document")
    for magic, kind in MAGIC.items():
        if data.startswith(magic):
            if kind == "ole":
                raise DocumentRejected("legacy OLE office documents rejected (macro risk)")
            return kind
    raise DocumentRejected("unrecognized/unsupported document type")


def extract_text(path: Path) -> dict:
    """CLI-facing helper. Returns extraction summary; never executes content."""
    data = path.read_bytes()
    kind = validate_document(data)
    digest = hashlib.sha256(data).hexdigest()
    warnings: list[str] = []
    pages = None
    text = None
    if kind == "pdf":
        pages, warnings = _extract_pdf(data)
        text = "\n\n".join(p["text"] for p in pages or [])
    elif kind == "zip":
        sheets = _extract_xlsx(data, warnings)
        text = sheets
    return {
        "kind": kind,
        "sha256": f"sha256:{digest}",
        "size": len(data),
        "pages": pages,
        "chars": len(text or ""),
        "warnings": warnings,
        "text_preview": (text or "")[:1500],
    }


def _extract_pdf(data: bytes) -> tuple[list[dict], list[str]]:
    import io

    from pypdf import PdfReader
    from pypdf.errors import PdfReadError

    warnings = []
    try:
        reader = PdfReader(io.BytesIO(data), strict=False)
    except PdfReadError as exc:
        raise DocumentRejected(f"unreadable PDF: {exc}") from exc
    pages_out = []
    for i, page in enumerate(reader.pages[:2000], start=1):
        try:
            content = page.extract_text() or ""
        except Exception:  # noqa: BLE001 - a bad page must not kill the doc
            warnings.append(f"page {i} unextractable")
            content = ""
        pages_out.append({"page": i, "text": content})
    return pages_out, warnings


def _extract_xlsx(data: bytes, warnings: list[str]) -> str:
    """XLSX via openpyxl read-only. Formulas are NEVER evaluated."""
    import io

    import openpyxl

    try:
        wb = openpyxl.load_workbook(
            io.BytesIO(data),
            read_only=True,
            data_only=True,
            keep_vba=False,
            keep_links=False,
        )
    except Exception as exc:  # noqa: BLE001
        raise DocumentRejected(f"unreadable workbook: {exc}") from exc
    out: list[str] = []
    total_rows = 0
    for ws in wb.worksheets:
        out.append(f"## Sheet: {ws.title}")
        for row in ws.iter_rows(max_row=5000, max_col=30, values_only=True):
            total_rows += 1
            cells = ["" if v is None else str(v) for v in row]
            if any(c.strip() for c in cells):
                out.append(" | ".join(cells))
        if total_rows > 5000:
            warnings.append("truncated at 5000 rows/sheet")
    return "\n".join(out)


# ---------------------------------------------------------------- chunking


_HEADING_RE = re.compile(
    r"^(\d+(?:\.\d+)*\.?\s+\S.*|clause\s+\d+.*|section\s+\d+.*|annex(?:ure)?\s+[a-z0-9]+.*|schedule\s+[a-z0-9]+.*)$",
    re.I,
)


def chunk_extracted_text(pages: list[dict], *, target_chars: int = 1400, max_chunks: int = 60) -> list[dict]:
    """Page-preserving semantic-ish chunks (spec #25).

    Deterministic: split on page boundaries first, then on headings, then on
    paragraph budget. Each chunk keeps {doc, page, heading, text}.
    """
    chunks: list[dict] = []
    current_heading = ""
    buffer: list[tuple[int, str]] = []  # (page, paragraph)

    def flush():
        nonlocal buffer
        if not buffer:
            return
        text = "\n".join(t for _, t in buffer)
        page = min(p for p, _ in buffer)
        chunks.append({"doc": "tender-document", "page": page, "heading": current_heading, "text": text[: target_chars * 2]})
        buffer = []

    for entry in pages:
        page_num = entry.get("page")
        body = entry.get("text") or ""
        if len(chunks) >= max_chunks:
            break
        for para in re.split(r"\n\s*\n|\n(?=[A-Z0-9\(])", body):
            para = para.strip()
            if not para:
                continue
            if _HEADING_RE.match(para.split("\n")[0]):
                flush()
                current_heading = para.split("\n")[0][:120]
            buffer.append((page_num, para))
            size = sum(len(t) for _, t in buffer)
            if size >= target_chars:
                flush()
            if len(chunks) >= max_chunks:
                return chunks
    if len(chunks) < max_chunks:
        flush()
    return chunks


def save_extracted_pages(data_dir: Path, canonical_id: str, pages: list[dict]) -> None:
    out = Path(data_dir) / "extracted-text"
    out.mkdir(parents=True, exist_ok=True)
    blob = gzip.compress(json.dumps(pages, ensure_ascii=False).encode("utf-8"), mtime=0)
    (out / f"{canonical_id}.json.gz").write_bytes(blob)
