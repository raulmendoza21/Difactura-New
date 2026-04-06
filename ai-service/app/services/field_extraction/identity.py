"""Identity extraction facade."""

from __future__ import annotations

from app.services.field_extraction.identity_parts.dates import extract_date
from app.services.field_extraction.identity_parts.invoice_number import (
    extract_invoice_number,
    extract_labeled_invoice_number,
    extract_ticket_invoice_number,
)
from app.services.field_extraction.identity_parts.rectified import extract_rectified_invoice_number
from app.services.field_extraction.shared import looks_like_ticket_document


def extract_identity(text: str, lines: list[str]) -> dict[str, str]:
    ticket_number = extract_ticket_invoice_number(lines)
    invoice_number = ticket_number
    if not invoice_number:
        invoice_number = (
            extract_labeled_invoice_number(text, lines)
            if looks_like_ticket_document(text)
            else extract_invoice_number(text, lines)
        )

    return {
        "numero_factura": invoice_number,
        "rectified_invoice_number": extract_rectified_invoice_number(text, lines),
        "fecha": extract_date(text, lines),
    }
