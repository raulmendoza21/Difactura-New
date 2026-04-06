from __future__ import annotations

from typing import Any

from app.models.document_bundle import DocumentBundle
from app.models.invoice_model import InvoiceData
from app.services.text_resolution.company_matching import company_matching_service
from app.services.text_resolution.document_family import document_family_service
from app.services.text_resolution.family_corrections_parts.company_sale import (
    apply_company_sale_corrections,
)
from app.services.text_resolution.family_corrections_parts.rectificative import (
    apply_rectificative_corrections,
    extract_rectificative_data,
)
from app.services.text_resolution.family_corrections_parts.shipping_billing import (
    apply_shipping_billing_purchase_corrections,
)
from app.services.text_resolution.family_corrections_parts.ticket import (
    apply_ticket_corrections,
)
from app.services.text_resolution.family_corrections_parts.withholding_purchase import (
    apply_withholding_purchase_corrections,
)
from app.services.text_resolution.party_resolution import party_resolution_service


class FamilyCorrectionService:
    def apply_family_corrections(
        self,
        normalized: InvoiceData,
        fallback: InvoiceData,
        *,
        raw_text: str,
        company_context: dict[str, str] | None = None,
    ) -> list[str]:
        warnings: list[str] = []
        company = company_matching_service.normalize_company_context(company_context)
        family, _ = document_family_service.detect(
            raw_text=raw_text,
            invoice=normalized,
            bundle=DocumentBundle(raw_text=raw_text),
            company_context=company,
        )

        warnings.extend(party_resolution_service.align_with_company_context(normalized, fallback, company))

        if family == "company_sale":
            warnings.extend(
                apply_company_sale_corrections(
                    normalized=normalized,
                    fallback=fallback,
                    company=company,
                    raw_text=raw_text,
                )
            )
        elif family == "shipping_billing_purchase":
            warnings.extend(
                apply_shipping_billing_purchase_corrections(
                    normalized=normalized,
                    fallback=fallback,
                    company=company,
                    raw_text=raw_text,
                )
            )
        elif family == "withholding_purchase":
            warnings.extend(
                apply_withholding_purchase_corrections(
                    normalized=normalized,
                    fallback=fallback,
                    company=company,
                    raw_text=raw_text,
                )
            )
        elif family == "rectificativa":
            warnings.extend(
                apply_rectificative_corrections(
                    normalized=normalized,
                    raw_text=raw_text,
                    company=company,
                )
            )
        elif family in {"ticket", "factura_simplificada"}:
            warnings.extend(
                apply_ticket_corrections(
                    normalized=normalized,
                    fallback=fallback,
                    raw_text=raw_text,
                )
            )

        return warnings

    def extract_rectificative_data(self, raw_text: str, company_context: dict[str, str]) -> dict[str, Any]:
        company = company_matching_service.normalize_company_context(company_context)
        return extract_rectificative_data(raw_text, company)


family_correction_service = FamilyCorrectionService()
