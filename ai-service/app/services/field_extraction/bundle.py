"""Bundle merge helpers for field extraction."""

from __future__ import annotations

from collections.abc import Callable

from app.models.document_bundle import DocumentBundle
from app.models.invoice_model import InvoiceData

from .bundle_parts import (
    build_logical_regions,
    select_best_amount_candidate,
    select_best_line_candidates,
    select_best_party_entity_candidates,
    select_best_text_candidate,
)


def extract_from_bundle(
    bundle: DocumentBundle,
    extract_region: Callable[[str], InvoiceData],
) -> tuple[InvoiceData, dict[str, InvoiceData]]:
    logical_regions = build_logical_regions(bundle)
    region_candidates: dict[str, InvoiceData] = {}

    for region_name, payload in logical_regions.items():
        text = payload["text"]
        if text.strip():
            region_candidates[region_name] = extract_region(text)

    if "full" not in region_candidates:
        region_candidates["full"] = extract_region(bundle.raw_text)

    merged = InvoiceData()
    merged.numero_factura = select_best_text_candidate("numero_factura", region_candidates, logical_regions)
    merged.rectified_invoice_number = select_best_text_candidate("rectified_invoice_number", region_candidates, logical_regions)
    merged.fecha = select_best_text_candidate("fecha", region_candidates, logical_regions)
    best_entities = select_best_party_entity_candidates(region_candidates, logical_regions)
    merged.proveedor = best_entities["proveedor"]
    merged.cif_proveedor = best_entities["cif_proveedor"]
    merged.cliente = best_entities["cliente"]
    merged.cif_cliente = best_entities["cif_cliente"]
    merged.base_imponible = select_best_amount_candidate("base_imponible", region_candidates, logical_regions)
    merged.iva_porcentaje = select_best_amount_candidate("iva_porcentaje", region_candidates, logical_regions)
    merged.iva = select_best_amount_candidate("iva", region_candidates, logical_regions)
    merged.retencion_porcentaje = select_best_amount_candidate("retencion_porcentaje", region_candidates, logical_regions)
    merged.retencion = select_best_amount_candidate("retencion", region_candidates, logical_regions)
    merged.total = select_best_amount_candidate("total", region_candidates, logical_regions)
    merged.lineas = select_best_line_candidates(region_candidates, logical_regions)
    return merged, region_candidates
