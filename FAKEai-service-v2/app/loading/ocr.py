"""OCR wrapper — Tesseract primary, Paddle fallback."""

from __future__ import annotations

import logging
import tempfile
import os

import pytesseract
from PIL import Image

from app.config import settings

logger = logging.getLogger(__name__)

pytesseract.pytesseract.tesseract_cmd = settings.tesseract_path


def run_ocr(image_path: str) -> str:
    """Run OCR on an image file. Returns extracted text."""
    img = Image.open(image_path)
    return run_ocr_on_pil_image(img)


def run_ocr_on_pil_image(img: Image.Image) -> str:
    """Run OCR on a PIL Image. Tesseract first, Paddle as fallback."""
    # Convert to RGB to avoid format issues with RGBA, CMYK, etc.
    if img.mode not in ("RGB", "L"):
        img = img.convert("RGB")

    text = _tesseract_ocr(img)
    if len(text.strip()) < 20 and settings.paddle_ocr_enabled:
        paddle_text = _paddle_ocr(img)
        if len(paddle_text.strip()) > len(text.strip()):
            return paddle_text
    return text


def _tesseract_ocr(img: Image.Image) -> str:
    try:
        return pytesseract.image_to_string(img, lang=settings.ocr_language).strip()
    except Exception as exc:
        logger.warning("Tesseract failed: %s", exc)
        return ""


# Singleton PaddleOCR instance
_paddle_instance = None
_paddle_init_error = None


def _get_paddle():
    global _paddle_instance, _paddle_init_error
    if _paddle_instance is not None:
        return _paddle_instance
    if _paddle_init_error is not None:
        return None
    try:
        from paddleocr import PaddleOCR
        _paddle_instance = PaddleOCR(
            use_doc_orientation_classify=False,
            use_doc_unwarping=False,
            use_textline_orientation=False,
            text_detection_model_name="PP-OCRv5_mobile_det",
            text_recognition_model_name="latin_PP-OCRv5_mobile_rec",
        )
        return _paddle_instance
    except Exception as exc:
        _paddle_init_error = exc
        logger.warning("PaddleOCR unavailable: %s", exc)
        return None


def _paddle_ocr(img: Image.Image) -> str:
    try:
        ocr = _get_paddle()
        if ocr is None:
            return ""

        # PaddleOCR v3.x uses predict() with a file path
        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp:
            img.save(tmp, format="PNG")
            tmp_path = tmp.name

        try:
            pages = list(ocr.predict(tmp_path))
        finally:
            os.unlink(tmp_path)

        if not pages:
            return ""

        page = pages[0]
        texts = [t.strip() for t in (page.get("rec_texts") or []) if str(t).strip()]
        return "\n".join(texts)
    except Exception as exc:
        logger.warning("PaddleOCR failed: %s", exc)
        return ""
