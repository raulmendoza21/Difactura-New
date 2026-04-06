from __future__ import annotations

from typing import Any

from app.models.invoice_model import InvoiceData
from app.services.text_resolution.party_resolution import party_resolution_service

from ..shared import is_empty_value, is_valid_iso_date, values_match


def build_field_confidence(
    *,
    final: InvoiceData,
    heuristic: InvoiceData,
    bundle_candidate: InvoiceData | None = None,
    ai_candidate: InvoiceData | None = None,
    evidence: dict[str, list[Any]] | None = None,
    score_line_field_confidence,
) -> dict[str, float]:
    evidence = evidence or {}
    return {
        "numero_factura": score_field_confidence(
            final.numero_factura,
            heuristic.numero_factura,
            getattr(bundle_candidate, "numero_factura", ""),
            getattr(ai_candidate, "numero_factura", ""),
            evidence_items=evidence.get("numero_factura", []),
        ),
        "fecha": score_field_confidence(
            final.fecha,
            heuristic.fecha,
            getattr(bundle_candidate, "fecha", ""),
            getattr(ai_candidate, "fecha", ""),
            validator=is_valid_iso_date,
            evidence_items=evidence.get("fecha", []),
        ),
        "proveedor": score_field_confidence(
            final.proveedor,
            heuristic.proveedor,
            getattr(bundle_candidate, "proveedor", ""),
            getattr(ai_candidate, "proveedor", ""),
            evidence_items=evidence.get("proveedor", []),
        ),
        "cif_proveedor": score_field_confidence(
            final.cif_proveedor,
            heuristic.cif_proveedor,
            getattr(bundle_candidate, "cif_proveedor", ""),
            getattr(ai_candidate, "cif_proveedor", ""),
            validator=party_resolution_service.is_valid_tax_id,
            evidence_items=evidence.get("cif_proveedor", []),
        ),
        "cliente": score_field_confidence(
            final.cliente,
            heuristic.cliente,
            getattr(bundle_candidate, "cliente", ""),
            getattr(ai_candidate, "cliente", ""),
            evidence_items=evidence.get("cliente", []),
        ),
        "cif_cliente": score_field_confidence(
            final.cif_cliente,
            heuristic.cif_cliente,
            getattr(bundle_candidate, "cif_cliente", ""),
            getattr(ai_candidate, "cif_cliente", ""),
            validator=party_resolution_service.is_valid_tax_id,
            evidence_items=evidence.get("cif_cliente", []),
        ),
        "base_imponible": score_field_confidence(
            final.base_imponible,
            heuristic.base_imponible,
            getattr(bundle_candidate, "base_imponible", 0.0),
            getattr(ai_candidate, "base_imponible", 0.0),
            evidence_items=evidence.get("base_imponible", []),
        ),
        "iva_porcentaje": score_field_confidence(
            final.iva_porcentaje,
            heuristic.iva_porcentaje,
            getattr(bundle_candidate, "iva_porcentaje", 0.0),
            getattr(ai_candidate, "iva_porcentaje", 0.0),
            evidence_items=evidence.get("iva_porcentaje", []),
        ),
        "iva": score_field_confidence(
            final.iva,
            heuristic.iva,
            getattr(bundle_candidate, "iva", 0.0),
            getattr(ai_candidate, "iva", 0.0),
            evidence_items=evidence.get("iva", []),
        ),
        "total": score_field_confidence(
            final.total,
            heuristic.total,
            getattr(bundle_candidate, "total", 0.0),
            getattr(ai_candidate, "total", 0.0),
            evidence_items=evidence.get("total", []),
        ),
        "lineas": score_line_field_confidence(
            final,
            heuristic,
            bundle_candidate,
            ai_candidate,
            evidence.get("lineas", []),
        ),
    }


def score_field_confidence(
    final_value: Any,
    heuristic_value: Any,
    bundle_value: Any,
    ai_value: Any,
    *,
    validator: Any | None = None,
    evidence_items: list[Any] | None = None,
) -> float:
    if is_empty_value(final_value):
        return 0.0

    evidence_items = evidence_items or []
    final_valid = bool(validator(final_value)) if validator else True
    score = 0.45 if final_valid else 0.25

    heuristic_present = not is_empty_value(heuristic_value)
    bundle_present = not is_empty_value(bundle_value)
    ai_present = not is_empty_value(ai_value)

    if heuristic_present and values_match(final_value, heuristic_value):
        score += 0.2
    elif heuristic_present:
        score -= 0.1

    if bundle_present and values_match(final_value, bundle_value):
        score += 0.18
    elif bundle_present:
        score -= 0.08

    if ai_present and values_match(final_value, ai_value):
        score += 0.25
    elif ai_present:
        score -= 0.1

    supporting_evidence = sum(
        1
        for item in evidence_items
        if getattr(item, "value", "") and getattr(item, "source", "") != "resolved"
    )
    if supporting_evidence >= 2:
        score += 0.07
    elif supporting_evidence == 1:
        score += 0.03

    if heuristic_present and ai_present and values_match(heuristic_value, ai_value):
        score += 0.1
    if bundle_present and heuristic_present and values_match(bundle_value, heuristic_value):
        score += 0.05

    return round(max(0.0, min(1.0, score)), 2)
