"""CIF/NIF validation using stdnum."""

from __future__ import annotations

import re


def clean_tax_id(value: str) -> str:
    return re.sub(r"[\s\-.]", "", (value or "").strip()).upper()


def is_valid_tax_id(value: str) -> bool:
    cleaned = clean_tax_id(value)
    if not cleaned:
        return False
    try:
        from stdnum.es import cif, dni, nie
        return cif.is_valid(cleaned) or dni.is_valid(cleaned) or nie.is_valid(cleaned)
    except Exception:
        return bool(re.match(r"^[A-HJ-NP-SUVW]\d{7}[0-9A-J]$", cleaned) or
                     re.match(r"^\d{8}[A-Z]$", cleaned) or
                     re.match(r"^[XYZ]\d{7}[A-Z]$", cleaned))
