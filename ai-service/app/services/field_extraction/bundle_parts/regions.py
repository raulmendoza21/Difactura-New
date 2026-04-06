from __future__ import annotations

from app.models.document_bundle import DocumentBundle, LayoutRegion

FIELD_REGION_WEIGHTS: dict[str, dict[str, float]] = {
    "numero_factura": {"header": 1.0, "parties": 0.35, "full": 0.5},
    "rectified_invoice_number": {"header": 1.0, "full": 0.45},
    "fecha": {"header": 1.0, "totals": 0.35, "full": 0.45},
    "proveedor": {"parties": 1.0, "header": 0.8, "full": 0.35},
    "cif_proveedor": {"parties": 1.0, "header": 0.8, "full": 0.35},
    "cliente": {"parties": 1.0, "header": 0.8, "full": 0.35},
    "cif_cliente": {"parties": 1.0, "header": 0.8, "full": 0.35},
    "base_imponible": {"totals": 1.0, "line_items": 0.35, "full": 0.45},
    "iva_porcentaje": {"totals": 1.0, "full": 0.35},
    "iva": {"totals": 1.0, "full": 0.35},
    "retencion_porcentaje": {"totals": 1.0, "full": 0.35},
    "retencion": {"totals": 1.0, "full": 0.35},
    "total": {"totals": 1.0, "full": 0.45},
}

REGION_GROUPS: dict[str, set[str]] = {
    "header": {"header", "header_left", "header_right", "company_anchor"},
    "parties": {"parties", "header_left", "header_right", "company_anchor"},
    "totals": {"totals", "footer"},
    "line_items": {"line_items", "body"},
}


def build_logical_regions(bundle: DocumentBundle) -> dict[str, dict]:
    logical_regions: dict[str, dict] = {
        "full": {
            "text": bundle.raw_text or "",
            "confidence": 0.4,
            "regions": [],
            "pages": {page.page_number for page in bundle.pages},
        }
    }
    for logical_name, region_types in REGION_GROUPS.items():
        matching_regions = [
            region for region in bundle.regions if region.region_type in region_types and region.text and region.text.strip()
        ]
        logical_regions[logical_name] = {
            "text": "\n".join(region.text for region in matching_regions).strip(),
            "confidence": _region_confidence(matching_regions),
            "regions": matching_regions,
            "pages": {region.page for region in matching_regions if region.page},
        }
    return logical_regions


def _region_confidence(regions: list[LayoutRegion]) -> float:
    if not regions:
        return 0.35
    confidences = [float(region.confidence or 0.0) for region in regions]
    return round(sum(confidences) / len(confidences), 3)
