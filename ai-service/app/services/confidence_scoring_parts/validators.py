from __future__ import annotations

import re

from app.models.invoice_model import InvoiceData


def validate_math(data: InvoiceData) -> float:
    if abs(data.total) <= 0 or abs(data.base_imponible) <= 0:
        return 0.0

    expected_total = data.base_imponible + data.iva
    tolerance = max(0.02, abs(data.total) * 0.01)
    if abs(expected_total - data.total) <= tolerance:
        return 1.0

    diff_pct = abs(expected_total - data.total) / max(abs(data.total), 0.01)
    if diff_pct < 0.05:
        return 0.5
    return 0.0


def validate_tax_consistency(data: InvoiceData) -> float:
    if abs(data.base_imponible) <= 0 or data.iva_porcentaje <= 0 or abs(data.iva) <= 0:
        return 0.0

    sign = -1 if data.base_imponible < 0 or data.iva < 0 or data.total < 0 else 1
    expected_tax = round(abs(data.base_imponible) * data.iva_porcentaje / 100, 2) * sign
    diff = abs(expected_tax - data.iva)
    tolerance = max(0.02, abs(expected_tax) * 0.02)

    if abs(data.total) > 0:
        expected_total = round(data.base_imponible + expected_tax, 2)
        total_tolerance = max(0.02, abs(data.total) * 0.01)
        if abs(expected_total - data.total) > total_tolerance:
            return 0.0

    if diff <= tolerance:
        return 1.0
    if diff <= max(0.1, abs(expected_tax) * 0.05):
        return 0.5
    return 0.0


def validate_line_items(data: InvoiceData) -> float:
    if not data.lineas:
        return 0.0

    populated_lines = [
        line for line in data.lineas if line.descripcion and (abs(line.importe) > 0 or abs(line.precio_unitario) > 0)
    ]
    if not populated_lines:
        return 0.0

    line_sum = round(sum(line.importe for line in populated_lines if abs(line.importe) > 0), 2)
    base_amount = abs(data.base_imponible or 0)
    total_amount = abs(data.total or 0)
    tax_amount = abs(data.iva or 0)

    if base_amount > 0 and abs(line_sum - data.base_imponible) <= max(0.02, base_amount * 0.02):
        return 1.0
    if base_amount > 0 and abs(line_sum - data.base_imponible) <= max(0.1, base_amount * 0.05):
        return 0.45
    if total_amount > 0 and tax_amount >= 0 and abs((line_sum + data.iva) - data.total) <= max(0.02, total_amount * 0.02):
        return 0.8
    if abs(line_sum) > 0:
        return 0.1
    return 0.3


def is_valid_tax_id(value: str) -> bool:
    if not value:
        return False
    cleaned = re.sub(r"\s+", "", value.upper())
    return bool(
        re.fullmatch(r"[A-HJ-NP-SUVW]\d{7}[0-9A-J]", cleaned)
        or re.fullmatch(r"\d{8}[A-Z]", cleaned)
        or re.fullmatch(r"[XYZ]\d{7}[A-Z]", cleaned)
    )


def is_valid_iso_date(value: str) -> bool:
    return bool(re.fullmatch(r"\d{4}-\d{2}-\d{2}", value or ""))


def is_generic_party_name(value: str) -> bool:
    normalized = re.sub(r"[^A-Z0-9]", "", (value or "").upper())
    return normalized in {"CLIENTE", "EMISOR", "PROVEEDOR", "FACTURA"}
