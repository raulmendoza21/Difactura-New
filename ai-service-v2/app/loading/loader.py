"""Document loader — Mistral OCR primary, Tesseract/Paddle fallback."""

from __future__ import annotations

import logging
from pathlib import Path

logger = logging.getLogger(__name__)


def load_document(file_path: str, mime_type: str = "") -> dict:
    """Load a document and return raw text + metadata.

    Returns dict with keys: text, pages, is_digital, source.
    """
    path = Path(file_path)
    if not path.exists():
        raise FileNotFoundError(f"File not found: {file_path}")

    mime = (mime_type or "").lower()
    ext = path.suffix.lower()

    is_pdf = mime == "application/pdf" or ext == ".pdf"
    is_image = mime.startswith("image/") or ext in {".png", ".jpg", ".jpeg", ".tiff", ".tif"}

    if not is_pdf and not is_image:
        raise ValueError(f"Unsupported file type: {ext} ({mime})")

    # Strategy 1: For PDFs, try digital text first
    if is_pdf:
        digital = _extract_pdf_digital(file_path)
        if digital["is_digital"] and len(digital["text"].strip()) > 50:
            logger.info("PDF digital text: %d chars, %d pages", len(digital["text"]), digital["pages"])
            return digital

    # Strategy 2: Mistral OCR (best quality for scanned docs and images)
    mistral_text = _try_mistral_ocr(file_path)
    if mistral_text:
        pages = _count_pdf_pages(file_path) if is_pdf else 1
        logger.info("Mistral OCR: %d chars", len(mistral_text))
        return {"text": mistral_text, "pages": pages, "is_digital": False, "source": "mistral_ocr"}

    # Strategy 3: Tesseract/Paddle OCR fallback
    if is_pdf:
        ocr_text = _ocr_pdf(file_path)
        pages = _count_pdf_pages(file_path)
    else:
        ocr_text = _ocr_image(file_path)
        pages = 1

    source = "tesseract_ocr" if ocr_text else "none"
    logger.info("Local OCR: %d chars", len(ocr_text))
    return {"text": ocr_text, "pages": pages, "is_digital": False, "source": source}


def _try_mistral_ocr(file_path: str) -> str:
    """Try Mistral OCR. Returns text or empty string on failure."""
    try:
        from app.loading.mistral_ocr import extract_text, is_available
        if not is_available():
            logger.debug("Mistral OCR not configured (no API key)")
            return ""
        return extract_text(file_path)
    except Exception as exc:
        logger.warning("Mistral OCR failed: %s", exc)
        return ""


def _extract_pdf_digital(file_path: str) -> dict:
    """Extract embedded text from a digital PDF."""
    import fitz

    doc = fitz.open(file_path)
    pages_text: list[str] = []

    for page in doc:
        blocks = page.get_text("blocks")
        if blocks:
            ordered = sorted(blocks, key=lambda b: (round(b[1], 1), round(b[0], 1)))
            text = "\n".join((b[4] or "").strip() for b in ordered if (b[4] or "").strip())
        else:
            text = page.get_text("text").strip()
        pages_text.append(text)

    doc.close()
    full_text = "\n\n".join(pages_text)
    avg_chars = len(full_text.replace(" ", "").replace("\n", "")) / max(len(pages_text), 1)
    is_digital = avg_chars > 50

    return {"text": full_text, "pages": len(pages_text), "is_digital": is_digital, "source": "pdf"}


def _count_pdf_pages(file_path: str) -> int:
    try:
        import fitz
        doc = fitz.open(file_path)
        n = len(doc)
        doc.close()
        return n
    except Exception:
        return 1


def _ocr_image(file_path: str) -> str:
    from app.loading.ocr import run_ocr
    return run_ocr(file_path)


def _ocr_pdf(file_path: str) -> str:
    import fitz
    from app.loading.ocr import run_ocr_on_pil_image

    doc = fitz.open(file_path)
    pages_text: list[str] = []

    for page in doc:
        pix = page.get_pixmap(dpi=300)
        from PIL import Image
        img = Image.frombytes("RGB", (pix.width, pix.height), pix.samples)
        text = run_ocr_on_pil_image(img)
        pages_text.append(text)

    doc.close()
    return "\n\n".join(pages_text)
