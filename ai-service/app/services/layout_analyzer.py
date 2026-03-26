from __future__ import annotations

import re
from collections import defaultdict

from app.models.document_bundle import BoundingBox, DocumentBundle, DocumentSpan, LayoutRegion


REGION_KEYWORDS = {
    "totals": ("TOTAL", "SUBTOTAL", "BASE", "BASE IMPONIBLE", "IMPUESTOS", "IGIC", "IVA", "RETEN", "IRPF"),
    "line_items": ("CONCEPTO", "DESCRIP", "ARTICULO", "ARTICULO", "IMPORTE", "PRECIO", "CANTIDAD", "UNIDADES"),
    "parties": ("CLIENTE", "PROVEEDOR", "EMISOR", "DESTINATARIO", "RECEPTOR", "FACTURAR A"),
}


class LayoutAnalyzer:
    """Build coarse layout regions from native text and OCR spans."""

    def analyze(self, bundle: DocumentBundle, company_context: dict[str, str] | None = None) -> list[LayoutRegion]:
        company_context = company_context or {}
        regions: list[LayoutRegion] = []

        for page in bundle.pages:
            ordered_spans = sorted(page.spans, key=lambda span: (round(span.bbox.y0, 1), round(span.bbox.x0, 1)))
            if not ordered_spans:
                continue

            regions.extend(self._build_page_slices(page.page_number, ordered_spans, page.height))
            regions.extend(self._build_keyword_regions(page.page_number, ordered_spans))
            regions.extend(self._build_party_regions(page.page_number, ordered_spans, company_context))

        return self._deduplicate_regions(regions)

    def _build_page_slices(self, page_number: int, spans: list[DocumentSpan], page_height: float) -> list[LayoutRegion]:
        if page_height <= 0:
            page_height = max((span.bbox.y1 for span in spans), default=0)

        header_spans = [span for span in spans if span.bbox.y0 <= page_height * 0.28]
        footer_spans = [span for span in spans if span.bbox.y1 >= page_height * 0.72]
        body_spans = [span for span in spans if span not in header_spans and span not in footer_spans]

        regions = []
        if header_spans:
            regions.append(self._region_from_spans(page_number, "header", header_spans, confidence=0.7))
        if body_spans:
            regions.append(self._region_from_spans(page_number, "body", body_spans, confidence=0.45))
        if footer_spans:
            regions.append(self._region_from_spans(page_number, "footer", footer_spans, confidence=0.6))
        return regions

    def _build_keyword_regions(self, page_number: int, spans: list[DocumentSpan]) -> list[LayoutRegion]:
        grouped: dict[str, list[DocumentSpan]] = defaultdict(list)
        for span in spans:
            upper_text = span.text.upper()
            for region_type, keywords in REGION_KEYWORDS.items():
                if any(keyword in upper_text for keyword in keywords):
                    grouped[region_type].append(span)

        return [
            self._region_from_spans(page_number, region_type, grouped_spans, confidence=0.75)
            for region_type, grouped_spans in grouped.items()
            if grouped_spans
        ]

    def _build_party_regions(
        self,
        page_number: int,
        spans: list[DocumentSpan],
        company_context: dict[str, str],
    ) -> list[LayoutRegion]:
        header_candidates = [span for span in spans if span.bbox.y0 <= max(240.0, self._page_height(spans) * 0.35)]
        if not header_candidates:
            return []

        left_spans = [span for span in header_candidates if span.bbox.x0 <= self._page_width(spans) * 0.55]
        right_spans = [span for span in header_candidates if span.bbox.x0 > self._page_width(spans) * 0.45]
        regions: list[LayoutRegion] = []

        if left_spans:
            regions.append(self._region_from_spans(page_number, "header_left", left_spans, confidence=0.55))
        if right_spans:
            regions.append(self._region_from_spans(page_number, "header_right", right_spans, confidence=0.55))

        company_name = re.sub(r"\s+", " ", str(company_context.get("name", "")).upper()).strip()
        if company_name:
            company_spans = [span for span in header_candidates if company_name and company_name[:12] in span.text.upper()]
            if company_spans:
                regions.append(self._region_from_spans(page_number, "company_anchor", company_spans, confidence=0.9))

        return regions

    def _region_from_spans(
        self,
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

    def _deduplicate_regions(self, regions: list[LayoutRegion]) -> list[LayoutRegion]:
        deduped: list[LayoutRegion] = []
        seen: set[tuple[str, int, str]] = set()
        for region in regions:
            key = (region.region_type, region.page, region.text[:120])
            if key in seen or not region.text:
                continue
            seen.add(key)
            deduped.append(region)
        return deduped

    def _page_width(self, spans: list[DocumentSpan]) -> float:
        return max((span.bbox.x1 for span in spans), default=0.0)

    def _page_height(self, spans: list[DocumentSpan]) -> float:
        return max((span.bbox.y1 for span in spans), default=0.0)


layout_analyzer = LayoutAnalyzer()
