from __future__ import annotations

import re
from typing import Any

from app.models.extraction_result import DecisionFlag
from app.models.invoice_model import InvoiceData

from .shared import is_empty_value


def build_decision_flags(
    *,
    invoice: InvoiceData,
    field_confidence: dict[str, float],
    warnings: list[str],
    company_match: dict[str, Any] | None = None,
) -> list[DecisionFlag]:
    flags: list[DecisionFlag] = []
    company_match = company_match or {}

    critical_fields = {
        "numero_factura": "Numero de factura",
        "fecha": "Fecha",
        "proveedor": "Emisor/contraparte",
        "cif_proveedor": "NIF/CIF emisor",
        "total": "Total",
    }
    for field_name, label in critical_fields.items():
        value = getattr(invoice, field_name, "")
        confidence = field_confidence.get(field_name, 0.0)
        if is_empty_value(value):
            flags.append(
                DecisionFlag(
                    code=f"missing_{field_name}",
                    severity="warning",
                    message=f"Falta {label.lower()} en la extraccion.",
                    field=field_name,
                    requires_review=True,
                )
            )
        elif confidence < 0.65:
            flags.append(
                DecisionFlag(
                    code=f"low_confidence_{field_name}",
                    severity="warning",
                    message=f"{label} tiene una confianza tecnica baja.",
                    field=field_name,
                    requires_review=True,
                )
            )

    if invoice.base_imponible and invoice.total:
        expected_total = round(invoice.base_imponible + invoice.iva - max(0, invoice.retencion or 0), 2)
        if abs(expected_total - invoice.total) > 0.05:
            flags.append(
                DecisionFlag(
                    code="amounts_not_coherent",
                    severity="error",
                    message="Los importes finales no cuadran entre base, impuestos, retencion y total.",
                    field="total",
                    requires_review=True,
                )
            )

    if company_match.get("issuer_matches_company") and company_match.get("recipient_matches_company"):
        flags.append(
            DecisionFlag(
                code="company_match_ambiguous",
                severity="warning",
                message="La empresa asociada encaja tanto con emisor como con receptor. Conviene revisar las partes.",
                field="proveedor",
                requires_review=True,
            )
        )

    normalized_provider = _normalize_party_value(invoice.proveedor)
    normalized_client = _normalize_party_value(invoice.cliente)
    if normalized_provider and normalized_client and normalized_provider == normalized_client:
        flags.append(
            DecisionFlag(
                code="same_party_both_roles",
                severity="error",
                message="Emisor y receptor parecen ser la misma entidad. Conviene revisar las partes detectadas.",
                field="proveedor",
                requires_review=True,
            )
        )

    normalized_provider_tax_id = _normalize_tax_id(invoice.cif_proveedor)
    normalized_client_tax_id = _normalize_tax_id(invoice.cif_cliente)
    if (
        normalized_provider_tax_id
        and normalized_client_tax_id
        and normalized_provider_tax_id == normalized_client_tax_id
    ):
        flags.append(
            DecisionFlag(
                code="same_tax_id_both_roles",
                severity="error",
                message="Emisor y receptor comparten el mismo NIF/CIF. Conviene revisar la asignacion de roles.",
                field="cif_proveedor",
                requires_review=True,
            )
        )

    for warning in warnings:
        if warning.startswith("discrepancia_"):
            flags.append(
                DecisionFlag(
                    code=warning,
                    severity="info",
                    message="Hubo conflicto entre distintas vias de extraccion y se resolvio por coherencia global.",
                    field=warning.replace("discrepancia_", ""),
                    requires_review=False,
                )
            )

    deduped: list[DecisionFlag] = []
    seen: set[str] = set()
    for flag in flags:
        if flag.code in seen:
            continue
        seen.add(flag.code)
        deduped.append(flag)
    return deduped


def _normalize_party_value(value: str) -> str:
    return re.sub(r"[^A-Z0-9]", "", str(value or "").upper())


def _normalize_tax_id(value: str) -> str:
    return re.sub(r"\s+", "", str(value or "").upper())
