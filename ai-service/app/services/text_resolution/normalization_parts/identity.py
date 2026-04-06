from __future__ import annotations

import re

from app.models.invoice_model import InvoiceData
from app.services.text_resolution.party_resolution import party_resolution_service


def maybe_correct_invoice_number(normalized: InvoiceData, fallback: InvoiceData, raw_text: str) -> list[str]:
    warnings: list[str] = []
    if is_suspicious_invoice_number(normalized.numero_factura) and looks_like_invoice_code(fallback.numero_factura):
        normalized.numero_factura = fallback.numero_factura
        warnings.append("numero_factura_corregido_con_fallback")

    raw_invoice_number = extract_invoice_number_from_raw_text(raw_text)
    if raw_invoice_number and (
        not looks_like_invoice_code(normalized.numero_factura)
        or party_resolution_service.is_valid_tax_id(normalized.numero_factura)
        or normalized.numero_factura in {normalized.cif_proveedor, normalized.cif_cliente}
    ):
        normalized.numero_factura = raw_invoice_number
        warnings.append("numero_factura_corregido_desde_texto")
    return warnings


def apply_tax_label_correction(normalized: InvoiceData, fallback: InvoiceData, raw_text: str) -> list[str]:
    warnings: list[str] = []
    upper_text = raw_text.upper()
    if "IGIC" in upper_text and is_igic_rate(fallback.iva_porcentaje) and not is_igic_rate(normalized.iva_porcentaje):
        normalized.iva_porcentaje = fallback.iva_porcentaje
        warnings.append("iva_porcentaje_corregido_por_texto_igic")
    elif "IVA" in upper_text and is_iva_rate(fallback.iva_porcentaje) and not is_iva_rate(normalized.iva_porcentaje):
        normalized.iva_porcentaje = fallback.iva_porcentaje
        warnings.append("iva_porcentaje_corregido_por_texto_iva")
    return warnings


def extract_invoice_number_from_raw_text(raw_text: str) -> str:
    if not raw_text:
        return ""

    lines = [line.strip() for line in raw_text.splitlines() if line.strip()]
    label_pattern = re.compile(r"^(?:n(?:u|ú)mero|n[°ºo])\s*:?\s*$", re.IGNORECASE)
    inline_label_pattern = re.compile(
        r"^(?:n(?:u|ú)mero(?:\s+de\s+factura)?|n[°ºo]\s*(?:de\s*)?factura?)\s*[:#.]?\s*([A-Z0-9][A-Z0-9 /.-]{2,30})$",
        re.IGNORECASE,
    )
    candidate_pattern = re.compile(r"^[A-Z0-9/-]{4,30}$", re.IGNORECASE)

    for index, line in enumerate(lines):
        inline_match = inline_label_pattern.match(line)
        if inline_match:
            cleaned_inline = re.sub(r"\s+", "", inline_match.group(1)).strip(" .,:;")
            if candidate_pattern.match(cleaned_inline) and looks_like_invoice_code(cleaned_inline):
                return cleaned_inline
        if not label_pattern.match(line):
            continue
        for candidate in lines[index + 1:index + 4]:
            cleaned = re.sub(r"\s+", "", candidate).strip(" .,:;")
            if candidate_pattern.match(cleaned) and looks_like_invoice_code(cleaned):
                return cleaned
    return ""


def looks_like_invoice_code(value: str) -> bool:
    if not value:
        return False
    cleaned = value.strip().upper()
    compact = re.sub(r"\s+", "", cleaned)
    if looks_like_calendar_date(compact):
        return False
    if re.fullmatch(r"[A-Z]{1,6}\d[\w/-]{4,}", compact):
        return True
    return bool(re.fullmatch(r"\d{1,6}[/-]\d{2,4}(?:[A-Z0-9/-]{0,12})", compact))


def looks_like_calendar_date(value: str) -> bool:
    compact = re.sub(r"\s+", "", str(value or "").strip())
    return bool(re.fullmatch(r"\d{1,2}[/-]\d{1,2}[/-]\d{2,4}", compact))


def is_suspicious_invoice_number(value: str) -> bool:
    if not value:
        return True
    cleaned = value.strip().upper()
    if re.fullmatch(r"\d{1,3}", cleaned):
        return True
    if len(cleaned) < 5:
        return True
    return not looks_like_invoice_code(cleaned)


def is_igic_rate(value: float) -> bool:
    return any(abs(float(value or 0) - rate) <= 0.05 for rate in (0, 1, 3, 5, 7, 9.5, 15, 20))


def is_iva_rate(value: float) -> bool:
    return any(abs(float(value or 0) - rate) <= 0.05 for rate in (4, 10, 21))
