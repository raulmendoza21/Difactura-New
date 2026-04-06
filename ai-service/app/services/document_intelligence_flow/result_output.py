from __future__ import annotations

from app.models.extraction_result import (
    CompanyMatch,
    DocumentInputProfile,
    EngineCompanyContext,
    EngineRequestContext,
    ExtractionResult,
)
from app.services.evidence_builder import evidence_builder


def build_extraction_result(
    *,
    resolution: dict,
    bundle,
    raw_text: str,
    filename: str,
    mime_type: str,
    company_context: dict[str, str] | None,
    input_profile: dict,
    provider: str,
    method: str,
    pages: int,
    warnings: list[str],
    ai_candidate,
) -> ExtractionResult:
    data = resolution["data"]
    company_match = resolution["company_match"]
    evidence = resolution["evidence"]
    field_confidence = resolution["field_confidence"]
    normalized_document = resolution["normalized_document"]
    coverage = resolution["coverage"]
    decision_flags = resolution["decision_flags"]

    processing_trace = evidence_builder.build_processing_trace(
        bundle=bundle,
        input_kind=input_profile.get("input_kind", ""),
        provider=provider,
        method=method,
        used_ocr=bool(input_profile.get("used_ocr")),
        used_ai=ai_candidate is not None,
        page_count=pages,
    )

    return ExtractionResult(
        success=True,
        engine_request=EngineRequestContext(
            file_name=filename or "",
            mime_type=mime_type,
            company_context=EngineCompanyContext(
                name=(company_context or {}).get("name", ""),
                tax_id=(company_context or {}).get("tax_id", "") or (company_context or {}).get("taxId", ""),
            ),
        ),
        data=data,
        document_input=DocumentInputProfile(**input_profile),
        field_confidence=field_confidence,
        normalized_document=normalized_document,
        coverage=coverage,
        evidence=evidence,
        decision_flags=decision_flags,
        company_match=CompanyMatch(**company_match),
        processing_trace=processing_trace,
        raw_text=raw_text,
        method=method,
        provider=provider,
        pages=pages,
        warnings=warnings,
    )
