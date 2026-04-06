import logging

import pytesseract
from PIL import Image

from app.config import settings
from app.services.ocr_processing.availability import is_tesseract_available
from app.services.ocr_processing.image_flow import (
    extract_image_ocr,
    extract_text_from_image,
)
from app.services.ocr_processing.paddle import extract_paddle_image_ocr, get_paddle_ocr
from app.services.ocr_processing.pdf_flow import (
    extract_pdf_ocr,
    extract_text_from_pdf_pages,
)
from app.services.ocr_processing.region_hint_flow import extract_region_hints
from app.services.ocr_processing.region_hints import (
    cleanup_hint_text,
    extract_image_region_hints,
    extract_pdf_region_hints,
    extract_region_hints_from_image,
    is_region_hint_usable,
    normalize_region_hint_text,
    region_hint_bonus,
)
from app.services.ocr_processing.shared import OCR_CONFIGS, bbox_from_polygon, get_ocr_configs, is_fast_photo_result_usable, score_ocr_candidate
from app.services.ocr_processing.tesseract import extract_best_text_from_variants, run_ocr_candidate

logger = logging.getLogger(__name__)

pytesseract.pytesseract.tesseract_cmd = settings.tesseract_path


class OCRService:
    """OCR service facade with OCR-specific responsibilities delegated to submodules."""

    OCR_CONFIGS = OCR_CONFIGS

    def __init__(self):
        self.language = settings.ocr_language
        self._paddle_ocr = None
        self._paddle_ocr_import_error = None

    def extract_text_from_image(self, image_path: str, input_kind: str = "image_scan") -> str:
        return extract_text_from_image(self, image_path, input_kind=input_kind)

    def extract_image_ocr(self, image_path: str, input_kind: str = "image_scan") -> dict:
        return extract_image_ocr(self, image_path, input_kind=input_kind)

    def extract_text_from_pdf_pages(self, file_path: str, input_kind: str = "pdf_scanned") -> str:
        return extract_text_from_pdf_pages(self, file_path, input_kind=input_kind)

    def extract_pdf_ocr(self, file_path: str, input_kind: str = "pdf_scanned") -> dict:
        return extract_pdf_ocr(self, file_path, input_kind=input_kind)

    def extract_region_hints(self, file_path: str, input_kind: str = "pdf_scanned", max_pages: int = 1) -> list[dict]:
        return extract_region_hints(self, file_path, input_kind=input_kind, max_pages=max_pages)

    def is_available(self) -> bool:
        return is_tesseract_available()

    def _extract_best_text_from_variants(self, image: Image.Image, input_kind: str) -> dict:
        return extract_best_text_from_variants(image, input_kind=input_kind, language=self.language)

    def _get_ocr_configs(self, input_kind: str) -> tuple[str, ...]:
        return get_ocr_configs(input_kind)

    def _is_fast_photo_result_usable(self, result: dict | None) -> bool:
        return is_fast_photo_result_usable(result)

    def _extract_paddle_image_ocr(self, image_path: str) -> dict:
        return extract_paddle_image_ocr(self, image_path)

    def _get_paddle_ocr(self):
        return get_paddle_ocr(self)

    def _extract_pdf_region_hints(self, file_path: str, *, input_kind: str, max_pages: int) -> list[dict]:
        return extract_pdf_region_hints(self, file_path, input_kind=input_kind, max_pages=max_pages)

    def _extract_image_region_hints(self, image_path: str, *, input_kind: str) -> list[dict]:
        return extract_image_region_hints(self, image_path, input_kind=input_kind)

    def _extract_region_hints_from_image(self, image: Image.Image, *, page_number: int, input_kind: str) -> list[dict]:
        return extract_region_hints_from_image(self, image, page_number=page_number, input_kind=input_kind)

    def _cleanup_hint_text(self, text: str) -> str:
        return cleanup_hint_text(text)

    def _normalize_region_hint_text(self, region_type: str, text: str) -> str:
        return normalize_region_hint_text(region_type, text)

    def _region_hint_bonus(self, region_type: str, text: str) -> float:
        return region_hint_bonus(region_type, text)

    def _is_region_hint_usable(self, region_type: str, text: str) -> bool:
        return is_region_hint_usable(region_type, text)

    def _run_ocr_candidate(self, image: Image.Image, config: str):
        return run_ocr_candidate(image, config, language=self.language)

    def _bbox_from_polygon(self, polygon):
        return bbox_from_polygon(polygon)

    def _score_ocr_candidate(self, text: str, confidences: list[float]) -> float:
        return score_ocr_candidate(text, confidences)


ocr_service = OCRService()
