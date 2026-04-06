from __future__ import annotations

from app.models.invoice_model import InvoiceData
from app.services.text_resolution.company_matching import company_matching_service
from app.services.text_resolution.family_corrections_parts.candidates import best_external_party_candidate
from app.services.text_resolution.party_resolution import party_resolution_service


def apply_shipping_billing_purchase_corrections(
    *,
    normalized: InvoiceData,
    fallback: InvoiceData,
    company: dict[str, str],
    raw_text: str,
) -> list[str]:
    warnings: list[str] = []
    footer_provider = party_resolution_service.extract_footer_legal_party(raw_text, company)
    best_counterparty = best_external_party_candidate(
        normalized=normalized,
        fallback=fallback,
        company=company,
        raw_text=raw_text,
    )

    selected_provider_name = ""
    selected_provider_tax_id = ""
    if footer_provider["name"] or footer_provider["tax_id"]:
        selected_provider_name = str(footer_provider["name"] or "")
        selected_provider_tax_id = str(footer_provider["tax_id"] or "")
    elif best_counterparty:
        selected_provider_name = str(best_counterparty["name"] or "")
        selected_provider_tax_id = str(best_counterparty["tax_id"] or "")
    elif fallback.proveedor and not company_matching_service.matches_company_context(
        fallback.proveedor,
        fallback.cif_proveedor,
        company,
    ):
        selected_provider_name = fallback.proveedor
        selected_provider_tax_id = fallback.cif_proveedor

    if selected_provider_name and (
        normalized.proveedor != selected_provider_name or normalized.cif_proveedor != selected_provider_tax_id
    ):
        normalized.proveedor = selected_provider_name
        normalized.cif_proveedor = selected_provider_tax_id or normalized.cif_proveedor
        warnings.append("familia_shipping_billing_proveedor_corregido")

    if company["name"] or company["tax_id"]:
        normalized.cliente = company["name"] or normalized.cliente
        normalized.cif_cliente = company["tax_id"] or normalized.cif_cliente
    return warnings
