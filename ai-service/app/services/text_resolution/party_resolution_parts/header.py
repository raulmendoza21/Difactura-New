from __future__ import annotations

import re

from app.services.text_resolution.company_matching import company_matching_service

from .shared import (
    compact_keyword_text,
    is_generic_party_candidate,
    looks_like_address_or_contact_line,
    matches_company_context,
    normalize_party_name,
    party_candidate_score,
)


def extract_ranked_provider_from_header(raw_text: str, company_context: dict[str, str] | None) -> str:
    company = company_matching_service.normalize_company_context(company_context)
    lines = [line.strip() for line in raw_text.splitlines() if line.strip()]
    candidates: list[tuple[int, str]] = []
    header_lines = lines[:18]

    for index, line in enumerate(header_lines):
        compact_line = re.sub(r"[\s.\-]", "", line.upper())
        matches = re.findall(r"[A-Z]\d{7}[A-Z0-9]|\d{8}[A-Z]", compact_line)
        tax_ids = [value for value in matches if not company.get("tax_id") or value != company["tax_id"]]
        if not tax_ids:
            continue

        anchored_candidates: list[tuple[int, str]] = []
        for candidate_line in reversed(header_lines[max(0, index - 12):index]):
            cleaned = re.sub(r"^\(\d+\)\s*", "", candidate_line).strip(" .,:;-")
            upper_candidate = cleaned.upper()
            if not cleaned or is_generic_party_candidate(cleaned):
                continue
            if matches_company_context(cleaned, "", company):
                continue
            if looks_like_address_or_contact_line(cleaned):
                continue
            if re.search(r",\s*\d{1,4}\b", cleaned) or re.search(r"\b\d{5}\b", upper_candidate):
                continue
            if not normalize_party_name(cleaned):
                continue
            candidate_score = party_candidate_score(cleaned, tax_ids[0])
            if re.search(r"\b(SL|S\.L\.|SA|S\.A\.|SLU|S\.L\.U\.)\b", upper_candidate):
                candidate_score += 2
            elif len(cleaned.split()) <= 2:
                candidate_score -= 2
            if "," in cleaned and not re.search(r"\d", cleaned):
                candidate_score += 1
            anchored_candidates.append((candidate_score, cleaned))

        if anchored_candidates:
            anchored_candidates.sort(key=lambda item: (item[0], len(item[1])), reverse=True)
            best_score, best_name = anchored_candidates[0]
            if best_score >= 3:
                return best_name

    for index, line in enumerate(header_lines):
        upper_line = line.upper()
        if "CLIENTE" in compact_keyword_text(line):
            break
        if matches_company_context(line, "", company):
            continue
        if any(token in upper_line for token in ("FACTURA", "DOCUMENTO", "FECHA", "NIF", "CIF", "DOMICILIO")):
            continue
        if looks_like_address_or_contact_line(line):
            continue

        cleaned = re.sub(r"^\(\d+\)\s*", "", line).strip(" .,:;-")
        if not cleaned or is_generic_party_candidate(cleaned):
            continue
        if re.search(r",\s*\d{1,4}\b", cleaned) or re.search(r"\b\d{5}\b", upper_line):
            continue
        if matches_company_context(cleaned, "", company):
            continue
        if not normalize_party_name(cleaned):
            continue

        nearby_tax_id = ""
        for candidate_line in lines[index:index + 4]:
            compact_line = re.sub(r"[\s.\-]", "", candidate_line.upper())
            matches = re.findall(r"[A-Z]\d{7}[A-Z0-9]|\d{8}[A-Z]", compact_line)
            for candidate_tax_id in matches:
                if company.get("tax_id") and candidate_tax_id == company["tax_id"]:
                    continue
                nearby_tax_id = candidate_tax_id
                break
            if nearby_tax_id:
                break

        candidate_score = party_candidate_score(cleaned, nearby_tax_id)
        upper_cleaned = cleaned.upper()
        if re.search(r"\b(SL|S\.L\.|SA|S\.A\.|SLU|S\.L\.U\.)\b", upper_cleaned):
            candidate_score += 2
        elif len(cleaned.split()) <= 2:
            candidate_score -= 2
        if "," in cleaned and not re.search(r"\d", cleaned):
            candidate_score += 1
        candidates.append((candidate_score, cleaned))

    if candidates:
        candidates.sort(key=lambda item: (item[0], len(item[1])), reverse=True)
        best_score, best_name = candidates[0]
        if best_score >= 3:
            return best_name

    return extract_provider_from_header(raw_text, company)


def _is_header_stop_line(value: str) -> bool:
    compact = compact_keyword_text(value)
    if compact == "FACTURA" or compact == "CLIENTE":
        return True
    return "DATOS DE FACTURACI" in compact or "DATOS DE ENVI" in compact


def extract_provider_from_header(raw_text: str, company_context: dict[str, str] | None) -> str:
    company = company_matching_service.normalize_company_context(company_context)
    lines = [line.strip() for line in raw_text.splitlines() if line.strip()]
    for line in lines[:12]:
        upper_line = line.upper()
        if _is_header_stop_line(line) or matches_company_context(line, "", company):
            if "CLIENTE" in compact_keyword_text(line):
                break
            continue
        if any(token in upper_line for token in ("NIF", "CIF", "DOMICILIO")):
            continue
        if looks_like_address_or_contact_line(line):
            continue
        cleaned = re.sub(r"^\(\d+\)\s*", "", line).strip(" .,:;-")
        if not cleaned or is_generic_party_candidate(cleaned):
            continue
        if matches_company_context(cleaned, "", company):
            continue
        if normalize_party_name(cleaned):
            return cleaned
    return ""
