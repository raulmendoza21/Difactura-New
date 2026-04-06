"""Party post-processing and header/ticket normalization."""

from __future__ import annotations

from app.models.invoice_model import InvoiceData

from .postprocessing_parts import (
    apply_company_line_fallback,
    assign_cifs,
    fill_missing_counterparty_from_header,
    normalize_ticket_parties,
    promote_registry_supplier,
    promote_registry_tax_id,
)


def apply_party_postprocessing(data: InvoiceData, text: str, lines: list[str], cifs: list[str]) -> None:
    apply_company_line_fallback(data, lines)
    promote_registry_supplier(data, text)
    assign_cifs(data, cifs, text)
    promote_registry_tax_id(data, text, cifs)
    fill_missing_counterparty_from_header(data, lines)
    normalize_ticket_parties(data, text, lines)
