import logging
import re
from pathlib import Path

import pytesseract
from PIL import Image

from app.config import settings
from app.utils.image_processing import build_ocr_variants

logger = logging.getLogger(__name__)

pytesseract.pytesseract.tesseract_cmd = settings.tesseract_path


class OCRService:
    """OCR service using Tesseract and PaddleOCR for scanned documents."""

    OCR_CONFIGS = ("--oem 3 --psm 6", "--oem 3 --psm 4", "--oem 3 --psm 11")

    def __init__(self):
        self.language = settings.ocr_language
        self._paddle_ocr = None
        self._paddle_ocr_import_error = None

    def extract_text_from_image(self, image_path: str, input_kind: str = "image_scan") -> str:
        return self.extract_image_ocr(image_path, input_kind=input_kind)["text"]

    def extract_image_ocr(self, image_path: str, input_kind: str = "image_scan") -> dict:
        path = Path(image_path)
        if not path.exists():
            raise FileNotFoundError(f"Image not found: {image_path}")

        paddle_result = None
        if input_kind == "image_photo" and settings.paddle_ocr_enabled:
            paddle_result = self._extract_paddle_image_ocr(image_path)
            if self._is_fast_photo_result_usable(paddle_result):
                logger.info(
                    "OCR extracted %s chars from %s using %s",
                    len(paddle_result["text"]),
                    path.name,
                    paddle_result["variant_name"],
                )
                return paddle_result

        with Image.open(image_path) as image:
            tesseract_result = self._extract_best_text_from_variants(image, input_kind=input_kind)

        candidates = [tesseract_result]
        if paddle_result and paddle_result["text"]:
            candidates.append(paddle_result)

        result = max(candidates, key=lambda item: item["score"])
        logger.info(
            "OCR extracted %s chars from %s using %s",
            len(result["text"]),
            path.name,
            result["variant_name"],
        )
        return result

    def extract_text_from_pdf_pages(self, file_path: str, input_kind: str = "pdf_scanned") -> str:
        return self.extract_pdf_ocr(file_path, input_kind=input_kind)["text"]

    def extract_pdf_ocr(self, file_path: str, input_kind: str = "pdf_scanned") -> dict:
        import fitz

        doc = fitz.open(file_path)
        all_text: list[str] = []
        preprocessing_steps = ["pdf_page_render"]
        best_variant_name = ""

        try:
            for page_num, page in enumerate(doc):
                mat = fitz.Matrix(300 / 72, 300 / 72)
                pix = page.get_pixmap(matrix=mat)
                img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
                result = self._extract_best_text_from_variants(img, input_kind=input_kind)

                all_text.append(result["text"].strip())
                for step in result["preprocessing_steps"]:
                    if step not in preprocessing_steps:
                        preprocessing_steps.append(step)
                best_variant_name = result["variant_name"] or best_variant_name
                logger.info(
                    "OCR page %s: %s chars using %s",
                    page_num + 1,
                    len(result["text"]),
                    result["variant_name"],
                )
        finally:
            doc.close()

        return {
            "text": "\n\n".join(filter(None, all_text)).strip(),
            "preprocessing_steps": preprocessing_steps,
            "variant_name": best_variant_name,
            "ocr_engine": "tesseract",
        }

    def is_available(self) -> bool:
        try:
            version = pytesseract.get_tesseract_version()
            logger.info("Tesseract version: %s", version)
            return True
        except Exception:
            logger.warning("Tesseract not available")
            return False

    def _extract_best_text_from_variants(self, image: Image.Image, input_kind: str) -> dict:
        best_result = {
            "text": "",
            "score": float("-inf"),
            "variant_name": "",
            "preprocessing_steps": [],
            "ocr_engine": "tesseract",
        }

        for variant in build_ocr_variants(image, input_kind=input_kind):
            for config in self._get_ocr_configs(input_kind):
                text, confidences = self._run_ocr_candidate(variant["image"], config)
                score = self._score_ocr_candidate(text, confidences)
                if score > best_result["score"]:
                    best_result = {
                        "text": text.strip(),
                        "score": score,
                        "variant_name": variant["name"],
                        "preprocessing_steps": variant["preprocessing_steps"],
                        "ocr_engine": "tesseract",
                    }

        return best_result

    def _get_ocr_configs(self, input_kind: str) -> tuple[str, ...]:
        if input_kind == "image_photo":
            return ("--oem 3 --psm 6", "--oem 3 --psm 4")
        return self.OCR_CONFIGS

    def _is_fast_photo_result_usable(self, result: dict | None) -> bool:
        if not result or not result.get("text"):
            return False

        text = result["text"].strip()
        if len(text) < 60:
            return False

        keyword_hits = sum(
            1
            for keyword in (
                "factura",
                "fecha",
                "total",
                "importe",
                "base",
                "igic",
                "iva",
                "documento",
                "cliente",
                "cif",
                "nif",
            )
            if keyword in text.lower()
        )
        return result.get("score", float("-inf")) >= 140 and keyword_hits >= 3

    def _extract_paddle_image_ocr(self, image_path: str) -> dict:
        paddle_ocr = self._get_paddle_ocr()
        if paddle_ocr is None:
            return {
                "text": "",
                "score": float("-inf"),
                "variant_name": "paddle_unavailable",
                "preprocessing_steps": [],
                "ocr_engine": "paddleocr",
            }

        try:
            pages = list(paddle_ocr.predict(image_path))
        except Exception as exc:
            logger.warning("PaddleOCR failed for %s: %s", image_path, exc)
            return {
                "text": "",
                "score": float("-inf"),
                "variant_name": "paddle_error",
                "preprocessing_steps": [],
                "ocr_engine": "paddleocr",
            }

        if not pages:
            return {
                "text": "",
                "score": float("-inf"),
                "variant_name": "paddle_empty",
                "preprocessing_steps": [],
                "ocr_engine": "paddleocr",
            }

        page = pages[0]
        texts = [text.strip() for text in (page.get("rec_texts") or []) if str(text).strip()]
        confidences = []
        for value in page.get("rec_scores") or []:
            try:
                confidences.append(float(value) * 100.0)
            except (TypeError, ValueError):
                continue

        text = "\n".join(texts)
        return {
            "text": text,
            "score": self._score_ocr_candidate(text, confidences),
            "variant_name": "paddle_mobile_original",
            "preprocessing_steps": [
                "engine:paddleocr",
                "source:original_image",
                f"text_det_limit_side_len:{settings.paddle_text_det_limit_side_len}",
            ],
            "ocr_engine": "paddleocr",
        }

    def _get_paddle_ocr(self):
        if not settings.paddle_ocr_enabled:
            return None

        if self._paddle_ocr is not None:
            return self._paddle_ocr

        if self._paddle_ocr_import_error is not None:
            return None

        try:
            from paddleocr import PaddleOCR

            self._paddle_ocr = PaddleOCR(
                use_doc_orientation_classify=False,
                use_doc_unwarping=False,
                use_textline_orientation=False,
                text_detection_model_name="PP-OCRv5_mobile_det",
                text_recognition_model_name="latin_PP-OCRv5_mobile_rec",
                text_det_limit_side_len=settings.paddle_text_det_limit_side_len,
            )
            return self._paddle_ocr
        except Exception as exc:
            self._paddle_ocr_import_error = exc
            logger.warning("PaddleOCR unavailable, falling back to Tesseract: %s", exc)
            return None

    def _run_ocr_candidate(self, image: Image.Image, config: str) -> tuple[str, list[float]]:
        text = pytesseract.image_to_string(
            image,
            lang=self.language,
            config=config,
        ).strip()
        data = pytesseract.image_to_data(
            image,
            lang=self.language,
            config=config,
            output_type=pytesseract.Output.DICT,
        )

        confidences: list[float] = []
        for value in data.get("conf", []):
            try:
                numeric = float(value)
            except (TypeError, ValueError):
                continue
            if numeric >= 0:
                confidences.append(numeric)

        return text, confidences

    def _score_ocr_candidate(self, text: str, confidences: list[float]) -> float:
        if not text:
            return float("-inf")

        compact = text.replace("\n", " ").strip()
        lines = [line.strip() for line in text.splitlines() if line.strip()]
        tokens = [token for token in compact.split() if token]

        alnum = sum(ch.isalnum() for ch in compact)
        digit_count = sum(ch.isdigit() for ch in compact)
        line_count = max(1, len(lines))
        word_count = len(tokens)
        weird_char_count = sum(ch in {"ï¿½", "?", "|"} for ch in compact)
        short_line_count = sum(len(line) <= 3 for line in lines)
        short_line_ratio = short_line_count / line_count
        short_token_count = sum(len(token.strip(".,:;()[]{}")) <= 2 for token in tokens)
        short_token_ratio = short_token_count / max(1, word_count)
        uppercase_word_count = sum(1 for token in tokens if len(token) > 2 and token.isupper())
        avg_token_length = (
            sum(len(token.strip(".,:;()[]{}")) for token in tokens) / max(1, word_count)
        )
        amount_like_count = len(re.findall(r"\b\d{1,4}[.,]\d{2}\b", compact))
        keyword_bonus = sum(
            20
            for keyword in (
                "factura",
                "fecha",
                "total",
                "iva",
                "igic",
                "base",
                "proveedor",
                "cliente",
                "importe",
                "subtotal",
                "documento",
                "iban",
                "nif",
                "cif",
            )
            if keyword in compact.lower()
        )

        confidence_score = 0.0
        if confidences:
            avg_confidence = sum(confidences) / len(confidences)
            confidence_score = avg_confidence * 1.2
            if avg_confidence < 35:
                confidence_score -= 40
            elif avg_confidence > 65:
                confidence_score += 20

        return (
            min(alnum, 900) * 0.35
            + min(digit_count, 120) * 1.5
            + min(line_count, 40) * 4
            + min(word_count, 100) * 2
            + amount_like_count * 14
            + uppercase_word_count * 1.5
            + keyword_bonus
            + confidence_score
            - weird_char_count * 10
            - short_line_ratio * 180
            - short_token_ratio * 140
            - max(0, 3.0 - avg_token_length) * 50
            - max(0, line_count - 80) * 4
        )


ocr_service = OCRService()
