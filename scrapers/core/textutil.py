"""Text hygiene for scraped content. All portal text is untrusted."""

from __future__ import annotations

import html
import re

_CTRL = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")
_WS = re.compile(r"[ \t\r\f\v]+")
_MULTINEWLINE = re.compile(r"\n{3,}")


def clean_text(raw: str | None, *, max_len: int = 8000) -> str | None:
    """Normalize whitespace and entities; truncate defensively."""
    if raw is None:
        return None
    text = html.unescape(html.unescape(str(raw)))
    text = text.replace("\u00a0", " ")  # &nbsp;
    text = _CTRL.sub(" ", text)
    text = _WS.sub(" ", text)
    text = re.sub(r" ?\n ?", "\n", text)
    text = _MULTINEWLINE.sub("\n\n", text).strip()
    if len(text) > max_len:
        text = text[:max_len].rstrip() + "…"
    return text or None


def safe_filename(name: str) -> str:
    """Neutralize path traversal / hostile filenames from portals."""
    name = name.replace("\\", "/").split("/")[-1]
    name = re.sub(r"[^A-Za-z0-9._-]+", "_", name)
    name = re.sub(r"_+", "_", name).strip("._")
    name = re.sub(r"_(?=\.)|(?<=\.)_", "", name)
    if not name or name in {".", ".."}:
        name = "download.bin"
    return name[:180]


def looks_like_url(value: str) -> bool:
    return value.startswith(("http://", "https://"))
