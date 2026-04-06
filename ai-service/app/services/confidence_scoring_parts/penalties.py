from __future__ import annotations

import re

from app.models.invoice_model import InvoiceData

from .validators import is_generic_party_name, is_valid_tax_id


def calculate_penalties(data: InvoiceData) -> float:
    penalty = 0.0
    total_amount = abs(data.total or 0)
    base_amount = abs(data.base_imponible or 0)
    tolerance = max(0.02, total_amount * 0.01) if total_amount > 0 else 0.02

    if data.proveedor and is_generic_party_name(data.proveedor):
        penalty += 0.08
    if data.cliente and is_generic_party_name(data.cliente):
        penalty += 0.06

    if total_amount > 0 and base_amount > 0 and total_amount + tolerance < base_amount:
        penalty += 0.18

    line_sum = round(sum(line.importe for line in data.lineas if abs(line.importe) > 0), 2)
    abs_line_sum = abs(line_sum)
    if abs_line_sum > 0 and total_amount > 0 and total_amount + tolerance < abs_line_sum:
        penalty += 0.18

    if abs_line_sum > 0 and base_amount > 0:
        delta = abs(line_sum - data.base_imponible)
        if delta > max(0.1, base_amount * 0.01):
            penalty += 0.18
        elif delta > 0.02:
            penalty += 0.12

    if data.cif_proveedor and not is_valid_tax_id(data.cif_proveedor):
        penalty += 0.08
    if data.cif_cliente and not is_valid_tax_id(data.cif_cliente):
        penalty += 0.06

    normalized_provider = _normalize_party_value(data.proveedor)
    normalized_client = _normalize_party_value(data.cliente)
    if normalized_provider and normalized_client and normalized_provider == normalized_client:
        penalty += 0.22

    normalized_provider_tax_id = _normalize_tax_id(data.cif_proveedor)
    normalized_client_tax_id = _normalize_tax_id(data.cif_cliente)
    if (
        normalized_provider_tax_id
        and normalized_client_tax_id
        and normalized_provider_tax_id == normalized_client_tax_id
    ):
        penalty += 0.24

    return penalty


def _normalize_party_value(value: str) -> str:
    return re.sub(r"[^A-Z0-9]", "", (value or "").upper())


def _normalize_tax_id(value: str) -> str:
    return re.sub(r"\s+", "", (value or "").upper())
