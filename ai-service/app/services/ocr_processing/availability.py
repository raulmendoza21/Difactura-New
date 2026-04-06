from __future__ import annotations

import logging

import pytesseract

logger = logging.getLogger(__name__)


def is_tesseract_available() -> bool:
    try:
        version = pytesseract.get_tesseract_version()
        logger.info("Tesseract version: %s", version)
        return True
    except Exception:
        logger.warning("Tesseract not available")
        return False
