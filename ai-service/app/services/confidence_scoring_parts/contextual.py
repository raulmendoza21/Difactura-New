from __future__ import annotations

from typing import Any


def apply_context_adjustments(
    score: float,
    *,
    field_confidence: dict[str, float] | None = None,
    evidence: dict[str, list[Any]] | None = None,
    decision_flags: list[Any] | None = None,
    coverage_ratio: float | None = None,
    optional_low_fields: set[str] | None = None,
    document_type: str = "",
) -> float:
    field_confidence = field_confidence or {}
    evidence = evidence or {}
    decision_flags = decision_flags or []
    optional_low_fields = optional_low_fields or set()

    low_fields = sum(
        1
        for field_name, value in field_confidence.items()
        if field_name not in optional_low_fields and isinstance(value, (int, float)) and value < 0.65
    )
    supported_fields = sum(1 for items in evidence.values() if items)
    blocking_flags = sum(
        1
        for flag in decision_flags
        if getattr(flag, "requires_review", False) and getattr(flag, "severity", "") == "error"
    )
    warning_flags = sum(
        1
        for flag in decision_flags
        if getattr(flag, "requires_review", False) and getattr(flag, "severity", "") == "warning"
    )

    if coverage_ratio is not None:
        if coverage_ratio >= 0.9:
            score += 0.03
        elif coverage_ratio < 0.6:
            score -= 0.08

    if supported_fields >= 8:
        score += 0.04
    elif supported_fields <= 4:
        score -= 0.06

    if document_type in {"ticket", "factura_simplificada"}:
        if low_fields >= 4:
            score -= 0.06
        elif low_fields >= 2:
            score -= 0.03
    elif low_fields >= 4:
        score -= 0.12
    elif low_fields >= 2:
        score -= 0.06

    score -= min(0.18, blocking_flags * 0.1)
    if document_type in {"ticket", "factura_simplificada"}:
        score -= min(0.08, warning_flags * 0.02)
    else:
        score -= min(0.12, warning_flags * 0.04)
    return round(max(0.0, min(1.0, score)), 2)
