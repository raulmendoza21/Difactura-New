from __future__ import annotations

from typing import Any, Callable

from app.models.document_bundle import DocumentBundle
from app.models.invoice_model import InvoiceData
from app.services.document_intelligence_flow.fallback_policy import resolve_input_profile
from app.services.document_intelligence_flow.helpers import merge_with_fallback
from app.services.field_extractor import field_extractor
from app.services.text_resolution.normalization import invoice_normalization_service
from app.services.text_resolution.region_hint_rescue import region_hint_rescue_service


def _build_bundle_candidate_state(bundle: DocumentBundle) -> tuple[InvoiceData | None, dict[str, Any]]:
    bundle_candidate, bundle_sources = field_extractor.extract_from_bundle(bundle)
    bundle.candidate_groups = region_hint_rescue_service.build_bundle_candidate_groups(
        bundle=bundle,
        bundle_sources=bundle_sources,
    )
    return bundle_candidate, bundle_sources


def build_primary_extraction_state(
    *,
    file_path: str,
    mime_type: str,
    company_context: dict[str, str] | None,
    include_page_images: bool,
    heuristic_extract: Callable[[str], InvoiceData],
    loader,
) -> dict[str, Any]:
    document = loader.load(
        file_path,
        mime_type,
        include_page_images=include_page_images,
        company_context=company_context,
    )
    bundle = document.get("bundle") or DocumentBundle(raw_text=document["raw_text"], page_count=document["pages"])
    bundle.refresh_derived_state()
    raw_text = bundle.raw_text or document["raw_text"]
    pages = document["pages"]
    input_profile = resolve_input_profile(bundle=bundle, document=document)
    warnings: list[str] = []

    fallback_data = heuristic_extract(raw_text)
    bundle_candidate, bundle_sources = _build_bundle_candidate_state(bundle)
    base_candidate = merge_with_fallback(bundle_candidate, fallback_data)
    base_candidate, base_warnings = invoice_normalization_service.normalize_invoice_data(
        base_candidate,
        fallback_data,
        raw_text=raw_text,
        company_context=company_context,
    )
    warnings.extend(base_warnings)

    bundle, raw_text, rescue_applied = region_hint_rescue_service.maybe_apply(
        file_path=file_path,
        input_profile=input_profile,
        company_context=company_context,
        bundle=bundle,
        raw_text=raw_text,
        base_candidate=base_candidate,
    )
    if rescue_applied:
        if "region_hint_rescue" not in input_profile.setdefault("preprocessing_steps", []):
            input_profile["preprocessing_steps"].append("region_hint_rescue")
        warnings.append("region_hint_rescue_applied")
        fallback_data = heuristic_extract(raw_text)
        bundle_candidate, bundle_sources = _build_bundle_candidate_state(bundle)
        base_candidate = merge_with_fallback(bundle_candidate, fallback_data)
        base_candidate, rescue_warnings = invoice_normalization_service.normalize_invoice_data(
            base_candidate,
            fallback_data,
            raw_text=raw_text,
            company_context=company_context,
        )
        warnings.extend(rescue_warnings)

    return {
        "document": document,
        "bundle": bundle,
        "raw_text": raw_text,
        "pages": pages,
        "input_profile": input_profile,
        "fallback_data": fallback_data,
        "bundle_candidate": bundle_candidate,
        "warnings": warnings,
        "data": base_candidate,
        "provider": "heuristic",
        "method": "doc_bundle",
        "ai_candidate": None,
    }
