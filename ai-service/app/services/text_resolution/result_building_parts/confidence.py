from __future__ import annotations

from typing import Any

from app.models.invoice_model import InvoiceData
from app.services.text_resolution.result_building_parts.confidence_parts.document_scoring import (
    refine_document_confidence as _refine_document_confidence,
)
from app.services.text_resolution.result_building_parts.confidence_parts.field_scoring import (
    build_field_confidence as _build_field_confidence,
    score_field_confidence as _score_field_confidence,
)
from app.services.text_resolution.result_building_parts.confidence_parts.line_scoring import (
    score_line_field_confidence as _score_line_field_confidence,
)


def build_field_confidence(
    *,
    final: InvoiceData,
    heuristic: InvoiceData,
    bundle_candidate: InvoiceData | None = None,
    ai_candidate: InvoiceData | None = None,
    evidence: dict[str, list[Any]] | None = None,
) -> dict[str, float]:
    return _build_field_confidence(
        final=final,
        heuristic=heuristic,
        bundle_candidate=bundle_candidate,
        ai_candidate=ai_candidate,
        evidence=evidence,
        score_line_field_confidence=_score_line_field_confidence,
    )

def refine_document_confidence(
    *,
    invoice: InvoiceData,
    current_confidence: float,
    field_confidence: dict[str, float],
    warnings: list[str],
    company_match: dict[str, object] | None = None,
    document_type: str = "",
    optional_low_fields: set[str] | None = None,
) -> float:
    return _refine_document_confidence(
        invoice=invoice,
        current_confidence=current_confidence,
        field_confidence=field_confidence,
        warnings=warnings,
        company_match=company_match,
        document_type=document_type,
        optional_low_fields=optional_low_fields,
    )


def score_field_confidence(
    final_value: Any,
    heuristic_value: Any,
    bundle_value: Any,
    ai_value: Any,
    *,
    validator: Any | None = None,
    evidence_items: list[Any] | None = None,
) -> float:
    return _score_field_confidence(
        final_value,
        heuristic_value,
        bundle_value,
        ai_value,
        validator=validator,
        evidence_items=evidence_items,
    )


def score_line_field_confidence(
    final: InvoiceData,
    heuristic: InvoiceData,
    bundle_candidate: InvoiceData | None,
    ai_candidate: InvoiceData | None,
    evidence_items: list[Any] | None = None,
) -> float:
    return _score_line_field_confidence(final, heuristic, bundle_candidate, ai_candidate, evidence_items)
