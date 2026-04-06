from __future__ import annotations

import re
from typing import Any

from app.models.invoice_model import LineItem


def is_empty_value(value: Any) -> bool:
    if value in ("", 0, 0.0, None):
        return True
    if isinstance(value, list) and not value:
        return True
    return False


def values_match(left: Any, right: Any) -> bool:
    if is_empty_value(left) and is_empty_value(right):
        return True
    if isinstance(left, (int, float)) or isinstance(right, (int, float)):
        try:
            return abs(float(left) - float(right)) <= max(
                0.02,
                abs(float(left)) * 0.02,
                abs(float(right)) * 0.02,
            )
        except (TypeError, ValueError):
            return False

    left_text = re.sub(r"[^A-Z0-9]", "", str(left).upper())
    right_text = re.sub(r"[^A-Z0-9]", "", str(right).upper())
    return left_text == right_text or left_text in right_text or right_text in left_text


def line_items_match(left: list[LineItem], right: list[LineItem]) -> bool:
    if not left or not right:
        return False

    left_sum = round(sum(line.importe for line in left if abs(line.importe) > 0), 2)
    right_sum = round(sum(line.importe for line in right if abs(line.importe) > 0), 2)
    if abs(left_sum) > 0 and abs(right_sum) > 0 and not values_match(left_sum, right_sum):
        return False

    if abs(len(left) - len(right)) > 1:
        return False

    left_descriptions = {re.sub(r"[^A-Z0-9]", "", line.descripcion.upper()) for line in left if line.descripcion}
    right_descriptions = {re.sub(r"[^A-Z0-9]", "", line.descripcion.upper()) for line in right if line.descripcion}
    if not left_descriptions or not right_descriptions:
        return True

    overlap = len(left_descriptions & right_descriptions)
    return overlap >= max(1, min(len(left_descriptions), len(right_descriptions)) - 1)


def is_valid_iso_date(value: str) -> bool:
    return bool(re.fullmatch(r"\d{4}-\d{2}-\d{2}", value or ""))
