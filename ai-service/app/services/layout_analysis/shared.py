from __future__ import annotations

from app.models.document_bundle import BoundingBox, DocumentSpan, LayoutRegion


def region_from_spans(
    page_number: int,
    region_type: str,
    spans: list[DocumentSpan],
    *,
    confidence: float,
) -> LayoutRegion:
    x0 = min(span.bbox.x0 for span in spans)
    y0 = min(span.bbox.y0 for span in spans)
    x1 = max(span.bbox.x1 for span in spans)
    y1 = max(span.bbox.y1 for span in spans)
    ordered_spans = sorted(spans, key=lambda span: (round(span.bbox.y0, 1), round(span.bbox.x0, 1)))
    return LayoutRegion(
        region_id=f"p{page_number}:{region_type}",
        region_type=region_type,
        page=page_number,
        bbox=BoundingBox.from_points(x0, y0, x1, y1),
        text="\n".join(span.text for span in ordered_spans if span.text).strip(),
        span_ids=[span.span_id for span in ordered_spans],
        confidence=round(confidence, 2),
    )


def deduplicate_regions(regions: list[LayoutRegion]) -> list[LayoutRegion]:
    deduped: list[LayoutRegion] = []
    seen: set[tuple[str, int, str]] = set()
    for region in regions:
        key = (region.region_type, region.page, region.text[:120])
        if key in seen or not region.text:
            continue
        seen.add(key)
        deduped.append(region)
    return deduped


def page_width(spans: list[DocumentSpan]) -> float:
    return max((span.bbox.x1 for span in spans), default=0.0)


def page_height(spans: list[DocumentSpan]) -> float:
    return max((span.bbox.y1 for span in spans), default=0.0)
