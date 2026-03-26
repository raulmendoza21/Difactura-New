"""Calculate confidence score for invoice extraction results."""

import logging
import re
from typing import Any

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
        base_amount = abs(data.base_imponible or 0)
        tax_amount = abs(data.iva or 0)
        total_amount = abs(data.total or 0)

        # Field presence scores
        scores["numero_factura"] = 1.0 if data.numero_factura else 0.0
        scores["fecha"] = 1.0 if self._is_valid_iso_date(data.fecha) else 0.0
        scores["cif_proveedor"] = 1.0 if self._is_valid_tax_id(data.cif_proveedor) else 0.0
        scores["proveedor"] = 1.0 if data.proveedor else 0.0
        scores["base_imponible"] = 1.0 if base_amount > 0 else 0.0
        scores["iva"] = 1.0 if tax_amount > 0 else 0.0
        scores["total"] = 1.0 if total_amount > 0 else 0.0
        scores["line_items"] = self._validate_line_items(data)

        # Math validation: base + iva should equal total
        scores["math_valid"] = self._validate_math(data)
        scores["tax_consistency"] = self._validate_tax_consistency(data)

        # Weighted average
        total_score = sum(
            scores[field] * weight
            for field, weight in self.WEIGHTS.items()
        )

        total_score -= self._calculate_penalties(data)

        # Clamp to [0, 1]
        total_score = max(0.0, min(1.0, total_score))

        logger.info(
            f"Confidence breakdown: {scores}, total={total_score:.2f}"
        )

        return round(total_score, 2)

    def score_with_context(
        self,
        data: InvoiceData,
        *,
        field_confidence: dict[str, float] | None = None,
        evidence: dict[str, list[Any]] | None = None,
        decision_flags: list[Any] | None = None,
        coverage_ratio: float | None = None,
    ) -> float:
        score = self.score(data)
        field_confidence = field_confidence or {}
        evidence = evidence or {}
        decision_flags = decision_flags or []

        low_fields = sum(1 for value in field_confidence.values() if isinstance(value, (int, float)) and value < 0.65)
        supported_fields = sum(1 for items in evidence.values() if items)
        blocking_flags = sum(1 for flag in decision_flags if getattr(flag, "requires_review", False) and getattr(flag, "severity", "") == "error")
        warning_flags = sum(1 for flag in decision_flags if getattr(flag, "requires_review", False) and getattr(flag, "severity", "") == "warning")

        if coverage_ratio is not None:
            if coverage_ratio >= 0.9:
                score += 0.03
            elif coverage_ratio < 0.6:
                score -= 0.08

        if supported_fields >= 8:
            score += 0.04
        elif supported_fields <= 4:
            score -= 0.06

        if low_fields >= 4:
            score -= 0.12
        elif low_fields >= 2:
            score -= 0.06

        score -= min(0.18, blocking_flags * 0.1)
        score -= min(0.12, warning_flags * 0.04)

        return round(max(0.0, min(1.0, score)), 2)

    def _validate_math(self, data: InvoiceData) -> float:
        """Check if base + iva = total (within tolerance)."""
        if abs(data.total) <= 0 or abs(data.base_imponible) <= 0:
            return 0.0

        expected_total = data.base_imponible + data.iva
        tolerance = max(0.02, abs(data.total) * 0.01)  # 1% or 2 cents

        if abs(expected_total - data.total) <= tolerance:
            return 1.0

        # Partial credit for close matches
        diff_pct = abs(expected_total - data.total) / max(abs(data.total), 0.01)
        if diff_pct < 0.05:
            return 0.5

        return 0.0

    def _validate_tax_consistency(self, data: InvoiceData) -> float:
        """Check if percentage, base and tax amount are coherent."""
        if abs(data.base_imponible) <= 0 or data.iva_porcentaje <= 0 or abs(data.iva) <= 0:
            return 0.0

        sign = -1 if data.base_imponible < 0 or data.iva < 0 or data.total < 0 else 1
        expected_tax = round(abs(data.base_imponible) * data.iva_porcentaje / 100, 2) * sign
        diff = abs(expected_tax - data.iva)
        tolerance = max(0.02, abs(expected_tax) * 0.02)

        if abs(data.total) > 0:
            expected_total = round(data.base_imponible + expected_tax, 2)
            total_tolerance = max(0.02, abs(data.total) * 0.01)
            if abs(expected_total - data.total) > total_tolerance:
                return 0.0

        if diff <= tolerance:
            return 1.0
        if diff <= max(0.1, abs(expected_tax) * 0.05):
            return 0.5
        return 0.0

    def _validate_line_items(self, data: InvoiceData) -> float:
        """Reward line-level structure and coherence with subtotal/total."""
        if not data.lineas:
            return 0.0

        populated_lines = [
            line for line in data.lineas if line.descripcion and (abs(line.importe) > 0 or abs(line.precio_unitario) > 0)
        ]
        if not populated_lines:
            return 0.0

        line_sum = round(sum(line.importe for line in populated_lines if abs(line.importe) > 0), 2)
        base_amount = abs(data.base_imponible or 0)
        total_amount = abs(data.total or 0)
        tax_amount = abs(data.iva or 0)

        if base_amount > 0 and abs(line_sum - data.base_imponible) <= max(0.02, base_amount * 0.02):
            return 1.0
        if base_amount > 0 and abs(line_sum - data.base_imponible) <= max(0.1, base_amount * 0.05):
            return 0.45
        if total_amount > 0 and tax_amount >= 0 and abs((line_sum + data.iva) - data.total) <= max(0.02, total_amount * 0.02):
            return 0.8
        if abs(line_sum) > 0:
            return 0.1
        return 0.3

    def _calculate_penalties(self, data: InvoiceData) -> float:
        penalty = 0.0
        total_amount = abs(data.total or 0)
        base_amount = abs(data.base_imponible or 0)
        tolerance = max(0.02, total_amount * 0.01) if total_amount > 0 else 0.02

        if data.proveedor and self._is_generic_party_name(data.proveedor):
            penalty += 0.08

        if total_amount > 0 and base_amount > 0 and total_amount + tolerance < base_amount:
            penalty += 0.18

        line_sum = round(sum(line.importe for line in data.lineas if abs(line.importe) > 0), 2)
        abs_line_sum = abs(line_sum)
        if abs_line_sum > 0 and total_amount > 0 and total_amount + tolerance < abs_line_sum:
            penalty += 0.18

        if abs_line_sum > 0 and base_amount > 0:
            delta = abs(line_sum - data.base_imponible)
            if delta > max(0.1, base_amount * 0.01):
                penalty += 0.18
            elif delta > 0.02:
                penalty += 0.12

        if data.cif_proveedor and not self._is_valid_tax_id(data.cif_proveedor):
            penalty += 0.08

        return penalty

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

    def _is_generic_party_name(self, value: str) -> bool:
        normalized = re.sub(r"[^A-Z0-9]", "", (value or "").upper())
        return normalized in {"CLIENTE", "EMISOR", "PROVEEDOR", "FACTURA"}


confidence_scorer = ConfidenceScorer()
