from __future__ import annotations

import pytesseract
from PIL import Image

from app.models.document_bundle import BoundingBox, DocumentSpan
from app.utils.image_processing import build_ocr_variants

from .shared import bbox_from_polygon, get_ocr_configs, score_ocr_candidate


def extract_best_text_from_variants(image: Image.Image, *, input_kind: str, language: str) -> dict:
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
        for config in get_ocr_configs(input_kind):
            text, confidences, spans = run_ocr_candidate(variant["image"], config, language=language)
            score = score_ocr_candidate(text, confidences)
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


def run_ocr_candidate(image: Image.Image, config: str, *, language: str) -> tuple[str, list[float], list[DocumentSpan]]:
    text = pytesseract.image_to_string(
        image,
        lang=language,
        config=config,
    ).strip()
    data = pytesseract.image_to_data(
        image,
        lang=language,
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
