from __future__ import annotations

from app.models.invoice_model import InvoiceData
from app.services.text_resolution.line_items import line_item_resolution_service


def normalize_line_items_with_fallback(normalized: InvoiceData, fallback: InvoiceData) -> list[str]:
    warnings: list[str] = []

    normalized.lineas, line_warnings = line_item_resolution_service.normalize_line_items(normalized.lineas)
    warnings.extend(line_warnings)
    normalized.lineas, summary_leak_warnings = line_item_resolution_service.repair_summary_leak_lines(
        normalized.lineas,
        base_amount=normalized.base_imponible or fallback.base_imponible,
        total_amount=normalized.total or fallback.total,
    )
    warnings.extend(summary_leak_warnings)

    fallback_line_items, _ = line_item_resolution_service.normalize_line_items(fallback.lineas)
    fallback_line_items, _ = line_item_resolution_service.repair_summary_leak_lines(
        fallback_line_items,
        base_amount=fallback.base_imponible or normalized.base_imponible,
        total_amount=fallback.total or normalized.total,
    )
    normalized.lineas, fallback_line_warnings = line_item_resolution_service.prefer_fallback_line_items(
        primary_line_items=normalized.lineas,
        fallback_line_items=fallback_line_items,
        base_amount=fallback.base_imponible or normalized.base_imponible,
    )
    warnings.extend(fallback_line_warnings)
    return warnings


def infer_base_from_lines(normalized: InvoiceData) -> list[str]:
    if normalized.base_imponible > 0 or not normalized.lineas:
        return []
    line_sum = round(sum(line.importe for line in normalized.lineas if line.importe > 0), 2)
    if line_sum <= 0:
        return []
    normalized.base_imponible = line_sum
    return ["base_inferida_desde_lineas"]


def enrich_line_items_from_amounts(normalized: InvoiceData) -> list[str]:
    return line_item_resolution_service.enrich_single_line_item_from_amounts(normalized)
