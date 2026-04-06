from __future__ import annotations

from typing import Any

from app.models.document_bundle import DocumentBundle
from app.models.extraction_result import DecisionFlag, FieldEvidence, ProcessingTraceItem
from app.models.invoice_model import InvoiceData
from app.services.evidence_building.decision_flags import build_decision_flags
from app.services.evidence_building.field_evidence import build_field_evidence
from app.services.evidence_building.processing_trace import build_processing_trace


class EvidenceBuilder:
    """Thin facade for evidence, review flags and processing trace builders."""

    def build_field_evidence(
        self,
        *,
        bundle: DocumentBundle,
        final: InvoiceData,
        heuristic: InvoiceData,
        bundle_candidate: InvoiceData | None,
        ai_candidate: InvoiceData | None,
    ) -> dict[str, list[FieldEvidence]]:
        return build_field_evidence(
            bundle=bundle,
            final=final,
            heuristic=heuristic,
            bundle_candidate=bundle_candidate,
            ai_candidate=ai_candidate,
        )

    def build_decision_flags(
        self,
        *,
        invoice: InvoiceData,
        field_confidence: dict[str, float],
        warnings: list[str],
        company_match: dict[str, Any] | None = None,
    ) -> list[DecisionFlag]:
        return build_decision_flags(
            invoice=invoice,
            field_confidence=field_confidence,
            warnings=warnings,
            company_match=company_match,
        )

    def build_processing_trace(
        self,
        *,
        bundle: DocumentBundle,
        input_kind: str,
        provider: str,
        method: str,
        used_ocr: bool,
        used_ai: bool,
        page_count: int,
    ) -> list[ProcessingTraceItem]:
        return build_processing_trace(
            bundle=bundle,
            input_kind=input_kind,
            provider=provider,
            method=method,
            used_ocr=used_ocr,
            used_ai=used_ai,
            page_count=page_count,
        )


evidence_builder = EvidenceBuilder()
