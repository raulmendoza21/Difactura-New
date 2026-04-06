from __future__ import annotations

from app.models.invoice_model import InvoiceData

from ...shared import looks_like_company_name, looks_like_ticket_document


def normalize_ticket_parties(data: InvoiceData, text: str, lines: list[str]) -> None:
    if not looks_like_ticket_document(text):
        return
    legal_candidates = []
    for line in lines[:12]:
        if looks_like_company_name(line) and line not in legal_candidates:
            legal_candidates.append(line[:200])
    if legal_candidates:
        data.proveedor = legal_candidates[0]
        if data.cliente == data.proveedor:
            data.cliente = ""
    if not data.proveedor and data.cliente:
        data.proveedor = data.cliente
        data.cliente = ""
    if not data.cif_proveedor and data.cif_cliente:
        data.cif_proveedor = data.cif_cliente
        data.cif_cliente = ""
    data.cliente = ""
    data.cif_cliente = ""
