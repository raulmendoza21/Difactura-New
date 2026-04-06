from __future__ import annotations

from app.models.invoice_model import InvoiceData
from app.services.text_resolution.amount_resolution_parts.normalization import normalize_amounts
from app.services.text_resolution.amount_resolution_parts.retention_summary import extract_retention_summary
from app.services.text_resolution.amount_resolution_parts.validators import (
    amounts_are_coherent,
    has_structured_tax_summary,
)
from app.services.text_resolution.amount_resolution_parts.withholding import (
    has_withholding_hint,
    should_clear_withholding,
)


class AmountResolutionService:
    def normalize_amounts(self, data: InvoiceData) -> list[str]:
        return normalize_amounts(data)

    def has_withholding_hint(self, raw_text: str) -> bool:
        return has_withholding_hint(raw_text)

    def should_clear_withholding(self, invoice: InvoiceData, raw_text: str) -> bool:
        return should_clear_withholding(invoice, raw_text)

    def extract_retention_summary(self, raw_text: str) -> dict[str, float]:
        return extract_retention_summary(raw_text)

    def has_structured_tax_summary(self, raw_text: str) -> bool:
        return has_structured_tax_summary(raw_text)

    def amounts_are_coherent(self, invoice: InvoiceData) -> bool:
        return amounts_are_coherent(invoice)


amount_resolution_service = AmountResolutionService()
