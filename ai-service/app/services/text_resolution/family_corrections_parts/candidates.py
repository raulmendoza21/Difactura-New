from __future__ import annotations

from app.models.invoice_model import InvoiceData
from app.services.text_resolution.company_matching import company_matching_service
from app.services.text_resolution.party_resolution import party_resolution_service


def best_external_party_candidate(
    *,
    normalized: InvoiceData,
    fallback: InvoiceData,
    company: dict[str, str],
    raw_text: str = "",
) -> dict[str, object] | None:
    candidates: list[dict[str, object]] = []
    seen: set[tuple[str, str]] = set()

    raw_parties = party_resolution_service.extract_parties_from_raw_text(raw_text) if raw_text else {}

    for name, tax_id in (
        (fallback.proveedor, fallback.cif_proveedor),
        (normalized.proveedor, normalized.cif_proveedor),
        (fallback.cliente, fallback.cif_cliente),
        (normalized.cliente, normalized.cif_cliente),
        (raw_parties.get("proveedor", ""), raw_parties.get("cif_proveedor", "")),
        (raw_parties.get("cliente", ""), raw_parties.get("cif_cliente", "")),
    ):
        clean_name = party_resolution_service.normalize_party_name(name)
        clean_tax_id = party_resolution_service.clean_tax_id(tax_id)
        if not clean_name and not clean_tax_id:
            continue
        if company_matching_service.matches_company_context(clean_name, clean_tax_id, company):
            continue
        key = (
            company_matching_service.normalize_party_value(clean_name),
            clean_tax_id,
        )
        if key in seen:
            continue
        seen.add(key)
        candidates.append(
            {
                "name": clean_name,
                "tax_id": clean_tax_id,
                "score": party_resolution_service.party_candidate_score(clean_name, clean_tax_id),
            }
        )

    if not candidates:
        return None

    candidates.sort(key=lambda item: (item["score"], bool(item["tax_id"]), len(str(item["name"]))), reverse=True)
    return candidates[0]
