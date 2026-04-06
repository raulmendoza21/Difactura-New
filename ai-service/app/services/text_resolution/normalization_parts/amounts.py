from __future__ import annotations

from app.models.invoice_model import InvoiceData
from app.services.text_resolution.amounts import amount_resolution_service


def apply_retention_summary(normalized: InvoiceData, retention_summary: dict[str, float]) -> list[str]:
    warnings: list[str] = []
    if (
        retention_summary["base"] > 0
        and retention_summary["tax_rate"] > 0
        and retention_summary["tax_amount"] > 0
        and retention_summary["withholding_amount"] > 0
        and retention_summary["total_due"] > 0
    ):
        normalized.base_imponible = retention_summary["base"]
        normalized.iva_porcentaje = retention_summary["tax_rate"]
        normalized.iva = retention_summary["tax_amount"]
        normalized.retencion_porcentaje = retention_summary["withholding_rate"] or normalized.retencion_porcentaje
        normalized.retencion = retention_summary["withholding_amount"]
        normalized.total = retention_summary["total_due"]
        warnings.append("importes_detectados_desde_resumen_con_retencion")

    if retention_summary["withholding_rate"] > 0 and normalized.retencion_porcentaje <= 0:
        normalized.retencion_porcentaje = retention_summary["withholding_rate"]
        warnings.append("retencion_porcentaje_detectado_desde_texto")
    if retention_summary["withholding_amount"] > 0 and normalized.retencion <= 0:
        normalized.retencion = retention_summary["withholding_amount"]
        warnings.append("retencion_importe_detectado_desde_texto")
    if retention_summary["tax_rate"] > 0 and normalized.iva_porcentaje <= 0:
        normalized.iva_porcentaje = retention_summary["tax_rate"]
        warnings.append("iva_porcentaje_detectado_desde_texto")

    return warnings


def apply_fallback_withholding(normalized: InvoiceData, fallback: InvoiceData) -> list[str]:
    warnings: list[str] = []
    if normalized.retencion_porcentaje <= 0 and fallback.retencion_porcentaje > 0:
        normalized.retencion_porcentaje = fallback.retencion_porcentaje
        warnings.append("retencion_porcentaje_corregido_con_fallback")
    if normalized.retencion <= 0 and fallback.retencion > 0:
        normalized.retencion = fallback.retencion
        warnings.append("retencion_importe_corregido_con_fallback")
    return warnings


def normalize_amounts_with_retention(normalized: InvoiceData, raw_text: str, retention_summary: dict[str, float]) -> list[str]:
    warnings = amount_resolution_service.normalize_amounts(normalized)

    if retention_summary["withholding_amount"] > 0 and retention_summary["total_due"] > 0:
        gross_total = retention_summary["gross_total"] or round(retention_summary["total_due"] + normalized.retencion, 2)
        if gross_total > 0 and normalized.iva_porcentaje > 0:
            inferred_base = retention_summary["base"] or round(
                gross_total - (retention_summary["tax_amount"] or normalized.iva),
                2,
            )
            inferred_tax = retention_summary["tax_amount"] or round(
                inferred_base * normalized.iva_porcentaje / 100,
                2,
            )
            normalized.base_imponible = round(inferred_base, 2)
            normalized.iva = round(inferred_tax, 2)
            normalized.total = round(retention_summary["total_due"], 2)
            warnings.append("importes_corregidos_con_retencion")
    return warnings


def reconcile_with_structured_summary(normalized: InvoiceData, fallback: InvoiceData, raw_text: str) -> list[str]:
    if not (
        raw_text
        and amount_resolution_service.has_structured_tax_summary(raw_text)
        and amount_resolution_service.amounts_are_coherent(fallback)
        and (
            abs(normalized.base_imponible - fallback.base_imponible) > 0.02
            or abs(normalized.iva - fallback.iva) > 0.02
            or abs(normalized.total - fallback.total) > 0.02
        )
    ):
        return []

    normalized.base_imponible = fallback.base_imponible
    normalized.iva_porcentaje = fallback.iva_porcentaje or normalized.iva_porcentaje
    normalized.iva = fallback.iva
    normalized.retencion_porcentaje = fallback.retencion_porcentaje or normalized.retencion_porcentaje
    normalized.retencion = fallback.retencion or normalized.retencion
    normalized.total = fallback.total
    return ["importes_corregidos_con_resumen_fallback"]


def clear_withholding_if_needed(normalized: InvoiceData, raw_text: str) -> list[str]:
    if not amount_resolution_service.should_clear_withholding(normalized, raw_text):
        return []
    normalized.retencion = 0.0
    normalized.retencion_porcentaje = 0.0
    warnings = ["retencion_descartada_sin_indicios_textuales"]
    warnings.extend(amount_resolution_service.normalize_amounts(normalized))
    return warnings
