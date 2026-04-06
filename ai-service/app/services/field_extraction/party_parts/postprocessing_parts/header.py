from __future__ import annotations

import re

from app.models.invoice_model import InvoiceData

from ...shared import (
    DOCUMENT_HEADER_LINE,
    GENERIC_HEADER_NOISE,
    STOP_PARTY_LINE,
    extract_line_tax_ids,
    looks_like_company_name,
    looks_like_party_name,
    normalize_party_value,
)


def fill_missing_counterparty_from_header(data: InvoiceData, lines: list[str]) -> None:
    if data.cliente and data.cif_cliente:
        return

    header_end = next(
        (index for index, line in enumerate(lines) if DOCUMENT_HEADER_LINE.match(line.strip())),
        min(len(lines), 18),
    )
    header_lines = lines[:header_end]
    provider_index = -1
    provider_norm = normalize_party_value(data.proveedor)
    if provider_norm:
        for index, line in enumerate(header_lines):
            if provider_norm in normalize_party_value(line):
                provider_index = index
                break

    candidates: list[tuple[str, str]] = []
    for index, line in enumerate(header_lines):
        if provider_index >= 0 and index <= provider_index:
            continue

        candidate_name = _clean_header_party_candidate(line)
        if not candidate_name or normalize_party_value(candidate_name) == normalize_party_value(data.proveedor):
            continue

        nearby_tax_id = ""
        for candidate_line in header_lines[index + 1:index + 13]:
            tax_ids = extract_line_tax_ids(candidate_line)
            if tax_ids:
                nearby_tax_id = tax_ids[0]
                break

        has_context = any(
            re.search(r"\b(?:c/|calle|avda|avenida|urb\.?|pol\.?|cp\b|\d{5})", candidate_line, re.IGNORECASE)
            for candidate_line in header_lines[index + 1:index + 13]
        )
        if nearby_tax_id or has_context:
            candidates.append((candidate_name, nearby_tax_id))

    if not candidates:
        return

    best_name, best_tax_id = candidates[0]
    if not data.cliente:
        data.cliente = best_name
    if not data.cif_cliente and best_tax_id:
        if best_tax_id != data.cif_proveedor:
            data.cif_cliente = best_tax_id
        elif looks_like_company_name(data.proveedor) and not looks_like_company_name(best_name):
            data.cif_cliente = best_tax_id
            data.cif_proveedor = ""


def _clean_header_party_candidate(line: str) -> str:
    cleaned = re.sub(r"^\(\d+\)\s*", "", line.strip())
    cleaned = re.sub(r"\s+", " ", cleaned).strip(" .,:;-")
    if not cleaned or cleaned.upper() in GENERIC_HEADER_NOISE:
        return ""
    if DOCUMENT_HEADER_LINE.match(cleaned) or STOP_PARTY_LINE.match(cleaned):
        return ""
    if extract_line_tax_ids(cleaned):
        return ""
    if any(token in cleaned.upper() for token in ("MAIL:", "WEB:", "HTTP", "TLF", "TEL", "WWW.")):
        return ""
    if not looks_like_party_name(cleaned):
        return ""
    if len(cleaned.split()) < 2 and not looks_like_company_name(cleaned):
        return ""
    return cleaned[:200]
