from __future__ import annotations

import re

from app.models.invoice_model import InvoiceData, LineItem


class LineItemResolutionService:
    def _description_quality_score(self, line_items: list[LineItem]) -> float:
        if not line_items:
            return 0.0

        score = 0.0
        for line in line_items:
            description = re.sub(r"\s+", " ", line.descripcion or "").strip()
            if not description:
                continue

            letters = sum(char.isalpha() for char in description)
            digits = sum(char.isdigit() for char in description)
            words = [token for token in re.findall(r"[A-ZÁÉÍÓÚÜÑa-záéíóúüñ0-9]+", description) if token]
            uppercase_words = [token for token in words if token.isupper() and any(char.isalpha() for char in token)]
            average_word_length = (sum(len(token) for token in words) / len(words)) if words else 0.0

            score += min(len(description), 120) * 0.08
            score += min(len(words), 12) * 1.8
            score += min(letters, 80) * 0.05
            if " - " in description or "-" in description:
                score += 1.0
            if digits and letters > digits:
                score += 0.5
            if len(words) <= 1:
                score -= 2.5
            if average_word_length >= 5:
                score += 1.0
            if uppercase_words and len(uppercase_words) >= max(1, len(words) // 2):
                score += 0.5
        return round(score, 2)

    def normalize_line_items(self, line_items: list[LineItem]) -> tuple[list[LineItem], list[str]]:
        normalized_items: list[LineItem] = []
        warnings: list[str] = []

        for index, line in enumerate(line_items):
            item = line.model_copy(deep=True)
            item.descripcion = re.sub(r"\s+", " ", item.descripcion or "").strip()

            if item.precio_unitario > 0 and item.cantidad <= 0 and item.importe <= 0:
                item.cantidad = 1.0
                item.importe = round(item.precio_unitario, 2)
                warnings.append(f"linea_{index + 1}_completada_desde_precio")
            elif item.precio_unitario > 0 and item.cantidad <= 0 and item.importe > 0:
                estimated_qty = item.importe / item.precio_unitario if item.precio_unitario else 0
                item.cantidad = float(max(1, round(estimated_qty))) if abs(round(estimated_qty) - estimated_qty) < 0.05 else 1.0
                warnings.append(f"linea_{index + 1}_cantidad_inferida")
            elif item.cantidad > 0 and item.precio_unitario > 0 and item.importe <= 0:
                item.importe = round(item.cantidad * item.precio_unitario, 2)
                warnings.append(f"linea_{index + 1}_importe_recalculado")

            normalized_items.append(item)

        return normalized_items, warnings

    def enrich_single_line_item_from_amounts(self, data: InvoiceData) -> list[str]:
        warnings: list[str] = []
        if len(data.lineas) != 1 or data.base_imponible <= 0:
            return warnings

        item = data.lineas[0]
        if item.importe > 0:
            return warnings

        item.importe = round(data.base_imponible, 2)
        if item.cantidad <= 0:
            item.cantidad = 1.0
        if item.precio_unitario <= 0 and item.cantidad > 0:
            item.precio_unitario = round(item.importe / item.cantidad, 2)

        warnings.append("linea_unica_completada_desde_base")
        return warnings

    def repair_summary_leak_lines(
        self,
        line_items: list[LineItem],
        *,
        base_amount: float = 0,
        total_amount: float = 0,
    ) -> tuple[list[LineItem], list[str]]:
        warnings: list[str] = []
        if len(line_items) < 2 or base_amount <= 0:
            return line_items, warnings

        reference_base = round(base_amount, 2)
        reference_total = round(total_amount, 2)
        line_sum = round(sum(line.importe for line in line_items if line.importe > 0), 2)
        if line_sum <= reference_base + 0.02:
            return line_items, warnings

        suspicious_index: int | None = None
        residual_amount = 0.0
        for index, line in enumerate(line_items):
            amount = round(line.importe, 2)
            if amount <= 0:
                continue
            amount_matches_summary = abs(amount - reference_base) <= 0.02 or (reference_total > 0 and abs(amount - reference_total) <= 0.02)
            if not amount_matches_summary:
                continue
            remaining_sum = round(line_sum - amount, 2)
            candidate_residual = round(reference_base - remaining_sum, 2)
            if -0.02 <= candidate_residual <= max(10.0, reference_base * 0.15):
                suspicious_index = index
                residual_amount = candidate_residual
                break

        if suspicious_index is None:
            return line_items, warnings

        repaired_items: list[LineItem] = []
        for index, line in enumerate(line_items):
            if index != suspicious_index:
                repaired_items.append(line)
                continue
            if residual_amount <= 0.02:
                warnings.append(f"linea_{index + 1}_resumen_descartada")
                continue

            repaired = line.model_copy(deep=True)
            repaired.importe = round(residual_amount, 2)
            if repaired.cantidad > 0:
                repaired.precio_unitario = round(repaired.importe / repaired.cantidad, 2)
            else:
                repaired.cantidad = 1.0
                repaired.precio_unitario = repaired.importe
            repaired_items.append(repaired)
            warnings.append(f"linea_{index + 1}_importe_ajustado_desde_resumen")

        return repaired_items, warnings

    def prefer_fallback_line_items(
        self,
        *,
        primary_line_items: list[LineItem],
        fallback_line_items: list[LineItem],
        base_amount: float = 0,
    ) -> tuple[list[LineItem], list[str]]:
        if not fallback_line_items:
            return primary_line_items, []
        if not primary_line_items:
            return fallback_line_items, ["lineas_completadas_con_fallback"]

        primary_sum = round(sum(line.importe for line in primary_line_items if line.importe > 0), 2)
        fallback_sum = round(sum(line.importe for line in fallback_line_items if line.importe > 0), 2)
        primary_quality = self._description_quality_score(primary_line_items)
        fallback_quality = self._description_quality_score(fallback_line_items)

        if base_amount > 0:
            primary_diff = abs(primary_sum - base_amount)
            fallback_diff = abs(fallback_sum - base_amount)
            if fallback_diff + 0.02 < primary_diff:
                return fallback_line_items, ["lineas_corregidas_con_fallback"]
            if fallback_diff <= 0.02 and primary_diff <= 0.02 and len(fallback_line_items) > len(primary_line_items):
                return fallback_line_items, ["lineas_enriquecidas_con_fallback"]
            if (
                fallback_diff <= 0.02
                and primary_diff <= 0.02
                and len(fallback_line_items) >= len(primary_line_items)
                and fallback_quality >= primary_quality + 3.0
            ):
                return fallback_line_items, ["lineas_descripcion_mejorada_con_fallback"]

        if len(fallback_line_items) > len(primary_line_items) and fallback_sum > primary_sum:
            return fallback_line_items, ["lineas_enriquecidas_con_fallback"]
        if (
            len(fallback_line_items) == len(primary_line_items)
            and abs(fallback_sum - primary_sum) <= 0.02
            and fallback_quality >= primary_quality + 4.0
        ):
            return fallback_line_items, ["lineas_descripcion_mejorada_con_fallback"]

        return primary_line_items, []

    def has_summary_leak_pattern(
        self,
        line_items: list[LineItem],
        *,
        base_amount: float = 0,
        total_amount: float = 0,
    ) -> bool:
        if len(line_items) < 2 or base_amount <= 0:
            return False

        reference_base = round(base_amount, 2)
        reference_total = round(total_amount, 2)
        line_sum = round(sum(line.importe for line in line_items if line.importe > 0), 2)
        if line_sum <= reference_base + 0.02:
            return False

        for line in line_items:
            amount = round(line.importe, 2)
            if amount <= 0:
                continue
            if abs(amount - reference_base) <= 0.02:
                return True
            if reference_total > 0 and abs(amount - reference_total) <= 0.02:
                return True
        return False

    def repair_single_line_tax_confusion(self, data: InvoiceData) -> list[str]:
        if len(data.lineas) != 1 or data.base_imponible <= 0 or data.iva <= 0:
            return []
        item = data.lineas[0]
        if abs(item.precio_unitario - data.base_imponible) <= 0.05 and abs(item.importe - data.iva) <= 0.05:
            item.importe = round(data.base_imponible, 2)
            if item.cantidad <= 0:
                item.cantidad = 1.0
            return ["linea_unica_importe_corregido_desde_base"]
        return []


line_item_resolution_service = LineItemResolutionService()
