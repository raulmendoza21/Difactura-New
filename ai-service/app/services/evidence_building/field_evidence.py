from __future__ import annotations

import re
from typing import Any

from app.models.document_bundle import BoundingBox, DocumentBundle, DocumentSpan
from app.models.extraction_result import FieldEvidence
from app.models.invoice_model import InvoiceData
from app.utils.text_processing import parse_amount

from .shared import deduplicate_items, is_empty_value, normalize_text, source_score, stringify_value, value_kind_for_source, values_match


def build_field_evidence(
    *,
    bundle: DocumentBundle,
    final: InvoiceData,
    heuristic: InvoiceData,
    bundle_candidate: InvoiceData | None,
    ai_candidate: InvoiceData | None,
) -> dict[str, list[FieldEvidence]]:
    sources = {
        "heuristic": heuristic,
        "layout": bundle_candidate,
        "doc_ai": ai_candidate,
    }
    field_map = {
        "numero_factura": "numero_factura",
        "fecha": "fecha",
        "proveedor": "proveedor",
        "cif_proveedor": "cif_proveedor",
        "cliente": "cliente",
        "cif_cliente": "cif_cliente",
        "base_imponible": "base_imponible",
        "iva_porcentaje": "iva_porcentaje",
        "iva": "iva",
        "retencion_porcentaje": "retencion_porcentaje",
        "retencion": "retencion",
        "total": "total",
    }
    evidence: dict[str, list[FieldEvidence]] = {}

    for response_field, invoice_field in field_map.items():
        final_value = getattr(final, invoice_field)
        items: list[FieldEvidence] = []
        if not is_empty_value(final_value):
            span = locate_span(bundle, final_value, response_field)
            items.append(
                build_item(
                    field=response_field,
                    value=final_value,
                    source="resolved",
                    extractor="global_resolver",
                    score=0.92,
                    span=span,
                )
            )

        for source_name, source_invoice in sources.items():
            if source_invoice is None:
                continue
            candidate_value = getattr(source_invoice, invoice_field, None)
            if is_empty_value(candidate_value):
                continue
            if not values_match(final_value, candidate_value):
                continue
            span = locate_span(bundle, candidate_value, response_field)
            items.append(
                build_item(
                    field=response_field,
                    value=candidate_value,
                    source=source_name,
                    extractor="field_candidate",
                    score=source_score(source_name),
                    span=span,
                )
            )

        evidence[response_field] = deduplicate_items(items)

    line_items: list[FieldEvidence] = []
    for index, line in enumerate(final.lineas or []):
        if not line.descripcion:
            continue
        span = locate_span(bundle, line.descripcion, "lineas")
        line_items.append(
            build_item(
                field="lineas",
                value=line.descripcion,
                source="resolved",
                extractor=f"line_item:{index + 1}",
                score=0.85 if span else 0.55,
                span=span,
            )
        )
    evidence["lineas"] = deduplicate_items(line_items)
    return evidence


def build_item(
    *,
    field: str,
    value: Any,
    source: str,
    extractor: str,
    score: float,
    span: DocumentSpan | None,
) -> FieldEvidence:
    value_kind = value_kind_for_source(source=source, extractor=extractor)
    return FieldEvidence(
        field=field,
        value=stringify_value(value),
        value_kind=value_kind,
        source=source,
        extractor=extractor,
        is_final=value_kind == "resolved",
        requires_review=value_kind == "inferred",
        page=span.page if span else 0,
        bbox=span.bbox if span else BoundingBox(),
        score=round(score, 2),
        text=span.text if span else "",
    )


def locate_span(bundle: DocumentBundle, value: Any, field_name: str) -> DocumentSpan | None:
    normalized_value = normalize_text(stringify_value(value))
    if not normalized_value:
        return None

    for span in bundle.spans:
        if span_matches_value(span.text, value, field_name, normalized_value):
            return span
    return None


def span_matches_value(text: str, value: Any, field_name: str, normalized_value: str) -> bool:
    normalized_span_text = normalize_text(text)
    if not normalized_span_text:
        return False

    if field_name in {"base_imponible", "iva_porcentaje", "iva", "retencion_porcentaje", "retencion", "total"}:
        try:
            numeric_value = float(value)
        except (TypeError, ValueError):
            return False
        for candidate in re.findall(r"-?\d[\d.,]*", text):
            try:
                if abs(parse_amount(candidate) - numeric_value) <= 0.02:
                    return True
            except Exception:
                continue
        return False

    return normalized_value in normalized_span_text or normalized_span_text in normalized_value
