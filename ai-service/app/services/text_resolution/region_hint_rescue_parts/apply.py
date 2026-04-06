from __future__ import annotations

import logging
from typing import Any

from app.models.document_bundle import BoundingBox, DocumentBundle, DocumentSpan, LayoutRegion
from app.models.invoice_model import InvoiceData
from app.services.providers.registry import get_document_parser_provider

from .shared import format_exception, normalize_hint_lookup, region_hint_priority, should_run

logger = logging.getLogger(__name__)


def maybe_apply(
    *,
    file_path: str,
    input_profile: dict[str, Any],
    company_context: dict[str, str] | None,
    bundle: DocumentBundle,
    raw_text: str,
    base_candidate: InvoiceData,
) -> tuple[DocumentBundle, str, bool]:
    if not should_run(
        base_candidate=base_candidate,
        input_profile=input_profile,
        company_context=company_context,
    ):
        return bundle, raw_text, False

    try:
        region_hints = get_document_parser_provider().extract_region_hints(
            file_path,
            input_kind=input_profile.get("input_kind", "pdf_scanned"),
            max_pages=1,
        )
    except Exception as exc:
        logger.warning("Region hint OCR rescue failed: %s", format_exception(exc))
        return bundle, raw_text, False

    if not region_hints:
        return bundle, raw_text, False

    region_hints = sorted(
        region_hints,
        key=lambda hint: (
            region_hint_priority(str(hint.get("region_type", "") or "")),
            int(hint.get("page_number", 1) or 1),
        ),
    )

    rescued_bundle = bundle.model_copy(deep=True)
    normalized_raw_text = normalize_hint_lookup(raw_text)
    additional_texts: list[str] = []

    for index, hint in enumerate(region_hints, start=1):
        text = str(hint.get("text", "") or "").strip()
        if not text:
            continue

        page_number = int(hint.get("page_number", 1) or 1)
        bbox_payload = hint.get("bbox") or {}
        bbox = BoundingBox.from_points(
            float(bbox_payload.get("x0", 0) or 0),
            float(bbox_payload.get("y0", 0) or 0),
            float(bbox_payload.get("x1", 0) or 0),
            float(bbox_payload.get("y1", 0) or 0),
        )
        region_type = str(hint.get("region_type", "") or "").strip() or "header"
        region = LayoutRegion(
            region_id=f"rescue:p{page_number}:{region_type}:{index}",
            region_type=region_type,
            page=page_number,
            bbox=bbox,
            text=text,
            confidence=0.88,
        )
        span = DocumentSpan(
            span_id=f"rescue:p{page_number}:{region_type}:{index}",
            page=page_number,
            text=text,
            bbox=bbox,
            source="ocr_region",
            engine="tesseract",
            block_no=900 + index,
            line_no=0,
            confidence=0.88,
        )
        rescued_bundle.regions.append(region)
        rescued_bundle.spans.append(span)

        page_index = page_number - 1
        if 0 <= page_index < len(rescued_bundle.pages):
            rescued_bundle.pages[page_index].spans.append(span)
            page_text = rescued_bundle.pages[page_index].reading_text or ""
            if normalize_hint_lookup(text) not in normalize_hint_lookup(page_text):
                rescued_bundle.pages[page_index].reading_text = "\n".join(
                    part for part in (page_text.strip(), text) if part
                ).strip()
                rescued_bundle.pages[page_index].ocr_text = "\n".join(
                    part for part in (rescued_bundle.pages[page_index].ocr_text.strip(), text) if part
                ).strip()

        if normalize_hint_lookup(text) not in normalized_raw_text:
            additional_texts.append(text)

    if additional_texts:
        rescued_bundle.raw_text = "\n".join(part for part in (*additional_texts, raw_text.strip()) if part).strip()
    rescued_bundle.refresh_derived_state()

    return rescued_bundle, rescued_bundle.raw_text or raw_text, True
