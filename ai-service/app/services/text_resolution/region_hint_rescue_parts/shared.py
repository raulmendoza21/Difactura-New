from __future__ import annotations

import re
from typing import Any

from app.models.invoice_model import InvoiceData
from app.services.text_resolution.company_matching import company_matching_service


def should_run(
    *,
    base_candidate: InvoiceData,
    input_profile: dict[str, Any],
    company_context: dict[str, str] | None,
) -> bool:
    company = company_matching_service.normalize_company_context(company_context)
    if not company["name"] and not company["tax_id"]:
        return False

    input_kind = input_profile.get("input_kind", "")
    if input_kind not in {"pdf_scanned", "image_scan", "image_photo"}:
        return False

    provider_matches = company_matching_service.matches_company_context(
        base_candidate.proveedor,
        base_candidate.cif_proveedor,
        company,
    )
    client_matches = company_matching_service.matches_company_context(
        base_candidate.cliente,
        base_candidate.cif_cliente,
        company,
    )
    if provider_matches or client_matches:
        return False

    provider_value = str(base_candidate.proveedor or "").strip()
    client_value = str(base_candidate.cliente or "").strip()
    missing_party = not provider_value or not client_value
    long_noise_party = len(provider_value) > 90 or len(client_value) > 90
    missing_tax_ids = not base_candidate.cif_proveedor or not base_candidate.cif_cliente
    return missing_party or long_noise_party or missing_tax_ids


def stringify_candidate_value(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, float):
        return f"{value:.2f}".rstrip("0").rstrip(".")
    return str(value)


def normalize_hint_lookup(value: str) -> str:
    return re.sub(r"\s+", " ", str(value or "").upper()).strip()


def region_hint_priority(region_type: str) -> int:
    priorities = {
        "header_left": 0,
        "header_right": 1,
        "header": 2,
        "totals": 3,
    }
    return priorities.get(region_type, 9)


def format_exception(exc: Exception) -> str:
    message = str(exc).strip()
    if message:
        return message
    return exc.__class__.__name__
