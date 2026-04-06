from __future__ import annotations

from typing import Any

from app.config import settings
from app.models.document_bundle import DocumentBundle
from app.models.extraction_result import ExtractionCoverage
from app.models.invoice_model import InvoiceData
from app.services.document_semantic_resolver import document_semantic_resolver

DOC_AI_VISUAL_INPUT_KINDS = {"pdf_scanned", "pdf_photo", "image_photo", "image_scan", "ticket"}
DOC_AI_CORE_FIELDS = ("numero_factura", "fecha", "total")
DOC_AI_PROVIDER_FIELDS = ("proveedor", "cif_proveedor")
DOC_AI_STRONG_CONFIDENCE_FLOOR = 0.68


def resolve_input_profile(*, bundle: DocumentBundle, document: dict[str, Any]) -> dict[str, Any]:
    profile = bundle.input_profile.model_dump() if bundle.input_profile else {}
    if profile.get("input_kind") or profile.get("text_source") or profile.get("input_route"):
        return profile
    return dict(document.get("input_profile") or {})


def should_run_doc_ai_fallback(
    *,
    resolution: dict[str, Any],
    input_profile: dict[str, Any],
    company_context: dict[str, str] | None = None,
) -> bool:
    if not settings.doc_ai_enabled:
        return False
    if not settings.doc_ai_selective_enabled:
        return True

    input_kind = str(input_profile.get("input_kind", "") or "")
    if input_kind not in DOC_AI_VISUAL_INPUT_KINDS:
        return False

    data: InvoiceData = resolution["data"]
    coverage: ExtractionCoverage = resolution["coverage"]
    field_confidence: dict[str, float] = resolution["field_confidence"]
    decision_flags = resolution["decision_flags"]
    company_match = resolution["company_match"]
    normalized_document = resolution.get("normalized_document")
    document_type = ""
    if normalized_document is not None:
        document_type = str(getattr(getattr(normalized_document, "classification", None), "document_type", "") or "")

    if data.confianza < settings.doc_ai_fallback_confidence_threshold:
        return True

    if len(coverage.missing_required_fields) >= settings.doc_ai_fallback_missing_required_threshold:
        return True

    review_warnings = sum(
        1
        for flag in decision_flags
        if getattr(flag, "requires_review", False) and getattr(flag, "severity", "") in {"warning", "error"}
    )
    if review_warnings >= settings.doc_ai_fallback_warning_threshold and data.confianza < DOC_AI_STRONG_CONFIDENCE_FLOOR:
        return True

    if _has_critical_identity_gap(field_confidence):
        return True

    if _has_weak_provider_identity(field_confidence) and data.confianza < DOC_AI_STRONG_CONFIDENCE_FLOOR:
        return True

    if document_type in {"ticket", "factura_simplificada"} and data.confianza < 0.45:
        return True

    company = document_semantic_resolver.normalize_company_context(company_context)
    if (
        (company["name"] or company["tax_id"])
        and company_match.get("matched_role") in {"", "ambiguous"}
        and data.confianza < 0.5
        and _has_weak_provider_identity(field_confidence)
    ):
        return True

    return False


def _has_critical_identity_gap(field_confidence: dict[str, float]) -> bool:
    return any(field_confidence.get(field_name, 0.0) < 0.55 for field_name in DOC_AI_CORE_FIELDS)


def _has_weak_provider_identity(field_confidence: dict[str, float]) -> bool:
    return all(field_confidence.get(field_name, 0.0) < 0.7 for field_name in DOC_AI_PROVIDER_FIELDS)
