from __future__ import annotations

from app.models.invoice_model import InvoiceData

from .party_resolution_parts.company_alignment import align_with_company_context
from .party_resolution_parts.header import extract_provider_from_header, extract_ranked_provider_from_header
from .party_resolution_parts.normalization import normalize_parties
from .party_resolution_parts.raw_text import extract_footer_legal_party, extract_parties_from_raw_text
from .party_resolution_parts.shared import (
    clean_tax_id,
    is_empty_value,
    is_generic_party_candidate,
    is_valid_tax_id,
    looks_like_address_or_contact_line,
    matches_company_context,
    normalize_party_name,
    normalize_tax_id_value,
    party_candidate_score,
    repair_tax_id_candidate,
    should_promote_party_candidate,
    values_match,
)


class PartyResolutionService:
    """Facade over modular party-resolution helpers."""

    def normalize_parties(
        self,
        data: InvoiceData,
        fallback: InvoiceData,
        *,
        raw_text: str,
        company_context: dict[str, str] | None = None,
    ) -> list[str]:
        return normalize_parties(data, fallback, raw_text=raw_text, company_context=company_context)

    def align_with_company_context(
        self,
        normalized: InvoiceData,
        fallback: InvoiceData,
        company_context: dict[str, str] | None,
    ) -> list[str]:
        return align_with_company_context(normalized, fallback, company_context)

    def extract_parties_from_raw_text(self, raw_text: str, company_context: dict[str, str] | None = None) -> dict[str, str]:
        return extract_parties_from_raw_text(raw_text, company_context=company_context)

    def extract_footer_legal_party(self, raw_text: str, company_context: dict[str, str] | None = None) -> dict[str, str]:
        return extract_footer_legal_party(raw_text, company_context=company_context)

    def extract_ranked_provider_from_header(self, raw_text: str, company_context: dict[str, str] | None) -> str:
        return extract_ranked_provider_from_header(raw_text, company_context)

    def extract_provider_from_header(self, raw_text: str, company_context: dict[str, str] | None) -> str:
        return extract_provider_from_header(raw_text, company_context)

    def should_promote_party_candidate(
        self,
        *,
        current_name: str,
        current_tax_id: str,
        candidate_name: str,
        candidate_tax_id: str,
    ) -> bool:
        return should_promote_party_candidate(
            current_name=current_name,
            current_tax_id=current_tax_id,
            candidate_name=candidate_name,
            candidate_tax_id=candidate_tax_id,
        )

    def party_candidate_score(self, name: str, tax_id: str) -> int:
        return party_candidate_score(name, tax_id)

    def is_generic_party_candidate(self, value: str) -> bool:
        return is_generic_party_candidate(value)

    def looks_like_address_or_contact_line(self, value: str) -> bool:
        return looks_like_address_or_contact_line(value)

    def normalize_party_name(self, value: str) -> str:
        return normalize_party_name(value)

    def normalize_tax_id_value(self, primary: str, fallback: str, *, role: str) -> tuple[str, list[str]]:
        return normalize_tax_id_value(primary, fallback, role=role)

    def matches_company_context(self, name: str, tax_id: str, company_context: dict[str, str] | None) -> bool:
        return matches_company_context(name, tax_id, company_context)

    def is_valid_tax_id(self, value: str) -> bool:
        return is_valid_tax_id(value)

    def clean_tax_id(self, value: str) -> str:
        return clean_tax_id(value)

    def repair_tax_id_candidate(self, value: str) -> tuple[str, bool]:
        return repair_tax_id_candidate(value)

    def values_match(self, left: object, right: object) -> bool:
        return values_match(left, right)

    def _is_empty_value(self, value: object) -> bool:
        return is_empty_value(value)


party_resolution_service = PartyResolutionService()
