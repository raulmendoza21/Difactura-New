from __future__ import annotations

import re

from app.services.field_extraction.shared import looks_like_ticket_document

from .shared import (
    compact_keyword_text,
    is_generic_party_candidate,
    looks_like_address_or_contact_line,
    matches_company_context,
    normalize_party_name,
    party_candidate_score,
)

EXPLICIT_CUSTOMER_LABEL = re.compile(r"\b(?:CLIENTE|DESTINATARIO|FACTURAR A|DATOS DEL CLIENTE)\b", re.IGNORECASE)
TICKET_HEADER_STOP = re.compile(
    r"\b(?:FECHA|HORA|MESA|CAMARERO|ARTICULO|UDS\b|TOTAL\b|TOTAL COMPRA|DETALLE DE PAGOS|CENTRO|VEND\.?|DOCUMENTO)\b",
    re.IGNORECASE,
)
EXPLICIT_TAX_LABEL = re.compile(r"\b(?:CIF|NIF|VAT)\b", re.IGNORECASE)
LEGAL_ENTITY_HINT = re.compile(r"(?:\bSL\b|S\.L\.?|\bSA\b|S\.A\.?|\bSLU\b|S\.L\.U\.?)", re.IGNORECASE)


def extract_ticket_parties(raw_text: str, company_context: dict[str, str] | None = None) -> dict[str, str]:
    result = {"proveedor": "", "cif_proveedor": "", "cliente": "", "cif_cliente": ""}
    if not looks_like_ticket_document(raw_text):
        return result

    lines = [_normalize_ticket_line(line) for line in raw_text.splitlines()]
    lines = [line for line in lines if line]
    if not lines:
        return result

    header_lines = _collect_ticket_header_lines(lines)
    provider_name, provider_tax_id = _select_ticket_provider(header_lines, company_context)
    result["proveedor"] = provider_name
    result["cif_proveedor"] = provider_tax_id

    if has_explicit_ticket_customer(raw_text):
        result.update(_extract_explicit_customer(lines))
    return result


def has_explicit_ticket_customer(raw_text: str) -> bool:
    if not looks_like_ticket_document(raw_text):
        return False
    return any(EXPLICIT_CUSTOMER_LABEL.search(line) for line in (raw_text or "").splitlines())


def _collect_ticket_header_lines(lines: list[str]) -> list[str]:
    header_lines: list[str] = []
    for line in lines[:18]:
        if TICKET_HEADER_STOP.search(line):
            break
        header_lines.append(line)
    return header_lines


def _select_ticket_provider(
    lines: list[str],
    company_context: dict[str, str] | None,
) -> tuple[str, str]:
    best_candidate: tuple[int, str, str] | None = None

    for index, line in enumerate(lines):
        cleaned = normalize_party_name(line)
        if not cleaned:
            continue
        if is_generic_party_candidate(cleaned) or looks_like_address_or_contact_line(cleaned):
            continue
        if matches_company_context(cleaned, "", company_context):
            continue

        nearby_tax_id, tax_distance = _find_nearby_tax_id(lines, index)
        score = party_candidate_score(cleaned, nearby_tax_id)
        upper_cleaned = cleaned.upper()
        if EXPLICIT_TAX_LABEL.search(" ".join(lines[index:index + 2])):
            score += 2
        if LEGAL_ENTITY_HINT.search(upper_cleaned):
            score += 2
        if not nearby_tax_id and len(cleaned.split()) <= 2:
            score -= 1
        if nearby_tax_id:
            score += max(0, 2 - tax_distance)
        elif len(cleaned.split()) >= 3:
            score += 1
        if nearby_tax_id and not LEGAL_ENTITY_HINT.search(upper_cleaned):
            score -= 1

        candidate = (score, cleaned, nearby_tax_id)
        if best_candidate is None or candidate > best_candidate:
            best_candidate = candidate

    if best_candidate is None:
        return "", ""
    return best_candidate[1], best_candidate[2]


def _find_nearby_tax_id(lines: list[str], index: int) -> tuple[str, int]:
    tax_id_pattern = re.compile(r"[A-Z]\d{7}[A-Z0-9]|\d{8}[A-Z]")
    for offset, candidate_line in enumerate(lines[index:index + 3]):
        compact = re.sub(r"[\s.\-]", "", candidate_line.upper())
        if not EXPLICIT_TAX_LABEL.search(candidate_line):
            continue
        matches = tax_id_pattern.findall(compact)
        if matches:
            return matches[0], offset
    return "", 99


def _extract_explicit_customer(lines: list[str]) -> dict[str, str]:
    result = {"cliente": "", "cif_cliente": ""}
    for index, line in enumerate(lines):
        if not EXPLICIT_CUSTOMER_LABEL.search(line):
            continue
        for candidate in lines[index + 1:index + 5]:
            if not result["cliente"]:
                normalized_candidate = normalize_party_name(candidate)
                if normalized_candidate and not looks_like_address_or_contact_line(normalized_candidate):
                    result["cliente"] = normalized_candidate
                    continue
            compact_candidate = re.sub(r"[\s.\-]", "", candidate.upper())
            matches = re.findall(r"[A-Z]\d{7}[A-Z0-9]|\d{8}[A-Z]", compact_candidate)
            if matches:
                result["cif_cliente"] = matches[0]
                break
        break
    return result


def _normalize_ticket_line(value: str) -> str:
    cleaned = re.sub(r"\s+", " ", (value or "").strip())
    cleaned = cleaned.lstrip("#").strip()
    compact = compact_keyword_text(cleaned)
    if compact in {"PVP", "IMPORTE", "UDS", "DESCRIPCION", "DESCRIPCION SALA 1"}:
        return ""
    if re.fullmatch(r"\*{2,}.*", cleaned):
        return ""
    if re.fullmatch(r"\[[A-Z0-9-]+\]", cleaned):
        return ""
    return cleaned
