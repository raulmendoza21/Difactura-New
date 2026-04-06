from __future__ import annotations

import re

from app.models.document_bundle import BoundingBox


OCR_CONFIGS = ("--oem 3 --psm 6", "--oem 3 --psm 4", "--oem 3 --psm 11")


def get_ocr_configs(input_kind: str) -> tuple[str, ...]:
    if input_kind == "image_photo":
        return ("--oem 3 --psm 6", "--oem 3 --psm 4")
    return OCR_CONFIGS


def is_fast_photo_result_usable(result: dict | None) -> bool:
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


def bbox_from_polygon(polygon) -> BoundingBox:
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


def score_ocr_candidate(text: str, confidences: list[float]) -> float:
    if not text:
        return float("-inf")

    compact = text.replace("\n", " ").strip()
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    tokens = [token for token in compact.split() if token]

    alnum = sum(ch.isalnum() for ch in compact)
    digit_count = sum(ch.isdigit() for ch in compact)
    line_count = max(1, len(lines))
    word_count = len(tokens)
    weird_char_count = sum(ch in {"Ã¯Â¿Â½", "?", "|"} for ch in compact)
    short_line_count = sum(len(line) <= 3 for line in lines)
    short_line_ratio = short_line_count / line_count
    short_token_count = sum(len(token.strip(".,:;()[]{}")) <= 2 for token in tokens)
    short_token_ratio = short_token_count / max(1, word_count)
    uppercase_word_count = sum(1 for token in tokens if len(token) > 2 and token.isupper())
    avg_token_length = sum(len(token.strip(".,:;()[]{}")) for token in tokens) / max(1, word_count)
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
