from __future__ import annotations

from typing import Any

from app.models.document_bundle import BundleCandidate, DocumentBundle
from app.models.invoice_model import InvoiceData
from app.services.text_resolution.region_hint_rescue_parts import (
    build_bundle_candidate_groups,
    format_exception,
    maybe_apply,
    normalize_hint_lookup,
    region_hint_priority,
    should_run,
    stringify_candidate_value,
)


class RegionHintRescueService:
    def maybe_apply(
        self,
        *,
        file_path: str,
        input_profile: dict[str, Any],
        company_context: dict[str, str] | None,
        bundle: DocumentBundle,
        raw_text: str,
        base_candidate: InvoiceData,
    ) -> tuple[DocumentBundle, str, bool]:
        return maybe_apply(
            file_path=file_path,
            input_profile=input_profile,
            company_context=company_context,
            bundle=bundle,
            raw_text=raw_text,
            base_candidate=base_candidate,
        )

    def build_bundle_candidate_groups(
        self,
        *,
        bundle: DocumentBundle,
        bundle_sources: dict[str, InvoiceData] | None,
    ) -> dict[str, list[BundleCandidate]]:
        return build_bundle_candidate_groups(bundle=bundle, bundle_sources=bundle_sources)

    def should_run(
        self,
        *,
        base_candidate: InvoiceData,
        input_profile: dict[str, Any],
        company_context: dict[str, str] | None,
    ) -> bool:
        return should_run(
            base_candidate=base_candidate,
            input_profile=input_profile,
            company_context=company_context,
        )

    def stringify_candidate_value(self, value: Any) -> str:
        return stringify_candidate_value(value)

    def normalize_hint_lookup(self, value: str) -> str:
        return normalize_hint_lookup(value)

    def region_hint_priority(self, region_type: str) -> int:
        return region_hint_priority(region_type)

    def _format_exception(self, exc: Exception) -> str:
        return format_exception(exc)


region_hint_rescue_service = RegionHintRescueService()
