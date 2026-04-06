from __future__ import annotations

from typing import Any

from app.models.document_bundle import DocumentBundle
from app.models.invoice_model import InvoiceData
from app.services.confidence_scorer import confidence_scorer
from app.services.document_semantic_resolver import document_semantic_resolver
from app.services.evidence_builder import evidence_builder

from .confidence import build_field_confidence, refine_document_confidence
from .document_metadata import build_extraction_coverage, build_extraction_document
from .shared import line_items_match, values_match


def build_resolution_state(
    *,
    data: InvoiceData,
    raw_text: str,
    filename: str,
    mime_type: str,
    pages: int,
    input_profile: dict[str, Any],
    bundle: DocumentBundle,
    fallback_data: InvoiceData,
    bundle_candidate: InvoiceData | None,
    ai_candidate: InvoiceData | None,
    provider: str,
    method: str,
    warnings: list[str],
    company_context: dict[str, str] | None = None,
) -> dict[str, Any]:
    warnings = _dedupe_warnings(warnings)
    company_match = dict(
        document_semantic_resolver.build_company_match(
            invoice=data,
            company_context=company_context,
        )
    )
    semantics = document_semantic_resolver.resolve(
        invoice=data,
        raw_text=raw_text,
        bundle=bundle,
        company_match=company_match,
        company_context=company_context,
    )
    if semantics.operation_kind in {"compra", "venta"}:
        data.tipo_factura = semantics.operation_kind
    company_match = semantics.company_match

    evidence = evidence_builder.build_field_evidence(
        bundle=bundle,
        final=data,
        heuristic=fallback_data,
        bundle_candidate=bundle_candidate,
        ai_candidate=ai_candidate,
    )
    field_confidence = build_field_confidence(
        final=data,
        heuristic=fallback_data,
        bundle_candidate=bundle_candidate,
        ai_candidate=ai_candidate,
        evidence=evidence,
    )
    normalized_document = build_extraction_document(
        invoice=data,
        raw_text=raw_text,
        filename=filename,
        mime_type=mime_type,
        pages=pages,
        input_profile=input_profile,
        bundle=bundle,
        provider=provider,
        method=method,
        warnings=warnings,
        company_context=company_context,
        company_match=company_match,
        semantics=semantics,
    )
    coverage = build_extraction_coverage(normalized_document)
    decision_flags = evidence_builder.build_decision_flags(
        invoice=data,
        field_confidence=field_confidence,
        warnings=warnings,
        company_match=company_match,
    )
    document_type = normalized_document.classification.document_type or ""
    optional_low_fields = _optional_low_confidence_fields(data, document_type)
    base_confidence = refine_document_confidence(
        invoice=data,
        current_confidence=confidence_scorer.score(data),
        field_confidence=field_confidence,
        warnings=warnings,
        company_match=company_match,
        document_type=document_type,
        optional_low_fields=optional_low_fields,
    )
    adjusted_confidence = confidence_scorer.score_with_context(
        data,
        field_confidence=field_confidence,
        evidence=evidence,
        decision_flags=decision_flags,
        coverage_ratio=coverage.completeness_ratio,
        optional_low_fields=optional_low_fields,
        document_type=document_type,
    )
    data.confianza = round(min(base_confidence, adjusted_confidence), 2)
    normalized_document.document_meta.extraction_confidence = data.confianza
    return {
        "data": data,
        "company_match": company_match,
        "semantics": semantics,
        "evidence": evidence,
        "field_confidence": field_confidence,
        "normalized_document": normalized_document,
        "coverage": coverage,
        "decision_flags": decision_flags,
    }


def _optional_low_confidence_fields(invoice: InvoiceData, document_type: str) -> set[str]:
    optional_fields: set[str] = set()

    if document_type not in {"ticket", "factura_simplificada"}:
        return optional_fields

    if not invoice.cliente:
        optional_fields.add("cliente")
    if not invoice.cif_cliente:
        optional_fields.add("cif_cliente")
    if not invoice.base_imponible:
        optional_fields.add("base_imponible")
    if not invoice.iva_porcentaje:
        optional_fields.add("iva_porcentaje")
    if not invoice.iva:
        optional_fields.add("iva")

    return optional_fields


def _dedupe_warnings(warnings: list[str]) -> list[str]:
    seen: set[str] = set()
    deduped: list[str] = []
    for warning in warnings:
        normalized = str(warning or "").strip()
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        deduped.append(normalized)
    return deduped


def compare_source_candidates(ai_candidate: InvoiceData, heuristic: InvoiceData) -> list[str]:
    warnings: list[str] = []

    key_fields = (
        ("numero_factura", "discrepancia_numero_factura"),
        ("fecha", "discrepancia_fecha"),
        ("proveedor", "discrepancia_proveedor"),
        ("cif_proveedor", "discrepancia_cif_proveedor"),
        ("cliente", "discrepancia_cliente"),
        ("cif_cliente", "discrepancia_cif_cliente"),
    )

    for field_name, warning_name in key_fields:
        ai_value = getattr(ai_candidate, field_name)
        heuristic_value = getattr(heuristic, field_name)
        if not ai_value or not heuristic_value:
            continue
        if not values_match(ai_value, heuristic_value):
            warnings.append(warning_name)

    numeric_fields = (
        ("base_imponible", "discrepancia_base_imponible"),
        ("iva_porcentaje", "discrepancia_iva_porcentaje"),
        ("iva", "discrepancia_iva_importe"),
        ("total", "discrepancia_total"),
    )
    for field_name, warning_name in numeric_fields:
        ai_value = float(getattr(ai_candidate, field_name) or 0)
        heuristic_value = float(getattr(heuristic, field_name) or 0)
        if ai_value <= 0 or heuristic_value <= 0:
            continue
        if not values_match(ai_value, heuristic_value):
            warnings.append(warning_name)

    if ai_candidate.lineas and heuristic.lineas and not line_items_match(ai_candidate.lineas, heuristic.lineas):
        warnings.append("discrepancia_lineas")

    return warnings
