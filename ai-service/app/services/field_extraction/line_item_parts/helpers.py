from __future__ import annotations

import re

from app.utils.text_processing import normalize_text, parse_amount

from ..shared import DOCUMENT_HEADER_LINE, GENERIC_HEADER_NOISE, normalize_label_line


def is_standalone_amount_line(line: str) -> bool:
    cleaned = sanitize_standalone_amount_line(line)
    if not cleaned:
        return False
    if not re.search(r"\d", cleaned):
        return False
    if any(char.isalpha() for char in cleaned):
        return False
    return bool(re.fullmatch(r"-?[\d.,]+", cleaned))


def sanitize_standalone_amount_line(line: str) -> str:
    cleaned = normalize_text(line or "").strip()
    if not cleaned:
        return ""
    cleaned = cleaned.replace("Ã¢â€šÂ¬", " ")
    cleaned = cleaned.replace("$", " ")
    cleaned = cleaned.replace("Ã‚Â£", " ")
    cleaned = cleaned.replace("?", " ")
    cleaned = cleaned.replace("Ã¢Ë†â€™", "-")
    cleaned = re.sub(r"\b(?:eur|euro|euros)\b", " ", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"\s+", "", cleaned)
    return cleaned


def parse_standalone_amount_line(line: str) -> float:
    return parse_amount(sanitize_standalone_amount_line(line))


def looks_like_summary_block(lines: list[str], index: int, footer_pattern: re.Pattern) -> bool:
    current = lines[index]
    if not is_standalone_amount_line(current):
        return False
    next_line = lines[index + 1] if index + 1 < len(lines) else ""
    if next_line and looks_like_item_description(next_line):
        return False
    if abs(parse_amount(current)) <= 10:
        return False

    lookahead = lines[index + 1:index + 5]
    footer_hits = sum(1 for line in lookahead if footer_pattern.search(line))
    return footer_hits >= 2


def resolve_vertical_amount_triplet(first: float, second: float, third: float) -> tuple[float, float, float] | None:
    candidates = [
        (first, second, third),
        (second, third, first),
        (third, second, first),
    ]

    best_candidate: tuple[float, float, float] | None = None
    best_delta = float("inf")

    for quantity, unit_price, amount in candidates:
        if quantity <= 0 or unit_price <= 0 or amount <= 0:
            continue
        if quantity > 1000 or unit_price > amount * 10:
            continue

        delta = abs(round(quantity * unit_price, 2) - amount)
        if delta > max(0.05, amount * 0.03):
            continue
        if delta < best_delta:
            best_candidate = (quantity, unit_price, amount)
            best_delta = delta

    return best_candidate


def is_note_line(value: str) -> bool:
    normalized = normalize_label_line(value)
    return normalized.startswith("de albar") or normalized.startswith("observaciones")


def looks_like_license_key_line(value: str) -> bool:
    raw_value = (value or "").strip()
    cleaned = re.sub(r"\s+", "", raw_value.upper())
    if len(cleaned) < 18:
        if (
            " " not in raw_value
            and len(cleaned) >= 8
            and re.fullmatch(r"[A-Z0-9-]+", cleaned)
        ):
            digit_count = sum(char.isdigit() for char in cleaned)
            letter_count = sum(char.isalpha() for char in cleaned)
            if "-" in cleaned and digit_count >= 2 and letter_count >= 3:
                return True
        return False
    if not re.fullmatch(r"[A-Z0-9-]+", cleaned):
        return False
    digit_count = sum(char.isdigit() for char in cleaned)
    if " " not in raw_value and digit_count >= 2:
        return True
    if digit_count < 4:
        return False
    return "-" in cleaned or digit_count >= max(6, len(cleaned) // 4)


def build_line_description(description_parts: list[str]) -> str:
    filtered: list[str] = []
    for part in description_parts:
        cleaned = re.sub(r"\s+", " ", (part or "").strip()).strip(" .,:;-")
        if not cleaned:
            continue
        if looks_like_license_key_line(cleaned):
            continue
        if re.fullmatch(r"[A-Z0-9-]{5,20}", cleaned) and (re.search(r"\d", cleaned) or "-" in cleaned):
            continue
        filtered.append(cleaned)
    return " ".join(filtered).strip()


def looks_like_item_description(value: str) -> bool:
    cleaned = re.sub(r"\s+", " ", value or "").strip()
    if len(cleaned) < 2:
        return False
    if is_note_line(cleaned):
        return False
    normalized = normalize_label_line(cleaned)
    compact = re.sub(r"[^a-z0-9]", "", normalized)
    if compact in {"concepto", "detalle", "descripcion", "descripcin", "importe", "uds", "neto"}:
        return False
    if compact == "partna":
        return False
    if normalized in {"concepto", "detalle", "descripcion", "importe", "uds", "neto"}:
        return False
    if compact in {"partn", "partno", "partnum", "partnumero", "partnº"}:
        return False
    return True


def is_table_header_noise(value: str) -> bool:
    stripped = value.strip()
    upper_value = stripped.upper()
    header_tokens = ("DESCRIPCI", "CONCEPTO", "DETALLE", "ART", "IMPORTE", "UDS", "PRECIO", "NETO", "DTO", "PART")
    header_hits = sum(1 for token in header_tokens if token in upper_value)
    return (
        bool(DOCUMENT_HEADER_LINE.match(stripped))
        or upper_value in GENERIC_HEADER_NOISE
        or header_hits >= 2
        or bool(
            re.fullmatch(
                r"(?:DESCRIPCI\w+|CONCEPTO|DETALLE|ART\w+|IMPORTE|UDS\.?|PRECIO|NETO|PART\.?\s*N[\W_]*[º°O]?)",
                stripped,
                re.IGNORECASE,
            )
        )
    )
