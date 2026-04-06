from __future__ import annotations

from app.models.document_bundle import DocumentSpan, LayoutRegion

from .shared import page_height, region_from_spans


def build_page_slices(page_number: int, spans: list[DocumentSpan], declared_page_height: float) -> list[LayoutRegion]:
    computed_page_height = declared_page_height if declared_page_height > 0 else page_height(spans)

    header_spans = [span for span in spans if span.bbox.y0 <= computed_page_height * 0.28]
    footer_spans = [span for span in spans if span.bbox.y1 >= computed_page_height * 0.72]
    body_spans = [span for span in spans if span not in header_spans and span not in footer_spans]

    regions = []
    if header_spans:
        regions.append(region_from_spans(page_number, "header", header_spans, confidence=0.7))
    if body_spans:
        regions.append(region_from_spans(page_number, "body", body_spans, confidence=0.45))
    if footer_spans:
        regions.append(region_from_spans(page_number, "footer", footer_spans, confidence=0.6))
    return regions
