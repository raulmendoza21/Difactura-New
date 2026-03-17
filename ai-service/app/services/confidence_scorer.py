"""Calculate confidence score for invoice extraction results."""

import logging
from app.models.invoice_model import InvoiceData

logger = logging.getLogger(__name__)


class ConfidenceScorer:
    """Score the confidence of extracted invoice data.

    Evaluates completeness and consistency of extracted fields.
    Returns a score between 0.0 and 1.0.
    """

    # Field weights for confidence calculation
    WEIGHTS = {
        "numero_factura": 0.15,
        "fecha": 0.10,
        "cif_proveedor": 0.15,
        "proveedor": 0.05,
        "base_imponible": 0.15,
        "iva": 0.10,
        "total": 0.15,
        "math_valid": 0.15,
    }

    def score(self, data: InvoiceData) -> float:
        """Calculate confidence score for extracted data."""
        scores = {}

        # Field presence scores
        scores["numero_factura"] = 1.0 if data.numero_factura else 0.0
        scores["fecha"] = 1.0 if data.fecha else 0.0
        scores["cif_proveedor"] = 1.0 if data.cif_proveedor else 0.0
        scores["proveedor"] = 1.0 if data.proveedor else 0.0
        scores["base_imponible"] = 1.0 if data.base_imponible > 0 else 0.0
        scores["iva"] = 1.0 if data.iva > 0 else 0.0
        scores["total"] = 1.0 if data.total > 0 else 0.0

        # Math validation: base + iva should equal total
        scores["math_valid"] = self._validate_math(data)

        # Weighted average
        total_score = sum(
            scores[field] * weight
            for field, weight in self.WEIGHTS.items()
        )

        # Clamp to [0, 1]
        total_score = max(0.0, min(1.0, total_score))

        logger.info(
            f"Confidence breakdown: {scores}, total={total_score:.2f}"
        )

        return round(total_score, 2)

    def _validate_math(self, data: InvoiceData) -> float:
        """Check if base + iva = total (within tolerance)."""
        if data.total <= 0 or data.base_imponible <= 0:
            return 0.0

        expected_total = data.base_imponible + data.iva
        tolerance = max(0.02, data.total * 0.01)  # 1% or 2 cents

        if abs(expected_total - data.total) <= tolerance:
            return 1.0

        # Partial credit for close matches
        diff_pct = abs(expected_total - data.total) / data.total
        if diff_pct < 0.05:
            return 0.5

        return 0.0


confidence_scorer = ConfidenceScorer()
