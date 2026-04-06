from __future__ import annotations

from collections import defaultdict

from app.models.document_bundle import DocumentSpan, LayoutRegion

from .shared import region_from_spans

REGION_KEYWORDS = {
    "totals": ("TOTAL", "SUBTOTAL", "BASE", "BASE IMPONIBLE", "IMPUESTOS", "IGIC", "IVA", "RETEN", "IRPF"),
    "line_items": ("CONCEPTO", "DESCRIP", "ARTICULO", "IMPORTE", "PRECIO", "CANTIDAD", "UNIDADES"),
    "parties": ("CLIENTE", "PROVEEDOR", "EMISOR", "DESTINATARIO", "RECEPTOR", "FACTURAR A"),
}


def build_keyword_regions(page_number: int, spans: list[DocumentSpan]) -> list[LayoutRegion]:
    grouped: dict[str, list[DocumentSpan]] = defaultdict(list)
    for span in spans:
        upper_text = span.text.upper()
        for region_type, keywords in REGION_KEYWORDS.items():
            if any(keyword in upper_text for keyword in keywords):
                grouped[region_type].append(span)

    return [
        region_from_spans(page_number, region_type, grouped_spans, confidence=0.75)
        for region_type, grouped_spans in grouped.items()
        if grouped_spans
    ]
