from __future__ import annotations

from app.models.invoice_model import InvoiceData
from app.services.text_resolution.amounts import amount_resolution_service
from app.services.text_resolution.family_corrections import family_correction_service
from app.services.text_resolution.normalization_parts import (
    apply_fallback_withholding,
    apply_retention_summary,
    apply_tax_label_correction,
    clear_withholding_if_needed,
    enrich_line_items_from_amounts,
    extract_invoice_number_from_raw_text,
    infer_base_from_lines,
    is_igic_rate,
    is_iva_rate,
    is_suspicious_invoice_number,
    looks_like_calendar_date,
    looks_like_invoice_code,
    maybe_correct_invoice_number,
    normalize_amounts_with_retention,
    normalize_line_items_with_fallback,
    reconcile_with_structured_summary,
)
from app.services.text_resolution.party_resolution import party_resolution_service


class InvoiceNormalizationService:
    def normalize_invoice_data(
        self,
        primary: InvoiceData,
        fallback: InvoiceData,
        *,
        raw_text: str = "",
        company_context: dict[str, str] | None = None,
    ) -> tuple[InvoiceData, list[str]]:
        normalized = primary.model_copy(deep=True)
        warnings: list[str] = []

        warnings.extend(maybe_correct_invoice_number(normalized, fallback, raw_text))
        warnings.extend(apply_tax_label_correction(normalized, fallback, raw_text))
        warnings.extend(
            party_resolution_service.normalize_parties(
                normalized,
                fallback,
                raw_text=raw_text,
                company_context=company_context,
            )
        )
        warnings.extend(normalize_line_items_with_fallback(normalized, fallback))
        warnings.extend(infer_base_from_lines(normalized))

        retention_summary = amount_resolution_service.extract_retention_summary(raw_text)
        warnings.extend(apply_retention_summary(normalized, retention_summary))
        warnings.extend(apply_fallback_withholding(normalized, fallback))
        warnings.extend(normalize_amounts_with_retention(normalized, raw_text, retention_summary))
        warnings.extend(enrich_line_items_from_amounts(normalized))
        warnings.extend(reconcile_with_structured_summary(normalized, fallback, raw_text))

        warnings.extend(
            family_correction_service.apply_family_corrections(
                normalized,
                fallback,
                raw_text=raw_text,
                company_context=company_context,
            )
        )
        warnings.extend(clear_withholding_if_needed(normalized, raw_text))
        return normalized, warnings

    def extract_invoice_number_from_raw_text(self, raw_text: str) -> str:
        return extract_invoice_number_from_raw_text(raw_text)

    def looks_like_invoice_code(self, value: str) -> bool:
        return looks_like_invoice_code(value)

    def looks_like_calendar_date(self, value: str) -> bool:
        return looks_like_calendar_date(value)

    def is_suspicious_invoice_number(self, value: str) -> bool:
        return is_suspicious_invoice_number(value)

    def is_igic_rate(self, value: float) -> bool:
        return is_igic_rate(value)

    def is_iva_rate(self, value: float) -> bool:
        return is_iva_rate(value)


invoice_normalization_service = InvoiceNormalizationService()
