"""Calculate confidence score for invoice extraction results."""

import logging
from typing import Any

from app.models.invoice_model import InvoiceData
from app.services.confidence_scoring_parts import (
    apply_context_adjustments,
    calculate_penalties,
    is_generic_party_name,
    is_valid_iso_date,
    is_valid_tax_id,
    validate_line_items,
    validate_math,
    validate_tax_consistency,
)

logger = logging.getLogger(__name__)


class ConfidenceScorer:
    """Score the confidence of extracted invoice data."""

    WEIGHTS = {
        "numero_factura": 0.14,
        "fecha": 0.08,
        "cif_proveedor": 0.14,
        "proveedor": 0.08,
        "base_imponible": 0.12,
        "iva": 0.08,
        "total": 0.12,
        "line_items": 0.08,
        "math_valid": 0.10,
        "tax_consistency": 0.06,
    }

    def score(self, data: InvoiceData) -> float:
        scores = {
            "numero_factura": 1.0 if data.numero_factura else 0.0,
            "fecha": 1.0 if self._is_valid_iso_date(data.fecha) else 0.0,
            "cif_proveedor": 1.0 if self._is_valid_tax_id(data.cif_proveedor) else 0.0,
            "proveedor": 1.0 if data.proveedor else 0.0,
            "base_imponible": 1.0 if abs(data.base_imponible or 0) > 0 else 0.0,
            "iva": 1.0 if abs(data.iva or 0) > 0 else 0.0,
            "total": 1.0 if abs(data.total or 0) > 0 else 0.0,
            "line_items": self._validate_line_items(data),
            "math_valid": self._validate_math(data),
            "tax_consistency": self._validate_tax_consistency(data),
        }

        total_score = sum(scores[field] * weight for field, weight in self.WEIGHTS.items())
        total_score -= self._calculate_penalties(data)
        total_score = max(0.0, min(1.0, total_score))

        logger.info("Confidence breakdown: %s, total=%.2f", scores, total_score)
        return round(total_score, 2)

    def score_with_context(
        self,
        data: InvoiceData,
        *,
        field_confidence: dict[str, float] | None = None,
        evidence: dict[str, list[Any]] | None = None,
        decision_flags: list[Any] | None = None,
        coverage_ratio: float | None = None,
        optional_low_fields: set[str] | None = None,
        document_type: str = "",
    ) -> float:
        return apply_context_adjustments(
            self.score(data),
            field_confidence=field_confidence,
            evidence=evidence,
            decision_flags=decision_flags,
            coverage_ratio=coverage_ratio,
            optional_low_fields=optional_low_fields,
            document_type=document_type,
        )

    def _validate_math(self, data: InvoiceData) -> float:
        return validate_math(data)

    def _validate_tax_consistency(self, data: InvoiceData) -> float:
        return validate_tax_consistency(data)

    def _validate_line_items(self, data: InvoiceData) -> float:
        return validate_line_items(data)

    def _calculate_penalties(self, data: InvoiceData) -> float:
        return calculate_penalties(data)

    def _is_valid_tax_id(self, value: str) -> bool:
        return is_valid_tax_id(value)

    def _is_valid_iso_date(self, value: str) -> bool:
        return is_valid_iso_date(value)

    def _is_generic_party_name(self, value: str) -> bool:
        return is_generic_party_name(value)


confidence_scorer = ConfidenceScorer()
