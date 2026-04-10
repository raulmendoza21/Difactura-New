"""Convert PDF pages or images to base64 PNG for Vision API."""

from __future__ import annotations

import base64
import io
import logging
from pathlib import Path

logger = logging.getLogger(__name__)


def file_to_images(file_path: str, dpi: int = 150, max_pages: int = 8) -> list[str]:
    """Return list of base64-encoded PNG strings, one per page/image.

    Handles: PDF (all pages), PNG, JPEG, TIFF, WEBP.
    DPI 150 = good balance quality vs token cost (~1,500 tokens/page).
    DPI 200 = higher quality (~2,500 tokens/page).
    """
    path = Path(file_path)
    ext = path.suffix.lower()

    if ext == ".pdf":
        return _pdf_to_images(file_path, dpi=dpi, max_pages=max_pages)
    else:
        return [_image_file_to_b64(file_path)]


def _pdf_to_images(file_path: str, dpi: int, max_pages: int) -> list[str]:
    import fitz  # PyMuPDF

    doc = fitz.open(file_path)
    pages = min(len(doc), max_pages)
    if len(doc) > max_pages:
        logger.warning("PDF has %d pages, processing first %d", len(doc), max_pages)

    zoom = dpi / 72.0
    mat = fitz.Matrix(zoom, zoom)
    result: list[str] = []

    for i in range(pages):
        pix = doc[i].get_pixmap(matrix=mat)
        png_bytes = pix.tobytes("png")
        result.append(base64.b64encode(png_bytes).decode("utf-8"))

    return result


def _image_file_to_b64(file_path: str) -> str:
    """Load an image, normalise to PNG, return base64 string."""
    from PIL import Image

    with Image.open(file_path) as img:
        img = img.convert("RGB")
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        return base64.b64encode(buf.getvalue()).decode("utf-8")
