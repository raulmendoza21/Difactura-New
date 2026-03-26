from __future__ import annotations

import re
from typing import Any

from app.models.document_bundle import BoundingBox, DocumentBundle, DocumentSpan
from app.models.extraction_result import DecisionFlag, FieldEvidence, ProcessingTraceItem
from app.models.invoice_model import InvoiceData
from app.utils.text_processing import parse_amount


class EvidenceBuilder:
    """Build field evidence, review flags and processing trace for extraction results."""

    def build_field_evidence(
        self,
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
            if not self._is_empty_value(final_value):
                span = self._locate_span(bundle, final_value, response_field)
                items.append(
                    self._build_item(
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
                if self._is_empty_value(candidate_value):
                    continue
                if not self._values_match(final_value, candidate_value):
                    continue
                span = self._locate_span(bundle, candidate_value, response_field)
                items.append(
                    self._build_item(
                        field=response_field,
                        value=candidate_value,
                        source=source_name,
                        extractor="field_candidate",
                        score=self._source_score(source_name),
                        span=span,
                    )
                )

            evidence[response_field] = self._deduplicate_items(items)

        line_items: list[FieldEvidence] = []
        for index, line in enumerate(final.lineas or []):
            if not line.descripcion:
                continue
            span = self._locate_span(bundle, line.descripcion, "lineas")
            line_items.append(
                self._build_item(
                    field="lineas",
                    value=line.descripcion,
                    source="resolved",
                    extractor=f"line_item:{index + 1}",
                    score=0.85 if span else 0.55,
                    span=span,
                )
            )
        evidence["lineas"] = self._deduplicate_items(line_items)
        return evidence

    def build_decision_flags(
        self,
        *,
        invoice: InvoiceData,
        field_confidence: dict[str, float],
        warnings: list[str],
        company_match: dict[str, Any] | None = None,
    ) -> list[DecisionFlag]:
        flags: list[DecisionFlag] = []
        company_match = company_match or {}

        critical_fields = {
            "numero_factura": "Numero de factura",
            "fecha": "Fecha",
            "proveedor": "Emisor/contraparte",
            "cif_proveedor": "NIF/CIF emisor",
            "total": "Total",
        }
        for field_name, label in critical_fields.items():
            value = getattr(invoice, field_name, "")
            confidence = field_confidence.get(field_name, 0.0)
            if self._is_empty_value(value):
                flags.append(
                    DecisionFlag(
                        code=f"missing_{field_name}",
                        severity="warning",
                        message=f"Falta {label.lower()} en la extraccion.",
                        field=field_name,
                        requires_review=True,
                    )
                )
            elif confidence < 0.65:
                flags.append(
                    DecisionFlag(
                        code=f"low_confidence_{field_name}",
                        severity="warning",
                        message=f"{label} tiene una confianza tecnica baja.",
                        field=field_name,
                        requires_review=True,
                    )
                )

        if invoice.base_imponible and invoice.total:
            expected_total = round(invoice.base_imponible + invoice.iva - max(0, invoice.retencion or 0), 2)
            if abs(expected_total - invoice.total) > 0.05:
                flags.append(
                    DecisionFlag(
                        code="amounts_not_coherent",
                        severity="error",
                        message="Los importes finales no cuadran entre base, impuestos, retencion y total.",
                        field="total",
                        requires_review=True,
                    )
                )

        if company_match.get("issuer_matches_company") and company_match.get("recipient_matches_company"):
            flags.append(
                DecisionFlag(
                    code="company_match_ambiguous",
                    severity="warning",
                    message="La empresa asociada encaja tanto con emisor como con receptor. Conviene revisar las partes.",
                    field="proveedor",
                    requires_review=True,
                )
            )

        for warning in warnings:
            if warning.startswith("discrepancia_"):
                flags.append(
                    DecisionFlag(
                        code=warning,
                        severity="info",
                        message="Hubo conflicto entre distintas vias de extraccion y se resolvio por coherencia global.",
                        field=warning.replace("discrepancia_", ""),
                        requires_review=False,
                    )
                )

        deduped: list[DecisionFlag] = []
        seen: set[str] = set()
        for flag in flags:
            if flag.code in seen:
                continue
            seen.add(flag.code)
            deduped.append(flag)
        return deduped

    def build_processing_trace(
        self,
        *,
        bundle: DocumentBundle,
        input_kind: str,
        provider: str,
        method: str,
        used_ocr: bool,
        used_ai: bool,
        page_count: int,
    ) -> list[ProcessingTraceItem]:
        trace = [
            ProcessingTraceItem(
                stage="input_router",
                summary=f"Entrada clasificada como {input_kind or 'desconocida'} con {page_count} pagina(s).",
                engine="document_loader",
            ),
            ProcessingTraceItem(
                stage="text_geometry",
                summary=f"Bundle documental construido con {len(bundle.spans)} spans y {len(bundle.regions)} regiones.",
                engine="ocr/pdf",
            ),
            ProcessingTraceItem(
                stage="layout_analysis",
                summary="Se reconstruyo el orden de lectura y las regiones principales del documento.",
                engine="layout_analyzer",
            ),
            ProcessingTraceItem(
                stage="candidate_resolution",
                summary="Se compararon candidatos heuristicos, layout-aware y opcionalmente doc_ai para resolver el documento final.",
                engine="document_intelligence",
            ),
        ]
        if used_ocr:
            trace.append(
                ProcessingTraceItem(
                    stage="ocr",
                    summary="Se utilizo OCR con geometria para enriquecer la evidencia documental.",
                    engine="paddleocr+tesseract",
                )
            )
        if used_ai:
            trace.append(
                ProcessingTraceItem(
                    stage="doc_ai",
                    summary="Se consulto el proveedor Doc AI como fuente secundaria de estructuracion.",
                    engine=provider or method,
                )
            )
        return trace

    def _build_item(
        self,
        *,
        field: str,
        value: Any,
        source: str,
        extractor: str,
        score: float,
        span: DocumentSpan | None,
    ) -> FieldEvidence:
        return FieldEvidence(
            field=field,
            value=self._stringify_value(value),
            source=source,
            extractor=extractor,
            page=span.page if span else 0,
            bbox=span.bbox if span else BoundingBox(),
            score=round(score, 2),
            text=span.text if span else "",
        )

    def _locate_span(self, bundle: DocumentBundle, value: Any, field_name: str) -> DocumentSpan | None:
        normalized_value = self._normalize_text(self._stringify_value(value))
        if not normalized_value:
            return None

        for span in bundle.spans:
            if self._span_matches_value(span.text, value, field_name, normalized_value):
                return span
        return None

    def _span_matches_value(self, text: str, value: Any, field_name: str, normalized_value: str) -> bool:
        normalized_text = self._normalize_text(text)
        if not normalized_text:
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

        return normalized_value in normalized_text or normalized_text in normalized_value

    def _source_score(self, source_name: str) -> float:
        return {
            "heuristic": 0.72,
            "layout": 0.8,
            "doc_ai": 0.78,
        }.get(source_name, 0.65)

    def _deduplicate_items(self, items: list[FieldEvidence]) -> list[FieldEvidence]:
        deduped: list[FieldEvidence] = []
        seen: set[tuple[str, str, int, int]] = set()
        for item in items:
            key = (
                item.field,
                item.value,
                item.page,
                int(item.score * 100),
            )
            if key in seen:
                continue
            seen.add(key)
            deduped.append(item)
        return deduped

    def _normalize_text(self, value: str) -> str:
        return re.sub(r"[^A-Z0-9]", "", str(value or "").upper())

    def _values_match(self, left: Any, right: Any) -> bool:
        if self._is_empty_value(left) and self._is_empty_value(right):
            return True
        try:
            return abs(float(left) - float(right)) <= max(0.02, abs(float(left)) * 0.02, abs(float(right)) * 0.02)
        except (TypeError, ValueError):
            pass
        return self._normalize_text(self._stringify_value(left)) == self._normalize_text(self._stringify_value(right))

    def _is_empty_value(self, value: Any) -> bool:
        if value in ("", None, 0, 0.0):
            return True
        if isinstance(value, list) and not value:
            return True
        return False

    def _stringify_value(self, value: Any) -> str:
        if value is None:
            return ""
        if isinstance(value, float):
            return f"{value:.2f}".rstrip("0").rstrip(".")
        return str(value)


evidence_builder = EvidenceBuilder()
