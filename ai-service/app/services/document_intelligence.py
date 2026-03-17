"""Document-to-JSON extraction with optional external AI provider."""

from __future__ import annotations

import json
import logging
import re
from typing import Any

from app.config import settings
from app.models.invoice_model import InvoiceData, LineItem
from app.services.confidence_scorer import confidence_scorer
from app.services.document_loader import document_loader
from app.services.field_extractor import field_extractor
from app.services.invoice_classifier import invoice_classifier

logger = logging.getLogger(__name__)


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

        return {
            "success": True,
            "data": data,
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

        return warnings

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
