from __future__ import annotations

import re

from ..shared import looks_like_tax_id_candidate

MONTH_MAP = {
    "enero": "01",
    "febrero": "02",
    "marzo": "03",
    "abril": "04",
    "mayo": "05",
    "junio": "06",
    "julio": "07",
    "agosto": "08",
    "septiembre": "09",
    "octubre": "10",
    "noviembre": "11",
    "diciembre": "12",
}


def normalize_invoice_number_candidate(value: str) -> str:
    cleaned = re.sub(r"\s+", " ", (value or "").strip())
    cleaned = re.sub(r"\s*([/-])\s*", r"\1", cleaned)
    cleaned = re.sub(r"\s+\d{1,2}[-/.]\d{1,2}[-/.]\d{2,4}$", "", cleaned)
    return cleaned.strip(" .,:;")


def looks_like_invoice_number_candidate(value: str) -> bool:
    cleaned = normalize_invoice_number_candidate(value).upper()
    if not cleaned or len(cleaned) < 4:
        return False
    if looks_like_tax_id_candidate(cleaned):
        return False
    if re.fullmatch(r"\d{1,3}", cleaned):
        return False
    if re.fullmatch(r"[A-Z0-9]{20,}", cleaned) and "-" not in cleaned and "/" not in cleaned and " " not in cleaned:
        return False
    if re.fullmatch(r"[A-Z0-9]{10,}", cleaned) and re.search(r"\d", cleaned) and not re.search(r"[/-]|\s", cleaned):
        letter_runs = re.findall(r"[A-Z]+", cleaned)
        digit_runs = re.findall(r"\d+", cleaned)
        if len(letter_runs) >= 2 and len(digit_runs) >= 2:
            return False
    return bool(
        re.fullmatch(r"[A-Z]{0,6}(?:[\s/-]?\d){2,}[A-Z0-9/-]*", cleaned)
        or re.fullmatch(r"[A-Z]{1,6}\d[\w/-]{3,18}", cleaned)
    )
