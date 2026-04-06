from __future__ import annotations

import logging

from PIL import Image

from app.config import settings
from app.models.document_bundle import DocumentSpan

from .shared import bbox_from_polygon, score_ocr_candidate

logger = logging.getLogger(__name__)


def get_paddle_ocr(service):
    if not settings.paddle_ocr_enabled:
        return None

    if service._paddle_ocr is not None:
        return service._paddle_ocr

    if service._paddle_ocr_import_error is not None:
        return None

    try:
        from paddleocr import PaddleOCR

        service._paddle_ocr = PaddleOCR(
            use_doc_orientation_classify=False,
            use_doc_unwarping=False,
            use_textline_orientation=False,
            text_detection_model_name="PP-OCRv5_mobile_det",
            text_recognition_model_name="latin_PP-OCRv5_mobile_rec",
            text_det_limit_side_len=settings.paddle_text_det_limit_side_len,
        )
        return service._paddle_ocr
    except Exception as exc:
        service._paddle_ocr_import_error = exc
        logger.warning("PaddleOCR unavailable, falling back to Tesseract: %s", exc)
        return None


def extract_paddle_image_ocr(service, image_path: str) -> dict:
    paddle_ocr = get_paddle_ocr(service)
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
        bbox = bbox_from_polygon(polygons[index] if index < len(polygons) else None)
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
        "score": score_ocr_candidate(text, confidences),
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
