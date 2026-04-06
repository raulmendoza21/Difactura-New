from __future__ import annotations

import re
from typing import Any


def normalize_text(value: str) -> str:
    return re.sub(r"[^A-Z0-9]", "", str(value or "").upper())


def stringify_value(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, float):
        return f"{value:.2f}".rstrip("0").rstrip(".")
    return str(value)


def is_empty_value(value: Any) -> bool:
    if value in ("", None, 0, 0.0):
        return True
    if isinstance(value, list) and not value:
        return True
    return False


def values_match(left: Any, right: Any) -> bool:
    if is_empty_value(left) and is_empty_value(right):
        return True
    try:
        return abs(float(left) - float(right)) <= max(0.02, abs(float(left)) * 0.02, abs(float(right)) * 0.02)
    except (TypeError, ValueError):
        pass
    return normalize_text(stringify_value(left)) == normalize_text(stringify_value(right))


def source_score(source_name: str) -> float:
    return {
        "heuristic": 0.72,
        "layout": 0.8,
        "doc_ai": 0.78,
    }.get(source_name, 0.65)


def value_kind_for_source(*, source: str, extractor: str) -> str:
    if source == "resolved":
        return "resolved"
    if source in {"inferred", "math_inference", "context_inference"}:
        return "inferred"
    if extractor.startswith("inference:"):
        return "inferred"
    return "observed"


def deduplicate_items(items: list[Any]) -> list[Any]:
    deduped: list[Any] = []
    seen: set[tuple[str, str, int, int]] = set()
    for item in items:
        key = (
            item.field,
            item.value,
            item.page,
            int(item.score * 100),
        )
        if key in seen:
            continue
        seen.add(key)
        deduped.append(item)
    return deduped
