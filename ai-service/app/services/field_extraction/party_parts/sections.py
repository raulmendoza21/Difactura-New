"""Section-based party extraction helpers."""

from __future__ import annotations

import re

from ..shared import (
    CLIENTE_HEADER,
    PROVEEDOR_HEADER,
    extract_line_tax_ids,
    looks_like_address_or_contact_line,
    looks_like_company_name,
    looks_like_party_name,
    normalize_label_line,
)

LEGAL_FOOTER_HINT = re.compile(r"\b(?:REGISTRO|MERCANTIL|INSCRIPC(?:ION|IÓN))\b", re.IGNORECASE)
LEGAL_NAME_NOISE = re.compile(r"^(?:REGISTRAD[OA]S?|INSCRIT[OA]S?|ADHERID[OA]S?)\b", re.IGNORECASE)


def extract_parallel_party_sections(lines: list[str]) -> dict[str, str]:
    result = {
        "proveedor": "",
        "cliente": "",
        "cif_proveedor": "",
        "cif_cliente": "",
    }

    for index in range(len(lines) - 1):
        current_line = lines[index]
        next_line = lines[index + 1]
        if not PROVEEDOR_HEADER.match(current_line) or not CLIENTE_HEADER.match(next_line):
            continue

        candidates: list[str] = []
        cifs: list[str] = []
        for candidate in lines[index + 2:index + 12]:
            if PROVEEDOR_HEADER.match(candidate) or CLIENTE_HEADER.match(candidate):
                break
            for value in extract_line_tax_ids(candidate):
                if value not in cifs:
                    cifs.append(value)
            if looks_like_party_name(candidate):
                candidates.append(candidate[:200])

        if len(candidates) >= 2:
            result["proveedor"] = candidates[0]
            result["cliente"] = candidates[1]
        if len(cifs) >= 1:
            result["cif_proveedor"] = cifs[0]
        if len(cifs) >= 2:
            result["cif_cliente"] = cifs[1]
        if result["proveedor"] or result["cliente"]:
            return result

    return result


def extract_party_section(lines: list[str], role: str) -> tuple[str, str]:
    header_pattern = PROVEEDOR_HEADER if role == "proveedor" else CLIENTE_HEADER
    other_header_pattern = CLIENTE_HEADER if role == "proveedor" else PROVEEDOR_HEADER

    for index, line in enumerate(lines):
        if not header_pattern.match(line):
            continue

        name = ""
        tax_id = ""
        for candidate in lines[index + 1:index + 7]:
            if other_header_pattern.match(candidate) or header_pattern.match(candidate):
                break
            if not tax_id:
                line_tax_ids = extract_line_tax_ids(candidate)
                if line_tax_ids:
                    tax_id = line_tax_ids[0]
            if not name and looks_like_party_name(candidate):
                name = candidate[:200]
            if name and tax_id:
                break

        if name or tax_id:
            return name, tax_id

    return "", ""


def extract_customer_from_shipping_billing(lines: list[str]) -> tuple[str, str]:
    normalized_lines = [normalize_label_line(line) for line in lines]
    header_indexes = {
        "shipping": next((index for index, line in enumerate(normalized_lines) if line.startswith("datos de env")), -1),
        "billing": next((index for index, line in enumerate(normalized_lines) if line.startswith("datos de facturaci")), -1),
    }

    if header_indexes["shipping"] < 0 and header_indexes["billing"] < 0:
        return "", ""

    section_candidates: list[tuple[str, str]] = []
    for key, start in header_indexes.items():
        if start < 0:
            continue

        other_starts = [value for other_key, value in header_indexes.items() if other_key != key and value > start]
        stop_index = min(other_starts) if other_starts else min(len(lines), start + 24)
        section_lines = lines[start + 1:stop_index]

        name = ""
        tax_id = ""
        for index, line in enumerate(section_lines):
            if not name and (looks_like_company_name(line) or looks_like_party_name(line)):
                name = line[:200]
            if not tax_id:
                tax_ids = extract_line_tax_ids(line)
                if tax_ids:
                    tax_id = tax_ids[0]
                elif normalize_label_line(line) == "cif":
                    for candidate in section_lines[index + 1:index + 4]:
                        candidate_tax_ids = extract_line_tax_ids(candidate)
                        if candidate_tax_ids:
                            tax_id = candidate_tax_ids[0]
                            break
            if name and tax_id:
                break

        if name or tax_id:
            section_candidates.append((name, tax_id))

    if not section_candidates:
        return "", ""

    for name, tax_id in section_candidates:
        if name and tax_id:
            return name, tax_id
    return section_candidates[0]


def extract_footer_legal_party(lines: list[str]) -> tuple[str, str]:
    tail_start = max(0, len(lines) - 24)
    tail_lines = lines[tail_start:]
    best_candidate: tuple[int, str, str] | None = None

    for local_index, line in enumerate(tail_lines):
        if not LEGAL_FOOTER_HINT.search(line):
            continue

        tax_ids = extract_line_tax_ids(line)
        if not tax_ids:
            continue

        name = _extract_company_name_from_legal_line(line)
        if not name:
            for previous_line in reversed(tail_lines[max(0, local_index - 2):local_index]):
                if looks_like_address_or_contact_line(previous_line):
                    continue
                if looks_like_company_name(previous_line) or looks_like_party_name(previous_line):
                    name = previous_line[:200]
                    break

        if not name:
            continue

        score = 0
        upper_line = line.upper()
        if looks_like_company_name(name):
            score += 4
        elif looks_like_party_name(name):
            score += 2
        if tax_ids:
            score += 4
        if "REGISTRO" in upper_line or "MERCANTIL" in upper_line:
            score += 2
        if "CIF" in upper_line or "NIF" in upper_line:
            score += 1

        candidate = (score, name[:200], tax_ids[0])
        if best_candidate is None or candidate > best_candidate:
            best_candidate = candidate

    if best_candidate is None:
        return "", ""
    return best_candidate[1], best_candidate[2]


def _extract_company_name_from_legal_line(line: str) -> str:
    cleaned = (line or "").strip()
    if not cleaned:
        return ""

    candidate = re.split(r"\b(?:CIF|NIF)\b", cleaned, maxsplit=1, flags=re.IGNORECASE)[0].strip(" -,:;")
    candidate = re.split(r"\bREGISTRO\b", candidate, maxsplit=1, flags=re.IGNORECASE)[0].strip(" -,:;")
    if " - " in candidate:
        candidate = candidate.split(" - ", 1)[0].strip(" -,:;")

    if LEGAL_NAME_NOISE.match(candidate):
        return ""
    if looks_like_address_or_contact_line(candidate):
        return ""
    if looks_like_company_name(candidate) or looks_like_party_name(candidate):
        return candidate[:200]
    return ""
