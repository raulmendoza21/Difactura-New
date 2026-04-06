from __future__ import annotations

from app.models.document_bundle import DocumentBundle, LayoutRegion
from app.services.layout_analysis.keywords import build_keyword_regions
from app.services.layout_analysis.parties import build_party_regions
from app.services.layout_analysis.shared import deduplicate_regions
from app.services.layout_analysis.slices import build_page_slices


class LayoutAnalyzer:
    """Build coarse layout regions from native text and OCR spans."""

    def analyze(self, bundle: DocumentBundle, company_context: dict[str, str] | None = None) -> list[LayoutRegion]:
        company_context = company_context or {}
        regions: list[LayoutRegion] = []

        for page in bundle.pages:
            ordered_spans = sorted(page.spans, key=lambda span: (round(span.bbox.y0, 1), round(span.bbox.x0, 1)))
            if not ordered_spans:
                continue

            regions.extend(build_page_slices(page.page_number, ordered_spans, page.height))
            regions.extend(build_keyword_regions(page.page_number, ordered_spans))
            regions.extend(build_party_regions(page.page_number, ordered_spans, company_context))

        return deduplicate_regions(regions)


layout_analyzer = LayoutAnalyzer()
