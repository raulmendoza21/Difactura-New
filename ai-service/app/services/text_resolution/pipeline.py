from __future__ import annotations

from app.models.document_bundle import DocumentBundle
from app.models.invoice_model import InvoiceData
from app.services.text_resolution.company_matching import company_matching_service
from app.services.text_resolution.document_family import document_family_service
from app.services.text_resolution.document_type import document_type_service
from app.services.text_resolution.models import DocumentSemanticResolution
from app.services.text_resolution.operation_kind import operation_kind_service
from app.services.text_resolution.tax_regime import tax_regime_service


class SemanticResolutionPipeline:
    def resolve(
        self,
        *,
        invoice: InvoiceData,
        raw_text: str,
        bundle: DocumentBundle,
        company_match: dict[str, object] | None = None,
        company_context: dict[str, str] | None = None,
    ) -> DocumentSemanticResolution:
        normalized_company = company_matching_service.normalize_company_context(company_context)
        resolved_company_match, match_trace = company_matching_service.build_company_match(
            invoice=invoice,
            company_context=normalized_company,
            preferred_match=company_match,
        )
        document_family, family_trace = document_family_service.detect(
            raw_text=raw_text,
            invoice=invoice,
            bundle=bundle,
            company_context=normalized_company,
        )
        document_type, type_trace = document_type_service.resolve(
            raw_text=raw_text,
            invoice=invoice,
            bundle=bundle,
        )
        operation_kind, operation_trace = operation_kind_service.resolve(
            invoice=invoice,
            raw_text=raw_text,
            document_type=document_type,
            document_family=document_family,
            company_match=resolved_company_match,
            company_context=normalized_company,
        )
        invoice_side, side_trace = operation_kind_service.resolve_invoice_side(
            operation_kind=operation_kind,
            company_match=resolved_company_match,
        )
        tax_regime, tax_trace = tax_regime_service.resolve(
            raw_text=raw_text,
            invoice=invoice,
            document_type=document_type,
        )

        return DocumentSemanticResolution(
            document_family=document_family,
            document_type=document_type,
            invoice_side=invoice_side,
            operation_kind=operation_kind,
            tax_regime=tax_regime,
            is_rectificative=document_type in {"factura_rectificativa", "abono"},
            is_simplified=document_type in {"factura_simplificada", "ticket"},
            counterparty_role=operation_kind_service.resolve_counterparty_role(operation_kind=operation_kind),
            company_match=resolved_company_match,
            decision_trace=match_trace + family_trace + type_trace + operation_trace + side_trace + tax_trace,
        )


semantic_resolution_pipeline = SemanticResolutionPipeline()
