"""Identity resolver — invoice number, date, rectified number."""

from __future__ import annotations

import re

from app.models.fields import ScanResult
from app.utils.regex_lib import (
    DATE_DMY,
    DATE_STANDALONE,
    DATE_TEXT_ES,
    INVOICE_CODE,
    INVOICE_NUMBER,
    LABEL_RECTIFIED,
    MONTHS_ES,
)
from app.utils.text import normalize_keyword


def resolve(scan: ScanResult) -> dict:
    """Return {numero_factura, fecha, rectified_invoice_number} + confidence per field."""
    numero = _resolve_invoice_number(scan)
    fecha = _resolve_date(scan)
    rectified = _resolve_rectified(scan)

    return {
        "numero_factura": numero,
        "fecha": fecha,
        "rectified_invoice_number": rectified,
        "confidence": {
            "numero_factura": 0.95 if numero else 0.0,
            "fecha": 0.95 if fecha else 0.0,
            "rectified_invoice_number": 0.9 if rectified else 0.0,
        },
    }


def _resolve_invoice_number(scan: ScanResult) -> str:
    # 1. Look in discovered fields for labeled invoice number
    invoice_labels = {"n factura", "numero factura", "numero de factura",
                      "n de factura", "fra", "invoice", "num factura",
                      "no factura", "factura n", "factura num", "factura no",
                      "factura numero", "numero"}
    for f in scan.fields:
        kw = normalize_keyword(f.label).lower()
        kw_clean = re.sub(r"[^a-z0-9 ]", "", kw).strip()
        if any(il in kw_clean for il in invoice_labels):
            value = f.value.strip()
            if _is_valid_invoice_number(value):
                return _clean_invoice_number(value)

    # 2. Regex on raw text
    m = INVOICE_NUMBER.search(scan.raw_text)
    if m:
        value = m.group(1).strip()
        if _is_valid_invoice_number(value):
            return _clean_invoice_number(value)

    # 3. Look for invoice-like codes (e.g. FI202600043, GC 26001163)
    for f in scan.fields:
        m = INVOICE_CODE.match(f.value.strip())
        if m and _is_valid_invoice_number(m.group(1)):
            return m.group(1)

    return ""


_INVOICE_BLACKLIST = re.compile(
    r"^(?:DOCUMENTO|PAGINA|P[ÁA]GINA|TOTAL|FACTURA|FECHA|CLIENTE|PROVEEDOR|"
    r"EMISOR|RECEPTOR|DESTINATARIO|IMPORTE|SUBTOTAL|BASE|IVA|IGIC|IRPF|"
    r"CUOTA|RETENCI[ÓO]N|DATOS|VENTA|COMPRA|TIPO|CONCEPTO|DESCRIPCI[ÓO]N|"
    r"OBSERVACIONES|FORMA\s+DE\s+PAGO|CUENTA)\b",
    re.IGNORECASE,
)
_PAGE_PATTERN = re.compile(r"P[áa]gina\s+\d+\s+de\s+\d+", re.IGNORECASE)


def _is_valid_invoice_number(value: str) -> bool:
    """Reject garbage values that aren't real invoice numbers."""
    if not value or len(value) < 2:
        return False
    # Must contain at least one digit
    if not re.search(r"\d", value):
        return False
    # Reject CIF/NIF/NIE patterns — these are tax IDs, not invoice numbers
    # Clean dashes/dots first since CIFs can appear as B-35590736 or B.35.222.249
    cleaned_v = re.sub(r"[\s.\-]", "", value.strip())
    if re.fullmatch(r"[A-HJ-NP-SUVW]\d{7}[0-9A-J]", cleaned_v, re.IGNORECASE):
        return False
    if re.fullmatch(r"\d{8}[A-Z]", cleaned_v):
        return False
    if re.fullmatch(r"[XYZ]\d{7}[A-Z]", cleaned_v, re.IGNORECASE):
        return False
    # Reject blacklisted words
    if _INVOICE_BLACKLIST.match(value.strip()):
        return False
    # Reject page references
    if _PAGE_PATTERN.search(value):
        return False
    # Reject values that are too long (likely garbled text)
    if len(value) > 30:
        return False
    return True


def _resolve_date(scan: ScanResult) -> str:
    # 1. Labeled date field
    date_labels = {"fecha", "fecha factura", "fecha de factura", "fecha emision",
                   "fecha de emision", "fecha expedicion", "date", "fecha de expedicion"}
    for f in scan.fields:
        kw = normalize_keyword(f.label).lower()
        kw_clean = re.sub(r"[^a-z0-9 ]", "", kw).strip()
        if any(dl in kw_clean for dl in date_labels):
            parsed = _parse_any_date(f.value)
            if parsed:
                return parsed

    # 2. Regex with label context
    m = DATE_DMY.search(scan.raw_text)
    if m:
        return _format_date(m.group(1), m.group(2), m.group(3))

    # 3. Text date "15 de marzo de 2026"
    m = DATE_TEXT_ES.search(scan.raw_text)
    if m:
        day, month_name, year = m.group(1), m.group(2).lower(), m.group(3)
        month = MONTHS_ES.get(month_name, 0)
        if month:
            return f"{year}-{month:02d}-{int(day):02d}"

    # 4. Standalone date pattern (first occurrence after first few lines)
    for i, line in enumerate(scan.lines):
        if i < 1:
            continue
        m = DATE_STANDALONE.search(line)
        if m:
            parsed = _format_date(m.group(1), m.group(2), m.group(3))
            if parsed:
                return parsed

    return ""


def _resolve_rectified(scan: ScanResult) -> str:
    m = LABEL_RECTIFIED.search(scan.raw_text)
    if m:
        return _clean_invoice_number(m.group(1))

    rect_labels = {"factura rectificada", "factura original", "rectifica a",
                   "factura que se rectifica"}
    for f in scan.fields:
        kw = normalize_keyword(f.label).lower()
        if any(rl in kw for rl in rect_labels):
            return _clean_invoice_number(f.value)

    return ""


def _clean_invoice_number(value: str) -> str:
    cleaned = value.strip().rstrip(".")
    cleaned = re.sub(r"\s+", " ", cleaned)
    # Strip trailing noise words that get captured from adjacent text
    cleaned = re.sub(r"\s+(?:FECHA|HORA|IMPORTE|TOTAL|PAGINA|PAGE)\s*$", "", cleaned, flags=re.IGNORECASE)
    return cleaned.strip()


def _parse_any_date(value: str) -> str:
    value = value.strip()
    # Try DD/MM/YYYY
    m = re.match(r"(\d{1,2})[/\-.](\d{1,2})[/\-.](\d{2,4})", value)
    if m:
        return _format_date(m.group(1), m.group(2), m.group(3))
    # Try text date
    m = DATE_TEXT_ES.search(value)
    if m:
        day, month_name, year = m.group(1), m.group(2).lower(), m.group(3)
        month = MONTHS_ES.get(month_name, 0)
        if month:
            return f"{year}-{month:02d}-{int(day):02d}"
    return ""


def _format_date(day: str, month: str, year: str) -> str:
    d, m, y = int(day), int(month), int(year)
    if y < 100:
        y += 2000
    if not (1 <= d <= 31 and 1 <= m <= 12 and 1900 <= y <= 2100):
        return ""
    return f"{y}-{m:02d}-{d:02d}"
