from __future__ import annotations

import re

from app.utils.text_processing import parse_amount

AMOUNT_PATTERN = re.compile(r"-?\d{1,3}(?:[.,]\d{3})*(?:[.,]\d{2})|-?\d+(?:[.,]\d{2})")
PERCENT_PATTERN = re.compile(r"(-?\d+(?:[.,]\d{1,2})?)\s*%")
AMOUNT_CONTEXT_HINT = re.compile(
    r"\b(?:BASE|TOTAL|IVA|IGIC|IMPUEST|CUOTA|NETO|PRECIO|PVP|IMPORTE|DTO|DESCUENTO|RETEN|IRPF|PORTES|AJUSTE)\b",
    re.IGNORECASE,
)
METADATA_NUMERIC_HINT = re.compile(
    r"\b(?:CIF|NIF|DNI|VAT|FACTURA(?:\s+NUM|\s+N[OUº°])?|DOCUMENTO|REFERENCIA|REF\.?|PEDIDO|ALBARAN|COD(?:IGO)?\.?\s+DE\s+CLIENTE|CONTACTO|REPRESENTANTE|ADMINISTRADOR|RESPONSABLE)\b",
    re.IGNORECASE,
)


def _normalize_amount_text(value: str) -> str:
    cleaned = (value or "").strip()
    cleaned = cleaned.replace("Ã¢â€šÂ¬", " ").replace("$", " ").replace("Ã‚Â£", " ")
    cleaned = cleaned.replace("Ã¢Ë†â€™", "-").replace("âˆ’", "-")
    cleaned = re.sub(r"\b(?:eur|euro|euros)\b", " ", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"\s+", " ", cleaned)
    return cleaned.strip()


def extract_numeric_candidates(text: str) -> list[float]:
    values: list[float] = []
    seen: set[float] = set()
    lines = (text or "").splitlines() or [text or ""]
    for raw_line in lines:
        line = _normalize_amount_text(raw_line)
        if not line or _should_skip_numeric_line(line):
            continue
        for match in AMOUNT_PATTERN.finditer(line):
            amount = round(parse_amount(match.group(0)), 2)
            if amount in seen:
                continue
            seen.add(amount)
            values.append(amount)
    return values


def extract_amount_candidates(text: str) -> list[float]:
    return extract_numeric_candidates(text)


def extract_amount(text: str) -> float:
    candidates = extract_amount_candidates(text)
    if not candidates:
        return 0.0
    return candidates[0]


def extract_amount_from_label_lines(lines: list[str], label_pattern: re.Pattern[str]) -> float:
    for index, line in enumerate(lines):
        if not label_pattern.search(line):
            continue
        current_value = extract_amount(line)
        if current_value:
            return current_value
        for lookahead in lines[index + 1:index + 4]:
            candidate = extract_amount(lookahead)
            if candidate:
                return candidate
    return 0.0


def extract_amount_around_exact_label(lines: list[str], label: str) -> float:
    pattern = re.compile(rf"^\s*{re.escape(label)}\s*:?\s*$", re.IGNORECASE)
    return extract_amount_from_label_lines(lines, pattern)


def extract_percentage_candidates(text: str) -> list[float]:
    values: list[float] = []
    seen: set[float] = set()
    for match in PERCENT_PATTERN.finditer(text or ""):
        raw = match.group(1).replace(",", ".")
        try:
            value = round(float(raw), 2)
        except ValueError:
            continue
        if value in seen:
            continue
        seen.add(value)
        values.append(value)
    return values


def _should_skip_numeric_line(line: str) -> bool:
    upper_line = (line or "").upper()
    if not upper_line:
        return True
    if AMOUNT_CONTEXT_HINT.search(upper_line):
        return False
    if METADATA_NUMERIC_HINT.search(upper_line):
        return True
    if re.search(r"\b(?:PROVEEDOR|CLIENTE|EMISOR|DESTINATARIO)\b", upper_line) and re.search(r"\d{7,}", upper_line):
        return True
    return False
