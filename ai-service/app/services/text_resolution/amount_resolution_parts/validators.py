from __future__ import annotations

from app.models.invoice_model import InvoiceData


def has_structured_tax_summary(raw_text: str) -> bool:
    upper_text = raw_text.upper()
    has_total = "TOTAL" in upper_text
    has_tax = "IMPUESTOS" in upper_text or "CUOTA" in upper_text
    has_base = "SUBTOTAL" in upper_text or "BASE IMPONIBLE" in upper_text or "\nBASE\n" in upper_text
    return has_total and has_tax and has_base


def amounts_are_coherent(invoice: InvoiceData) -> bool:
    if abs(invoice.base_imponible) <= 0 or abs(invoice.total) <= 0:
        return False

    sign = -1 if invoice.base_imponible < 0 or invoice.total < 0 or invoice.iva < 0 else 1
    withholding = round(max(0, abs(invoice.retencion or 0)), 2)

    if abs(invoice.iva) > 0:
        expected_total = round(invoice.base_imponible + invoice.iva - (withholding * sign), 2)
        return abs(expected_total - invoice.total) <= 0.05

    if invoice.iva_porcentaje > 0:
        expected_tax = round(abs(invoice.base_imponible) * invoice.iva_porcentaje / 100, 2) * sign
        expected_total = round(invoice.base_imponible + expected_tax - (withholding * sign), 2)
        return abs(expected_total - invoice.total) <= 0.05

    return False
