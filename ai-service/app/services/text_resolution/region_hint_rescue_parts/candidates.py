from __future__ import annotations

from app.models.document_bundle import BoundingBox, BundleCandidate, DocumentBundle
from app.models.invoice_model import InvoiceData

from .shared import stringify_candidate_value


def build_bundle_candidate_groups(
    *,
    bundle: DocumentBundle,
    bundle_sources: dict[str, InvoiceData] | None,
) -> dict[str, list[BundleCandidate]]:
    bundle_sources = bundle_sources or {}
    field_map = {
        "numero_factura": "numero_factura",
        "fecha": "fecha",
        "proveedor": "proveedor",
        "cif_proveedor": "cif_proveedor",
        "cliente": "cliente",
        "cif_cliente": "cif_cliente",
        "base_imponible": "base_imponible",
        "iva_porcentaje": "iva_porcentaje",
        "iva": "iva",
        "retencion_porcentaje": "retencion_porcentaje",
        "retencion": "retencion",
        "total": "total",
    }
    grouped: dict[str, list[BundleCandidate]] = {}
    for region_type, candidate_invoice in bundle_sources.items():
        region = next((item for item in bundle.regions if item.region_type == region_type), None)
        page = region.page if region else 0
        bbox = region.bbox if region else BoundingBox()
        region_score = round(region.confidence, 2) if region else 0.5
        for response_field, invoice_field in field_map.items():
            value = getattr(candidate_invoice, invoice_field, None)
            if value in ("", None, 0, 0.0):
                continue
            grouped.setdefault(response_field, []).append(
                BundleCandidate(
                    candidate_id=f"{region_type}:{response_field}:{len(grouped.get(response_field, [])) + 1}",
                    field=response_field,
                    value=stringify_candidate_value(value),
                    source="bundle_region",
                    extractor=region_type,
                    page=page,
                    region_type=region_type,
                    bbox=bbox,
                    score=region_score,
                )
            )
    return grouped
