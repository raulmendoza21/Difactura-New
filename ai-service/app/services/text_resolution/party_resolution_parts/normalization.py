from __future__ import annotations

from app.models.invoice_model import InvoiceData

from .raw_text import extract_parties_from_raw_text
from .shared import normalize_party_name, normalize_tax_id_value, should_promote_party_candidate, values_match


def normalize_parties(
    data: InvoiceData,
    fallback: InvoiceData,
    *,
    raw_text: str,
    company_context: dict[str, str] | None = None,
) -> list[str]:
    warnings: list[str] = []

    data.proveedor = normalize_party_name(data.proveedor)
    data.cliente = normalize_party_name(data.cliente)
    fallback_provider = normalize_party_name(fallback.proveedor)
    fallback_client = normalize_party_name(fallback.cliente)
    raw_parties = extract_parties_from_raw_text(raw_text, company_context=company_context)

    if not data.proveedor and fallback_provider:
        data.proveedor = fallback_provider
        warnings.append("proveedor_corregido_con_fallback")

    if not data.cliente and fallback_client:
        data.cliente = fallback_client
        warnings.append("cliente_corregido_con_fallback")

    if data.proveedor and data.cliente and values_match(data.proveedor, data.cliente):
        if fallback_provider and not values_match(fallback_provider, data.cliente):
            data.proveedor = fallback_provider
            warnings.append("proveedor_desambiguado_con_fallback")
        elif fallback_client and not values_match(fallback_client, data.proveedor):
            data.cliente = fallback_client
            warnings.append("cliente_desambiguado_con_fallback")

    if should_promote_party_candidate(
        current_name=data.proveedor,
        current_tax_id=data.cif_proveedor,
        candidate_name=raw_parties["proveedor"],
        candidate_tax_id=raw_parties["cif_proveedor"],
    ):
        data.proveedor = raw_parties["proveedor"]
        if raw_parties["cif_proveedor"]:
            data.cif_proveedor = raw_parties["cif_proveedor"]
        warnings.append("proveedor_detectado_desde_bloque_texto")

    if raw_parties["cif_proveedor"] and (not data.cif_proveedor or data.cif_proveedor == data.cif_cliente):
        data.cif_proveedor = raw_parties["cif_proveedor"]
        warnings.append("cif_proveedor_detectado_desde_bloque_texto")

    if should_promote_party_candidate(
        current_name=data.cliente,
        current_tax_id=data.cif_cliente,
        candidate_name=raw_parties["cliente"],
        candidate_tax_id=raw_parties["cif_cliente"],
    ):
        data.cliente = raw_parties["cliente"]
        if raw_parties["cif_cliente"]:
            data.cif_cliente = raw_parties["cif_cliente"]
        warnings.append("cliente_detectado_desde_bloque_texto")

    if raw_parties["cif_cliente"] and not data.cif_cliente:
        data.cif_cliente = raw_parties["cif_cliente"]
        warnings.append("cif_cliente_detectado_desde_bloque_texto")

    data.cif_proveedor, provider_tax_warnings = normalize_tax_id_value(
        data.cif_proveedor,
        fallback.cif_proveedor,
        role="proveedor",
    )
    warnings.extend(provider_tax_warnings)

    data.cif_cliente, customer_tax_warnings = normalize_tax_id_value(
        data.cif_cliente,
        fallback.cif_cliente,
        role="cliente",
    )
    warnings.extend(customer_tax_warnings)

    return warnings
