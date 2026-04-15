"""Mistral OCR — upload file, run OCR, get text. Primary OCR provider."""

from __future__ import annotations

import logging
import re
from pathlib import Path

from app.config import settings

logger = logging.getLogger(__name__)


def is_available() -> bool:
    if not settings.mistral_api_key:
        return False
    try:
        _create_client()
        return True
    except Exception:
        return False


def extract_text(file_path: str) -> str:
    """Run Mistral OCR on a file. Returns plain text."""
    path = Path(file_path)
    if not path.exists():
        raise FileNotFoundError(f"File not found: {file_path}")

    client = _create_client()
    file_id: str | None = None

    try:
        # Upload
        with open(path, "rb") as handle:
            payload = {"file_name": path.name, "content": handle}
            try:
                upload_resp = client.files.upload(file=payload, purpose="ocr", visibility="workspace")
            except TypeError:
                upload_resp = client.files.upload(file=payload, purpose="ocr")

        file_id = str(getattr(upload_resp, "id", "") or upload_resp.get("id", ""))
        if not file_id:
            raise RuntimeError("Mistral no devolvió file_id")

        # OCR
        ocr_resp = client.ocr.process(
            model=settings.mistral_ocr_model,
            document={"file_id": file_id},
            extract_header=True,
            extract_footer=True,
            table_format="markdown",
        )

        return _response_to_text(ocr_resp)

    finally:
        if file_id:
            try:
                client.files.delete(file_id=file_id)
            except Exception:
                pass


def _create_client():
    import importlib
    try:
        mod = importlib.import_module("mistralai")
    except ImportError as exc:
        raise RuntimeError("mistralai not installed") from exc

    cls = getattr(mod, "Mistral", None)
    if cls is None:
        raise RuntimeError("Could not find Mistral client class")
    return cls(api_key=settings.mistral_api_key, server_url=settings.mistral_base_url)


def _response_to_text(response) -> str:
    """Extract plain text from Mistral OCR response."""
    resp = _to_dict(response)
    pages = resp.get("pages", []) or []
    parts: list[str] = []

    for page in pages:
        page_map = _to_dict(page)
        md = str(page_map.get("markdown", "") or "").strip()

        # Expand table references
        for table in (page_map.get("tables", []) or []):
            t = _to_dict(table)
            tid = str(t.get("id", "") or "").strip()
            content = _table_to_text(t)
            if tid and content:
                md = md.replace(f"[{tid}]({tid})", content)

        # Include header/footer if they have useful data
        header = str(page_map.get("header", "") or "").strip()
        footer = str(page_map.get("footer", "") or "").strip()

        sections = []
        if header and _normalize(header) not in _normalize(md):
            sections.append(header)
        sections.append(md)
        if footer and _normalize(footer) not in _normalize("\n".join(sections)):
            sections.append(footer)

        parts.append("\n".join(s for s in sections if s))

    raw = "\n\n".join(parts).strip()
    return _strip_markdown(raw)


def _table_to_text(table: dict) -> str:
    content = str(table.get("content", "") or "").strip()
    if not content:
        return ""
    lines = []
    for line in content.splitlines():
        line = line.strip()
        if not line or re.fullmatch(r"\|\s*[-:\s|]+\|?", line):
            continue
        if "|" in line:
            cells = [c.strip() for c in line.strip("|").split("|") if c.strip() and c.strip() != "---"]
            lines.extend(cells)
        else:
            lines.append(line)
    return "\n".join(lines)


def _normalize(text: str) -> str:
    return re.sub(r"[^A-Z0-9]", "", text.upper())


def _strip_markdown(text: str) -> str:
    """Remove markdown formatting that Mistral OCR injects."""
    lines = text.split("\n")
    cleaned: list[str] = []
    for line in lines:
        # Remove heading markers
        line = re.sub(r"^#{1,6}\s+", "", line)
        # Remove bold/italic
        line = re.sub(r"\*{1,3}(.+?)\*{1,3}", r"\1", line)
        # Remove markdown links [text](url)
        line = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", line)
        # Remove image refs ![alt](url)
        line = re.sub(r"!\[[^\]]*\]\([^)]+\)", "", line)
        # Remove horizontal rules
        if re.fullmatch(r"[-*_]{3,}\s*", line):
            continue
        cleaned.append(line)
    return "\n".join(cleaned)


def _to_dict(obj) -> dict:
    if isinstance(obj, dict):
        return obj
    if hasattr(obj, "model_dump"):
        return obj.model_dump()
    if hasattr(obj, "__dict__"):
        return obj.__dict__
    return {}
