from __future__ import annotations

import re

from app.services.text_resolution.company_matching import company_matching_service


def matches_company_context(name: str, tax_id: str, company_context: dict[str, str] | None) -> bool:
    company = company_matching_service.normalize_company_context(company_context)
    return company_matching_service.matches_company_context(name, tax_id, company)


def compact_keyword_text(value: str) -> str:
    compact = re.sub(r"[^A-Z0-9]+", " ", (value or "").upper())
    return re.sub(r"\s+", " ", compact).strip()


def normalize_party_name(value: str) -> str:
    cleaned = re.sub(r"\s+", " ", (value or "").strip()).strip(" .,:;-")
    if not cleaned:
        return ""

    normalized_token = re.sub(r"[^A-Z0-9]", "", cleaned.upper())
    blocked_tokens = {"CLIENTE", "EMISOR", "PROVEEDOR", "DESTINATARIO", "COMPRADOR", "FACTURA"}
    if normalized_token in blocked_tokens:
        return ""

    letters = sum(char.isalpha() for char in cleaned)
    digits = sum(char.isdigit() for char in cleaned)
    if letters < 3 or digits > max(3, letters):
        return ""
    return cleaned[:200]


def is_generic_party_candidate(value: str) -> bool:
    normalized = compact_keyword_text(value)
    if not normalized:
        return True
    generic_values = {
        "DOMICILIO",
        "CLIENTE",
        "PROVEEDOR",
        "EMISOR",
        "RECEPTOR",
    }
    if normalized in generic_values:
        return True
    return bool(re.fullmatch(r"\d{5}.*", normalized))


def looks_like_address_or_contact_line(value: str) -> bool:
    keyword_text = compact_keyword_text(value)
    if not keyword_text:
        return False

    if re.search(r"\b(?:HTTP|WWW|MAIL|EMAIL|TEL|TLF|TFNO|TELEFONO)\b", keyword_text):
        return True
    if re.search(r"\bM ?VIL\b", keyword_text):
        return True
    raw_text = str(value or "").upper()
    if re.search(r"(?:^|[\s(,;:-])C/\s*", raw_text):
        return True
    if re.search(r"\b(?:CALLE|AVDA|AVENIDA|URB|LOCAL|POL|POLIGONO|CTRA|PLAZA|PASEO)\b", keyword_text):
        return True
    if re.search(r",\s*\d{1,4}\b", str(value or "")):
        return True
    if re.search(r"\b\d{5}\b", keyword_text):
        return True
    return False


def party_candidate_score(name: str, tax_id: str) -> int:
    score = 0
    clean_name = normalize_party_name(name)
    if clean_name:
        score += 2
        if len(clean_name.split()) >= 2:
            score += 1
        if re.search(r"\b(SL|S\.L\.|SA|S\.A\.|SLU|S\.L\.U\.|S\.C\.|S\.C\.P\.?|SCPROFESIONAL|PROFESIONAL)\b", clean_name.upper()):
            score += 1
        if len(clean_name.split()) >= 5:
            score += 1
    if is_valid_tax_id(clean_tax_id(tax_id)):
        score += 3
    if is_generic_party_candidate(clean_name):
        score -= 3
    if clean_name and looks_like_address_or_contact_line(clean_name):
        score -= 2
    return score


def should_promote_party_candidate(
    *,
    current_name: str,
    current_tax_id: str,
    candidate_name: str,
    candidate_tax_id: str,
) -> bool:
    if not candidate_name and not candidate_tax_id:
        return False
    if is_generic_party_candidate(candidate_name) and not is_valid_tax_id(candidate_tax_id):
        return False

    current_score = party_candidate_score(current_name, current_tax_id)
    candidate_score = party_candidate_score(candidate_name, candidate_tax_id)
    if current_score <= 0:
        return candidate_score > 0
    return candidate_score > current_score


def is_valid_tax_id(value: str) -> bool:
    if not value:
        return False
    cleaned = re.sub(r"\s+", "", value.upper())
    if re.fullmatch(r"[A-HJ-NP-SUVW]\d{7}[0-9A-J]", cleaned):
        return True
    if re.fullmatch(r"\d{8}[A-Z]", cleaned):
        return True
    if re.fullmatch(r"[XYZ]\d{7}[A-Z]", cleaned):
        return True
    return False


def clean_tax_id(value: str) -> str:
    if not value:
        return ""
    cleaned = re.sub(r"[\s\-]", "", value.upper())
    replacements = {"€": "E", "£": "E", "|": "I"}
    for source, target in replacements.items():
        cleaned = cleaned.replace(source, target)
    return cleaned


def repair_tax_id_candidate(value: str) -> tuple[str, bool]:
    cleaned = clean_tax_id(value)
    if not cleaned or is_valid_tax_id(cleaned):
        return cleaned, False

    if len(cleaned) != 9:
        return cleaned, False

    digit_map = {"O": "0", "Q": "0", "D": "0", "I": "1", "L": "1", "Z": "2", "S": "5", "G": "6", "B": "8"}
    alpha_map = {"0": "O", "1": "I", "2": "Z", "5": "S", "6": "G", "8": "B"}

    has_ocr_noise_in_numeric_positions = any(char in digit_map for char in cleaned[1:8])
    if has_ocr_noise_in_numeric_positions or cleaned[0] in {"£", "€"}:
        cif_candidate = "".join(
            alpha_map.get(char, char) if index == 0 else digit_map.get(char, char) if 0 < index < 8 else char
            for index, char in enumerate(cleaned)
        )
        if is_valid_tax_id(cif_candidate):
            return cif_candidate, True

    if cleaned[-1].isalpha():
        nif_candidate = "".join(digit_map.get(char, char) if index < 8 else char for index, char in enumerate(cleaned))
        if is_valid_tax_id(nif_candidate):
            return nif_candidate, True

        nie_candidate = "".join(
            (
                "X"
                if index == 0 and char in {"1", "I"}
                else alpha_map.get(char, char)
                if index == 0
                else digit_map.get(char, char)
                if index < 8
                else char
            )
            for index, char in enumerate(cleaned)
        )
        if is_valid_tax_id(nie_candidate):
            return nie_candidate, True

    return cleaned, False


def normalize_tax_id_value(primary: str, fallback: str, *, role: str) -> tuple[str, list[str]]:
    warnings: list[str] = []
    current = clean_tax_id(primary)
    fallback_clean = clean_tax_id(fallback)

    repaired_current, current_was_repaired = repair_tax_id_candidate(current)
    repaired_fallback, _ = repair_tax_id_candidate(fallback_clean)
    fallback_candidate = repaired_fallback if is_valid_tax_id(repaired_fallback) else fallback_clean

    if is_valid_tax_id(current) and not current_was_repaired:
        return current, warnings

    if is_valid_tax_id(fallback_candidate):
        warnings.append(f"cif_{role}_corregido_con_fallback")
        return fallback_candidate, warnings

    if is_valid_tax_id(repaired_current):
        if current_was_repaired:
            warnings.append(f"cif_{role}_reparado_ocr")
        return repaired_current, warnings

    if current:
        warnings.append(f"cif_{role}_no_valido")
    return current, warnings


def values_match(left: object, right: object) -> bool:
    if is_empty_value(left) and is_empty_value(right):
        return True
    if isinstance(left, (int, float)) or isinstance(right, (int, float)):
        try:
            return abs(float(left) - float(right)) <= max(0.02, abs(float(left)) * 0.02, abs(float(right)) * 0.02)
        except (TypeError, ValueError):
            return False

    left_text = re.sub(r"[^A-Z0-9]", "", str(left).upper())
    right_text = re.sub(r"[^A-Z0-9]", "", str(right).upper())
    return left_text == right_text or left_text in right_text or right_text in left_text


def is_empty_value(value: object) -> bool:
    if value is None:
        return True
    if isinstance(value, str):
        return value.strip() == ""
    if isinstance(value, (int, float)):
        return abs(float(value)) < 1e-9
    return False
