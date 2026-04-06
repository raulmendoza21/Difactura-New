from __future__ import annotations

from app.models.document_bundle import BundleInputProfile
from app.services.document_loading.bundle_factory import (
    build_pdf_bundle,
    pdf_result_payload,
    provider_page_entries_payload,
)
from app.services.document_loading.input_profile import (
    augment_preprocessing_steps,
    detect_document_family_hint,
    has_low_resolution_pages,
    rotation_hint,
)
from app.services.document_loading.provider_flow import (
    extract_pdf_with_fallback,
    resolve_primary_provider,
)


def load_pdf_document(
    *,
    file_path: str,
    include_page_images: bool,
    company_context: dict[str, str] | None,
    render_pdf_pages,
) -> dict:
    requested_provider, provider = resolve_primary_provider()
    provider_result, provider_trace = extract_pdf_with_fallback(
        requested_provider=requested_provider,
        provider=provider,
        file_path=file_path,
        include_page_images=include_page_images,
    )

    raw_text = provider_result.text if provider_result.is_digital else ""
    method = provider_result.method or ("digital" if provider_result.is_digital else "ocr")
    used_ocr = not provider_result.is_digital
    preprocessing_steps = (
        provider_result.preprocessing_steps
        or (["pdf_text_extraction"] if provider_result.is_digital else ["pdf_page_render", "ocr_preprocess"])
    )
    pdf_result = pdf_result_payload(provider_result)
    ocr_page_entries: list[dict] = []
    if not raw_text.strip():
        raw_text = provider_result.text
        used_ocr = True
        ocr_page_entries = provider_page_entries_payload(provider_result.page_entries) or [
            {
                "page_number": page_number,
                "text": raw_text,
                "spans": [],
                "width": 0,
                "height": 0,
            }
            for page_number in range(1, int(provider_result.pages or 0) + 1)
        ]

    page_images = render_pdf_pages(file_path) if include_page_images else []
    bundle = build_pdf_bundle(
        pdf_result=pdf_result,
        raw_text=raw_text.strip(),
        ocr_page_entries=ocr_page_entries,
        company_context=company_context,
    )
    input_kind = "pdf_digital" if pdf_result["is_digital"] else "pdf_scanned"
    bundle.input_profile = BundleInputProfile(
        input_kind=input_kind,
        text_source="digital_text" if pdf_result["is_digital"] else "ocr",
        requested_provider=str(provider_trace["requested_provider"]),
        document_provider=str(provider_trace["document_provider"]),
        fallback_provider=str(provider_trace["fallback_provider"]),
        fallback_applied=bool(provider_trace["fallback_applied"]),
        fallback_reason=str(provider_trace["fallback_reason"]),
        is_digital_pdf=pdf_result["is_digital"],
        used_ocr=used_ocr or not pdf_result["is_digital"],
        used_page_images=bool(page_images),
        ocr_engine=provider_result.ocr_engine if (used_ocr or not pdf_result["is_digital"]) else "",
        preprocessing_steps=augment_preprocessing_steps(preprocessing_steps, provider_trace),
        document_family_hint=detect_document_family_hint(bundle.raw_text),
        low_resolution=has_low_resolution_pages(bundle.pages),
        rotation_hint=rotation_hint(bundle.pages),
        input_route="pdf_native_bundle" if pdf_result["is_digital"] else "pdf_ocr_bundle",
    )
    return {
        "raw_text": bundle.raw_text,
        "pages": provider_result.pages or pdf_result["pages"],
        "method": method,
        "page_images": page_images,
        "input_profile": bundle.input_profile.model_dump(),
        "bundle": bundle,
    }
