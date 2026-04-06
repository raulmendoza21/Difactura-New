from __future__ import annotations

import re

from app.models.invoice_model import InvoiceData


def has_withholding_hint(raw_text: str) -> bool:
    upper_text = raw_text.upper()
    compact_text = re.sub(r"[^A-Z0-9]", "", upper_text)
    return any(
        token in upper_text or token in compact_text
        for token in ("IRPF", "RETEN", "RENTEN", "RETENCION", "RENTENCION", "%RET")
    )


def should_clear_withholding(invoice: InvoiceData, raw_text: str) -> bool:
    withholding = round(max(0, invoice.retencion or 0), 2)
    if withholding <= 0 and (invoice.retencion_porcentaje or 0) <= 0:
        return False

    total_with_withholding = round(invoice.base_imponible + invoice.iva - withholding, 2)
    total_without_withholding = round(invoice.base_imponible + invoice.iva, 2)
    delta_with = abs(total_with_withholding - invoice.total)
    delta_without = abs(total_without_withholding - invoice.total)

    if delta_without + 0.05 < delta_with:
        return True

    return not has_withholding_hint(raw_text) and delta_without <= 0.05
