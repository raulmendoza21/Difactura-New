"""Calculate confidence score for invoice extraction results."""

import logging
import re

from app.models.invoice_model import InvoiceData

logger = logging.getLogger(__name__)


class ConfidenceScorer:
    """Score the confidence of extracted invoice data.

    Evaluates completeness and consistency of extracted fields.
    Returns a score between 0.0 and 1.0.
    """

    # Field weights for confidence calculation
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
        """Calculate confidence score for extracted data."""
        scores = {}

        # Field presence scores
        scores["numero_factura"] = 1.0 if data.numero_factura else 0.0
        scores["fecha"] = 1.0 if self._is_valid_iso_date(data.fecha) else 0.0
        scores["cif_proveedor"] = 1.0 if self._is_valid_tax_id(data.cif_proveedor) else 0.0
        scores["proveedor"] = 1.0 if data.proveedor else 0.0
        scores["base_imponible"] = 1.0 if data.base_imponible > 0 else 0.0
        scores["iva"] = 1.0 if data.iva > 0 else 0.0
        scores["total"] = 1.0 if data.total > 0 else 0.0
        scores["line_items"] = self._validate_line_items(data)

        # Math validation: base + iva should equal total
        scores["math_valid"] = self._validate_math(data)
        scores["tax_consistency"] = self._validate_tax_consistency(data)

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

    def _validate_tax_consistency(self, data: InvoiceData) -> float:
        """Check if percentage, base and tax amount are coherent."""
        if data.base_imponible <= 0 or data.iva_porcentaje <= 0 or data.iva < 0:
            return 0.0

        expected_tax = round(data.base_imponible * data.iva_porcentaje / 100, 2)
        diff = abs(expected_tax - data.iva)
        tolerance = max(0.02, expected_tax * 0.02)

        if data.total > 0:
            expected_total = round(data.base_imponible + expected_tax, 2)
            total_tolerance = max(0.02, data.total * 0.01)
            if abs(expected_total - data.total) > total_tolerance:
                return 0.0

        if diff <= tolerance:
            return 1.0
        if diff <= max(0.1, expected_tax * 0.05):
            return 0.5
        return 0.0

    def _validate_line_items(self, data: InvoiceData) -> float:
        """Reward line-level structure and coherence with subtotal/total."""
        if not data.lineas:
            return 0.0

        populated_lines = [
            line for line in data.lineas if line.descripcion and (line.importe > 0 or line.precio_unitario > 0)
        ]
        if not populated_lines:
            return 0.0

        line_sum = round(sum(line.importe for line in populated_lines if line.importe > 0), 2)
        if data.base_imponible > 0 and abs(line_sum - data.base_imponible) <= max(0.02, data.base_imponible * 0.02):
            return 1.0
        if data.total > 0 and data.iva >= 0 and abs((line_sum + data.iva) - data.total) <= max(0.02, data.total * 0.02):
            return 0.8
        if line_sum > 0:
            return 0.2
        return 0.3

    def _is_valid_tax_id(self, value: str) -> bool:
        if not value:
            return False

        cleaned = re.sub(r"\s+", "", value.upper())
        return bool(
            re.fullmatch(r"[A-HJ-NP-SUVW]\d{7}[0-9A-J]", cleaned)
            or re.fullmatch(r"\d{8}[A-Z]", cleaned)
            or re.fullmatch(r"[XYZ]\d{7}[A-Z]", cleaned)
        )

    def _is_valid_iso_date(self, value: str) -> bool:
        return bool(re.fullmatch(r"\d{4}-\d{2}-\d{2}", value or ""))


confidence_scorer = ConfidenceScorer()
