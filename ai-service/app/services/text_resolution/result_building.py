from __future__ import annotations

from typing import Any

from app.models.document_bundle import DocumentBundle
from app.models.document_contract import DocumentType, NormalizedInvoiceDocument
from app.models.extraction_result import ExtractionCoverage
from app.models.invoice_model import InvoiceData, LineItem
from app.services.text_resolution.result_building_parts.confidence import (
    build_field_confidence,
    refine_document_confidence,
    score_field_confidence,
    score_line_field_confidence,
)
from app.services.text_resolution.result_building_parts.document_metadata import (
    build_extraction_coverage,
    build_extraction_document,
    extract_due_date,
    extract_iban,
    extract_payment_method,
    infer_document_type,
    infer_tax_regime,
)
from app.services.text_resolution.result_building_parts.resolution import (
    build_resolution_state,
    compare_source_candidates,
)
from app.services.text_resolution.result_building_parts.shared import (
    is_empty_value,
    is_valid_iso_date,
    line_items_match,
    values_match,
)


class DocumentResultBuilder:
    """Thin facade for normalized document/result construction."""

    def build_resolution_state(self, **kwargs) -> dict[str, Any]:
        return build_resolution_state(**kwargs)

    def build_extraction_document(self, **kwargs) -> NormalizedInvoiceDocument:
        return build_extraction_document(**kwargs)

    def compare_source_candidates(self, ai_candidate: InvoiceData, heuristic: InvoiceData) -> list[str]:
        return compare_source_candidates(ai_candidate, heuristic)

    def build_field_confidence(
        self,
        *,
        final: InvoiceData,
        heuristic: InvoiceData,
        bundle_candidate: InvoiceData | None = None,
        ai_candidate: InvoiceData | None = None,
        evidence: dict[str, list[Any]] | None = None,
    ) -> dict[str, float]:
        return build_field_confidence(
            final=final,
            heuristic=heuristic,
            bundle_candidate=bundle_candidate,
            ai_candidate=ai_candidate,
            evidence=evidence,
        )

    def refine_document_confidence(
        self,
        *,
        invoice: InvoiceData,
        current_confidence: float,
        field_confidence: dict[str, float],
        warnings: list[str],
        company_match: dict[str, object] | None = None,
        document_type: str = "",
        optional_low_fields: set[str] | None = None,
    ) -> float:
        return refine_document_confidence(
            invoice=invoice,
            current_confidence=current_confidence,
            field_confidence=field_confidence,
            warnings=warnings,
            company_match=company_match,
            document_type=document_type,
            optional_low_fields=optional_low_fields,
        )

    def score_field_confidence(self, *args, **kwargs) -> float:
        return score_field_confidence(*args, **kwargs)

    def score_line_field_confidence(
        self,
        final: InvoiceData,
        heuristic: InvoiceData,
        bundle_candidate: InvoiceData | None,
        ai_candidate: InvoiceData | None,
        evidence_items: list[Any] | None = None,
    ) -> float:
        return score_line_field_confidence(final, heuristic, bundle_candidate, ai_candidate, evidence_items)

    def values_match(self, left: Any, right: Any) -> bool:
        return values_match(left, right)

    def line_items_match(self, left: list[LineItem], right: list[LineItem]) -> bool:
        return line_items_match(left, right)

    def is_valid_iso_date(self, value: str) -> bool:
        return is_valid_iso_date(value)

    def infer_document_type(
        self,
        raw_text: str,
        invoice: InvoiceData,
        *,
        bundle: DocumentBundle | None = None,
    ) -> DocumentType:
        return infer_document_type(raw_text, invoice, bundle=bundle)

    def infer_tax_regime(
        self,
        raw_text: str,
        invoice: InvoiceData,
        *,
        bundle: DocumentBundle | None = None,
    ) -> str:
        return infer_tax_regime(raw_text, invoice, bundle=bundle)

    def extract_due_date(self, raw_text: str) -> str:
        return extract_due_date(raw_text)

    def extract_payment_method(self, raw_text: str) -> str:
        return extract_payment_method(raw_text)

    def extract_iban(self, raw_text: str) -> str:
        return extract_iban(raw_text)

    def build_extraction_coverage(self, normalized_document: NormalizedInvoiceDocument) -> ExtractionCoverage:
        return build_extraction_coverage(normalized_document)

    def is_empty_value(self, value: Any) -> bool:
        return is_empty_value(value)


document_result_builder = DocumentResultBuilder()
