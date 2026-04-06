from __future__ import annotations

import logging
from pathlib import Path

from PIL import Image

from app.config import settings

logger = logging.getLogger(__name__)


def extract_text_from_image(service, image_path: str, *, input_kind: str = "image_scan") -> str:
    return extract_image_ocr(service, image_path, input_kind=input_kind)["text"]


def extract_image_ocr(service, image_path: str, *, input_kind: str = "image_scan") -> dict:
    path = Path(image_path)
    if not path.exists():
        raise FileNotFoundError(f"Image not found: {image_path}")

    paddle_result = None
    if input_kind == "image_photo" and settings.paddle_ocr_enabled:
        paddle_result = service._extract_paddle_image_ocr(image_path)
        if service._is_fast_photo_result_usable(paddle_result):
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
        tesseract_result = service._extract_best_text_from_variants(image, input_kind=input_kind)

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
