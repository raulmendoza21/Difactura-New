"""Convert PDF pages or images to base64 PNG for Vision API."""

from __future__ import annotations

import base64
import io
import logging
from pathlib import Path

logger = logging.getLogger(__name__)


def file_to_images(file_path: str, dpi: int = 300, max_pages: int = 8) -> list[str]:
    """Return list of base64-encoded PNG strings, one per page/image.

    Handles: PDF (all pages), PNG, JPEG, TIFF, WEBP.
    DPI 300 = maximum quality for accurate OCR (~3,500 tokens/page).
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
    """Load an image, apply EXIF rotation + mild enhancement, return base64 PNG string.

    Applied enhancements (conservative, won't hurt clean scans):
    - EXIF auto-rotation: fixes phone photos taken in portrait but tagged as landscape.
    - Sharpness ×1.35: helps with slightly out-of-focus photos.
    - Contrast ×1.15: lifts washed-out receipts / low-light shots.
    - Minimum resolution: if narrower than 1200 px, upscale ×2 so Vision API has
      enough detail. Clean scans are already well above this threshold.
    """
    from PIL import Image, ImageEnhance, ImageOps

    with Image.open(file_path) as img:
        # 1. Correct orientation from EXIF data (phone photos)
        img = ImageOps.exif_transpose(img)
        img = img.convert("RGB")

        # 2. Upscale only if too small (phone photo at minimum resolution)
        width, height = img.size
        if width < 1200:
            scale = 2
            img = img.resize((width * scale, height * scale), Image.LANCZOS)
            logger.debug("Upscaled image from %dx%d to %dx%d", width, height, width * scale, height * scale)

        # 3. Cap maximum dimension at 2048px — OpenAI Vision with detail=high
        #    always rescales to ~1024px anyway; sending huge originals wastes time.
        width, height = img.size
        max_dim = 2048
        if max(width, height) > max_dim:
            ratio = max_dim / max(width, height)
            new_w, new_h = int(width * ratio), int(height * ratio)
            img = img.resize((new_w, new_h), Image.LANCZOS)
            logger.debug("Downscaled image from %dx%d to %dx%d", width, height, new_w, new_h)

        # 4. Mild sharpness enhancement — helps text legibility in soft photos
        img = ImageEnhance.Sharpness(img).enhance(1.35)

        # 4. Mild contrast boost — helps washed-out receipts and low-light shots
        img = ImageEnhance.Contrast(img).enhance(1.15)

        buf = io.BytesIO()
        img.save(buf, format="PNG", optimize=False)
        return base64.b64encode(buf.getvalue()).decode("utf-8")
