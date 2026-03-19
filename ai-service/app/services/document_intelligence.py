"""Document-to-JSON extraction with optional external AI provider."""

from __future__ import annotations

import json
import logging
import re
from typing import Any

from app.config import settings
from app.models.document_contract import (
    DocumentType,
    NormalizedInvoiceDocument,
    TaxRegime,
    build_normalized_document_from_invoice_data,
)
from app.models.extraction_result import ExtractionCoverage
from app.models.invoice_model import InvoiceData, LineItem
from app.services.confidence_scorer import confidence_scorer
from app.services.document_loader import document_loader
from app.services.field_extractor import field_extractor
from app.services.invoice_classifier import invoice_classifier

logger = logging.getLogger(__name__)

PRIORITY_CONTRACT_FIELDS = (
    "classification.document_type",
    "classification.invoice_side",
    "identity.issue_date",
    "identity.invoice_number",
    "issuer.name",
    "issuer.tax_id",
    "totals.subtotal",
    "totals.total",
    "tax_breakdown",
    "line_items",
)


PROMPT = """Extrae los datos de la factura y devuelve solo JSON valido.
No escribas explicaciones ni markdown.
Si un campo no aparece, usa cadena vacia o 0.
Schema:
{
  "numero_factura": "string",
  "fecha": "YYYY-MM-DD",
  "proveedor": "string",
  "cif_proveedor": "string",
  "cliente": "string",
  "cif_cliente": "string",
  "base_imponible": 0,
  "iva_porcentaje": 0,
  "iva": 0,
  "total": 0,
  "lineas": [
    {
      "descripcion": "string",
      "cantidad": 0,
      "precio_unitario": 0,
      "importe": 0
    }
  ]
}
Prioriza exactitud sobre completitud.
"""


class DocumentIntelligenceService:
    """Hybrid extraction using an AI provider with heuristic fallback."""

    async def extract(self, file_path: str, filename: str = "", mime_type: str = "") -> dict:
        provider_name = settings.doc_ai_provider if settings.doc_ai_enabled else "heuristic"
        uses_images = provider_name == "openai_compatible"
        document = document_loader.load(file_path, mime_type, include_page_images=uses_images)
        raw_text = document["raw_text"]
        pages = document["pages"]
        fallback_data = self._heuristic_extract(raw_text)

        warnings: list[str] = []
        method = document["method"]
        provider = "heuristic"
        data = fallback_data

        if settings.doc_ai_enabled:
            try:
                ai_data, provider = await self._extract_with_provider(
                    provider_name=provider_name,
                    raw_text=raw_text,
                    page_images=document["page_images"][: settings.doc_ai_max_pages],
                    filename=filename,
                )
                ai_data = self._merge_with_fallback(ai_data, fallback_data)
                ai_data, normalization_warnings = self._normalize_invoice_data(ai_data, fallback_data)
                warnings.extend(normalization_warnings)
                ai_data.tipo_factura = invoice_classifier.classify(
                    raw_text,
                    ai_data.proveedor,
                    ai_data.cliente,
                )
                ai_data.confianza = confidence_scorer.score(ai_data)
                data = ai_data
                method = "doc_ai"
            except Exception as exc:
                formatted_exc = self._format_exception(exc)
                logger.warning("Doc AI extraction failed, falling back to heuristics: %s", formatted_exc)
                warnings.append(f"doc_ai_fallback: {formatted_exc}")

        normalized_document = self._build_extraction_document(
            invoice=data,
            raw_text=raw_text,
            filename=filename,
            mime_type=mime_type,
            provider=provider,
            method=method,
            warnings=warnings,
        )
        coverage = self._build_extraction_coverage(normalized_document)

        return {
            "success": True,
            "data": data,
            "normalized_document": normalized_document,
            "coverage": coverage,
            "raw_text": raw_text,
            "method": method,
            "provider": provider,
            "pages": pages,
            "warnings": warnings,
        }

    async def _extract_with_provider(
        self,
        provider_name: str,
        raw_text: str,
        page_images: list[str],
        filename: str,
    ) -> tuple[InvoiceData, str]:
        if provider_name == "openai_compatible":
            return (
                await self._extract_with_openai_compatible(
                    raw_text=raw_text,
                    page_images=page_images,
                    filename=filename,
                ),
                "openai_compatible",
            )
        if provider_name == "ollama":
            return (
                await self._extract_with_ollama(
                    raw_text=raw_text,
                    filename=filename,
                ),
                "ollama",
            )

        raise RuntimeError(f"Proveedor Doc AI no soportado: {provider_name}")

    def _normalize_invoice_data(
        self,
        primary: InvoiceData,
        fallback: InvoiceData,
    ) -> tuple[InvoiceData, list[str]]:
        normalized = primary.model_copy(deep=True)
        warnings: list[str] = []

        normalized.lineas, line_warnings = self._normalize_line_items(normalized.lineas)
        warnings.extend(line_warnings)

        if normalized.base_imponible <= 0 and normalized.lineas:
            line_sum = round(sum(line.importe for line in normalized.lineas if line.importe > 0), 2)
            if line_sum > 0:
                normalized.base_imponible = line_sum
                warnings.append("base_inferida_desde_lineas")

        if not self._is_valid_tax_id(normalized.cif_proveedor) and self._is_valid_tax_id(fallback.cif_proveedor):
            normalized.cif_proveedor = fallback.cif_proveedor
            warnings.append("cif_proveedor_corregido_con_fallback")

        if not self._is_valid_tax_id(normalized.cif_cliente) and self._is_valid_tax_id(fallback.cif_cliente):
            normalized.cif_cliente = fallback.cif_cliente
            warnings.append("cif_cliente_corregido_con_fallback")

        amount_warnings = self._normalize_amounts(normalized)
        warnings.extend(amount_warnings)

        return normalized, warnings

    def _heuristic_extract(self, raw_text: str) -> InvoiceData:
        data = field_extractor.extract(raw_text)
        data.tipo_factura = invoice_classifier.classify(raw_text, data.proveedor, data.cliente)
        data.confianza = confidence_scorer.score(data)
        return data

    async def _extract_with_openai_compatible(
        self,
        raw_text: str,
        page_images: list[str],
        filename: str,
    ) -> InvoiceData:
        if not settings.doc_ai_base_url or not settings.doc_ai_model:
            raise RuntimeError("DOC_AI_BASE_URL y DOC_AI_MODEL son obligatorios")

        content: list[dict[str, Any]] = [
            {
                "type": "text",
                "text": (
                    f"{PROMPT}\n"
                    f"Nombre de archivo: {filename or 'invoice'}\n"
                    f"Texto OCR/extraido:\n{raw_text[:12000]}"
                ),
            }
        ]
        for page_image in page_images:
            content.append(
                {
                    "type": "image_url",
                    "image_url": {"url": page_image},
                }
            )

        payload = {
            "model": settings.doc_ai_model,
            "temperature": 0,
            "response_format": {"type": "json_object"},
            "messages": [
                {
                    "role": "system",
                    "content": "Eres un extractor preciso de facturas. Responde solo JSON.",
                },
                {
                    "role": "user",
                    "content": content,
                },
            ],
        }

        headers = {}
        if settings.doc_ai_api_key:
            headers["Authorization"] = f"Bearer {settings.doc_ai_api_key}"

        import httpx

        async with httpx.AsyncClient(timeout=settings.doc_ai_timeout_seconds) as client:
            response = await client.post(
                f"{settings.doc_ai_base_url.rstrip('/')}/chat/completions",
                headers=headers,
                json=payload,
            )
            response.raise_for_status()

        response_json = response.json()
        message_content = response_json["choices"][0]["message"]["content"]
        parsed = self._parse_json_payload(message_content)
        return self._invoice_from_payload(parsed)

    async def _extract_with_ollama(
        self,
        raw_text: str,
        filename: str,
    ) -> InvoiceData:
        if not settings.doc_ai_base_url or not settings.doc_ai_model:
            raise RuntimeError("DOC_AI_BASE_URL y DOC_AI_MODEL son obligatorios")
        if not raw_text.strip():
            raise RuntimeError("No hay texto OCR para estructurar con Ollama")

        payload = {
            "model": settings.doc_ai_model,
            "stream": False,
            "format": self._response_schema(),
            "keep_alive": settings.doc_ai_keep_alive,
            "options": {
                "temperature": 0,
            },
            "messages": [
                {
                    "role": "system",
                    "content": "Eres un extractor preciso de facturas. Responde solo JSON valido.",
                },
                {
                    "role": "user",
                    "content": self._build_text_prompt(raw_text=raw_text, filename=filename),
                },
            ],
        }

        import httpx

        async with httpx.AsyncClient(timeout=settings.doc_ai_timeout_seconds) as client:
            response = await client.post(
                f"{settings.doc_ai_base_url.rstrip('/')}/api/chat",
                json=payload,
            )
            response.raise_for_status()

        response_json = response.json()
        message_content = response_json["message"]["content"]
        parsed = self._parse_json_payload(message_content)
        return self._invoice_from_payload(parsed)

    def _build_text_prompt(self, raw_text: str, filename: str) -> str:
        return (
            f"{PROMPT}\n"
            f"Nombre de archivo: {filename or 'invoice'}\n"
            "Usa solo la informacion del texto; no inventes datos.\n"
            f"Texto OCR/extraido:\n{raw_text[:16000]}"
        )

    def _response_schema(self) -> dict[str, Any]:
        return InvoiceData.model_json_schema()

    def _parse_json_payload(self, payload: Any) -> dict[str, Any]:
        if isinstance(payload, dict):
            return payload

        if isinstance(payload, list):
            text_parts = []
            for item in payload:
                if isinstance(item, dict) and item.get("type") == "text":
                    text_parts.append(item.get("text", ""))
            payload = "\n".join(text_parts)

        if not isinstance(payload, str):
            raise ValueError("Respuesta no compatible del proveedor Doc AI")

        payload = payload.strip()
        if payload.startswith("```"):
            payload = payload.strip("`")
            payload = payload.replace("json\n", "", 1).strip()

        start = payload.find("{")
        end = payload.rfind("}")
        if start < 0 or end < 0:
            raise ValueError("No se encontro JSON en la respuesta")

        return json.loads(payload[start:end + 1])

    def _invoice_from_payload(self, payload: dict[str, Any]) -> InvoiceData:
        line_items = payload.get("lineas", []) or []
        payload["lineas"] = [
            item if isinstance(item, LineItem) else LineItem(**item)
            for item in line_items
            if isinstance(item, dict)
        ]
        return InvoiceData(**payload)

    def _build_extraction_document(
        self,
        *,
        invoice: InvoiceData,
        raw_text: str,
        filename: str,
        mime_type: str,
        provider: str,
        method: str,
        warnings: list[str],
    ) -> NormalizedInvoiceDocument:
        document_type = self._infer_document_type(raw_text, invoice)
        tax_regime = self._infer_tax_regime(raw_text, invoice)
        return build_normalized_document_from_invoice_data(
            invoice,
            source_channel="web",
            file_name=filename,
            mime_type=mime_type,
            extraction_provider=provider,
            extraction_method=method,
            document_type=document_type,
            tax_regime=tax_regime,
            warnings=warnings,
            raw_text_excerpt=raw_text[:400],
        )

    def _infer_document_type(self, raw_text: str, invoice: InvoiceData) -> DocumentType:
        upper_text = raw_text.upper()
        if "FACTURA RECTIFICAT" in upper_text:
            return "factura_rectificativa"
        if "ABONO" in upper_text:
            return "abono"
        if "FACTURA SIMPLIFICADA" in upper_text:
            return "factura_simplificada"
        if "PROFORMA" in upper_text:
            return "proforma"
        if "TICKET" in upper_text:
            return "ticket"
        if "DUA" in upper_text:
            return "dua"
        if invoice.numero_factura or invoice.fecha or invoice.total > 0:
            return "factura_completa"
        return "desconocido"

    def _infer_tax_regime(self, raw_text: str, invoice: InvoiceData) -> TaxRegime:
        upper_text = raw_text.upper()
        if "AIEM" in upper_text:
            return "AIEM"
        if "IGIC" in upper_text:
            return "IGIC"
        if "IVA" in upper_text or re.search(r"\bVA\s*(4|10|21)\s*%?", upper_text):
            return "IVA"
        if "NO SUJET" in upper_text:
            return "NOT_SUBJECT"
        if "EXENT" in upper_text:
            return "EXEMPT"
        if "INVERSI" in upper_text and "SUJETO PASIVO" in upper_text:
            return "REVERSE_CHARGE"
        if invoice.iva_porcentaje in {1, 3, 5, 7, 9.5, 15, 20}:
            return "IGIC"
        if invoice.iva_porcentaje in {4, 10, 21}:
            return "IVA"
        if invoice.iva_porcentaje > 0 or invoice.iva > 0:
            return "UNKNOWN"
        return "UNKNOWN"

    def _build_extraction_coverage(
        self,
        normalized_document: NormalizedInvoiceDocument,
    ) -> ExtractionCoverage:
        field_checks = {
            "classification.document_type": normalized_document.classification.document_type != "desconocido",
            "classification.invoice_side": normalized_document.classification.invoice_side != "desconocida",
            "identity.issue_date": bool(normalized_document.identity.issue_date),
            "identity.invoice_number": bool(normalized_document.identity.invoice_number),
            "issuer.name": bool(normalized_document.issuer.name),
            "issuer.tax_id": bool(normalized_document.issuer.tax_id),
            "totals.subtotal": normalized_document.totals.subtotal > 0,
            "totals.total": normalized_document.totals.total > 0,
            "tax_breakdown": bool(normalized_document.tax_breakdown),
            "line_items": bool(normalized_document.line_items),
        }
        present_fields = [field_name for field_name in PRIORITY_CONTRACT_FIELDS if field_checks[field_name]]
        missing_fields = [field_name for field_name in PRIORITY_CONTRACT_FIELDS if not field_checks[field_name]]
        ratio = round(len(present_fields) / len(PRIORITY_CONTRACT_FIELDS), 2)
        return ExtractionCoverage(
            required_fields_present=present_fields,
            missing_required_fields=missing_fields,
            completeness_ratio=ratio,
        )

    def _merge_with_fallback(self, primary: InvoiceData, fallback: InvoiceData) -> InvoiceData:
        merged = primary.model_copy(deep=True)
        for field_name in InvoiceData.model_fields:
            primary_value = getattr(primary, field_name)
            fallback_value = getattr(fallback, field_name)
            if self._is_empty_value(primary_value):
                setattr(merged, field_name, fallback_value)
        return merged

    def _is_empty_value(self, value: Any) -> bool:
        if value in ("", 0, 0.0, None):
            return True
        if isinstance(value, list) and not value:
            return True
        return False

    def _format_exception(self, exc: Exception) -> str:
        message = str(exc).strip()
        if message:
            return message
        return exc.__class__.__name__

    def _normalize_line_items(self, line_items: list[LineItem]) -> tuple[list[LineItem], list[str]]:
        normalized_items: list[LineItem] = []
        warnings: list[str] = []

        for index, line in enumerate(line_items):
            item = line.model_copy(deep=True)
            item.descripcion = re.sub(r"\s+", " ", item.descripcion or "").strip()

            if item.precio_unitario > 0 and item.cantidad <= 0 and item.importe <= 0:
                item.cantidad = 1.0
                item.importe = round(item.precio_unitario, 2)
                warnings.append(f"linea_{index + 1}_completada_desde_precio")
            elif item.precio_unitario > 0 and item.cantidad <= 0 and item.importe > 0:
                estimated_qty = item.importe / item.precio_unitario if item.precio_unitario else 0
                if abs(round(estimated_qty) - estimated_qty) < 0.05:
                    item.cantidad = float(max(1, round(estimated_qty)))
                else:
                    item.cantidad = 1.0
                warnings.append(f"linea_{index + 1}_cantidad_inferida")
            elif item.cantidad > 0 and item.precio_unitario > 0 and item.importe <= 0:
                item.importe = round(item.cantidad * item.precio_unitario, 2)
                warnings.append(f"linea_{index + 1}_importe_recalculado")

            normalized_items.append(item)

        return normalized_items, warnings

    def _normalize_amounts(self, data: InvoiceData) -> list[str]:
        warnings: list[str] = []

        if data.total > 0 and data.iva_porcentaje > 0 and data.base_imponible <= 0 and data.iva <= 0:
            divisor = 1 + (data.iva_porcentaje / 100)
            data.base_imponible = round(data.total / divisor, 2)
            data.iva = round(data.total - data.base_imponible, 2)
            warnings.append("base_e_iva_inferidos_desde_total_y_porcentaje")

        if data.total > 0 and data.base_imponible > 0 and data.iva <= 0:
            data.iva = round(max(0, data.total - data.base_imponible), 2)
            warnings.append("iva_inferido_desde_total")

        if data.base_imponible > 0 and data.iva_porcentaje > 0:
            expected_iva = round(data.base_imponible * data.iva_porcentaje / 100, 2)
            if data.total > 0:
                expected_total = round(data.base_imponible + expected_iva, 2)
                current_diff = abs(round(data.base_imponible + data.iva, 2) - data.total)
                expected_diff = abs(expected_total - data.total)
                if expected_diff + 0.02 < current_diff:
                    data.iva = expected_iva
                    warnings.append("iva_recalculado_desde_porcentaje")
            elif data.iva <= 0 or abs(data.iva - expected_iva) > 0.02:
                data.iva = expected_iva
                warnings.append("iva_recalculado_desde_porcentaje")

        if data.base_imponible > 0 and data.iva > 0 and data.iva_porcentaje <= 0:
            data.iva_porcentaje = round((data.iva / data.base_imponible) * 100, 2)
            warnings.append("iva_porcentaje_inferido_desde_base_e_iva")

        if data.base_imponible > 0 and data.iva > 0 and data.total <= 0:
            data.total = round(data.base_imponible + data.iva, 2)
            warnings.append("total_inferido_desde_base_e_iva")

        if data.total > 0 and data.iva > 0 and data.base_imponible <= 0:
            data.base_imponible = round(max(0, data.total - data.iva), 2)
            warnings.append("base_inferida_desde_total_e_iva")

        if data.total > 0 and data.base_imponible > 0 and data.iva > 0:
            expected_total = round(data.base_imponible + data.iva, 2)
            if abs(expected_total - data.total) > 0.02:
                line_sum = round(sum(line.importe for line in data.lineas if line.importe > 0), 2)
                if line_sum > 0 and abs(line_sum - data.base_imponible) <= 0.02:
                    data.total = expected_total
                    warnings.append("total_recalculado_desde_base_e_iva")

        line_sum = round(sum(line.importe for line in data.lineas if line.importe > 0), 2)
        amount_candidates = self._pick_best_amounts(data, line_sum)
        if amount_candidates:
            base_candidate, iva_candidate = amount_candidates

            if line_sum > 0 and abs(base_candidate - line_sum) <= 0.02 and abs(data.base_imponible - base_candidate) > 0.02:
                warnings.append("base_reconciliada_con_lineas")
            elif abs(data.base_imponible - base_candidate) > 0.02:
                warnings.append("base_recalculada_por_consistencia")

            if abs(data.iva - iva_candidate) > 0.02:
                warnings.append("iva_recalculado_por_consistencia")

            data.base_imponible = base_candidate
            data.iva = iva_candidate

        return warnings

    def _pick_best_amounts(self, data: InvoiceData, line_sum: float) -> tuple[float, float] | None:
        candidates: list[tuple[float, float]] = []

        if data.base_imponible > 0:
            candidates.append((round(data.base_imponible, 2), round(max(0, data.iva), 2)))

        if line_sum > 0:
            if data.iva_porcentaje > 0:
                candidates.append(
                    (
                        line_sum,
                        round(line_sum * data.iva_porcentaje / 100, 2),
                    )
                )
            if data.total > 0:
                candidates.append((line_sum, round(max(0, data.total - line_sum), 2)))

        if data.total > 0 and data.iva > 0:
            candidates.append((round(max(0, data.total - data.iva), 2), round(data.iva, 2)))

        if data.total > 0 and data.iva_porcentaje > 0:
            divisor = 1 + (data.iva_porcentaje / 100)
            inferred_base = round(data.total / divisor, 2)
            candidates.append((inferred_base, round(data.total - inferred_base, 2)))

        filtered_candidates: list[tuple[float, float]] = []
        seen = set()
        for base_candidate, iva_candidate in candidates:
            if base_candidate <= 0 and iva_candidate <= 0:
                continue
            key = (round(base_candidate, 2), round(iva_candidate, 2))
            if key in seen:
                continue
            seen.add(key)
            filtered_candidates.append(key)

        if not filtered_candidates:
            return None

        def score_candidate(base_candidate: float, iva_candidate: float) -> tuple[int, int, float]:
            score = 0

            if data.total > 0 and abs(round(base_candidate + iva_candidate, 2) - data.total) <= 0.02:
                score += 4
            elif data.total > 0 and abs(round(base_candidate + iva_candidate, 2) - data.total) <= max(0.1, data.total * 0.02):
                score += 2

            if data.iva_porcentaje > 0:
                expected_iva = round(base_candidate * data.iva_porcentaje / 100, 2)
                if abs(expected_iva - iva_candidate) <= 0.02:
                    score += 3
                elif abs(expected_iva - iva_candidate) <= max(0.1, expected_iva * 0.03):
                    score += 1

            if line_sum > 0 and abs(base_candidate - line_sum) <= 0.02:
                score += 2
            elif line_sum > 0 and abs(base_candidate - line_sum) <= max(0.1, line_sum * 0.02):
                score += 1

            # Prefer candidates that keep an extracted positive tax amount when totals fit.
            if iva_candidate > 0:
                score += 1

            total_distance = 0.0
            if data.total > 0:
                total_distance += abs(round(base_candidate + iva_candidate, 2) - data.total)
            if data.iva_porcentaje > 0:
                total_distance += abs(round(base_candidate * data.iva_porcentaje / 100, 2) - iva_candidate)
            if line_sum > 0:
                total_distance += abs(base_candidate - line_sum)

            return score, int(abs(base_candidate - line_sum) <= 0.02), -round(total_distance, 4)

        best_base, best_iva = max(filtered_candidates, key=lambda candidate: score_candidate(*candidate))
        return round(best_base, 2), round(best_iva, 2)

    def _is_valid_tax_id(self, value: str) -> bool:
        if not value:
            return False
        cleaned = re.sub(r"\s+", "", value.upper())
        if re.fullmatch(r"[A-HJ-NP-SUVW]\d{7}[0-9A-J]", cleaned):
            return True
        if re.fullmatch(r"\d{8}[A-Z]", cleaned):
            return True
        if re.fullmatch(r"[XYZ]\d{7}[A-Z]", cleaned):
            return True
        return False


document_intelligence_service = DocumentIntelligenceService()
