from __future__ import annotations

import re

from app.models.invoice_model import InvoiceData

from ...shared import extract_line_tax_ids, looks_like_company_name, normalize_party_value


def promote_registry_supplier(data: InvoiceData, text: str) -> None:
    match = re.search(
        r"([A-ZÃƒÂÃƒâ€°ÃƒÂÃƒâ€œÃƒÅ¡ÃƒÅ“Ãƒâ€˜][^\n]{3,120}?)\s*-\s*REGISTRO\s+MERCANTIL[^\n]*?\bCIF\b\s*([A-Z0-9.\- ]{8,20})",
        text,
        re.IGNORECASE,
    )
    if not match:
        return

    supplier_name = re.sub(r"\s+", " ", match.group(1)).strip(" .,:;-")
    tax_ids = extract_line_tax_ids(match.group(0))
    supplier_tax_id = tax_ids[0] if tax_ids else re.sub(r"[\s.\-]", "", match.group(2).upper())

    if not supplier_name and not supplier_tax_id:
        return

    if not data.proveedor or normalize_party_value(data.proveedor) == normalize_party_value(data.cliente):
        data.proveedor = supplier_name or data.proveedor
        if supplier_tax_id:
            data.cif_proveedor = supplier_tax_id
        return

    if data.cif_cliente and supplier_tax_id and data.cif_cliente == supplier_tax_id:
        data.cif_cliente = ""

    if supplier_tax_id and data.cif_proveedor and data.cif_proveedor != supplier_tax_id and data.cif_cliente == data.cif_proveedor:
        data.cif_cliente = data.cif_proveedor
        data.proveedor = supplier_name or data.proveedor
        data.cif_proveedor = supplier_tax_id


def apply_company_line_fallback(data: InvoiceData, lines: list[str]) -> None:
    if data.proveedor and data.cliente:
        return

    company_candidates: list[str] = []
    for line in lines[:20]:
        if looks_like_company_name(line) and line not in company_candidates:
            company_candidates.append(line[:200])

    if not data.proveedor and company_candidates:
        data.proveedor = company_candidates[0]
    if not data.cliente and len(company_candidates) > 1:
        data.cliente = company_candidates[1]
