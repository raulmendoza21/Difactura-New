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
from app.models.document_bundle import BoundingBox, DocumentBundle, DocumentSpan, LayoutRegion
from app.models.extraction_result import ExtractionCoverage
from app.models.invoice_model import InvoiceData, LineItem
from app.services.confidence_scorer import confidence_scorer
from app.services.document_loader import document_loader
from app.services.evidence_builder import evidence_builder
from app.services.field_extractor import field_extractor
from app.services.invoice_classifier import invoice_classifier
from app.utils.text_processing import parse_amount

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
Si aparece IGIC, no lo conviertas en IVA y usa el porcentaje visible exacto.
Si una linea combina numero de documento y fecha (por ejemplo "FI202600043 07-01-2026"),
usa el codigo como numero_factura y la fecha como fecha.
Si aparecen bloques de SUBTOTAL / IMPUESTOS / TOTAL, respeta esos importes antes de inferir otros.
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
  "retencion_porcentaje": 0,
  "retencion": 0,
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

    async def extract(
        self,
        file_path: str,
        filename: str = "",
        mime_type: str = "",
        company_context: dict[str, str] | None = None,
    ) -> dict:
        provider_name = settings.doc_ai_provider if settings.doc_ai_enabled else "heuristic"
        uses_images = provider_name == "openai_compatible"
        document = document_loader.load(file_path, mime_type, include_page_images=uses_images)
        bundle = document.get("bundle") or DocumentBundle(raw_text=document["raw_text"], page_count=document["pages"])
        raw_text = bundle.raw_text or document["raw_text"]
        pages = document["pages"]
        input_profile = document["input_profile"]
        fallback_data = self._heuristic_extract(raw_text)
        bundle_candidate, bundle_sources = field_extractor.extract_from_bundle(bundle)
        base_candidate = self._merge_with_fallback(bundle_candidate, fallback_data)

        warnings: list[str] = []
        base_candidate, base_warnings = self._normalize_invoice_data(
            base_candidate,
            fallback_data,
            raw_text=raw_text,
            company_context=company_context,
        )
        warnings.extend(base_warnings)

        bundle, raw_text, rescue_applied = self._maybe_apply_region_hint_rescue(
            file_path=file_path,
            input_profile=input_profile,
            company_context=company_context,
            bundle=bundle,
            raw_text=raw_text,
            base_candidate=base_candidate,
        )
        if rescue_applied:
            if "region_hint_rescue" not in input_profile.setdefault("preprocessing_steps", []):
                input_profile["preprocessing_steps"].append("region_hint_rescue")
            warnings.append("region_hint_rescue_applied")
            fallback_data = self._heuristic_extract(raw_text)
            bundle_candidate, bundle_sources = field_extractor.extract_from_bundle(bundle)
            base_candidate = self._merge_with_fallback(bundle_candidate, fallback_data)
            base_candidate, rescue_warnings = self._normalize_invoice_data(
                base_candidate,
                fallback_data,
                raw_text=raw_text,
                company_context=company_context,
            )
            warnings.extend(rescue_warnings)

        method = "doc_bundle"
        provider = "heuristic"
        data = base_candidate
        ai_candidate: InvoiceData | None = None
        data.tipo_factura = self._infer_invoice_type(
            invoice=data,
            raw_text=raw_text,
            company_context=company_context,
        )

        if settings.doc_ai_enabled:
            try:
                ai_data, provider = await self._extract_with_provider(
                    provider_name=provider_name,
                    raw_text=raw_text,
                    page_images=document["page_images"][: settings.doc_ai_max_pages],
                    filename=filename,
                )
                ai_candidate = ai_data.model_copy(deep=True)
                warnings.extend(self._compare_source_candidates(ai_candidate, base_candidate))
                ai_data = self._merge_with_fallback(ai_data, base_candidate)
                ai_data, normalization_warnings = self._normalize_invoice_data(
                    ai_data,
                    base_candidate,
                    raw_text=raw_text,
                    company_context=company_context,
                )
                warnings.extend(normalization_warnings)
                ai_data.tipo_factura = self._infer_invoice_type(
                    invoice=ai_data,
                    raw_text=raw_text,
                    company_context=company_context,
                )
                data = ai_data
                method = "doc_bundle_doc_ai"
            except Exception as exc:
                formatted_exc = self._format_exception(exc)
                logger.warning("Doc AI extraction failed, falling back to heuristics: %s", formatted_exc)
                warnings.append(f"doc_ai_fallback: {formatted_exc}")

        company_match = self._build_company_match(data=data, company_context=company_context)
        evidence = evidence_builder.build_field_evidence(
            bundle=bundle,
            final=data,
            heuristic=fallback_data,
            bundle_candidate=bundle_candidate,
            ai_candidate=ai_candidate,
        )
        field_confidence = self._build_field_confidence(
            final=data,
            heuristic=fallback_data,
            bundle_candidate=bundle_candidate,
            ai_candidate=ai_candidate,
            evidence=evidence,
        )
        normalized_document = self._build_extraction_document(
            invoice=data,
            raw_text=raw_text,
            filename=filename,
            mime_type=mime_type,
            pages=pages,
            input_profile=input_profile,
            provider=provider,
            method=method,
            warnings=warnings,
        )
        coverage = self._build_extraction_coverage(normalized_document)
        decision_flags = evidence_builder.build_decision_flags(
            invoice=data,
            field_confidence=field_confidence,
            warnings=warnings,
            company_match=company_match,
        )
        base_confidence = self._refine_document_confidence(
            invoice=data,
            current_confidence=confidence_scorer.score(data),
            field_confidence=field_confidence,
            warnings=warnings,
        )
        adjusted_confidence = confidence_scorer.score_with_context(
            data,
            field_confidence=field_confidence,
            evidence=evidence,
            decision_flags=decision_flags,
            coverage_ratio=coverage.completeness_ratio,
        )
        data.confianza = round(min(base_confidence, adjusted_confidence), 2)
        normalized_document.document_meta.extraction_confidence = data.confianza
        processing_trace = evidence_builder.build_processing_trace(
            bundle=bundle,
            input_kind=input_profile.get("input_kind", ""),
            provider=provider,
            method=method,
            used_ocr=bool(input_profile.get("used_ocr")),
            used_ai=ai_candidate is not None,
            page_count=pages,
        )

        return {
            "success": True,
            "data": data,
            "document_input": input_profile,
            "field_confidence": field_confidence,
            "normalized_document": normalized_document,
            "coverage": coverage,
            "evidence": evidence,
            "decision_flags": decision_flags,
            "company_match": company_match,
            "processing_trace": processing_trace,
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
        *,
        raw_text: str = "",
        company_context: dict[str, str] | None = None,
    ) -> tuple[InvoiceData, list[str]]:
        normalized = primary.model_copy(deep=True)
        warnings: list[str] = []
        upper_text = raw_text.upper()

        if self._is_suspicious_invoice_number(normalized.numero_factura) and self._looks_like_invoice_code(
            fallback.numero_factura
        ):
            normalized.numero_factura = fallback.numero_factura
            warnings.append("numero_factura_corregido_con_fallback")

        raw_invoice_number = self._extract_invoice_number_from_raw_text(raw_text)
        if raw_invoice_number and (
            not self._looks_like_invoice_code(normalized.numero_factura)
            or self._is_valid_tax_id(normalized.numero_factura)
            or normalized.numero_factura in {normalized.cif_proveedor, normalized.cif_cliente}
        ):
            normalized.numero_factura = raw_invoice_number
            warnings.append("numero_factura_corregido_desde_texto")

        if "IGIC" in upper_text and self._is_igic_rate(fallback.iva_porcentaje) and not self._is_igic_rate(
            normalized.iva_porcentaje
        ):
            normalized.iva_porcentaje = fallback.iva_porcentaje
            warnings.append("iva_porcentaje_corregido_por_texto_igic")
        elif "IVA" in upper_text and self._is_iva_rate(fallback.iva_porcentaje) and not self._is_iva_rate(
            normalized.iva_porcentaje
        ):
            normalized.iva_porcentaje = fallback.iva_porcentaje
            warnings.append("iva_porcentaje_corregido_por_texto_iva")

        normalized.proveedor = self._normalize_party_name(normalized.proveedor)
        normalized.cliente = self._normalize_party_name(normalized.cliente)
        fallback_provider = self._normalize_party_name(fallback.proveedor)
        fallback_client = self._normalize_party_name(fallback.cliente)
        raw_parties = self._extract_parties_from_raw_text(raw_text)

        if not normalized.proveedor and fallback_provider:
            normalized.proveedor = fallback_provider
            warnings.append("proveedor_corregido_con_fallback")

        if not normalized.cliente and fallback_client:
            normalized.cliente = fallback_client
            warnings.append("cliente_corregido_con_fallback")

        if (
            normalized.proveedor
            and normalized.cliente
            and self._values_match(normalized.proveedor, normalized.cliente)
        ):
            if fallback_provider and not self._values_match(fallback_provider, normalized.cliente):
                normalized.proveedor = fallback_provider
                warnings.append("proveedor_desambiguado_con_fallback")
            elif fallback_client and not self._values_match(fallback_client, normalized.proveedor):
                normalized.cliente = fallback_client
                warnings.append("cliente_desambiguado_con_fallback")

        if self._should_promote_party_candidate(
            current_name=normalized.proveedor,
            current_tax_id=normalized.cif_proveedor,
            candidate_name=raw_parties["proveedor"],
            candidate_tax_id=raw_parties["cif_proveedor"],
        ):
            normalized.proveedor = raw_parties["proveedor"]
            if raw_parties["cif_proveedor"]:
                normalized.cif_proveedor = raw_parties["cif_proveedor"]
            warnings.append("proveedor_detectado_desde_bloque_texto")

        if raw_parties["cif_proveedor"] and (
            not normalized.cif_proveedor
            or normalized.cif_proveedor == normalized.cif_cliente
        ):
            normalized.cif_proveedor = raw_parties["cif_proveedor"]
            warnings.append("cif_proveedor_detectado_desde_bloque_texto")

        if self._should_promote_party_candidate(
            current_name=normalized.cliente,
            current_tax_id=normalized.cif_cliente,
            candidate_name=raw_parties["cliente"],
            candidate_tax_id=raw_parties["cif_cliente"],
        ):
            normalized.cliente = raw_parties["cliente"]
            if raw_parties["cif_cliente"]:
                normalized.cif_cliente = raw_parties["cif_cliente"]
            warnings.append("cliente_detectado_desde_bloque_texto")

        if raw_parties["cif_cliente"] and not normalized.cif_cliente:
            normalized.cif_cliente = raw_parties["cif_cliente"]
            warnings.append("cif_cliente_detectado_desde_bloque_texto")

        normalized.lineas, line_warnings = self._normalize_line_items(normalized.lineas)
        warnings.extend(line_warnings)
        normalized.lineas, summary_leak_warnings = self._repair_summary_leak_lines(
            normalized.lineas,
            base_amount=normalized.base_imponible or fallback.base_imponible,
            total_amount=normalized.total or fallback.total,
        )
        warnings.extend(summary_leak_warnings)
        fallback_line_items, _ = self._normalize_line_items(fallback.lineas)
        fallback_line_items, _ = self._repair_summary_leak_lines(
            fallback_line_items,
            base_amount=fallback.base_imponible or normalized.base_imponible,
            total_amount=fallback.total or normalized.total,
        )
        normalized.lineas, fallback_line_warnings = self._prefer_fallback_line_items(
            primary_line_items=normalized.lineas,
            fallback_line_items=fallback_line_items,
            base_amount=fallback.base_imponible or normalized.base_imponible,
        )
        warnings.extend(fallback_line_warnings)

        if normalized.base_imponible <= 0 and normalized.lineas:
            line_sum = round(sum(line.importe for line in normalized.lineas if line.importe > 0), 2)
            if line_sum > 0:
                normalized.base_imponible = line_sum
                warnings.append("base_inferida_desde_lineas")

        normalized.cif_proveedor, provider_tax_warnings = self._normalize_tax_id_value(
            normalized.cif_proveedor,
            fallback.cif_proveedor,
            role="proveedor",
        )
        warnings.extend(provider_tax_warnings)

        normalized.cif_cliente, customer_tax_warnings = self._normalize_tax_id_value(
            normalized.cif_cliente,
            fallback.cif_cliente,
            role="cliente",
        )
        warnings.extend(customer_tax_warnings)

        retention_summary = self._extract_retention_summary(raw_text)
        if (
            retention_summary["base"] > 0
            and retention_summary["tax_rate"] > 0
            and retention_summary["tax_amount"] > 0
            and retention_summary["withholding_amount"] > 0
            and retention_summary["total_due"] > 0
        ):
            normalized.base_imponible = retention_summary["base"]
            normalized.iva_porcentaje = retention_summary["tax_rate"]
            normalized.iva = retention_summary["tax_amount"]
            normalized.retencion_porcentaje = retention_summary["withholding_rate"] or normalized.retencion_porcentaje
            normalized.retencion = retention_summary["withholding_amount"]
            normalized.total = retention_summary["total_due"]
            warnings.append("importes_detectados_desde_resumen_con_retencion")

        if retention_summary["withholding_rate"] > 0 and normalized.retencion_porcentaje <= 0:
            normalized.retencion_porcentaje = retention_summary["withholding_rate"]
            warnings.append("retencion_porcentaje_detectado_desde_texto")
        if retention_summary["withholding_amount"] > 0 and normalized.retencion <= 0:
            normalized.retencion = retention_summary["withholding_amount"]
            warnings.append("retencion_importe_detectado_desde_texto")
        if retention_summary["tax_rate"] > 0 and normalized.iva_porcentaje <= 0:
            normalized.iva_porcentaje = retention_summary["tax_rate"]
            warnings.append("iva_porcentaje_detectado_desde_texto")

        if normalized.retencion_porcentaje <= 0 and fallback.retencion_porcentaje > 0:
            normalized.retencion_porcentaje = fallback.retencion_porcentaje
            warnings.append("retencion_porcentaje_corregido_con_fallback")

        if normalized.retencion <= 0 and fallback.retencion > 0:
            normalized.retencion = fallback.retencion
            warnings.append("retencion_importe_corregido_con_fallback")

        amount_warnings = self._normalize_amounts(normalized)
        warnings.extend(amount_warnings)

        if self._should_clear_withholding(normalized, raw_text):
            normalized.retencion = 0.0
            normalized.retencion_porcentaje = 0.0
            warnings.append("retencion_descartada_sin_indicios_textuales")
            warnings.extend(self._normalize_amounts(normalized))

        if retention_summary["withholding_amount"] > 0 and retention_summary["total_due"] > 0:
            gross_total = retention_summary["gross_total"] or round(retention_summary["total_due"] + normalized.retencion, 2)
            if gross_total > 0 and normalized.iva_porcentaje > 0:
                inferred_base = retention_summary["base"] or round(gross_total - (retention_summary["tax_amount"] or normalized.iva), 2)
                inferred_tax = retention_summary["tax_amount"] or round(inferred_base * normalized.iva_porcentaje / 100, 2)
                normalized.base_imponible = round(inferred_base, 2)
                normalized.iva = round(inferred_tax, 2)
                normalized.total = round(retention_summary["total_due"], 2)
                warnings.append("importes_corregidos_con_retencion")

        line_enrichment_warnings = self._enrich_single_line_item_from_amounts(normalized)
        warnings.extend(line_enrichment_warnings)

        if (
            raw_text
            and self._has_structured_tax_summary(raw_text)
            and self._amounts_are_coherent(fallback)
            and (
                abs(normalized.base_imponible - fallback.base_imponible) > 0.02
                or abs(normalized.iva - fallback.iva) > 0.02
                or abs(normalized.total - fallback.total) > 0.02
            )
        ):
            normalized.base_imponible = fallback.base_imponible
            normalized.iva_porcentaje = fallback.iva_porcentaje or normalized.iva_porcentaje
            normalized.iva = fallback.iva
            normalized.retencion_porcentaje = fallback.retencion_porcentaje or normalized.retencion_porcentaje
            normalized.retencion = fallback.retencion or normalized.retencion
            normalized.total = fallback.total
            warnings.append("importes_corregidos_con_resumen_fallback")

        family_warnings = self._apply_family_corrections(
            normalized,
            fallback,
            raw_text=raw_text,
            company_context=company_context,
        )
        warnings.extend(family_warnings)

        if self._should_clear_withholding(normalized, raw_text):
            normalized.retencion = 0.0
            normalized.retencion_porcentaje = 0.0
            warnings.append("retencion_descartada_sin_indicios_textuales")
            warnings.extend(self._normalize_amounts(normalized))

        return normalized, warnings

    def _infer_invoice_type(
        self,
        *,
        invoice: InvoiceData,
        raw_text: str,
        company_context: dict[str, str] | None = None,
    ) -> str:
        company = self._normalize_company_context(company_context)
        if company["name"] or company["tax_id"]:
            provider_matches = self._matches_company_context(
                invoice.proveedor,
                invoice.cif_proveedor,
                company,
            )
            client_matches = self._matches_company_context(
                invoice.cliente,
                invoice.cif_cliente,
                company,
            )
            if provider_matches and not client_matches:
                return "venta"
            if client_matches and not provider_matches:
                return "compra"

        family = self._detect_document_family(raw_text, company)
        if family == "company_sale":
            return "venta"
        if family in {"shipping_billing_purchase", "withholding_purchase", "rectificativa"}:
            return "compra"

        return invoice_classifier.classify(raw_text, invoice.proveedor, invoice.cliente)

    def _apply_family_corrections(
        self,
        normalized: InvoiceData,
        fallback: InvoiceData,
        *,
        raw_text: str,
        company_context: dict[str, str] | None = None,
    ) -> list[str]:
        warnings: list[str] = []
        company = self._normalize_company_context(company_context)
        family = self._detect_document_family(raw_text, company)

        warnings.extend(self._align_with_company_context(normalized, fallback, company))

        if family == "company_sale":
            if (
                self._matches_company_context(fallback.proveedor, fallback.cif_proveedor, company)
                or self._matches_company_context(normalized.proveedor, normalized.cif_proveedor, company)
            ):
                normalized.proveedor = fallback.proveedor or company["name"] or normalized.proveedor
                normalized.cif_proveedor = fallback.cif_proveedor or company["tax_id"] or normalized.cif_proveedor
            if fallback.cliente and not self._matches_company_context(fallback.cliente, fallback.cif_cliente, company):
                normalized.cliente = fallback.cliente
                normalized.cif_cliente = fallback.cif_cliente or normalized.cif_cliente
            warnings.extend(self._repair_single_line_tax_confusion(normalized))

        elif family == "shipping_billing_purchase":
            if fallback.proveedor and not self._matches_company_context(fallback.proveedor, fallback.cif_proveedor, company):
                normalized.proveedor = fallback.proveedor
                normalized.cif_proveedor = fallback.cif_proveedor or normalized.cif_proveedor
            if company["name"] or company["tax_id"]:
                normalized.cliente = company["name"] or normalized.cliente
                normalized.cif_cliente = company["tax_id"] or normalized.cif_cliente

        elif family == "withholding_purchase":
            header_provider = self._extract_ranked_provider_from_header(raw_text, company)
            if header_provider:
                normalized.proveedor = header_provider
            if fallback.proveedor and not self._matches_company_context(fallback.proveedor, fallback.cif_proveedor, company):
                normalized.proveedor = header_provider or fallback.proveedor
            if fallback.cif_proveedor and not self._matches_company_context("", fallback.cif_proveedor, company):
                normalized.cif_proveedor = fallback.cif_proveedor
            if company["name"] or company["tax_id"]:
                normalized.cliente = company["name"] or normalized.cliente
                normalized.cif_cliente = company["tax_id"] or normalized.cif_cliente

        elif family == "rectificativa":
            rect_data = self._extract_rectificative_data(raw_text, company)
            if rect_data["supplier_name"]:
                normalized.proveedor = rect_data["supplier_name"]
            if rect_data["supplier_tax_id"]:
                normalized.cif_proveedor = rect_data["supplier_tax_id"]
            if company["name"] or company["tax_id"]:
                normalized.cliente = company["name"] or normalized.cliente
                normalized.cif_cliente = company["tax_id"] or normalized.cif_cliente
            if rect_data["invoice_number"]:
                normalized.numero_factura = rect_data["invoice_number"]
            if rect_data["rectified_invoice_number"]:
                normalized.rectified_invoice_number = rect_data["rectified_invoice_number"]
            if rect_data["base"] != 0:
                normalized.base_imponible = rect_data["base"]
            if rect_data["tax_rate"] > 0:
                normalized.iva_porcentaje = rect_data["tax_rate"]
            if rect_data["tax_amount"] != 0:
                normalized.iva = rect_data["tax_amount"]
            if rect_data["total"] != 0:
                normalized.total = rect_data["total"]
            if rect_data["description"] and normalized.base_imponible != 0:
                normalized.lineas = [
                    LineItem(
                        descripcion=rect_data["description"],
                        cantidad=1.0,
                        precio_unitario=normalized.base_imponible,
                        importe=normalized.base_imponible,
                    )
                ]
            warnings.append("familia_rectificativa_corregida")

        return warnings

    def _align_with_company_context(
        self,
        normalized: InvoiceData,
        fallback: InvoiceData,
        company: dict[str, str],
    ) -> list[str]:
        warnings: list[str] = []
        if not company["name"] and not company["tax_id"]:
            return warnings

        provider_matches = self._matches_company_context(normalized.proveedor, normalized.cif_proveedor, company)
        client_matches = self._matches_company_context(normalized.cliente, normalized.cif_cliente, company)
        fallback_provider_matches = self._matches_company_context(fallback.proveedor, fallback.cif_proveedor, company)
        fallback_client_matches = self._matches_company_context(fallback.cliente, fallback.cif_cliente, company)

        if fallback_provider_matches and not provider_matches:
            normalized.proveedor = company["name"] or fallback.proveedor or normalized.proveedor
            normalized.cif_proveedor = company["tax_id"] or fallback.cif_proveedor or normalized.cif_proveedor
            provider_matches = True
            warnings.append("proveedor_alineado_con_empresa_asociada")

        if fallback_client_matches and not client_matches:
            normalized.cliente = company["name"] or fallback.cliente or normalized.cliente
            normalized.cif_cliente = company["tax_id"] or fallback.cif_cliente or normalized.cif_cliente
            client_matches = True
            warnings.append("cliente_alineado_con_empresa_asociada")

        if provider_matches and client_matches:
            if fallback_client_matches and not fallback_provider_matches:
                normalized.proveedor = fallback.proveedor or normalized.proveedor
                normalized.cif_proveedor = fallback.cif_proveedor or normalized.cif_proveedor
                normalized.cliente = company["name"] or normalized.cliente
                normalized.cif_cliente = company["tax_id"] or normalized.cif_cliente
                warnings.append("proveedor_restaurado_desde_fallback")
            elif fallback_provider_matches and not fallback_client_matches:
                normalized.cliente = fallback.cliente or normalized.cliente
                normalized.cif_cliente = fallback.cif_cliente or normalized.cif_cliente
                normalized.proveedor = company["name"] or normalized.proveedor
                normalized.cif_proveedor = company["tax_id"] or normalized.cif_proveedor
                warnings.append("cliente_restaurado_desde_fallback")

        if provider_matches and not client_matches:
            if self._party_candidate_score(fallback.cliente, fallback.cif_cliente) > self._party_candidate_score(normalized.cliente, normalized.cif_cliente):
                normalized.cliente = fallback.cliente or normalized.cliente
                normalized.cif_cliente = fallback.cif_cliente or normalized.cif_cliente
        elif client_matches and not provider_matches:
            if self._party_candidate_score(fallback.proveedor, fallback.cif_proveedor) > self._party_candidate_score(normalized.proveedor, normalized.cif_proveedor):
                normalized.proveedor = fallback.proveedor or normalized.proveedor
                normalized.cif_proveedor = fallback.cif_proveedor or normalized.cif_proveedor

        return warnings

    def _detect_document_family(self, raw_text: str, company: dict[str, str] | None = None) -> str:
        upper_text = raw_text.upper()
        if "RECTIFICATIVA" in upper_text:
            return "rectificativa"
        if "IRPF" in upper_text or "RENTENCIÓN" in upper_text or "RETENCIÓN" in upper_text:
            return "withholding_purchase"
        if "DATOS DE FACTURACIÓN" in upper_text and "DATOS DE ENV" in upper_text:
            return "shipping_billing_purchase"
        if self._looks_like_company_sale_layout(raw_text, company):
            return "company_sale"
        return "generic"

    def _normalize_company_context(self, company_context: dict[str, str] | None) -> dict[str, str]:
        company_context = company_context or {}
        return {
            "name": self._normalize_party_name(company_context.get("name", "")),
            "tax_id": self._clean_tax_id(company_context.get("tax_id", "") or company_context.get("taxId", "")),
        }

    def _matches_company_context(self, name: str, tax_id: str, company: dict[str, str]) -> bool:
        company_tax_id = company.get("tax_id", "")
        if company_tax_id and self._clean_tax_id(tax_id) == company_tax_id:
            return True

        company_name = company.get("name", "")
        if not company_name or not name:
            return False

        normalized_name = self._normalize_party_value(name)
        normalized_company = self._normalize_party_value(company_name)
        if normalized_name == normalized_company:
            return True

        anchor = self._company_anchor_token(company_name)
        return bool(anchor and anchor in normalized_name)

    def _build_company_match(self, *, data: InvoiceData, company_context: dict[str, str] | None = None) -> dict[str, Any]:
        company = self._normalize_company_context(company_context)
        if not company["name"] and not company["tax_id"]:
            return {
                "issuer_matches_company": False,
                "recipient_matches_company": False,
                "matched_role": "",
                "matched_by": "",
                "confidence": 0.0,
            }

        issuer_matches = self._matches_company_context(data.proveedor, data.cif_proveedor, company)
        recipient_matches = self._matches_company_context(data.cliente, data.cif_cliente, company)
        if issuer_matches and recipient_matches:
            matched_role = "ambiguous"
        elif issuer_matches:
            matched_role = "issuer"
        elif recipient_matches:
            matched_role = "recipient"
        else:
            matched_role = ""

        matched_by = "tax_id" if company["tax_id"] and (
            self._clean_tax_id(data.cif_proveedor) == company["tax_id"]
            or self._clean_tax_id(data.cif_cliente) == company["tax_id"]
        ) else "name" if matched_role else ""
        confidence = 0.0
        if matched_role == "ambiguous":
            confidence = 0.45
        elif matched_role and matched_by == "tax_id":
            confidence = 0.95
        elif matched_role:
            confidence = 0.75

        return {
            "issuer_matches_company": issuer_matches,
            "recipient_matches_company": recipient_matches,
            "matched_role": matched_role,
            "matched_by": matched_by,
            "confidence": round(confidence, 2),
        }

    def _maybe_apply_region_hint_rescue(
        self,
        *,
        file_path: str,
        input_profile: dict[str, Any],
        company_context: dict[str, str] | None,
        bundle: DocumentBundle,
        raw_text: str,
        base_candidate: InvoiceData,
    ) -> tuple[DocumentBundle, str, bool]:
        if not self._should_run_region_hint_rescue(
            base_candidate=base_candidate,
            input_profile=input_profile,
            company_context=company_context,
        ):
            return bundle, raw_text, False

        from app.services.ocr_service import ocr_service

        try:
            region_hints = ocr_service.extract_region_hints(
                file_path,
                input_kind=input_profile.get("input_kind", "pdf_scanned"),
                max_pages=1,
            )
        except Exception as exc:
            logger.warning("Region hint OCR rescue failed: %s", self._format_exception(exc))
            return bundle, raw_text, False

        if not region_hints:
            return bundle, raw_text, False

        region_hints = sorted(
            region_hints,
            key=lambda hint: (
                self._region_hint_priority(str(hint.get("region_type", "") or "")),
                int(hint.get("page_number", 1) or 1),
            ),
        )

        rescued_bundle = bundle.model_copy(deep=True)
        normalized_raw_text = self._normalize_hint_lookup(raw_text)
        additional_texts: list[str] = []

        for index, hint in enumerate(region_hints, start=1):
            text = str(hint.get("text", "") or "").strip()
            if not text:
                continue

            page_number = int(hint.get("page_number", 1) or 1)
            bbox_payload = hint.get("bbox") or {}
            bbox = BoundingBox.from_points(
                float(bbox_payload.get("x0", 0) or 0),
                float(bbox_payload.get("y0", 0) or 0),
                float(bbox_payload.get("x1", 0) or 0),
                float(bbox_payload.get("y1", 0) or 0),
            )
            region_type = str(hint.get("region_type", "") or "").strip() or "header"
            region = LayoutRegion(
                region_id=f"rescue:p{page_number}:{region_type}:{index}",
                region_type=region_type,
                page=page_number,
                bbox=bbox,
                text=text,
                confidence=0.88,
            )
            span = DocumentSpan(
                span_id=f"rescue:p{page_number}:{region_type}:{index}",
                page=page_number,
                text=text,
                bbox=bbox,
                source="ocr_region",
                engine="tesseract",
                block_no=900 + index,
                line_no=0,
                confidence=0.88,
            )
            rescued_bundle.regions.append(region)
            rescued_bundle.spans.append(span)

            page_index = page_number - 1
            if 0 <= page_index < len(rescued_bundle.pages):
                rescued_bundle.pages[page_index].spans.append(span)
                page_text = rescued_bundle.pages[page_index].reading_text or ""
                if self._normalize_hint_lookup(text) not in self._normalize_hint_lookup(page_text):
                    rescued_bundle.pages[page_index].reading_text = "\n".join(
                        part for part in (page_text.strip(), text) if part
                    ).strip()
                    rescued_bundle.pages[page_index].ocr_text = "\n".join(
                        part for part in (rescued_bundle.pages[page_index].ocr_text.strip(), text) if part
                    ).strip()

            if self._normalize_hint_lookup(text) not in normalized_raw_text:
                additional_texts.append(text)

        if additional_texts:
            rescued_bundle.raw_text = "\n".join(
                part for part in (*additional_texts, raw_text.strip()) if part
            ).strip()
            rescued_bundle.page_texts = [page.reading_text for page in rescued_bundle.pages]

        return rescued_bundle, rescued_bundle.raw_text or raw_text, True

    def _should_run_region_hint_rescue(
        self,
        *,
        base_candidate: InvoiceData,
        input_profile: dict[str, Any],
        company_context: dict[str, str] | None,
    ) -> bool:
        company = self._normalize_company_context(company_context)
        if not company["name"] and not company["tax_id"]:
            return False

        input_kind = input_profile.get("input_kind", "")
        if input_kind not in {"pdf_scanned", "image_scan", "image_photo"}:
            return False

        provider_matches = self._matches_company_context(base_candidate.proveedor, base_candidate.cif_proveedor, company)
        client_matches = self._matches_company_context(base_candidate.cliente, base_candidate.cif_cliente, company)
        if provider_matches or client_matches:
            return False

        provider_value = str(base_candidate.proveedor or "").strip()
        client_value = str(base_candidate.cliente or "").strip()
        missing_party = not provider_value or not client_value
        long_noise_party = len(provider_value) > 90 or len(client_value) > 90
        missing_tax_ids = not base_candidate.cif_proveedor or not base_candidate.cif_cliente

        return missing_party or long_noise_party or missing_tax_ids

    def _normalize_hint_lookup(self, value: str) -> str:
        return re.sub(r"\s+", " ", str(value or "").upper()).strip()

    def _region_hint_priority(self, region_type: str) -> int:
        priorities = {
            "header_left": 0,
            "header_right": 1,
            "header": 2,
            "totals": 3,
        }
        return priorities.get(region_type, 9)

    def _company_anchor_token(self, value: str) -> str:
        legal_tokens = {
            "SL",
            "SA",
            "SLU",
            "SC",
            "CB",
            "SRL",
            "SOCIEDAD",
            "LIMITADA",
            "ANONIMA",
            "PROFESIONAL",
        }
        generic_tokens = {
            "SERVICIOS",
            "INFORMATICOS",
            "INFORMÁTICOS",
            "SOLUCIONES",
            "SISTEMAS",
            "CONSULTORIA",
            "CONSULTORÍA",
            "ASESORES",
            "ASESORIA",
            "ASESORIA",
            "GESTION",
            "GESTIÓN",
            "COMERCIAL",
            "HOSTELERIA",
            "HOSTELERÍA",
            "SUPERMERCADOS",
            "RESTAURANTE",
        }
        preferred_candidates: list[str] = []
        fallback_candidates: list[str] = []
        for token in re.findall(r"[A-ZÁÉÍÓÚÜÑ0-9]+", (value or "").upper()):
            cleaned = re.sub(r"[^A-Z0-9]", "", token)
            if len(cleaned) < 4 or cleaned in legal_tokens or cleaned.isdigit():
                continue
            if cleaned in generic_tokens:
                fallback_candidates.append(cleaned)
            else:
                preferred_candidates.append(cleaned)

        if preferred_candidates:
            preferred_candidates.sort(key=len, reverse=True)
            return preferred_candidates[0]
        if fallback_candidates:
            fallback_candidates.sort(key=len, reverse=True)
            return fallback_candidates[0]
        return ""

    def _normalize_party_value(self, value: str) -> str:
        return re.sub(r"[^A-Z0-9]", "", (value or "").upper())

    def _should_promote_party_candidate(
        self,
        *,
        current_name: str,
        current_tax_id: str,
        candidate_name: str,
        candidate_tax_id: str,
    ) -> bool:
        if not candidate_name and not candidate_tax_id:
            return False
        if self._is_generic_party_candidate(candidate_name) and not self._is_valid_tax_id(candidate_tax_id):
            return False

        current_score = self._party_candidate_score(current_name, current_tax_id)
        candidate_score = self._party_candidate_score(candidate_name, candidate_tax_id)
        if current_score <= 0:
            return candidate_score > 0
        return candidate_score > current_score

    def _party_candidate_score(self, name: str, tax_id: str) -> int:
        score = 0
        clean_name = self._normalize_party_name(name)
        if clean_name:
            score += 2
            if len(clean_name.split()) >= 2:
                score += 1
            if re.search(r"\b(SL|S\.L\.|SA|S\.A\.|SLU|S\.L\.U\.|S\.C\.|SCPROFESIONAL)\b", clean_name.upper()):
                score += 1
        if self._is_valid_tax_id(self._clean_tax_id(tax_id)):
            score += 3
        if self._is_generic_party_candidate(clean_name):
            score -= 3
        if clean_name and self._looks_like_address_or_contact_line(clean_name):
            score -= 2
        return score

    def _extract_ranked_provider_from_header(self, raw_text: str, company: dict[str, str]) -> str:
        lines = [line.strip() for line in raw_text.splitlines() if line.strip()]
        candidates: list[tuple[int, str]] = []
        header_lines = lines[:18]

        for index, line in enumerate(header_lines):
            compact_line = re.sub(r"[\s.\-]", "", line.upper())
            matches = re.findall(r"[A-Z]\d{7}[A-Z0-9]|\d{8}[A-Z]", compact_line)
            tax_ids = [
                value
                for value in matches
                if not company.get("tax_id") or value != company["tax_id"]
            ]
            if not tax_ids:
                continue

            anchored_candidates: list[tuple[int, str]] = []
            for candidate_line in reversed(header_lines[max(0, index - 5):index]):
                cleaned = re.sub(r"^\(\d+\)\s*", "", candidate_line).strip(" .,:;-")
                upper_candidate = cleaned.upper()
                if not cleaned or self._is_generic_party_candidate(cleaned):
                    continue
                if (
                    re.search(r"SERVI", upper_candidate)
                    and re.search(r"INFORM|FORMA|MORN", upper_candidate)
                    and not re.search(r"\b(SL|S\.L\.|SA|S\.A\.|SLU|S\.L\.U\.)\b", upper_candidate)
                ):
                    continue
                if self._matches_company_context(cleaned, "", company):
                    continue
                if self._looks_like_address_or_contact_line(cleaned):
                    continue
                if re.search(r",\s*\d{1,4}\b", cleaned) or re.search(r"\b\d{5}\b", upper_candidate):
                    continue
                if not self._normalize_party_name(cleaned):
                    continue
                candidate_score = self._party_candidate_score(cleaned, tax_ids[0])
                if re.search(r"\b(SL|S\.L\.|SA|S\.A\.|SLU|S\.L\.U\.)\b", upper_candidate):
                    candidate_score += 2
                elif len(cleaned.split()) <= 2:
                    candidate_score -= 2
                if "," in cleaned and not re.search(r"\d", cleaned):
                    candidate_score += 1
                anchored_candidates.append((candidate_score, cleaned))

            if anchored_candidates:
                anchored_candidates.sort(key=lambda item: (item[0], len(item[1])), reverse=True)
                best_score, best_name = anchored_candidates[0]
                if best_score >= 3:
                    return best_name

        for index, line in enumerate(header_lines):
            upper_line = line.upper()
            if "CLIENTE:" in upper_line:
                break
            if self._matches_company_context(line, "", company):
                continue
            if any(token in upper_line for token in ("FACTURA", "DOCUMENTO", "FECHA", "NIF", "CIF", "DOMICILIO")):
                continue
            if self._looks_like_address_or_contact_line(line):
                continue

            cleaned = re.sub(r"^\(\d+\)\s*", "", line).strip(" .,:;-")
            if not cleaned or self._is_generic_party_candidate(cleaned):
                continue
            if (
                re.search(r"SERVI", cleaned.upper())
                and re.search(r"INFORM|FORMA|MORN", cleaned.upper())
                and not re.search(r"\b(SL|S\.L\.|SA|S\.A\.|SLU|S\.L\.U\.)\b", cleaned.upper())
            ):
                continue
            if re.search(r",\s*\d{1,4}\b", cleaned) or re.search(r"\b\d{5}\b", upper_line):
                continue
            if self._matches_company_context(cleaned, "", company):
                continue
            if not self._normalize_party_name(cleaned):
                continue

            nearby_tax_id = ""
            for candidate_line in lines[index:index + 4]:
                compact_line = re.sub(r"[\s.\-]", "", candidate_line.upper())
                matches = re.findall(r"[A-Z]\d{7}[A-Z0-9]|\d{8}[A-Z]", compact_line)
                for candidate_tax_id in matches:
                    if company.get("tax_id") and candidate_tax_id == company["tax_id"]:
                        continue
                    nearby_tax_id = candidate_tax_id
                    break
                if nearby_tax_id:
                    break

            candidate_score = self._party_candidate_score(cleaned, nearby_tax_id)
            upper_cleaned = cleaned.upper()
            if re.search(r"\b(SL|S\.L\.|SA|S\.A\.|SLU|S\.L\.U\.)\b", upper_cleaned):
                candidate_score += 2
            elif len(cleaned.split()) <= 2:
                candidate_score -= 2
            if "," in cleaned and not re.search(r"\d", cleaned):
                candidate_score += 1
            candidates.append((candidate_score, cleaned))

        if candidates:
            candidates.sort(key=lambda item: (item[0], len(item[1])), reverse=True)
            best_score, best_name = candidates[0]
            if best_score >= 3:
                return best_name

        return self._extract_provider_from_header(raw_text, company)

    def _is_generic_party_candidate(self, value: str) -> bool:
        normalized = re.sub(r"\s+", " ", (value or "").strip()).upper()
        if not normalized:
            return True
        generic_values = {
            "SERVICIOS INFORMATICOS",
            "SERVICIOS INFORMÁTICOS",
            "DOMICILIO",
            "CLIENTE",
            "PROVEEDOR",
            "EMISOR",
            "RECEPTOR",
        }
        if normalized in generic_values:
            return True
        return bool(re.fullmatch(r"\d{5}.*", normalized))

    def _looks_like_company_sale_layout(self, raw_text: str, company: dict[str, str] | None = None) -> bool:
        company = company or {}
        upper_text = raw_text.upper()
        if "FACTURA" not in upper_text or "DOCUMENTO" not in upper_text or "FECHA" not in upper_text:
            return False
        if "DATOS DE FACTURACIÓN" in upper_text and "DATOS DE ENV" in upper_text:
            return False

        normalized_text = self._normalize_party_value(raw_text)
        company_tax_id = self._clean_tax_id(company.get("tax_id", ""))
        company_anchor = self._company_anchor_token(company.get("name", ""))
        has_company_context = bool(
            (company_tax_id and company_tax_id in normalized_text)
            or (company_anchor and company_anchor in normalized_text)
        )
        has_summary = any(token in upper_text for token in ("%IGIC", "%IVA", "SUBTOTAL", "BASE", "TOTAL"))
        has_body = "CONCEPTO" in upper_text or "IMPORTE" in upper_text
        return has_company_context and has_summary and has_body

    def _has_withholding_hint(self, raw_text: str) -> bool:
        upper_text = raw_text.upper()
        compact_text = re.sub(r"[^A-Z0-9]", "", upper_text)
        return any(
            token in upper_text or token in compact_text
            for token in ("IRPF", "RETEN", "RENTEN", "RETENCION", "RENTENCION", "%RET")
        )

    def _should_clear_withholding(self, invoice: InvoiceData, raw_text: str) -> bool:
        withholding = round(max(0, invoice.retencion or 0), 2)
        if withholding <= 0 and (invoice.retencion_porcentaje or 0) <= 0:
            return False

        total_with_withholding = round(invoice.base_imponible + invoice.iva - withholding, 2)
        total_without_withholding = round(invoice.base_imponible + invoice.iva, 2)
        delta_with = abs(total_with_withholding - invoice.total)
        delta_without = abs(total_without_withholding - invoice.total)

        if delta_without + 0.05 < delta_with:
            return True

        return not self._has_withholding_hint(raw_text) and delta_without <= 0.05

    def _repair_single_line_tax_confusion(self, invoice: InvoiceData) -> list[str]:
        if len(invoice.lineas) != 1 or invoice.base_imponible <= 0 or invoice.iva <= 0:
            return []
        item = invoice.lineas[0]
        if abs(item.precio_unitario - invoice.base_imponible) <= 0.05 and abs(item.importe - invoice.iva) <= 0.05:
            item.importe = round(invoice.base_imponible, 2)
            if item.cantidad <= 0:
                item.cantidad = 1.0
            return ["linea_unica_importe_corregido_desde_base"]
        return []

    def _extract_rectificative_data(self, raw_text: str, company: dict[str, str]) -> dict[str, Any]:
        lines = [line.strip() for line in raw_text.splitlines() if line.strip()]
        upper_lines = [line.upper() for line in lines]
        result = {
            "invoice_number": "",
            "rectified_invoice_number": "",
            "supplier_name": "",
            "supplier_tax_id": "",
            "base": 0.0,
            "tax_rate": 0.0,
            "tax_amount": 0.0,
            "total": 0.0,
            "description": "",
        }

        result["supplier_name"] = self._extract_ranked_provider_from_header(raw_text, company)

        for line in lines[:18]:
            if "NIF" not in line.upper() and "CIF" not in line.upper():
                continue
            tax_ids = re.findall(r"[A-Z]\d{7}[A-Z0-9]|\d{8}[A-Z]", re.sub(r"[\s.\-]", "", line.upper()))
            for candidate in tax_ids:
                if company.get("tax_id") and candidate == company["tax_id"]:
                    continue
                result["supplier_tax_id"] = candidate
                break
            if result["supplier_tax_id"]:
                break

        invoice_match = re.search(r"\bAB[A-Z0-9/-]{6,}\b", raw_text, re.IGNORECASE)
        if invoice_match:
            result["invoice_number"] = invoice_match.group(0).upper()

        rectified_match = re.search(r"(?:RECTIFICA\s+A)\s*[\n ]*([A-Z]{1,6}\d[\w/-]{3,25})", raw_text, re.IGNORECASE)
        if rectified_match:
            result["rectified_invoice_number"] = rectified_match.group(1).upper()

        try:
            concept_index = next(index for index, line in enumerate(upper_lines) if line == "CONCEPTO")
        except StopIteration:
            concept_index = -1
        if concept_index >= 0:
            for candidate in lines[concept_index + 1:concept_index + 6]:
                cleaned = re.sub(r"\s+", " ", candidate).strip(" .,:;-")
                if not cleaned or cleaned.startswith("-") or re.fullmatch(r"-?[\d.,]+", cleaned):
                    continue
                if cleaned.upper().startswith("SUBTOTAL") or cleaned.upper().startswith("TOTAL"):
                    break
                if len(cleaned) >= 6:
                    result["description"] = cleaned
                    break

        if not result["description"]:
            trigger_index = next(
                (
                    index
                    for index, line in enumerate(upper_lines)
                    if "CAUSA RECT" in line or line == "CONCEPTO"
                ),
                -1,
            )
            if trigger_index >= 0:
                for candidate in lines[trigger_index + 1:trigger_index + 8]:
                    cleaned = re.sub(r"\s+", " ", candidate).strip(" .,:;-")
                    upper_candidate = cleaned.upper()
                    if not cleaned or cleaned.startswith("-") or re.fullmatch(r"-?[\d.,]+", cleaned):
                        continue
                    if any(token in upper_candidate for token in ("SUBTOTAL", "IMPUEST", "TOTAL", "DOCUMENTO", "FECHA", "RECTIFICA", "NIF", "CIF")):
                        continue
                    if self._looks_like_address_or_contact_line(cleaned):
                        continue
                    if len(cleaned) >= 10:
                        result["description"] = cleaned
                        break

        def signed_amount_for_label(label: str) -> float:
            for index in range(len(upper_lines) - 1, -1, -1):
                upper_line = upper_lines[index]
                if label not in upper_line:
                    continue
                if label == "TOTAL":
                    for candidate in lines[index + 1:index + 3]:
                        matches = re.findall(r"-?\d{1,3}(?:[.,]\d{3})*(?:[.,]\d{2})|-?\d+(?:[.,]\d{2})", candidate)
                        if matches:
                            return round(parse_amount(matches[-1]), 2)
                for candidate in reversed(lines[max(0, index - 2):index + 1]):
                    matches = re.findall(r"-?\d{1,3}(?:[.,]\d{3})*(?:[.,]\d{2})|-?\d+(?:[.,]\d{2})", candidate)
                    if matches:
                        return round(parse_amount(matches[-1]), 2)
                for candidate in lines[index + 1:index + 3]:
                    matches = re.findall(r"-?\d{1,3}(?:[.,]\d{3})*(?:[.,]\d{2})|-?\d+(?:[.,]\d{2})", candidate)
                    if matches:
                        return round(parse_amount(matches[-1]), 2)
            return 0.0

        result["base"] = signed_amount_for_label("SUBTOTAL")
        result["tax_amount"] = signed_amount_for_label("IMPUESTOS")
        result["total"] = signed_amount_for_label("TOTAL")

        if result["base"] != 0 and result["total"] != 0:
            inferred_tax = round(result["total"] - result["base"], 2)
            if inferred_tax != 0 and (
                result["tax_amount"] == 0
                or abs(abs(result["tax_amount"]) - abs(inferred_tax)) > 0.05
            ):
                result["tax_amount"] = inferred_tax

        rate_match = re.search(r"(\d{1,2}(?:[.,]\d{1,2})?)\s*%[^\n]*IMPUESTOS", raw_text, re.IGNORECASE)
        if rate_match:
            result["tax_rate"] = float(rate_match.group(1).replace(",", "."))
        elif "%IGIC" in raw_text.upper():
            result["tax_rate"] = 7.0
        elif result["base"] and result["tax_amount"]:
            result["tax_rate"] = round(abs(result["tax_amount"] / result["base"]) * 100, 2)

        if result["base"] and result["tax_amount"]:
            inferred_rate = round(abs(result["tax_amount"] / result["base"]) * 100, 2)
            if result["tax_rate"] <= 0 or result["tax_rate"] > 35 or abs(result["tax_rate"] - inferred_rate) > 0.5:
                if inferred_rate <= 35:
                    result["tax_rate"] = inferred_rate

        return result

    def _extract_provider_from_header(self, raw_text: str, company: dict[str, str]) -> str:
        lines = [line.strip() for line in raw_text.splitlines() if line.strip()]
        stop_tokens = {"FACTURA", "CLIENTE:", "DATOS DE FACTURACIÓN", "DATOS DE ENVIO", "DATOS DE ENVÍO"}
        for line in lines[:12]:
            upper_line = line.upper()
            if upper_line in stop_tokens or self._matches_company_context(line, "", company):
                if "CLIENTE:" in upper_line:
                    break
                continue
            if any(token in upper_line for token in ("NIF", "CIF", "DOMICILIO")):
                continue
            if self._looks_like_address_or_contact_line(line):
                continue
            cleaned = re.sub(r"^\(\d+\)\s*", "", line).strip(" .,:;-")
            if not cleaned:
                continue
            if self._is_generic_party_candidate(cleaned):
                continue
            if self._matches_company_context(cleaned, "", company):
                continue
            if self._normalize_party_name(cleaned):
                return cleaned
        return ""

    def _looks_like_address_or_contact_line(self, value: str) -> bool:
        upper_value = (value or "").upper()
        if not upper_value:
            return False

        if any(token in upper_value for token in ("HTTP", "WWW.", "MAIL", "EMAIL", "TEL", "TLF", "MÓVIL", "MOVIL")):
            return True
        if re.search(r"\b(?:C/|CALLE|AVDA\.?|AVENIDA|URB\.?|LOCAL|POL\.?|POLIGONO|POLÍGONO|CTRA\.?)\b", upper_value):
            return True
        if re.search(r"\b\d{5}\b", upper_value):
            return True
        return False

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
        pages: int,
        input_profile: dict[str, Any],
        provider: str,
        method: str,
        warnings: list[str],
    ) -> NormalizedInvoiceDocument:
        document_type = self._infer_document_type(raw_text, invoice)
        document_type = self._apply_document_type_hint(document_type, input_profile.get("document_family_hint", ""))
        tax_regime = self._infer_tax_regime(raw_text, invoice)
        due_date = self._extract_due_date(raw_text)
        payment_method = self._extract_payment_method(raw_text)
        iban = self._extract_iban(raw_text)
        return build_normalized_document_from_invoice_data(
            invoice,
            source_channel="web",
            input_kind=input_profile.get("input_kind", ""),
            text_source=input_profile.get("text_source", ""),
            file_name=filename,
            mime_type=mime_type,
            page_count=pages,
            ocr_engine=input_profile.get("ocr_engine", ""),
            preprocessing_steps=input_profile.get("preprocessing_steps", []),
            extraction_provider=provider,
            extraction_method=method,
            document_type=document_type,
            tax_regime=tax_regime,
            due_date=due_date,
            payment_method=payment_method,
            iban=iban,
            warnings=warnings,
            raw_text_excerpt=raw_text[:400],
        )

    def _apply_document_type_hint(self, current: DocumentType, hint: str) -> DocumentType:
        hint_map: dict[str, DocumentType] = {
            "factura_rectificativa": "factura_rectificativa",
            "factura_simplificada": "factura_simplificada",
            "ticket": "ticket",
            "invoice": "factura_completa",
        }
        hinted = hint_map.get(hint or "", "desconocido")
        if current != "desconocido":
            return current
        return hinted

    def _compare_source_candidates(self, ai_candidate: InvoiceData, heuristic: InvoiceData) -> list[str]:
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
            if not self._values_match(ai_value, heuristic_value):
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
            if not self._values_match(ai_value, heuristic_value):
                warnings.append(warning_name)

        if ai_candidate.lineas and heuristic.lineas and not self._line_items_match(ai_candidate.lineas, heuristic.lineas):
            warnings.append("discrepancia_lineas")

        return warnings

    def _build_field_confidence(
        self,
        *,
        final: InvoiceData,
        heuristic: InvoiceData,
        bundle_candidate: InvoiceData | None = None,
        ai_candidate: InvoiceData | None = None,
        evidence: dict[str, list[Any]] | None = None,
    ) -> dict[str, float]:
        evidence = evidence or {}
        scores = {
            "numero_factura": self._score_field_confidence(
                final.numero_factura,
                heuristic.numero_factura,
                getattr(bundle_candidate, "numero_factura", ""),
                getattr(ai_candidate, "numero_factura", ""),
                evidence_items=evidence.get("numero_factura", []),
            ),
            "fecha": self._score_field_confidence(
                final.fecha,
                heuristic.fecha,
                getattr(bundle_candidate, "fecha", ""),
                getattr(ai_candidate, "fecha", ""),
                validator=self._is_valid_iso_date,
                evidence_items=evidence.get("fecha", []),
            ),
            "proveedor": self._score_field_confidence(
                final.proveedor,
                heuristic.proveedor,
                getattr(bundle_candidate, "proveedor", ""),
                getattr(ai_candidate, "proveedor", ""),
                evidence_items=evidence.get("proveedor", []),
            ),
            "cif_proveedor": self._score_field_confidence(
                final.cif_proveedor,
                heuristic.cif_proveedor,
                getattr(bundle_candidate, "cif_proveedor", ""),
                getattr(ai_candidate, "cif_proveedor", ""),
                validator=self._is_valid_tax_id,
                evidence_items=evidence.get("cif_proveedor", []),
            ),
            "cliente": self._score_field_confidence(
                final.cliente,
                heuristic.cliente,
                getattr(bundle_candidate, "cliente", ""),
                getattr(ai_candidate, "cliente", ""),
                evidence_items=evidence.get("cliente", []),
            ),
            "cif_cliente": self._score_field_confidence(
                final.cif_cliente,
                heuristic.cif_cliente,
                getattr(bundle_candidate, "cif_cliente", ""),
                getattr(ai_candidate, "cif_cliente", ""),
                validator=self._is_valid_tax_id,
                evidence_items=evidence.get("cif_cliente", []),
            ),
            "base_imponible": self._score_field_confidence(
                final.base_imponible,
                heuristic.base_imponible,
                getattr(bundle_candidate, "base_imponible", 0.0),
                getattr(ai_candidate, "base_imponible", 0.0),
                evidence_items=evidence.get("base_imponible", []),
            ),
            "iva_porcentaje": self._score_field_confidence(
                final.iva_porcentaje,
                heuristic.iva_porcentaje,
                getattr(bundle_candidate, "iva_porcentaje", 0.0),
                getattr(ai_candidate, "iva_porcentaje", 0.0),
                evidence_items=evidence.get("iva_porcentaje", []),
            ),
            "iva": self._score_field_confidence(
                final.iva,
                heuristic.iva,
                getattr(bundle_candidate, "iva", 0.0),
                getattr(ai_candidate, "iva", 0.0),
                evidence_items=evidence.get("iva", []),
            ),
            "total": self._score_field_confidence(
                final.total,
                heuristic.total,
                getattr(bundle_candidate, "total", 0.0),
                getattr(ai_candidate, "total", 0.0),
                evidence_items=evidence.get("total", []),
            ),
            "lineas": self._score_line_field_confidence(final, heuristic, bundle_candidate, ai_candidate, evidence.get("lineas", [])),
        }
        return scores

    def _refine_document_confidence(
        self,
        *,
        invoice: InvoiceData,
        current_confidence: float,
        field_confidence: dict[str, float],
        warnings: list[str],
    ) -> float:
        score = float(current_confidence or 0.0)
        normalized_warnings = [warning.lower() for warning in warnings]
        source_discrepancy_count = sum(1 for warning in normalized_warnings if warning.startswith("discrepancia_"))
        resolved_warning_count = sum(
            1
            for warning in normalized_warnings
            if any(
                token in warning
                for token in (
                    "corregido",
                    "desambiguado",
                    "reconciliad",
                    "reconstruido",
                    "inferido",
                    "ajustado",
                    "enriquecid",
                    "completad",
                )
            )
        )
        critical_warning_count = sum(
            1
            for warning in normalized_warnings
            if "no_valido" in warning or "falt" in warning
        )
        secondary_warning_count = max(
            0,
            len(normalized_warnings) - source_discrepancy_count - resolved_warning_count - critical_warning_count,
        )

        final_is_coherent = self._amounts_are_coherent(invoice)
        line_sum = round(sum(line.importe for line in invoice.lineas if line.importe > 0), 2)
        line_tolerance = max(0.02, invoice.base_imponible * 0.01) if invoice.base_imponible > 0 else 0.02
        line_items_match = invoice.base_imponible <= 0 or line_sum <= 0 or abs(line_sum - invoice.base_imponible) <= line_tolerance

        if critical_warning_count:
            score -= min(0.24, critical_warning_count * 0.1)

        if final_is_coherent and line_items_match:
            if source_discrepancy_count:
                score -= min(0.12, source_discrepancy_count * 0.03)
            if resolved_warning_count:
                score -= min(0.08, resolved_warning_count * 0.02)
            if secondary_warning_count:
                score -= min(0.09, secondary_warning_count * 0.03)
        else:
            if source_discrepancy_count:
                score -= min(0.24, source_discrepancy_count * 0.08)
            if resolved_warning_count:
                score -= min(0.16, resolved_warning_count * 0.05)
            if secondary_warning_count:
                score -= min(0.12, secondary_warning_count * 0.04)

        key_fields = (
            "numero_factura",
            "fecha",
            "proveedor",
            "cif_proveedor",
            "cliente",
            "cif_cliente",
            "base_imponible",
            "iva_porcentaje",
            "iva",
            "total",
            "lineas",
        )
        low_fields = [field for field in key_fields if (field_confidence.get(field) or 0) < 0.75]
        medium_fields = [field for field in key_fields if 0.75 <= (field_confidence.get(field) or 0) < 0.9]

        if low_fields:
            if final_is_coherent and line_items_match:
                score -= min(0.12, len(low_fields) * 0.02)
            else:
                score -= min(0.24, len(low_fields) * 0.04)
        if len(medium_fields) >= 3:
            score -= 0.02 if final_is_coherent and line_items_match else 0.04

        if invoice.base_imponible > 0 and line_sum > 0:
            mismatch = abs(line_sum - invoice.base_imponible)
            if mismatch > line_tolerance:
                score -= 0.12

        if critical_warning_count >= 2:
            score = min(score, 0.78)
        elif critical_warning_count == 1:
            score = min(score, 0.88)
        elif normalized_warnings and not final_is_coherent:
            score = min(score, 0.94)

        if not final_is_coherent and len(low_fields) >= 3:
            score = min(score, 0.74)
        elif not final_is_coherent and len(low_fields) >= 1:
            score = min(score, 0.89)

        if final_is_coherent and line_items_match:
            score = max(score, 0.72 if normalized_warnings else 0.8)

        return round(max(0.0, min(1.0, score)), 2)

    def _score_field_confidence(
        self,
        final_value: Any,
        heuristic_value: Any,
        bundle_value: Any,
        ai_value: Any,
        *,
        validator: Any | None = None,
        evidence_items: list[Any] | None = None,
    ) -> float:
        if self._is_empty_value(final_value):
            return 0.0

        evidence_items = evidence_items or []
        final_valid = bool(validator(final_value)) if validator else True
        score = 0.45 if final_valid else 0.25

        heuristic_present = not self._is_empty_value(heuristic_value)
        bundle_present = not self._is_empty_value(bundle_value)
        ai_present = not self._is_empty_value(ai_value)

        if heuristic_present and self._values_match(final_value, heuristic_value):
            score += 0.2
        elif heuristic_present:
            score -= 0.1

        if bundle_present and self._values_match(final_value, bundle_value):
            score += 0.18
        elif bundle_present:
            score -= 0.08

        if ai_present and self._values_match(final_value, ai_value):
            score += 0.25
        elif ai_present:
            score -= 0.1

        supporting_evidence = sum(1 for item in evidence_items if getattr(item, "value", "") and getattr(item, "source", "") != "resolved")
        if supporting_evidence >= 2:
            score += 0.07
        elif supporting_evidence == 1:
            score += 0.03

        if heuristic_present and ai_present and self._values_match(heuristic_value, ai_value):
            score += 0.1
        if bundle_present and heuristic_present and self._values_match(bundle_value, heuristic_value):
            score += 0.05

        return round(max(0.0, min(1.0, score)), 2)

    def _score_line_field_confidence(
        self,
        final: InvoiceData,
        heuristic: InvoiceData,
        bundle_candidate: InvoiceData | None,
        ai_candidate: InvoiceData | None,
        evidence_items: list[Any] | None = None,
    ) -> float:
        if not final.lineas:
            return 0.0

        evidence_items = evidence_items or []
        score = 0.35 if confidence_scorer._validate_line_items(final) > 0 else 0.2
        if confidence_scorer._validate_line_items(final) >= 0.8:
            score += 0.2

        if heuristic.lineas and self._line_items_match(final.lineas, heuristic.lineas):
            score += 0.2
        elif heuristic.lineas:
            score -= 0.1

        if bundle_candidate and bundle_candidate.lineas and self._line_items_match(final.lineas, bundle_candidate.lineas):
            score += 0.18
        elif bundle_candidate and bundle_candidate.lineas:
            score -= 0.08

        if ai_candidate and ai_candidate.lineas and self._line_items_match(final.lineas, ai_candidate.lineas):
            score += 0.25
        elif ai_candidate and ai_candidate.lineas:
            score -= 0.1

        if len(evidence_items) >= 2:
            score += 0.07

        return round(max(0.0, min(1.0, score)), 2)

    def _values_match(self, left: Any, right: Any) -> bool:
        if self._is_empty_value(left) and self._is_empty_value(right):
            return True
        if isinstance(left, (int, float)) or isinstance(right, (int, float)):
            try:
                return abs(float(left) - float(right)) <= max(0.02, abs(float(left)) * 0.02, abs(float(right)) * 0.02)
            except (TypeError, ValueError):
                return False

        left_text = re.sub(r"[^A-Z0-9]", "", str(left).upper())
        right_text = re.sub(r"[^A-Z0-9]", "", str(right).upper())
        return left_text == right_text or left_text in right_text or right_text in left_text

    def _line_items_match(self, left: list[LineItem], right: list[LineItem]) -> bool:
        if not left or not right:
            return False

        left_sum = round(sum(line.importe for line in left if abs(line.importe) > 0), 2)
        right_sum = round(sum(line.importe for line in right if abs(line.importe) > 0), 2)
        if abs(left_sum) > 0 and abs(right_sum) > 0 and not self._values_match(left_sum, right_sum):
            return False

        if abs(len(left) - len(right)) > 1:
            return False

        left_descriptions = {re.sub(r"[^A-Z0-9]", "", line.descripcion.upper()) for line in left if line.descripcion}
        right_descriptions = {re.sub(r"[^A-Z0-9]", "", line.descripcion.upper()) for line in right if line.descripcion}
        if not left_descriptions or not right_descriptions:
            return True

        overlap = len(left_descriptions & right_descriptions)
        return overlap >= max(1, min(len(left_descriptions), len(right_descriptions)) - 1)

    def _is_valid_iso_date(self, value: str) -> bool:
        return bool(re.fullmatch(r"\d{4}-\d{2}-\d{2}", value or ""))

    def _looks_like_invoice_code(self, value: str) -> bool:
        if not value:
            return False
        cleaned = value.strip().upper()
        return bool(re.fullmatch(r"[A-Z]{1,6}\d[\w/-]{4,}", cleaned))

    def _is_suspicious_invoice_number(self, value: str) -> bool:
        if not value:
            return True
        cleaned = value.strip().upper()
        if re.fullmatch(r"\d{1,3}", cleaned):
            return True
        if len(cleaned) < 5:
            return True
        return not self._looks_like_invoice_code(cleaned)

    def _is_igic_rate(self, value: float) -> bool:
        return any(abs(float(value or 0) - rate) <= 0.05 for rate in (0, 1, 3, 5, 7, 9.5, 15, 20))

    def _is_iva_rate(self, value: float) -> bool:
        return any(abs(float(value or 0) - rate) <= 0.05 for rate in (4, 10, 21))

    def _infer_document_type(self, raw_text: str, invoice: InvoiceData) -> DocumentType:
        upper_text = raw_text.upper()
        if "FACTURA RECTIFICAT" in upper_text or "RECTIFICATIVA" in upper_text:
            return "factura_rectificativa"
        if "ABONO" in upper_text:
            return "abono"
        if "FACTURA SIMPLIFICADA" in upper_text or "FRA. SIMPLIFICADA" in upper_text or "FRA SIMPLIFICADA" in upper_text:
            return "factura_simplificada"
        if "PROFORMA" in upper_text:
            return "proforma"
        if any(token in upper_text for token in ("TICKET", "DOCUMENTO DE VENTA", "CONSULTA BORRADOR", "NO VALIDO COMO FACTURA")):
            return "ticket"
        if "DUA" in upper_text:
            return "dua"
        if invoice.numero_factura or invoice.fecha or invoice.total > 0:
            return "factura_completa"
        return "desconocido"

    def _extract_due_date(self, raw_text: str) -> str:
        match = re.search(
            r"(?:fecha\s+vencim(?:iento|ienta)?|vencimiento|vence)\s*[:.]?\s*(\d{1,2}[/\-\.]\d{1,2}[/\-\.]\d{2,4})",
            raw_text,
            re.IGNORECASE,
        )
        if not match:
            return ""

        raw_date = match.group(1)
        if re.fullmatch(r"\d{2}/\d{2}/\d{4}", raw_date):
            day, month, year = raw_date.split("/")
            return f"{year}-{month}-{day}"
        if re.fullmatch(r"\d{2}-\d{2}-\d{4}", raw_date):
            day, month, year = raw_date.split("-")
            return f"{year}-{month}-{day}"
        if re.fullmatch(r"\d{2}\.\d{2}\.\d{4}", raw_date):
            day, month, year = raw_date.split(".")
            return f"{year}-{month}-{day}"
        return raw_date

    def _extract_payment_method(self, raw_text: str) -> str:
        match = re.search(
            r"(?:forma\s+de\s+pago|metodo\s+de\s+pago|payment\s+method)\s*[:.]?\s*([^\n]+)",
            raw_text,
            re.IGNORECASE,
        )
        candidate = (match.group(1).strip() if match else "").strip(" .,:;-")
        normalized_text = raw_text.upper()

        if not candidate:
            if "TRANSFERENCIA" in normalized_text:
                return "Transferencia"
            if "DOMICILIACION" in normalized_text:
                return "Domiciliacion"
            if "TARJETA" in normalized_text:
                return "Tarjeta"
            if "EFECTIVO" in normalized_text:
                return "Efectivo"
            return ""

        lowered = candidate.lower()
        if "transfer" in lowered:
            return "Transferencia"
        if "domic" in lowered or "recibo" in lowered:
            return "Domiciliacion"
        if "tarjeta" in lowered:
            return "Tarjeta"
        if "efectivo" in lowered or "contado" in lowered:
            return "Efectivo"
        return candidate[:80]

    def _extract_iban(self, raw_text: str) -> str:
        match = re.search(r"\b([A-Z]{2}\d{2}(?:[\s-]?\d{4}){5})\b", raw_text, re.IGNORECASE)
        if not match:
            return ""
        return re.sub(r"[\s-]", "", match.group(1).upper())

    def _infer_tax_regime(self, raw_text: str, invoice: InvoiceData) -> TaxRegime:
        upper_text = raw_text.upper()
        tax_rate = float(invoice.iva_porcentaje or 0)
        if "AIEM" in upper_text:
            return "AIEM"
        if "IGIC" in upper_text:
            return "IGIC"
        if tax_rate in {1, 3, 5, 7, 9.5, 15, 20}:
            return "IGIC"
        if "IVA" in upper_text or re.search(r"\bVA\s*(4|10|21)\s*%?", upper_text):
            return "IVA"
        if "NO SUJET" in upper_text:
            return "NOT_SUBJECT"
        if "EXENT" in upper_text:
            return "EXEMPT"
        if "INVERSI" in upper_text and "SUJETO PASIVO" in upper_text:
            return "REVERSE_CHARGE"
        if tax_rate in {4, 10, 21}:
            return "IVA"
        if tax_rate > 0 or invoice.iva != 0:
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
            "totals.subtotal": abs(normalized_document.totals.subtotal) > 0,
            "totals.total": abs(normalized_document.totals.total) > 0,
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

    def _enrich_single_line_item_from_amounts(self, data: InvoiceData) -> list[str]:
        warnings: list[str] = []
        if len(data.lineas) != 1 or data.base_imponible <= 0:
            return warnings

        item = data.lineas[0]
        if item.importe > 0:
            return warnings

        item.importe = round(data.base_imponible, 2)
        if item.cantidad <= 0:
            item.cantidad = 1.0
        if item.precio_unitario <= 0 and item.cantidad > 0:
            item.precio_unitario = round(item.importe / item.cantidad, 2)

        warnings.append("linea_unica_completada_desde_base")
        return warnings

    def _repair_summary_leak_lines(
        self,
        line_items: list[LineItem],
        *,
        base_amount: float = 0,
        total_amount: float = 0,
    ) -> tuple[list[LineItem], list[str]]:
        warnings: list[str] = []
        if len(line_items) < 2 or base_amount <= 0:
            return line_items, warnings

        reference_base = round(base_amount, 2)
        reference_total = round(total_amount, 2)
        line_sum = round(sum(line.importe for line in line_items if line.importe > 0), 2)
        if line_sum <= reference_base + 0.02:
            return line_items, warnings

        suspicious_index: int | None = None
        residual_amount = 0.0
        for index, line in enumerate(line_items):
            amount = round(line.importe, 2)
            if amount <= 0:
                continue

            amount_matches_summary = (
                abs(amount - reference_base) <= 0.02
                or (reference_total > 0 and abs(amount - reference_total) <= 0.02)
            )
            if not amount_matches_summary:
                continue

            remaining_sum = round(line_sum - amount, 2)
            candidate_residual = round(reference_base - remaining_sum, 2)
            if -0.02 <= candidate_residual <= max(10.0, reference_base * 0.15):
                suspicious_index = index
                residual_amount = candidate_residual
                break

        if suspicious_index is None:
            return line_items, warnings

        repaired_items: list[LineItem] = []
        for index, line in enumerate(line_items):
            if index != suspicious_index:
                repaired_items.append(line)
                continue

            if residual_amount <= 0.02:
                warnings.append(f"linea_{index + 1}_resumen_descartada")
                continue

            repaired = line.model_copy(deep=True)
            repaired.importe = round(residual_amount, 2)
            if repaired.cantidad > 0:
                repaired.precio_unitario = round(repaired.importe / repaired.cantidad, 2)
            else:
                repaired.cantidad = 1.0
                repaired.precio_unitario = repaired.importe

            repaired_items.append(repaired)
            warnings.append(f"linea_{index + 1}_importe_ajustado_desde_resumen")

        return repaired_items, warnings

    def _prefer_fallback_line_items(
        self,
        *,
        primary_line_items: list[LineItem],
        fallback_line_items: list[LineItem],
        base_amount: float = 0,
    ) -> tuple[list[LineItem], list[str]]:
        if not fallback_line_items:
            return primary_line_items, []
        if not primary_line_items:
            return fallback_line_items, ["lineas_completadas_con_fallback"]

        primary_sum = round(sum(line.importe for line in primary_line_items if line.importe > 0), 2)
        fallback_sum = round(sum(line.importe for line in fallback_line_items if line.importe > 0), 2)

        if base_amount > 0:
            primary_diff = abs(primary_sum - base_amount)
            fallback_diff = abs(fallback_sum - base_amount)
            if fallback_diff + 0.02 < primary_diff:
                return fallback_line_items, ["lineas_corregidas_con_fallback"]
            if fallback_diff <= 0.02 and primary_diff <= 0.02 and len(fallback_line_items) > len(primary_line_items):
                return fallback_line_items, ["lineas_enriquecidas_con_fallback"]

        if len(fallback_line_items) > len(primary_line_items) and fallback_sum > primary_sum:
            return fallback_line_items, ["lineas_enriquecidas_con_fallback"]

        return primary_line_items, []

    def _has_summary_leak_pattern(
        self,
        line_items: list[LineItem],
        *,
        base_amount: float = 0,
        total_amount: float = 0,
    ) -> bool:
        if len(line_items) < 2 or base_amount <= 0:
            return False

        reference_base = round(base_amount, 2)
        reference_total = round(total_amount, 2)
        line_sum = round(sum(line.importe for line in line_items if line.importe > 0), 2)
        if line_sum <= reference_base + 0.02:
            return False

        for line in line_items:
            amount = round(line.importe, 2)
            if amount <= 0:
                continue
            if abs(amount - reference_base) <= 0.02:
                return True
            if reference_total > 0 and abs(amount - reference_total) <= 0.02:
                return True

        return False

    def _normalize_amounts(self, data: InvoiceData) -> list[str]:
        warnings: list[str] = []
        line_sum = round(sum(line.importe for line in data.lineas if line.importe > 0), 2)
        withholding = round(max(0, data.retencion or 0), 2)

        if data.total > 0 and data.iva_porcentaje > 0 and data.base_imponible <= 0 and data.iva <= 0:
            divisor = 1 + (data.iva_porcentaje / 100)
            gross_total = round(data.total + withholding, 2) if withholding > 0 else data.total
            data.base_imponible = round(gross_total / divisor, 2)
            data.iva = round(gross_total - data.base_imponible, 2)
            warnings.append("base_e_iva_inferidos_desde_total_y_porcentaje")

        if data.total > 0 and data.base_imponible > 0 and data.iva <= 0:
            gross_total = round(data.total + withholding, 2) if withholding > 0 else data.total
            data.iva = round(max(0, gross_total - data.base_imponible), 2)
            warnings.append("iva_inferido_desde_total")

        if data.base_imponible > 0 and data.iva_porcentaje > 0:
            expected_iva = round(data.base_imponible * data.iva_porcentaje / 100, 2)
            if data.total > 0:
                expected_total = round(data.base_imponible + expected_iva - withholding, 2)
                current_diff = abs(round(data.base_imponible + data.iva - withholding, 2) - data.total)
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
            data.total = round(data.base_imponible + data.iva - withholding, 2)
            warnings.append("total_inferido_desde_base_e_iva")

        if data.total > 0 and data.iva > 0 and data.base_imponible <= 0:
            gross_total = round(data.total + withholding, 2) if withholding > 0 else data.total
            data.base_imponible = round(max(0, gross_total - data.iva), 2)
            warnings.append("base_inferida_desde_total_e_iva")

        summary_is_consistent = (
            data.base_imponible > 0
            and data.total > 0
            and (
                data.iva <= 0
                or abs(round(data.base_imponible + data.iva - withholding, 2) - data.total) <= 0.05
            )
        )
        summary_leak_suspected = self._has_summary_leak_pattern(
            data.lineas,
            base_amount=data.base_imponible,
            total_amount=data.total,
        )
        if line_sum > 0 and data.total > 0 and data.total + 0.02 < line_sum:
            if summary_is_consistent and summary_leak_suspected:
                warnings.append("lineas_inconsistentes_con_resumen_fiscal")
            else:
                data.base_imponible = line_sum
                if data.iva_porcentaje > 0:
                    data.iva = round(line_sum * data.iva_porcentaje / 100, 2)
                    data.total = round(data.base_imponible + data.iva - withholding, 2)
                    warnings.append("total_reconstruido_desde_lineas")
                else:
                    data.total = line_sum
                    warnings.append("total_ajustado_al_minimo_de_lineas")

        if data.total > 0 and data.base_imponible > 0 and data.iva > 0:
            expected_total = round(data.base_imponible + data.iva - withholding, 2)
            if abs(expected_total - data.total) > 0.02:
                if line_sum > 0 and abs(line_sum - data.base_imponible) <= 0.02:
                    data.total = expected_total
                    warnings.append("total_recalculado_desde_base_e_iva")

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
        withholding = round(max(0, data.retencion or 0), 2)

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
                gross_total = round(data.total + withholding, 2) if withholding > 0 else data.total
                candidates.append((line_sum, round(max(0, gross_total - line_sum), 2)))

        if data.total > 0 and data.iva > 0:
            gross_total = round(data.total + withholding, 2) if withholding > 0 else data.total
            candidates.append((round(max(0, gross_total - data.iva), 2), round(data.iva, 2)))

        if data.total > 0 and data.iva_porcentaje > 0:
            divisor = 1 + (data.iva_porcentaje / 100)
            gross_total = round(data.total + withholding, 2) if withholding > 0 else data.total
            inferred_base = round(gross_total / divisor, 2)
            candidates.append((inferred_base, round(gross_total - inferred_base, 2)))

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

            candidate_total = round(base_candidate + iva_candidate - withholding, 2)

            if data.total > 0 and abs(candidate_total - data.total) <= 0.02:
                score += 4
            elif data.total > 0 and abs(candidate_total - data.total) <= max(0.1, data.total * 0.02):
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
                total_distance += abs(candidate_total - data.total)
            if data.iva_porcentaje > 0:
                total_distance += abs(round(base_candidate * data.iva_porcentaje / 100, 2) - iva_candidate)
            if line_sum > 0:
                total_distance += abs(base_candidate - line_sum)

            return score, int(abs(base_candidate - line_sum) <= 0.02), -round(total_distance, 4)

        best_base, best_iva = max(filtered_candidates, key=lambda candidate: score_candidate(*candidate))
        return round(best_base, 2), round(best_iva, 2)

    def _extract_invoice_number_from_raw_text(self, raw_text: str) -> str:
        if not raw_text:
            return ""

        lines = [line.strip() for line in raw_text.splitlines() if line.strip()]
        label_pattern = re.compile(r"^(?:n[uú]mero|n[°ºo])\s*:?\s*$", re.IGNORECASE)
        candidate_pattern = re.compile(r"^[A-Z0-9/-]{4,30}$", re.IGNORECASE)

        for index, line in enumerate(lines):
            if not label_pattern.match(line):
                continue
            for candidate in lines[index + 1:index + 4]:
                cleaned = re.sub(r"\s+", "", candidate).strip(" .,:;")
                if candidate_pattern.match(cleaned) and self._looks_like_invoice_code(cleaned):
                    return cleaned
        return ""

    def _extract_retention_summary(self, raw_text: str) -> dict[str, float]:
        summary = {
            "base": 0.0,
            "tax_rate": 0.0,
            "tax_amount": 0.0,
            "withholding_rate": 0.0,
            "withholding_amount": 0.0,
            "gross_total": 0.0,
            "total_due": 0.0,
        }
        if not raw_text:
            return summary

        lines = [line.strip() for line in raw_text.splitlines() if line.strip()]
        normalized_lines = [re.sub(r"\s+", " ", line.lower()).strip(" .:;,-") for line in lines]
        compact_lines = [re.sub(r"[^a-z0-9]", "", line) for line in normalized_lines]

        def amount_candidates(window: list[str]) -> list[float]:
            values: list[float] = []
            for line in window:
                if "%" in line and "€" not in line and not re.search(r"\d{1,3}(?:[.,]\d{3})+[.,]\d{2}", line):
                    continue
                for match in re.findall(r"-?\d{1,3}(?:[.,]\d{3})*(?:[.,]\d{2})|-?\d{1,6}(?:[.,]\d{2})", line):
                    values.append(abs(parse_amount(match)))
            return [value for value in values if value > 0]

        def percent_candidates(window: list[str]) -> list[float]:
            values: list[float] = []
            for line in window:
                compact = re.sub(r"[^a-z0-9]", "", line.lower())
                if "%" not in line and "igic" not in compact and "irpf" not in compact and "reten" not in compact:
                    continue
                for match in re.findall(r"\d{1,2}(?:[.,]\d{1,2})?", line):
                    values.append(float(match.replace(",", ".")))
            return values

        for index, compact_line in enumerate(compact_lines):
            previous_window = list(reversed(lines[max(0, index - 3):index]))
            next_window = lines[index + 1:index + 4]

            if compact_line == "totalfactura":
                amounts = amount_candidates(previous_window) + amount_candidates(next_window)
                if amounts:
                    summary["total_due"] = amounts[0]
            elif compact_line == "total":
                amounts = amount_candidates(previous_window) + amount_candidates(next_window)
                if amounts:
                    summary["gross_total"] = amounts[0]
            elif compact_line in {"igic", "iva"}:
                amounts = amount_candidates(previous_window) + amount_candidates(next_window)
                percents = [value for value in percent_candidates(previous_window + next_window) if 0 < value <= 21]
                if amounts:
                    summary["tax_amount"] = amounts[0]
                if percents:
                    summary["tax_rate"] = percents[0]
            elif "retenc" in compact_line or "irpf" in compact_line:
                amounts = amount_candidates(previous_window) + amount_candidates(next_window)
                percents = [value for value in percent_candidates(previous_window + next_window) if 0 < value <= 25]
                if amounts:
                    summary["withholding_amount"] = amounts[0]
                if percents:
                    summary["withholding_rate"] = percents[0]

        if (
            summary["gross_total"] > 0
            and summary["tax_amount"] > 0
            and summary["withholding_amount"] > 0
            and summary["total_due"] > 0
        ):
            if abs(summary["gross_total"] + summary["tax_amount"] - summary["withholding_amount"] - summary["total_due"]) <= 0.2:
                summary["base"] = summary["gross_total"]
                summary["gross_total"] = round(summary["base"] + summary["tax_amount"], 2)
            else:
                summary["base"] = round(summary["total_due"] + summary["withholding_amount"] - summary["tax_amount"], 2)
                summary["gross_total"] = round(summary["base"] + summary["tax_amount"], 2)
        elif summary["gross_total"] <= 0 and summary["total_due"] > 0 and summary["withholding_amount"] > 0:
            summary["gross_total"] = round(summary["total_due"] + summary["withholding_amount"], 2)
        if summary["base"] <= 0 and summary["gross_total"] > 0 and summary["tax_amount"] > 0:
            summary["base"] = round(summary["gross_total"] - summary["tax_amount"], 2)

        return summary

    def _extract_parties_from_raw_text(self, raw_text: str) -> dict[str, str]:
        result = {
            "proveedor": "",
            "cif_proveedor": "",
            "cliente": "",
            "cif_cliente": "",
        }
        if not raw_text:
            return result

        lines = [line.strip() for line in raw_text.splitlines() if line.strip()]
        normalized_lines = [re.sub(r"\s+", " ", line).strip() for line in lines]
        compact_lines = [re.sub(r"[^A-Z0-9]", "", line.upper()) for line in normalized_lines]

        cliente_index = next((i for i, compact in enumerate(compact_lines) if compact == "CLIENTE"), -1)
        cif_index = next((i for i, compact in enumerate(compact_lines) if compact in {"CIF", "CIFNIF"}), -1)

        if cliente_index > 0:
            candidate = normalized_lines[cliente_index - 1]
            if candidate and "DOMICILIO" not in candidate.upper():
                result["cliente"] = candidate

        if cif_index >= 0:
            for candidate in normalized_lines[cif_index + 1:cif_index + 4]:
                tax_ids = re.findall(r"[A-Z]\d{7}[A-Z0-9]|\d{8}[A-Z]", re.sub(r"[\s.\-]", "", candidate.upper()))
                if tax_ids:
                    result["cif_cliente"] = tax_ids[0]
                    break

        top_limit = cliente_index if cliente_index > 0 else min(len(normalized_lines), 8)
        for index in range(top_limit):
            candidate = normalized_lines[index]
            compact = compact_lines[index]
            if not candidate or compact in {"FACTURA", "NUMERO", "FECHA"}:
                continue
            tax_ids = re.findall(r"[A-Z]\d{7}[A-Z0-9]|\d{8}[A-Z]", re.sub(r"[\s.\-]", "", candidate.upper()))
            if tax_ids and not result["cif_proveedor"]:
                result["cif_proveedor"] = tax_ids[0]
                continue
            if (
                not result["proveedor"]
                and len(candidate.split()) >= 2
                and not any(token in candidate.upper() for token in ("FACTURA", "NÚMERO", "FECHA"))
                and not self._looks_like_address_or_contact_line(candidate)
                and not self._is_generic_party_candidate(candidate)
            ):
                result["proveedor"] = candidate

        return result

    def _has_structured_tax_summary(self, raw_text: str) -> bool:
        upper_text = raw_text.upper()
        has_total = "TOTAL" in upper_text
        has_tax = "IMPUESTOS" in upper_text or "CUOTA" in upper_text
        has_base = (
            "SUBTOTAL" in upper_text
            or "BASE IMPONIBLE" in upper_text
            or "\nBASE\n" in upper_text
        )
        return has_total and has_tax and has_base

    def _amounts_are_coherent(self, invoice: InvoiceData) -> bool:
        if abs(invoice.base_imponible) <= 0 or abs(invoice.total) <= 0:
            return False

        sign = -1 if invoice.base_imponible < 0 or invoice.total < 0 or invoice.iva < 0 else 1
        withholding = round(max(0, abs(invoice.retencion or 0)), 2)

        if abs(invoice.iva) > 0:
            expected_total = round(invoice.base_imponible + invoice.iva - (withholding * sign), 2)
            return abs(expected_total - invoice.total) <= 0.05

        if invoice.iva_porcentaje > 0:
            expected_tax = round(abs(invoice.base_imponible) * invoice.iva_porcentaje / 100, 2) * sign
            expected_total = round(invoice.base_imponible + expected_tax - (withholding * sign), 2)
            return abs(expected_total - invoice.total) <= 0.05

        return False

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

    def _normalize_party_name(self, value: str) -> str:
        cleaned = re.sub(r"\s+", " ", (value or "").strip()).strip(" .,:;-")
        if not cleaned:
            return ""

        normalized_token = re.sub(r"[^A-Z0-9]", "", cleaned.upper())
        blocked_tokens = {
            "CLIENTE",
            "EMISOR",
            "PROVEEDOR",
            "DESTINATARIO",
            "COMPRADOR",
            "FACTURA",
        }
        if normalized_token in blocked_tokens:
            return ""

        letters = sum(char.isalpha() for char in cleaned)
        digits = sum(char.isdigit() for char in cleaned)
        if letters < 3 or digits > max(3, letters):
            return ""
        return cleaned[:200]

    def _normalize_tax_id_value(self, primary: str, fallback: str, *, role: str) -> tuple[str, list[str]]:
        warnings: list[str] = []
        current = self._clean_tax_id(primary)
        fallback_clean = self._clean_tax_id(fallback)

        repaired_current, current_was_repaired = self._repair_tax_id_candidate(current)
        repaired_fallback, _ = self._repair_tax_id_candidate(fallback_clean)
        fallback_candidate = repaired_fallback if self._is_valid_tax_id(repaired_fallback) else fallback_clean

        if self._is_valid_tax_id(current) and not current_was_repaired:
            return current, warnings

        if self._is_valid_tax_id(fallback_candidate):
            warnings.append(f"cif_{role}_corregido_con_fallback")
            return fallback_candidate, warnings

        if self._is_valid_tax_id(repaired_current):
            if current_was_repaired:
                warnings.append(f"cif_{role}_reparado_ocr")
            return repaired_current, warnings

        if current:
            warnings.append(f"cif_{role}_no_valido")
        return current, warnings

    def _clean_tax_id(self, value: str) -> str:
        if not value:
            return ""
        cleaned = re.sub(r"[\s\-]", "", value.upper())
        replacements = {
            "€": "E",
            "£": "E",
            "|": "I",
        }
        for source, target in replacements.items():
            cleaned = cleaned.replace(source, target)
        return cleaned

    def _repair_tax_id_candidate(self, value: str) -> tuple[str, bool]:
        cleaned = self._clean_tax_id(value)
        if not cleaned or self._is_valid_tax_id(cleaned):
            return cleaned, False

        if len(cleaned) != 9:
            return cleaned, False

        digit_map = {
            "O": "0",
            "Q": "0",
            "D": "0",
            "I": "1",
            "L": "1",
            "Z": "2",
            "S": "5",
            "G": "6",
            "B": "8",
        }
        alpha_map = {
            "0": "O",
            "1": "I",
            "2": "Z",
            "5": "S",
            "6": "G",
            "8": "B",
        }

        has_ocr_noise_in_numeric_positions = any(char in digit_map for char in cleaned[1:8])
        if has_ocr_noise_in_numeric_positions or cleaned[0] in {"£", "€"}:
            cif_candidate = "".join(
                alpha_map.get(char, char) if index == 0 else digit_map.get(char, char) if 0 < index < 8 else char
                for index, char in enumerate(cleaned)
            )
            if self._is_valid_tax_id(cif_candidate):
                return cif_candidate, True

        if cleaned[-1].isalpha():
            nif_candidate = "".join(
                digit_map.get(char, char) if index < 8 else char
                for index, char in enumerate(cleaned)
            )
            if self._is_valid_tax_id(nif_candidate):
                return nif_candidate, True

            nie_candidate = "".join(
                ("X" if index == 0 and char in {"1", "I"} else alpha_map.get(char, char) if index == 0 else digit_map.get(char, char) if index < 8 else char)
                for index, char in enumerate(cleaned)
            )
            if self._is_valid_tax_id(nie_candidate):
                return nie_candidate, True

        return cleaned, False


document_intelligence_service = DocumentIntelligenceService()
