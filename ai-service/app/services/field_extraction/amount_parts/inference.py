from __future__ import annotations

from app.models.invoice_model import InvoiceData


def infer_amounts(data: InvoiceData) -> None:
    base = round(float(data.base_imponible or 0.0), 2)
    tax_percent = round(float(data.iva_porcentaje or 0.0), 2)
    tax_amount = round(float(data.iva or 0.0), 2)
    withholding_percent = round(float(data.retencion_porcentaje or 0.0), 2)
    withholding_amount = round(abs(float(data.retencion or 0.0)), 2)
    total = round(float(data.total or 0.0), 2)

    if not tax_amount and base and tax_percent:
        tax_amount = round(base * (tax_percent / 100.0), 2)
        data.iva = tax_amount

    if not withholding_amount and base and withholding_percent:
        withholding_amount = round(abs(base) * (withholding_percent / 100.0), 2)
        data.retencion = withholding_amount

    if not total and (base or tax_amount or withholding_amount):
        data.total = round(base + tax_amount - withholding_amount, 2)
    elif total and not tax_amount and base:
        inferred_tax = round(total - base + withholding_amount, 2)
        if inferred_tax:
            data.iva = inferred_tax
            tax_amount = inferred_tax

    if not data.base_imponible and total and tax_amount:
        data.base_imponible = round(total - tax_amount + withholding_amount, 2)

    if not data.iva_porcentaje and data.base_imponible and data.iva:
        base_value = float(data.base_imponible)
        if abs(base_value) > 1e-9:
            data.iva_porcentaje = round(abs(float(data.iva)) / abs(base_value) * 100.0, 2)

    if not data.retencion_porcentaje and data.base_imponible and data.retencion:
        base_value = float(data.base_imponible)
        if abs(base_value) > 1e-9:
            data.retencion_porcentaje = round(abs(float(data.retencion)) / abs(base_value) * 100.0, 2)

    data.retencion = abs(float(data.retencion or 0.0))
