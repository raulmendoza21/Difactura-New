import logging
from pathlib import Path

import pytesseract
from PIL import Image

from app.config import settings
from app.utils.image_processing import preprocess_image

logger = logging.getLogger(__name__)

pytesseract.pytesseract.tesseract_cmd = settings.tesseract_path


class OCRService:
    """OCR service using Tesseract for scanned documents."""

    def __init__(self):
        self.language = settings.ocr_language

    def extract_text_from_image(self, image_path: str) -> str:
        path = Path(image_path)
        if not path.exists():
            raise FileNotFoundError(f"Image not found: {image_path}")

        image = Image.open(image_path)
        processed = preprocess_image(image)
        text = self._extract_best_text(processed)

        logger.info("OCR extracted %s chars from %s", len(text), path.name)
        return text.strip()

    def extract_text_from_pdf_pages(self, file_path: str) -> str:
        import fitz

        doc = fitz.open(file_path)
        all_text = []

        for page_num, page in enumerate(doc):
            mat = fitz.Matrix(300 / 72, 300 / 72)
            pix = page.get_pixmap(matrix=mat)
            img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)

            processed = preprocess_image(img)
            text = self._extract_best_text(processed)

            all_text.append(text.strip())
            logger.info("OCR page %s: %s chars", page_num + 1, len(text))

        doc.close()
        return "\n\n".join(all_text)

    def is_available(self) -> bool:
        try:
            version = pytesseract.get_tesseract_version()
            logger.info("Tesseract version: %s", version)
            return True
        except Exception:
            logger.warning("Tesseract not available")
            return False

    def _extract_best_text(self, image: Image.Image) -> str:
        best_text = ""
        best_score = float("-inf")

        for config in ("--oem 3 --psm 6", "--oem 3 --psm 4", "--oem 3 --psm 11"):
            text = pytesseract.image_to_string(
                image,
                lang=self.language,
                config=config,
            ).strip()
            score = self._score_text_quality(text)
            if score > best_score:
                best_score = score
                best_text = text

        return best_text

    def _score_text_quality(self, text: str) -> float:
        if not text:
            return float("-inf")

        compact = text.replace("\n", " ").strip()
        alnum = sum(ch.isalnum() for ch in compact)
        digit_count = sum(ch.isdigit() for ch in compact)
        line_count = max(1, len([line for line in text.splitlines() if line.strip()]))

        keyword_bonus = 0
        for keyword in ("factura", "fecha", "total", "iva", "base", "proveedor", "cliente"):
            if keyword in compact.lower():
                keyword_bonus += 20

        return alnum + digit_count * 2 + line_count * 3 + keyword_bonus


ocr_service = OCRService()
