from __future__ import annotations

from app.models.document_bundle import DocumentBundle
from app.models.document_contract import DocumentType, InvoiceSide, OperationKind, TaxRegime
from app.models.invoice_model import InvoiceData
from app.services.text_resolution.company_matching import company_matching_service
from app.services.text_resolution.document_family import document_family_service
from app.services.text_resolution.document_type import document_type_service
from app.services.text_resolution.models import DocumentSemanticResolution
from app.services.text_resolution.operation_kind import operation_kind_service
from app.services.text_resolution.pipeline import semantic_resolution_pipeline
from app.services.text_resolution.tax_regime import tax_regime_service


class DocumentSemanticResolver:
    def resolve(
        self,
        *,
        invoice: InvoiceData,
        raw_text: str,
        bundle: DocumentBundle,
        company_match: dict[str, object] | None = None,
        company_context: dict[str, str] | None = None,
    ) -> DocumentSemanticResolution:
        return semantic_resolution_pipeline.resolve(
            invoice=invoice,
            raw_text=raw_text,
            bundle=bundle,
            company_match=company_match,
            company_context=company_context,
        )

    def detect_document_family(
        self,
        *,
        raw_text: str,
        company_context: dict[str, str] | None = None,
        invoice: InvoiceData | None = None,
        bundle: DocumentBundle | None = None,
    ) -> str:
        family, _ = document_family_service.detect(
            raw_text=raw_text,
            invoice=invoice or InvoiceData(),
            bundle=bundle or DocumentBundle(raw_text=raw_text),
            company_context=company_context,
        )
        return family

    def build_company_match(
        self,
        *,
        invoice: InvoiceData,
        company_context: dict[str, str] | None = None,
    ) -> dict[str, object]:
        company_match, _ = company_matching_service.build_company_match(
            invoice=invoice,
            company_context=company_context,
        )
        return company_match

    def resolve_document_type(self, *, raw_text: str, invoice: InvoiceData, bundle: DocumentBundle) -> DocumentType:
        document_type, _ = document_type_service.resolve(
            raw_text=raw_text,
            invoice=invoice,
            bundle=bundle,
        )
        return document_type

    def resolve_operation_kind(
        self,
        *,
        invoice: InvoiceData,
        raw_text: str,
        document_type: DocumentType,
        document_family: str,
        company_match: dict[str, object],
        company_context: dict[str, str],
    ) -> OperationKind:
        operation_kind, _ = operation_kind_service.resolve(
            invoice=invoice,
            raw_text=raw_text,
            document_type=document_type,
            document_family=document_family,
            company_match=company_match,
            company_context=company_context,
        )
        return operation_kind

    def resolve_invoice_side(self, *, operation_kind: OperationKind, company_match: dict[str, object]) -> InvoiceSide:
        invoice_side, _ = operation_kind_service.resolve_invoice_side(
            operation_kind=operation_kind,
            company_match=company_match,
        )
        return invoice_side

    def resolve_tax_regime(self, *, raw_text: str, invoice: InvoiceData, document_type: DocumentType) -> TaxRegime:
        tax_regime, _ = tax_regime_service.resolve(
            raw_text=raw_text,
            invoice=invoice,
            document_type=document_type,
        )
        return tax_regime

    def normalize_company_context(self, company_context: dict[str, str] | None) -> dict[str, str]:
        return company_matching_service.normalize_company_context(company_context)

    def matches_company_context(self, name: str, tax_id: str, company_context: dict[str, str]) -> bool:
        return company_matching_service.matches_company_context(name, tax_id, company_context)


document_semantic_resolver = DocumentSemanticResolver()
