"""Shared helpers and constants for field extraction."""

from __future__ import annotations

import re

from app.utils.regex_patterns import CIF_NIF

PROVEEDOR_HEADER = re.compile(
    r"^(?:proveedor|emisor|raz[oó]n\s+social|datos\s+del\s+emisor)\s*:?\s*$",
    re.IGNORECASE,
)
CLIENTE_HEADER = re.compile(
    r"^(?:cliente|destinatario|comprador|facturar\s+a|datos\s+del\s+cliente)\s*:?\s*$",
    re.IGNORECASE,
)
STOP_PARTY_LINE = re.compile(
    r"^(?:c/?|calle|avda\.?|avenida|cp\b|c[oó]digo\s+postal|fecha|factura|forma\s+de\s+pago|email|tel[ée]fono|observaciones)\b",
    re.IGNORECASE,
)

DOCUMENT_HEADER_LINE = re.compile(
    r"^(?:factura|invoice|documento|fecha|importe|concepto|base|%igic|%iva|cuota|subtotal|total)$",
    re.IGNORECASE,
)
GENERIC_HEADER_NOISE = {
    "VENCIMIENTOS",
    "ENTIDADES",
    "TRANSPORTE",
    "TRACKING",
    "FACTURA NUM",
    "FACTURA NUM.",
}
TAX_ID_METADATA_HINT = re.compile(
    r"\b(?:factura(?:\s+num|\s+n[ouº°])?|documento|ref(?:erencia)?|c[oó]d\.?\s+de\s+cliente|entrada\s+factura|pedido|albar[aá]n)\b",
    re.IGNORECASE,
)

NON_PARTY_TAX_ID_HINT = re.compile(
    r"\b(?:contacto|representante|administrador|responsable|tracking)\b",
    re.IGNORECASE,
)


def normalize_label_line(line: str) -> str:
    normalized = re.sub(r"\s+", " ", line or "").strip().lower()
    return normalized.strip(" .:;,-")


def normalize_party_value(value: str) -> str:
    return re.sub(r"[^A-Z0-9]", "", (value or "").upper())


def extract_line_tax_ids(line: str) -> list[str]:
    values = []
    if not line:
        return values

    upper_line = line.upper()
    has_explicit_tax_label = bool(re.search(r"\b(?:CIF|NIF|VAT)\b", upper_line))
    if not has_explicit_tax_label and (TAX_ID_METADATA_HINT.search(line) or NON_PARTY_TAX_ID_HINT.search(line) or re.search(r"\bDNI\b", upper_line)):
        return values

    candidates = [line, re.sub(r"\.", "", line or "")]
    for candidate in candidates:
        for match in CIF_NIF.finditer(candidate):
            cif = next(group for group in match.groups() if group is not None)
            cleaned = re.sub(r"[\s\-.]", "", cif).upper()
            if cleaned not in values:
                values.append(cleaned)
    return values


def looks_like_tax_id_candidate(value: str) -> bool:
    cleaned = re.sub(r"[\s.\-]", "", (value or "").upper())
    return bool(
        re.fullmatch(r"[A-HJ-NP-SUVW]\d{7}[0-9A-J]", cleaned)
        or re.fullmatch(r"\d{8}[A-Z]", cleaned)
        or re.fullmatch(r"[XYZ]\d{7}[A-Z]", cleaned)
    )


def looks_like_address_or_contact_line(value: str) -> bool:
    upper_value = (value or "").upper()
    if not upper_value:
        return False
    if re.search(r"\b(?:MAIL|WEB|HTTP|TF|TEL|TLF|MOVIL|M[ÓO]VIL|EMAIL)\b", upper_value):
        return True
    if re.search(r"\b(?:C/|CALLE|AVDA\.?|AVENIDA|URB\.?|LOCAL|POL\.?|POLIGONO|POL[ÍI]GONO|CTRA\.?|PLAZA|PASEO)\b", upper_value):
        return True
    if re.search(r"\b\d{5}\b", upper_value):
        return True
    return False


def looks_like_party_name(value: str) -> bool:
    cleaned = value.strip()
    if not cleaned or len(cleaned) < 4:
        return False
    if PROVEEDOR_HEADER.match(cleaned) or CLIENTE_HEADER.match(cleaned):
        return False
    if STOP_PARTY_LINE.match(cleaned):
        return False
    if extract_line_tax_ids(cleaned):
        return False

    letters = sum(char.isalpha() for char in cleaned)
    digits = sum(char.isdigit() for char in cleaned)
    if letters < 3 or digits > max(2, letters // 2):
        return False

    upper_cleaned = cleaned.upper()
    blocked_tokens = {"FACTURA", "TOTAL", "BASE", "IVA", "IGIC", "TRANSFERENCIA"}
    if upper_cleaned in blocked_tokens:
        return False
    return True


def looks_like_company_name(value: str) -> bool:
    if not looks_like_party_name(value):
        return False

    upper_value = value.upper()
    if looks_like_address_or_contact_line(upper_value):
        return False

    return bool(
        re.search(
            r"(?:\bSL\b|S\.L\.|(?:\bSA\b)|S\.A\.|(?:\bSLU\b)|S\.L\.U\.|S\.C\.PROFESIONAL|S\.C\.|SCPROFESIONAL)",
            upper_value,
        )
    )


def looks_like_ticket_document(text: str) -> bool:
    upper_text = (text or "").upper()
    return any(
        token in upper_text
        for token in (
            "FACTURA SIMPLIFICADA",
            "FRA. SIMPLIFICADA",
            "FRA SIMPLIFICADA",
            "DOCUMENTO DE VENTA",
            "CONSULTA BORRADOR",
            "NO VALIDO COMO FACTURA",
        )
    )
