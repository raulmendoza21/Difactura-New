from __future__ import annotations

from PIL import Image

from app.models.document_bundle import BundleInputProfile
from app.services.document_loading.bundle_factory import (
    build_image_bundle,
    provider_page_entries_payload,
)
from app.services.document_loading.input_profile import (
    augment_preprocessing_steps,
    detect_document_family_hint,
    has_low_resolution_pages,
    rotation_hint,
)
from app.services.document_loading.provider_flow import (
    extract_image_with_fallback,
    resolve_primary_provider,
)


def load_image_document(
    *,
    file_path: str,
    mime_type: str,
    include_page_images: bool,
    company_context: dict[str, str] | None,
    classify_input,
    image_to_data_url,
    build_bundle=build_image_bundle,
) -> dict:
    page_images: list[str] = []
    input_kind = classify_input(file_path)
    if include_page_images:
        with Image.open(file_path) as image:
            rgb_image = image.convert("RGB")
            page_images = [image_to_data_url(rgb_image, mime_type or "image/png")]

    requested_provider, provider = resolve_primary_provider()
    provider_result, provider_trace = extract_image_with_fallback(
        requested_provider=requested_provider,
        provider=provider,
        file_path=file_path,
        mime_type=mime_type,
        input_kind=input_kind,
        include_page_images=include_page_images,
    )
    page_entries = provider_page_entries_payload(provider_result.page_entries) or [
        {
            "page_number": 1,
            "text": provider_result.text,
            "spans": [],
            "width": 0,
            "height": 0,
        }
    ]
    bundle = build_bundle(page_entries, provider_result.text, company_context=company_context)
    bundle.input_profile = BundleInputProfile(
        input_kind=input_kind,
        text_source="ocr",
        requested_provider=str(provider_trace["requested_provider"]),
        document_provider=str(provider_trace["document_provider"]),
        fallback_provider=str(provider_trace["fallback_provider"]),
        fallback_applied=bool(provider_trace["fallback_applied"]),
        fallback_reason=str(provider_trace["fallback_reason"]),
        is_digital_pdf=False,
        used_ocr=True,
        used_page_images=bool(page_images),
        ocr_engine=provider_result.ocr_engine,
        preprocessing_steps=augment_preprocessing_steps(provider_result.preprocessing_steps, provider_trace),
        document_family_hint=detect_document_family_hint(bundle.raw_text),
        low_resolution=has_low_resolution_pages(bundle.pages),
        rotation_hint=rotation_hint(bundle.pages),
        input_route="image_ocr_bundle",
    )
    return {
        "raw_text": bundle.raw_text,
        "pages": max(1, bundle.page_count),
        "method": "ocr",
        "page_images": page_images,
        "input_profile": bundle.input_profile.model_dump(),
        "bundle": bundle,
    }
