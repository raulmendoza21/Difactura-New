"""Document-to-JSON extraction orchestrator."""

from __future__ import annotations

import logging
from typing import Any

from app.config import settings
from app.models.document_bundle import DocumentBundle
from app.models.extraction_result import ExtractionResult
from app.models.invoice_model import InvoiceData
from app.services.confidence_scorer import confidence_scorer
from app.services.document_intelligence_flow.fallback_policy import (
    resolve_input_profile,
    should_run_doc_ai_fallback,
)
from app.services.document_intelligence_flow.fallback_stage import maybe_apply_doc_ai_fallback
from app.services.document_intelligence_flow.helpers import (
    format_exception,
    invoice_from_payload,
    merge_with_fallback,
    parse_json_payload,
    response_schema,
)
from app.services.document_intelligence_flow.primary_stage import build_primary_extraction_state
from app.services.document_intelligence_flow.prompt import DOC_AI_PROMPT
from app.services.document_intelligence_flow.provider_clients import (
    extract_with_ollama,
    extract_with_openai_compatible,
)
from app.services.document_loader import document_loader
from app.services.field_extractor import field_extractor
from app.services.document_intelligence_flow.result_output import build_extraction_result
from app.services.text_resolution.result_building import document_result_builder

logger = logging.getLogger(__name__)


class DocumentIntelligenceService:
    """Hybrid extraction using an AI provider with heuristic fallback."""

    async def extract(
        self,
        file_path: str,
        filename: str = "",
        mime_type: str = "",
        company_context: dict[str, str] | None = None,
    ) -> ExtractionResult:
        provider_name = settings.doc_ai_provider if settings.doc_ai_enabled else "heuristic"
        uses_images = provider_name == "openai_compatible"
        state = build_primary_extraction_state(
            file_path=file_path,
            mime_type=mime_type,
            company_context=company_context,
            include_page_images=uses_images,
            heuristic_extract=self._heuristic_extract,
            loader=document_loader,
        )
        state["mime_type"] = mime_type
        state["resolution"] = self._build_resolution(
            data=state["data"],
            raw_text=state["raw_text"],
            filename=filename,
            mime_type=mime_type,
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
        state = await maybe_apply_doc_ai_fallback(
            state=state,
            provider_name=provider_name,
            filename=filename,
            company_context=company_context,
            build_resolution=self._build_resolution,
            extract_with_provider=self._extract_with_provider,
        )
        return build_extraction_result(
            resolution=state["resolution"],
            bundle=state["bundle"],
            raw_text=state["raw_text"],
            filename=filename,
            mime_type=mime_type,
            company_context=company_context,
            input_profile=state["input_profile"],
            provider=state["provider"],
            method=state["method"],
            pages=state["pages"],
            warnings=state["warnings"],
            ai_candidate=state["ai_candidate"],
        )

    def _build_resolution(
        self,
        *,
        data: InvoiceData,
        raw_text: str,
        filename: str,
        mime_type: str,
        pages: int,
        input_profile: dict[str, Any],
        bundle: DocumentBundle,
        fallback_data: InvoiceData,
        bundle_candidate: InvoiceData | None,
        ai_candidate: InvoiceData | None,
        provider: str,
        method: str,
        warnings: list[str],
        company_context: dict[str, str] | None = None,
    ) -> dict[str, Any]:
        return document_result_builder.build_resolution_state(
            data=data,
            raw_text=raw_text,
            filename=filename,
            mime_type=mime_type,
            pages=pages,
            input_profile=input_profile,
            bundle=bundle,
            fallback_data=fallback_data,
            bundle_candidate=bundle_candidate,
            ai_candidate=ai_candidate,
            provider=provider,
            method=method,
            warnings=warnings,
            company_context=company_context,
        )

    def _resolve_input_profile(self, *, bundle: DocumentBundle, document: dict[str, Any]) -> dict[str, Any]:
        return resolve_input_profile(bundle=bundle, document=document)

    def _should_run_doc_ai_fallback(
        self,
        *,
        resolution: dict[str, Any],
        input_profile: dict[str, Any],
        company_context: dict[str, str] | None = None,
    ) -> bool:
        return should_run_doc_ai_fallback(
            resolution=resolution,
            input_profile=input_profile,
            company_context=company_context,
        )

    async def _extract_with_provider(
        self,
        provider_name: str,
        raw_text: str,
        page_images: list[str],
        filename: str,
    ) -> tuple[InvoiceData, str]:
        if provider_name == "openai_compatible":
            return (
                await extract_with_openai_compatible(
                    raw_text=raw_text,
                    page_images=page_images,
                    filename=filename,
                    prompt=DOC_AI_PROMPT,
                ),
                "openai_compatible",
            )
        if provider_name == "ollama":
            return (
                await extract_with_ollama(
                    raw_text=raw_text,
                    filename=filename,
                    prompt=DOC_AI_PROMPT,
                ),
                "ollama",
            )

        raise RuntimeError(f"Proveedor Doc AI no soportado: {provider_name}")

    def _heuristic_extract(self, raw_text: str) -> InvoiceData:
        data = field_extractor.extract(raw_text)
        data.confianza = confidence_scorer.score(data)
        return data

    def _response_schema(self) -> dict[str, Any]:
        return response_schema()

    def _parse_json_payload(self, payload: Any) -> dict[str, Any]:
        return parse_json_payload(payload)

    def _invoice_from_payload(self, payload: dict[str, Any]) -> InvoiceData:
        return invoice_from_payload(payload)

    def _merge_with_fallback(self, primary: InvoiceData, fallback: InvoiceData) -> InvoiceData:
        return merge_with_fallback(primary, fallback)

    def _is_empty_value(self, value: Any) -> bool:
        from app.services.document_intelligence_flow.helpers import is_empty_value

        return is_empty_value(value)

    def _format_exception(self, exc: Exception) -> str:
        return format_exception(exc)

document_intelligence_service = DocumentIntelligenceService()
