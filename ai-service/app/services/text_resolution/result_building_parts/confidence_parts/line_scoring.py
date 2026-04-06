from __future__ import annotations

from typing import Any

from app.models.invoice_model import InvoiceData
from app.services.confidence_scorer import confidence_scorer

from ..shared import line_items_match


def score_line_field_confidence(
    final: InvoiceData,
    heuristic: InvoiceData,
    bundle_candidate: InvoiceData | None,
    ai_candidate: InvoiceData | None,
    evidence_items: list[Any] | None = None,
) -> float:
    if not final.lineas:
        return 0.0

    evidence_items = evidence_items or []
    validation_score = confidence_scorer._validate_line_items(final)
    score = 0.35 if validation_score > 0 else 0.2
    if validation_score >= 0.8:
        score += 0.2

    if heuristic.lineas and line_items_match(final.lineas, heuristic.lineas):
        score += 0.2
    elif heuristic.lineas:
        score -= 0.1

    if bundle_candidate and bundle_candidate.lineas and line_items_match(final.lineas, bundle_candidate.lineas):
        score += 0.18
    elif bundle_candidate and bundle_candidate.lineas:
        score -= 0.08

    if ai_candidate and ai_candidate.lineas and line_items_match(final.lineas, ai_candidate.lineas):
        score += 0.25
    elif ai_candidate and ai_candidate.lineas:
        score -= 0.1

    if len(evidence_items) >= 2:
        score += 0.07

    return round(max(0.0, min(1.0, score)), 2)
