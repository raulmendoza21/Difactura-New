import logging
import re
from pathlib import Path

import pytesseract
from PIL import Image

from app.config import settings
from app.models.document_bundle import BoundingBox, DocumentSpan
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
                paddle_result["page_entries"] = [
                    {
                        "page_number": 1,
                        "width": float(paddle_result.get("image_width", 0)),
                        "height": float(paddle_result.get("image_height", 0)),
                        "text": paddle_result["text"],
                        "spans": paddle_result.get("spans", []),
                        "ocr_engine": paddle_result.get("ocr_engine", ""),
                    }
                ]
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
        result["page_entries"] = [
            {
                "page_number": 1,
                "width": float(result.get("image_width", 0)),
                "height": float(result.get("image_height", 0)),
                "text": result["text"],
                "spans": result.get("spans", []),
                "ocr_engine": result.get("ocr_engine", ""),
            }
        ]
        return result

    def extract_text_from_pdf_pages(self, file_path: str, input_kind: str = "pdf_scanned") -> str:
        return self.extract_pdf_ocr(file_path, input_kind=input_kind)["text"]

    def extract_pdf_ocr(self, file_path: str, input_kind: str = "pdf_scanned") -> dict:
        import fitz

        doc = fitz.open(file_path)
        all_text: list[str] = []
        page_entries: list[dict] = []
        preprocessing_steps = ["pdf_page_render"]
        best_variant_name = ""

        try:
            for page_num, page in enumerate(doc):
                mat = fitz.Matrix(300 / 72, 300 / 72)
                pix = page.get_pixmap(matrix=mat)
                img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
                result = self._extract_best_text_from_variants(img, input_kind=input_kind)

                all_text.append(result["text"].strip())
                page_entries.append(
                    {
                        "page_number": page_num + 1,
                        "width": float(pix.width),
                        "height": float(pix.height),
                        "text": result["text"].strip(),
                        "spans": [
                            span.model_copy(update={"page": page_num + 1})
                            for span in result.get("spans", [])
                        ],
                        "ocr_engine": result.get("ocr_engine", ""),
                    }
                )
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
            "page_entries": page_entries,
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
            "spans": [],
            "image_width": float(image.width),
            "image_height": float(image.height),
        }

        for variant in build_ocr_variants(image, input_kind=input_kind):
            for config in self._get_ocr_configs(input_kind):
                text, confidences, spans = self._run_ocr_candidate(variant["image"], config)
                score = self._score_ocr_candidate(text, confidences)
                if score > best_result["score"]:
                    best_result = {
                        "text": text.strip(),
                        "score": score,
                        "variant_name": variant["name"],
                        "preprocessing_steps": variant["preprocessing_steps"],
                        "ocr_engine": "tesseract",
                        "spans": spans,
                        "image_width": float(variant["image"].width),
                        "image_height": float(variant["image"].height),
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
                "spans": [],
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
                "spans": [],
            }

        if not pages:
            return {
                "text": "",
                "score": float("-inf"),
                "variant_name": "paddle_empty",
                "preprocessing_steps": [],
                "ocr_engine": "paddleocr",
                "spans": [],
            }

        page = pages[0]
        with Image.open(image_path) as image:
            image_width = float(image.width)
            image_height = float(image.height)
        texts = [text.strip() for text in (page.get("rec_texts") or []) if str(text).strip()]
        confidences = []
        for value in page.get("rec_scores") or []:
            try:
                confidences.append(float(value) * 100.0)
            except (TypeError, ValueError):
                continue

        text = "\n".join(texts)
        polygons = page.get("rec_polys") or page.get("dt_polys") or []
        spans: list[DocumentSpan] = []
        for index, value in enumerate(texts):
            bbox = self._bbox_from_polygon(polygons[index] if index < len(polygons) else None)
            spans.append(
                DocumentSpan(
                    span_id=f"paddle:p1:b{index}:l0",
                    page=1,
                    text=value,
                    bbox=bbox,
                    source="ocr",
                    engine="paddleocr",
                    block_no=index,
                    line_no=0,
                    confidence=round((confidences[index] / 100.0), 2) if index < len(confidences) else None,
                )
            )
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
            "spans": spans,
            "image_width": image_width,
            "image_height": image_height,
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

    def _run_ocr_candidate(self, image: Image.Image, config: str) -> tuple[str, list[float], list[DocumentSpan]]:
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
        line_map: dict[tuple[int, int], dict] = {}
        for value in data.get("conf", []):
            try:
                numeric = float(value)
            except (TypeError, ValueError):
                continue
            if numeric >= 0:
                confidences.append(numeric)

        total_items = len(data.get("text", []))
        for index in range(total_items):
            token = str(data.get("text", [""])[index] or "").strip()
            if not token:
                continue
            try:
                token_conf = float(data.get("conf", [0])[index])
            except (TypeError, ValueError):
                token_conf = -1
            if token_conf < 0:
                continue

            block_no = int(data.get("block_num", [0])[index] or 0)
            line_no = int(data.get("line_num", [0])[index] or 0)
            key = (block_no, line_no)
            current = line_map.setdefault(
                key,
                {
                    "texts": [],
                    "x0": float(data.get("left", [0])[index]),
                    "y0": float(data.get("top", [0])[index]),
                    "x1": float(data.get("left", [0])[index]) + float(data.get("width", [0])[index]),
                    "y1": float(data.get("top", [0])[index]) + float(data.get("height", [0])[index]),
                    "confidences": [],
                },
            )
            left = float(data.get("left", [0])[index])
            top = float(data.get("top", [0])[index])
            width = float(data.get("width", [0])[index])
            height = float(data.get("height", [0])[index])
            current["texts"].append(token)
            current["x0"] = min(current["x0"], left)
            current["y0"] = min(current["y0"], top)
            current["x1"] = max(current["x1"], left + width)
            current["y1"] = max(current["y1"], top + height)
            current["confidences"].append(token_conf)

        spans: list[DocumentSpan] = []
        for (block_no, line_no), payload in sorted(line_map.items(), key=lambda item: (item[1]["y0"], item[1]["x0"])):
            line_conf = 0.0
            if payload["confidences"]:
                line_conf = round((sum(payload["confidences"]) / len(payload["confidences"])) / 100.0, 2)
            spans.append(
                DocumentSpan(
                    span_id=f"tesseract:p1:b{block_no}:l{line_no}",
                    page=1,
                    text=" ".join(payload["texts"]).strip(),
                    bbox=BoundingBox.from_points(payload["x0"], payload["y0"], payload["x1"], payload["y1"]),
                    source="ocr",
                    engine="tesseract",
                    block_no=block_no,
                    line_no=line_no,
                    confidence=line_conf,
                )
            )

        return text, confidences, spans

    def _bbox_from_polygon(self, polygon) -> BoundingBox:
        if polygon is None:
            return BoundingBox()
        try:
            points = [(float(point[0]), float(point[1])) for point in polygon]
        except (TypeError, ValueError, IndexError):
            return BoundingBox()
        if not points:
            return BoundingBox()
        xs = [point[0] for point in points]
        ys = [point[1] for point in points]
        return BoundingBox.from_points(min(xs), min(ys), max(xs), max(ys))

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
