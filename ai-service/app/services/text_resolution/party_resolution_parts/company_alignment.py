from __future__ import annotations

from app.models.invoice_model import InvoiceData
from app.services.text_resolution.company_matching import company_matching_service

from .shared import matches_company_context, party_candidate_score


def align_with_company_context(
    normalized: InvoiceData,
    fallback: InvoiceData,
    company_context: dict[str, str] | None,
) -> list[str]:
    company = company_matching_service.normalize_company_context(company_context)
    warnings: list[str] = []
    if not company["name"] and not company["tax_id"]:
        return warnings

    provider_matches = matches_company_context(normalized.proveedor, normalized.cif_proveedor, company)
    client_matches = matches_company_context(normalized.cliente, normalized.cif_cliente, company)
    fallback_provider_matches = matches_company_context(fallback.proveedor, fallback.cif_proveedor, company)
    fallback_client_matches = matches_company_context(fallback.cliente, fallback.cif_cliente, company)

    if fallback_provider_matches and not provider_matches:
        normalized.proveedor = company["name"] or fallback.proveedor or normalized.proveedor
        normalized.cif_proveedor = company["tax_id"] or fallback.cif_proveedor or normalized.cif_proveedor
        provider_matches = True
        warnings.append("proveedor_alineado_con_empresa_asociada")

    if fallback_client_matches and not client_matches:
        normalized.cliente = company["name"] or fallback.cliente or normalized.cliente
        normalized.cif_cliente = company["tax_id"] or fallback.cif_cliente or normalized.cif_cliente
        client_matches = True
        warnings.append("cliente_alineado_con_empresa_asociada")

    if provider_matches and client_matches:
        fallback_client_score = party_candidate_score(fallback.cliente, fallback.cif_cliente)
        fallback_provider_score = party_candidate_score(fallback.proveedor, fallback.cif_proveedor)

        if fallback_client_matches and not fallback_provider_matches and fallback_provider_score >= 3:
            normalized.proveedor = fallback.proveedor or normalized.proveedor
            normalized.cif_proveedor = fallback.cif_proveedor or normalized.cif_proveedor
            normalized.cliente = company["name"] or normalized.cliente
            normalized.cif_cliente = company["tax_id"] or normalized.cif_cliente
            warnings.append("proveedor_restaurado_desde_fallback")
        elif fallback_provider_matches and not fallback_client_matches and fallback_client_score >= 3:
            normalized.cliente = fallback.cliente or normalized.cliente
            normalized.cif_cliente = fallback.cif_cliente or normalized.cif_cliente
            normalized.proveedor = company["name"] or normalized.proveedor
            normalized.cif_proveedor = company["tax_id"] or normalized.cif_proveedor
            warnings.append("cliente_restaurado_desde_fallback")

    if provider_matches and not client_matches:
        if party_candidate_score(fallback.cliente, fallback.cif_cliente) > party_candidate_score(
            normalized.cliente,
            normalized.cif_cliente,
        ):
            normalized.cliente = fallback.cliente or normalized.cliente
            normalized.cif_cliente = fallback.cif_cliente or normalized.cif_cliente
    elif client_matches and not provider_matches:
        if party_candidate_score(fallback.proveedor, fallback.cif_proveedor) > party_candidate_score(
            normalized.proveedor,
            normalized.cif_proveedor,
        ):
            normalized.proveedor = fallback.proveedor or normalized.proveedor
            normalized.cif_proveedor = fallback.cif_proveedor or normalized.cif_proveedor

    return warnings
