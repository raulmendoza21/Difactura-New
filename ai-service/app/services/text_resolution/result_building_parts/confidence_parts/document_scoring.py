from __future__ import annotations

import re

from app.models.invoice_model import InvoiceData
from app.services.text_resolution.amounts import amount_resolution_service


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
    score = float(current_confidence or 0.0)
    company_match = company_match or {}
    optional_low_fields = optional_low_fields or set()
    normalized_warnings = [warning.lower() for warning in warnings]
    source_discrepancy_count = sum(1 for warning in normalized_warnings if warning.startswith("discrepancia_"))
    resolved_warning_count = sum(
        1
        for warning in normalized_warnings
        if any(
            token in warning
            for token in (
                "corregido",
                "desambiguado",
                "reconciliad",
                "reconstruido",
                "inferido",
                "ajustado",
                "enriquecid",
                "completad",
            )
        )
    )
    critical_warning_count = sum(1 for warning in normalized_warnings if "no_valido" in warning or "falt" in warning)
    secondary_warning_count = max(
        0,
        len(normalized_warnings) - source_discrepancy_count - resolved_warning_count - critical_warning_count,
    )

    final_is_coherent = amount_resolution_service.amounts_are_coherent(invoice)
    line_sum = round(sum(line.importe for line in invoice.lineas if line.importe > 0), 2)
    line_items_are_coherent = _line_items_are_coherent(invoice, line_sum)
    semantic_penalty, semantic_cap = _semantic_party_penalty(invoice, company_match)

    if semantic_penalty:
        score -= semantic_penalty

    if critical_warning_count:
        score -= min(0.24, critical_warning_count * 0.1)

    if final_is_coherent and line_items_are_coherent:
        if source_discrepancy_count:
            score -= min(0.12, source_discrepancy_count * 0.03)
        if resolved_warning_count:
            if document_type in {"ticket", "factura_simplificada"}:
                score -= min(0.02, resolved_warning_count * 0.005)
            else:
                score -= min(0.04, resolved_warning_count * 0.01)
        if secondary_warning_count:
            if document_type in {"ticket", "factura_simplificada"}:
                score -= min(0.03, secondary_warning_count * 0.01)
            else:
                score -= min(0.06, secondary_warning_count * 0.02)
    else:
        if source_discrepancy_count:
            score -= min(0.24, source_discrepancy_count * 0.08)
        if resolved_warning_count:
            score -= min(0.16, resolved_warning_count * 0.05)
        if secondary_warning_count:
            score -= min(0.12, secondary_warning_count * 0.04)

    key_fields = [
        "numero_factura",
        "fecha",
        "proveedor",
        "cif_proveedor",
        "base_imponible",
        "iva_porcentaje",
        "iva",
        "total",
        "lineas",
    ]
    if invoice.cliente or invoice.cif_cliente:
        key_fields.extend(("cliente", "cif_cliente"))
    low_fields = [
        field
        for field in key_fields
        if field not in optional_low_fields and (field_confidence.get(field) or 0) < 0.75
    ]
    medium_fields = [
        field
        for field in key_fields
        if field not in optional_low_fields and 0.75 <= (field_confidence.get(field) or 0) < 0.9
    ]

    if low_fields:
        if final_is_coherent and line_items_are_coherent:
            score -= min(0.12, len(low_fields) * 0.02)
        else:
            score -= min(0.24, len(low_fields) * 0.04)
    if len(medium_fields) >= 3:
        score -= 0.02 if final_is_coherent and line_items_are_coherent else 0.04

    if not line_items_are_coherent and line_sum > 0:
        if invoice.base_imponible > 0 or invoice.total > 0:
            score -= 0.12

    if critical_warning_count >= 2:
        score = min(score, 0.78)
    elif critical_warning_count == 1:
        score = min(score, 0.88)
    elif normalized_warnings and not final_is_coherent:
        score = min(score, 0.94)

    if not final_is_coherent and len(low_fields) >= 3:
        score = min(score, 0.74)
    elif not final_is_coherent and len(low_fields) >= 1:
        score = min(score, 0.89)

    if final_is_coherent and line_items_are_coherent:
        if document_type in {"ticket", "factura_simplificada"}:
            score = max(score, 0.58 if normalized_warnings else 0.68)
        else:
            score = max(score, 0.72 if normalized_warnings else 0.8)
    if semantic_cap is not None:
        score = min(score, semantic_cap)

    return round(max(0.0, min(1.0, score)), 2)


def _line_items_are_coherent(invoice: InvoiceData, line_sum: float) -> bool:
    if line_sum <= 0:
        return True

    candidate_targets: list[tuple[float, float]] = []
    if invoice.base_imponible > 0:
        candidate_targets.append((invoice.base_imponible, max(0.02, invoice.base_imponible * 0.01)))
    if invoice.total > 0:
        candidate_targets.append((invoice.total, max(0.02, invoice.total * 0.01)))

    if not candidate_targets:
        return True

    return any(abs(line_sum - target) <= tolerance for target, tolerance in candidate_targets)


def _semantic_party_penalty(invoice: InvoiceData, company_match: dict[str, object]) -> tuple[float, float | None]:
    penalty = 0.0
    cap: float | None = None

    normalized_provider = _normalize_party_value(invoice.proveedor)
    normalized_client = _normalize_party_value(invoice.cliente)
    if normalized_provider and normalized_client and normalized_provider == normalized_client:
        penalty += 0.18
        cap = min(cap, 0.68) if cap is not None else 0.68

    normalized_provider_tax_id = _normalize_tax_id(invoice.cif_proveedor)
    normalized_client_tax_id = _normalize_tax_id(invoice.cif_cliente)
    if (
        normalized_provider_tax_id
        and normalized_client_tax_id
        and normalized_provider_tax_id == normalized_client_tax_id
    ):
        penalty += 0.22
        cap = min(cap, 0.64) if cap is not None else 0.64

    matched_role = str(company_match.get("matched_role", "") or "")
    if matched_role == "ambiguous" or (
        company_match.get("issuer_matches_company") and company_match.get("recipient_matches_company")
    ):
        penalty += 0.1
        cap = min(cap, 0.78) if cap is not None else 0.78

    return penalty, cap


def _normalize_party_value(value: str) -> str:
    return re.sub(r"[^A-Z0-9]", "", str(value or "").upper())


def _normalize_tax_id(value: str) -> str:
    return re.sub(r"\s+", "", str(value or "").upper())
