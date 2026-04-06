from __future__ import annotations

from app.models.invoice_model import InvoiceData
from app.services.text_resolution.company_matching import company_matching_service
from app.services.text_resolution.family_corrections_parts.candidates import best_external_party_candidate
from app.services.text_resolution.line_items import line_item_resolution_service


def apply_company_sale_corrections(
    *,
    normalized: InvoiceData,
    fallback: InvoiceData,
    company: dict[str, str],
    raw_text: str,
) -> list[str]:
    warnings: list[str] = []
    normalized_provider_matches = company_matching_service.matches_company_context(
        normalized.proveedor,
        normalized.cif_proveedor,
        company,
    )
    normalized_client_matches = company_matching_service.matches_company_context(
        normalized.cliente,
        normalized.cif_cliente,
        company,
    )
    fallback_provider_matches = company_matching_service.matches_company_context(
        fallback.proveedor,
        fallback.cif_proveedor,
        company,
    )
    fallback_client_matches = company_matching_service.matches_company_context(
        fallback.cliente,
        fallback.cif_cliente,
        company,
    )
    best_counterparty = best_external_party_candidate(
        normalized=normalized,
        fallback=fallback,
        company=company,
        raw_text=raw_text,
    )

    if (
        normalized_provider_matches
        or normalized_client_matches
        or fallback_provider_matches
        or fallback_client_matches
    ):
        previous_provider = (normalized.proveedor, normalized.cif_proveedor)
        previous_client = (normalized.cliente, normalized.cif_cliente)
        normalized.proveedor = company["name"] or normalized.proveedor
        normalized.cif_proveedor = company["tax_id"] or normalized.cif_proveedor
        if best_counterparty:
            normalized.cliente = str(best_counterparty["name"] or normalized.cliente)
            normalized.cif_cliente = str(best_counterparty["tax_id"] or normalized.cif_cliente)
        if previous_provider != (normalized.proveedor, normalized.cif_proveedor) or previous_client != (
            normalized.cliente,
            normalized.cif_cliente,
        ):
            warnings.append("familia_company_sale_roles_corregidos")

    warnings.extend(line_item_resolution_service.repair_single_line_tax_confusion(normalized))
    return warnings
