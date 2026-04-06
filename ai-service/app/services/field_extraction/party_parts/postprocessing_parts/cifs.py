from __future__ import annotations

import re

from app.models.invoice_model import InvoiceData

from ...shared import extract_line_tax_ids


def assign_cifs(data: InvoiceData, cifs: list[str], text: str) -> None:
    if not cifs:
        return
    lines = (text or "").splitlines()

    proveedor_labels = [
        re.compile(r"proveedor\s*:", re.IGNORECASE),
        re.compile(r"emisor\s*:", re.IGNORECASE),
        re.compile(r"cif\s+proveedor\s*:", re.IGNORECASE),
        re.compile(r"nif\s+proveedor\s*:", re.IGNORECASE),
        re.compile(r"raz[oó]n social\s*:", re.IGNORECASE),
    ]
    cliente_labels = [
        re.compile(r"cliente\s*:", re.IGNORECASE),
        re.compile(r"cif\s+cliente\s*:", re.IGNORECASE),
        re.compile(r"nif\s+cliente\s*:", re.IGNORECASE),
        re.compile(r"destinatario\s*:", re.IGNORECASE),
        re.compile(r"comprador\s*:", re.IGNORECASE),
    ]

    def last_match_pos(patterns: list[re.Pattern[str]], value: str) -> int:
        pos = -1
        for pattern in patterns:
            for match in pattern.finditer(value):
                if match.start() > pos:
                    pos = match.start()
        return pos

    for cif in cifs:
        source_line = next((line for line in lines if cif in line.upper()), "")
        upper_source_line = source_line.upper()
        if re.search(r"\b(?:CONTACTO|REPRESENTANTE|ADMINISTRADOR|RESPONSABLE)\b", upper_source_line):
            continue
        if "DNI" in upper_source_line and not re.search(r"\b(?:PROVEEDOR|CLIENTE|EMISOR|DESTINATARIO)\b", upper_source_line):
            continue
        cif_pos = text.upper().find(cif)
        if cif_pos < 0:
            continue
        context_before = text[max(0, cif_pos - 300):cif_pos]
        last_proveedor = last_match_pos(proveedor_labels, context_before)
        last_cliente = last_match_pos(cliente_labels, context_before)

        if last_proveedor >= 0 and last_proveedor >= last_cliente:
            data.cif_proveedor = cif
        elif last_cliente >= 0 and last_cliente > last_proveedor:
            data.cif_cliente = cif

    if len(cifs) == 1:
        only_cif = cifs[0]
        if not data.cif_proveedor and not data.cif_cliente:
            data.cif_proveedor = only_cif
        return

    if not data.cif_proveedor and len(cifs) >= 1:
        data.cif_proveedor = cifs[0]
    if not data.cif_cliente and len(cifs) >= 2:
        data.cif_cliente = cifs[1]


def promote_registry_tax_id(data: InvoiceData, text: str, cifs: list[str]) -> None:
    match = re.search(
        r"registrad[oa][^\n]{0,160}?\bcif\b[^\n]{0,20}",
        text,
        re.IGNORECASE,
    )
    if not match:
        return

    match_tax_ids = extract_line_tax_ids(match.group(0))
    registry_cif = match_tax_ids[0] if match_tax_ids else ""
    if registry_cif:
        data.cif_proveedor = registry_cif
        if not data.cif_cliente or data.cif_cliente == registry_cif:
            for cif in cifs:
                if cif != registry_cif:
                    data.cif_cliente = cif
                    break
