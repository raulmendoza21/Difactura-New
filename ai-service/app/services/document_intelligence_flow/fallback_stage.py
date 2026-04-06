from __future__ import annotations

import logging
from typing import Any, Awaitable, Callable

from app.config import settings
from app.models.invoice_model import InvoiceData
from app.services.document_intelligence_flow.fallback_policy import should_run_doc_ai_fallback
from app.services.document_intelligence_flow.helpers import format_exception, merge_with_fallback
from app.services.text_resolution.normalization import invoice_normalization_service
from app.services.text_resolution.result_building import document_result_builder

logger = logging.getLogger(__name__)


async def maybe_apply_doc_ai_fallback(
    *,
    state: dict[str, Any],
    provider_name: str,
    filename: str,
    company_context: dict[str, str] | None,
    build_resolution: Callable[..., dict[str, Any]],
    extract_with_provider: Callable[[str, str, list[str], str], Awaitable[tuple[InvoiceData, str]]],
) -> dict[str, Any]:
    if not settings.doc_ai_enabled:
        return state

    resolution = state["resolution"]
    if not should_run_doc_ai_fallback(
        resolution=resolution,
        input_profile=state["input_profile"],
        company_context=company_context,
    ):
        return state

    try:
        ai_data, provider = await extract_with_provider(
            provider_name,
            state["raw_text"],
            state["document"]["page_images"][: settings.doc_ai_max_pages],
            filename,
        )
        ai_candidate = ai_data.model_copy(deep=True)
        state["warnings"].extend(document_result_builder.compare_source_candidates(ai_candidate, state["data"]))
        ai_data = merge_with_fallback(ai_data, state["data"])
        ai_data, normalization_warnings = invoice_normalization_service.normalize_invoice_data(
            ai_data,
            state["data"],
            raw_text=state["raw_text"],
            company_context=company_context,
        )
        state["warnings"].extend(normalization_warnings)
        state["data"] = ai_data
        state["provider"] = provider
        state["method"] = "doc_bundle_doc_ai_fallback"
        state["ai_candidate"] = ai_candidate
    except Exception as exc:
        formatted_exc = format_exception(exc)
        logger.warning("Selective Doc AI fallback failed, keeping primary result: %s", formatted_exc)
        state["warnings"].append(f"doc_ai_fallback_error: {formatted_exc}")

    state["resolution"] = build_resolution(
        data=state["data"],
        raw_text=state["raw_text"],
        filename=filename,
        mime_type=state["mime_type"],
        pages=state["pages"],
        input_profile=state["input_profile"],
        bundle=state["bundle"],
        fallback_data=state["fallback_data"],
        bundle_candidate=state["bundle_candidate"],
        ai_candidate=state["ai_candidate"],
        provider=state["provider"],
        method=state["method"],
        warnings=state["warnings"],
        company_context=company_context,
    )
    return state
