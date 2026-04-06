from __future__ import annotations

from app.models.document_bundle import DocumentBundle, DocumentPageBundle, DocumentSpan
from app.models.document_provider import ProviderDocumentResult, ProviderPageEntry
from app.services.layout_analyzer import layout_analyzer


def provider_page_entries_payload(page_entries: list[ProviderPageEntry]) -> list[dict]:
    return [
        {
            "page_number": entry.page_number,
            "width": entry.width,
            "height": entry.height,
            "text": entry.text,
            "spans": entry.spans,
            "ocr_engine": entry.ocr_engine,
        }
        for entry in page_entries
    ]


def pdf_result_payload(provider_result: ProviderDocumentResult) -> dict:
    return {
        "text": provider_result.text,
        "pages": provider_result.pages,
        "is_digital": provider_result.is_digital,
        "page_entries": provider_page_entries_payload(provider_result.page_entries) if provider_result.is_digital else [],
    }


def build_pdf_bundle(
    *,
    pdf_result: dict,
    raw_text: str,
    ocr_page_entries: list[dict],
    company_context: dict[str, str] | None = None,
) -> DocumentBundle:
    pages: list[DocumentPageBundle] = []
    all_spans: list[DocumentSpan] = []
    ocr_map = {entry.get("page_number", index + 1): entry for index, entry in enumerate(ocr_page_entries)}
    page_entries = list(pdf_result.get("page_entries", []))

    if not page_entries:
        total_pages = int(pdf_result.get("pages", 0) or len(ocr_page_entries) or 0)
        fallback_texts = [part.strip() for part in raw_text.split("\n\n") if part.strip()]
        if not fallback_texts and raw_text.strip():
            fallback_texts = [raw_text.strip()]
        for index in range(total_pages):
            page_number = index + 1
            fallback_text = fallback_texts[index] if index < len(fallback_texts) else raw_text.strip()
            page_entries.append(
                {
                    "page_number": page_number,
                    "width": 0,
                    "height": 0,
                    "text": fallback_text,
                    "spans": [],
                }
            )

    for page_entry in page_entries:
        page_number = int(page_entry.get("page_number", 0) or 0)
        native_spans = list(page_entry.get("spans", []))
        ocr_entry = ocr_map.get(page_number, {})
        ocr_spans = list(ocr_entry.get("spans", []))
        page_spans = sorted(
            [
                span.model_copy(update={"page": page_number}) if isinstance(span, DocumentSpan) else DocumentSpan(**span)
                for span in [*native_spans, *ocr_spans]
            ],
            key=lambda span: (round(span.bbox.y0, 1), round(span.bbox.x0, 1)),
        )
        pages.append(
            DocumentPageBundle(
                page_number=page_number,
                width=float(page_entry.get("width", 0)),
                height=float(page_entry.get("height", 0)),
                native_text=str(page_entry.get("text", "") or "").strip(),
                ocr_text=str(ocr_entry.get("text", "") or "").strip(),
                reading_text="\n".join(span.text for span in page_spans if span.text).strip()
                or str(page_entry.get("text", "") or "").strip()
                or str(ocr_entry.get("text", "") or "").strip(),
                spans=page_spans,
            )
        )
        all_spans.extend(page_spans)

    bundle = DocumentBundle(
        raw_text=raw_text,
        pages=pages,
        spans=all_spans,
    )
    bundle.regions = layout_analyzer.analyze(bundle, company_context=company_context)
    bundle.refresh_derived_state()
    return bundle


def build_image_bundle(
    page_entries: list[dict],
    raw_text: str,
    *,
    company_context: dict[str, str] | None = None,
) -> DocumentBundle:
    pages: list[DocumentPageBundle] = []
    all_spans: list[DocumentSpan] = []

    for index, page_entry in enumerate(page_entries, start=1):
        raw_spans = page_entry.get("spans", [])
        page_spans = sorted(
            [
                span.model_copy(update={"page": index}) if isinstance(span, DocumentSpan) else DocumentSpan(**span)
                for span in raw_spans
            ],
            key=lambda span: (round(span.bbox.y0, 1), round(span.bbox.x0, 1)),
        )
        pages.append(
            DocumentPageBundle(
                page_number=index,
                width=float(page_entry.get("width", 0)),
                height=float(page_entry.get("height", 0)),
                ocr_text=str(page_entry.get("text", "") or "").strip(),
                reading_text="\n".join(span.text for span in page_spans if span.text).strip()
                or str(page_entry.get("text", "") or "").strip(),
                spans=page_spans,
            )
        )
        all_spans.extend(page_spans)

    bundle = DocumentBundle(
        raw_text=raw_text.strip(),
        pages=pages,
        spans=all_spans,
    )
    bundle.regions = layout_analyzer.analyze(bundle, company_context=company_context)
    bundle.refresh_derived_state()
    return bundle
