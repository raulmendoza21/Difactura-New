from __future__ import annotations

from app.models.invoice_model import InvoiceData
from app.services.field_extraction.line_items import extract_line_items
from app.services.field_extraction.amount_parts.ticket import (
    extract_ticket_tax_summary,
    has_explicit_ticket_tax_summary,
)
from app.services.field_extraction.shared import looks_like_ticket_document
from app.services.text_resolution.party_resolution_parts.ticket import has_explicit_ticket_customer


def apply_ticket_corrections(
    *,
    normalized: InvoiceData,
    fallback: InvoiceData,
    raw_text: str,
) -> list[str]:
    warnings: list[str] = []
    if not looks_like_ticket_document(raw_text):
        return warnings

    if not has_explicit_ticket_customer(raw_text) and (normalized.cliente or normalized.cif_cliente):
        normalized.cliente = ""
        normalized.cif_cliente = ""
        warnings.append("familia_ticket_cliente_descartado")

    summary = extract_ticket_tax_summary(raw_text)
    if summary["total"] > 0 and abs(normalized.total - summary["total"]) > 0.02:
        normalized.total = summary["total"]
        warnings.append("familia_ticket_total_corregido")

    if summary["base_imponible"] > 0 and abs(normalized.base_imponible - summary["base_imponible"]) > 0.02:
        normalized.base_imponible = summary["base_imponible"]
        warnings.append("familia_ticket_base_corregida")

    if summary["iva"] > 0 and abs(normalized.iva - summary["iva"]) > 0.02:
        normalized.iva = summary["iva"]
        warnings.append("familia_ticket_cuota_corregida")

    if summary["iva_porcentaje"] > 0 and abs(normalized.iva_porcentaje - summary["iva_porcentaje"]) > 0.02:
        normalized.iva_porcentaje = summary["iva_porcentaje"]
        warnings.append("familia_ticket_porcentaje_corregido")

    if not has_explicit_ticket_tax_summary(raw_text):
        if normalized.iva_porcentaje > 25:
            normalized.iva_porcentaje = 0.0
            warnings.append("familia_ticket_porcentaje_descartado")
        if normalized.iva > normalized.total > 0:
            normalized.iva = 0.0
            warnings.append("familia_ticket_cuota_descartada")
        if normalized.base_imponible > normalized.total > 0:
            normalized.base_imponible = 0.0
            warnings.append("familia_ticket_base_descartada")
        if fallback.cliente and normalized.cliente:
            normalized.cliente = ""
            normalized.cif_cliente = ""
            warnings.append("familia_ticket_cliente_fallback_descartado")

    rebuilt_lines = extract_line_items(raw_text)
    if rebuilt_lines and _should_prefer_ticket_lines(rebuilt_lines, normalized):
        normalized.lineas = rebuilt_lines
        warnings.append("familia_ticket_lineas_reconstruidas_desde_raw_text")

    return warnings


def _should_prefer_ticket_lines(rebuilt_lines: list, normalized: InvoiceData) -> bool:
    if not normalized.lineas:
        return True
    if _contains_ticket_noise(normalized.lineas):
        return True

    rebuilt_sum = round(sum(line.importe for line in rebuilt_lines if line.importe > 0), 2)
    current_sum = round(sum(line.importe for line in normalized.lineas if line.importe > 0), 2)
    reference_total = round(normalized.total, 2)

    if reference_total > 0:
        rebuilt_diff = abs(rebuilt_sum - reference_total)
        current_diff = abs(current_sum - reference_total)
        if rebuilt_diff + 0.02 < current_diff:
            return True
    return len(rebuilt_lines) > len(normalized.lineas) and rebuilt_sum >= current_sum


def _contains_ticket_noise(line_items: list) -> bool:
    noise_tokens = ("EFFECTIVO", "EFECTIVO", "ENTREGADO", "CAMBIO", "FORMA DE PAGO", "IMG-", "GRACIAS", "PLAN DINO")
    for line in line_items:
        description = (line.descripcion or "").upper()
        if any(token in description for token in noise_tokens):
            return True
    return False
