from __future__ import annotations

from app.models.invoice_model import InvoiceData
from app.services.text_resolution.company_matching import company_matching_service
from app.services.text_resolution.party_resolution import party_resolution_service


def apply_withholding_purchase_corrections(
    *,
    normalized: InvoiceData,
    fallback: InvoiceData,
    company: dict[str, str],
    raw_text: str,
) -> list[str]:
    warnings: list[str] = []
    header_provider = party_resolution_service.extract_ranked_provider_from_header(raw_text, company)
    if header_provider:
        normalized.proveedor = header_provider
    if fallback.proveedor and not company_matching_service.matches_company_context(
        fallback.proveedor,
        fallback.cif_proveedor,
        company,
    ):
        normalized.proveedor = header_provider or fallback.proveedor
    if fallback.cif_proveedor and not company_matching_service.matches_company_context(
        "",
        fallback.cif_proveedor,
        company,
    ):
        normalized.cif_proveedor = fallback.cif_proveedor
    if company["name"] or company["tax_id"]:
        normalized.cliente = company["name"] or normalized.cliente
        normalized.cif_cliente = company["tax_id"] or normalized.cif_cliente
    return warnings
