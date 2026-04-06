"""Tests for document intelligence service."""

from unittest.mock import AsyncMock, patch

from app.models.document_bundle import DocumentBundle, DocumentPageBundle, LayoutRegion
from app.models.extraction_result import DecisionFlag, ExtractionCoverage
from app.models.invoice_model import InvoiceData, LineItem
from app.services.document_intelligence import DocumentIntelligenceService
from app.services.document_semantic_resolver import document_semantic_resolver
from app.services.evidence_builder import evidence_builder
from app.services.text_resolution.amounts import amount_resolution_service
from app.services.text_resolution.line_items import line_item_resolution_service
from app.services.text_resolution.normalization import invoice_normalization_service
from app.services.text_resolution.party_resolution import party_resolution_service
from app.services.text_resolution.region_hint_rescue import region_hint_rescue_service
from app.services.text_resolution.result_building import document_result_builder
from app.config import settings


class TestDocumentIntelligenceService:

    def test_parse_json_payload_from_text_block(self):
        service = DocumentIntelligenceService()
        payload = [
            {
                "type": "text",
                "text": '```json\n{"numero_factura":"F-1","total":121}\n```',
            }
        ]

        result = service._parse_json_payload(payload)

        assert result["numero_factura"] == "F-1"
        assert result["total"] == 121

    def test_merge_with_fallback_fills_missing_fields(self):
        service = DocumentIntelligenceService()
        primary = InvoiceData(numero_factura="", total=0)
        fallback = InvoiceData(numero_factura="F-2026-1", total=121)

        result = service._merge_with_fallback(primary, fallback)

        assert result.numero_factura == "F-2026-1"
        assert result.total == 121

    def test_response_schema_contains_expected_fields(self):
        service = DocumentIntelligenceService()

        schema = service._response_schema()

        assert schema["type"] == "object"
        assert "numero_factura" in schema["properties"]
        assert "lineas" in schema["properties"]

    def test_normalize_invoice_data_repairs_invalid_amounts_and_ids(self):
        service = DocumentIntelligenceService()
        primary = InvoiceData(
            cif_proveedor="876543210",
            base_imponible=213,
            iva_porcentaje=21,
            iva=447.3,
            total=257.73,
            lineas=[
                {"descripcion": "VPN", "cantidad": 0, "precio_unitario": 95, "importe": 0},
                {"descripcion": "Soporte", "cantidad": 0, "precio_unitario": 48, "importe": 0},
            ],
        )
        fallback = InvoiceData(cif_proveedor="E9988776A")

        normalized, warnings = invoice_normalization_service.normalize_invoice_data(primary, fallback)

        assert normalized.cif_proveedor == "E9988776A"
        assert normalized.iva == 44.73
        assert normalized.lineas[0].cantidad == 1
        assert normalized.lineas[0].importe == 95
        assert "cif_proveedor_corregido_con_fallback" in warnings
        assert "iva_recalculado_desde_porcentaje" in warnings

    def test_normalize_invoice_data_clears_ticket_customer_and_ignores_payment_totals(self):
        primary = InvoiceData(
            numero_factura="2026/900213-00004245",
            proveedor="DINOSOL SUPERMERCADOS, S.L.",
            cif_proveedor="B61742565",
            cliente="",
            cif_cliente="",
            total=8.50,
            base_imponible=0.0,
            iva=0.0,
            iva_porcentaje=0.0,
        )
        fallback = InvoiceData(
            cliente="No especificado",
            total=50.0,
            base_imponible=8.50,
            iva=41.50,
            iva_porcentaje=488.24,
        )
        raw_text = """
        DINOSOL SUPERMERCADOS, S.L.
        C.I.F.: B61742565
        Documento
        2026/900213-00004245
        ARTICULO
        HIPERDINO CAFE SOLUBLE DESCAFEIN B 2
        4,80
        TIRMA CAFE MEZCLA SUAVE 250GRS
        3,70
        TOTAL COMPRA:
        8,50
        TOTAL ENTREGADO:
        50,00
        A DEVOLVER:
        41,50
        DOCUMENTO DE VENTA
        FACTURA SIMPLIFICADA
        """

        normalized, warnings = invoice_normalization_service.normalize_invoice_data(
            primary,
            fallback,
            raw_text=raw_text,
        )

        assert normalized.cliente == ""
        assert normalized.cif_cliente == ""
        assert normalized.total == 8.50
        assert normalized.iva == 0.0
        assert normalized.iva_porcentaje == 0.0
        assert "familia_ticket_cliente_descartado" in warnings

    def test_normalize_invoice_data_restores_explicit_ticket_tax_summary_after_line_reconstruction(self):
        primary = InvoiceData(
            numero_factura="TO01-1235663",
            proveedor="HOSTELERIA GRESSARA, S.L.",
            cif_proveedor="B35590736",
            cliente="C.C. LAS ARENAS-1fno:328 221 471",
            cif_cliente="O01123566",
            base_imponible=18.70,
            iva_porcentaje=21.0,
            iva=3.93,
            total=22.63,
            lineas=[
                LineItem(descripcion="PEQUEÑA AGUA SIN G", cantidad=1.0, precio_unitario=1.20, importe=1.20),
                LineItem(descripcion="RACION CROQUETAS D", cantidad=1.0, precio_unitario=7.50, importe=7.50),
                LineItem(descripcion="1/2 RACION PESCADO", cantidad=1.0, precio_unitario=8.00, importe=8.00),
                LineItem(descripcion="ENVASES PARA LLEVA", cantidad=1.0, precio_unitario=0.40, importe=0.40),
            ],
        )
        fallback = InvoiceData()
        raw_text = """
        HOSTELERIA GRESSARA, S.L.
        CIF: B-35590736
        FRA. SIMPLIFICADA
        TO01-1235663 FECHA09/01/2025
        UDS
        DESCRIPCION SALA 1
        1
        PEQUEÑA AGUA SIN G
        1,20
        1,20
        1
        RACION CROQUETAS D
        7,50
        7,50
        1
        1/2 RACION PESCADO
        8,00
        8,00
        1
        ENVASES PARA LLEVA
        0,40
        0,40
        TOTAL 17,10
        ENTREGADO 17,10
        CAMBIO 0,00
        I.G.I.C. INCLUIDO
        BASE 15,98 CUOTA 1,12
        """

        normalized, warnings = invoice_normalization_service.normalize_invoice_data(
            primary,
            fallback,
            raw_text=raw_text,
        )

        assert normalized.cliente == ""
        assert normalized.cif_cliente == ""
        assert normalized.base_imponible == 15.98
        assert normalized.iva == 1.12
        assert normalized.total == 17.10
        assert "familia_ticket_total_corregido" in warnings

    def test_infer_tax_regime_detects_igic_from_text(self):
        service = DocumentIntelligenceService()
        invoice = InvoiceData(base_imponible=100, iva=7, iva_porcentaje=7)

        result = document_result_builder.infer_tax_regime("Factura con IGIC general al 7%", invoice)

        assert result == "IGIC"

    def test_build_extraction_coverage_reports_missing_priority_fields(self):
        service = DocumentIntelligenceService()
        invoice = InvoiceData(
            numero_factura="F-2026-001",
            tipo_factura="compra",
            fecha="2026-03-15",
            proveedor="Proveedor Demo SL",
            cif_proveedor="B12345678",
            base_imponible=100,
            iva=7,
            iva_porcentaje=7,
            total=107,
            lineas=[{"descripcion": "Servicio", "cantidad": 1, "precio_unitario": 100, "importe": 100}],
            confianza=0.8,
        )

        normalized = document_result_builder.build_extraction_document(
            invoice=invoice,
            raw_text="Factura con IGIC general al 7%",
            filename="factura.pdf",
            mime_type="application/pdf",
            pages=1,
            input_profile={
                "input_kind": "pdf_digital",
                "text_source": "digital_text",
                "ocr_engine": "",
                "preprocessing_steps": ["pdf_text_extraction"],
            },
            provider="ollama",
            method="doc_ai",
            warnings=[],
        )

        coverage = document_result_builder.build_extraction_coverage(normalized)

        assert coverage.completeness_ratio == 0.9
        assert coverage.missing_required_fields == ["classification.invoice_side"]
        assert normalized.document_meta.input_kind == "pdf_digital"
        assert normalized.document_meta.text_source == "digital_text"
        assert normalized.document_meta.page_count == 1

    def test_build_extraction_document_extracts_due_date_payment_and_iban(self):
        service = DocumentIntelligenceService()
        invoice = InvoiceData(
            numero_factura="F-2026-001",
            tipo_factura="compra",
            fecha="2026-03-15",
            proveedor="Proveedor Demo SL",
            cif_proveedor="B12345678",
            base_imponible=100,
            iva=21,
            iva_porcentaje=21,
            total=121,
            confianza=0.8,
        )

        normalized = document_result_builder.build_extraction_document(
            invoice=invoice,
            raw_text=(
                "Factura\n"
                "Fecha vencimiento: 31/03/2026\n"
                "Forma de pago: Transferencia bancaria\n"
                "Transferencia a ES12 2100 1234 5602 0000 9988\n"
            ),
            filename="factura.pdf",
            mime_type="application/pdf",
            pages=1,
            input_profile={
                "input_kind": "pdf_scanned",
                "text_source": "ocr",
                "ocr_engine": "tesseract",
                "preprocessing_steps": ["pdf_page_render", "ocr_variant:balanced_binary"],
            },
            provider="ollama",
            method="doc_ai",
            warnings=[],
        )

        assert normalized.identity.due_date == "2026-03-31"
        assert normalized.payment_info.payment_method == "Transferencia"
        assert normalized.payment_info.iban == "ES1221001234560200009988"

    def test_normalize_amounts_infers_base_and_tax_from_total_and_rate(self):
        service = DocumentIntelligenceService()
        invoice = InvoiceData(
            total=107,
            iva_porcentaje=7,
            base_imponible=0,
            iva=0,
        )

        warnings = amount_resolution_service.normalize_amounts(invoice)

        assert invoice.base_imponible == 100
        assert invoice.iva == 7
        assert "base_e_iva_inferidos_desde_total_y_porcentaje" in warnings

    def test_normalize_amounts_prefers_line_sum_when_it_best_matches_total(self):
        service = DocumentIntelligenceService()
        invoice = InvoiceData(
            base_imponible=337.59,
            iva_porcentaje=21,
            iva=70.89,
            total=337.59,
            lineas=[
                {"descripcion": "Firewall", "cantidad": 1, "precio_unitario": 149, "importe": 149},
                {"descripcion": "Copias", "cantidad": 1, "precio_unitario": 58, "importe": 58},
                {"descripcion": "Mantenimiento", "cantidad": 1, "precio_unitario": 72, "importe": 72},
            ],
        )

        warnings = amount_resolution_service.normalize_amounts(invoice)

        assert invoice.base_imponible == 279
        assert invoice.iva == 58.59
        assert "base_reconciliada_con_lineas" in warnings

    def test_normalize_amounts_rebuilds_total_when_total_is_lower_than_line_sum(self):
        service = DocumentIntelligenceService()
        invoice = InvoiceData(
            base_imponible=150.65,
            iva_porcentaje=21,
            iva=31.64,
            total=182.29,
            lineas=[
                {"descripcion": "Firewall", "cantidad": 1, "precio_unitario": 149, "importe": 149},
                {"descripcion": "Copias", "cantidad": 1, "precio_unitario": 58, "importe": 58},
                {"descripcion": "Mantenimiento", "cantidad": 1, "precio_unitario": 72, "importe": 72},
            ],
        )

        warnings = amount_resolution_service.normalize_amounts(invoice)

        assert invoice.base_imponible == 279
        assert invoice.iva == 58.59
        assert invoice.total == 337.59
        assert "total_reconstruido_desde_lineas" in warnings

    def test_repair_summary_leak_lines_adjusts_last_line_residual(self):
        service = DocumentIntelligenceService()
        line_items = [
            LineItem(descripcion="Plataforma Web DicRM. Incluye Hosting y Asistenca", cantidad=1, precio_unitario=143.85, importe=143.85),
            LineItem(descripcion="Mantenimiento de la Página Web y del dominio. Incluye Hosting", cantidad=1, precio_unitario=114.00, importe=114.00),
            LineItem(descripcion="Otros", cantidad=1, precio_unitario=54.00, importe=54.00),
            LineItem(descripcion="Dipresencia", cantidad=1, precio_unitario=312.85, importe=312.85),
        ]

        repaired, warnings = line_item_resolution_service.repair_summary_leak_lines(
            line_items,
            base_amount=312.85,
            total_amount=334.75,
        )

        assert repaired[-1].descripcion == "Dipresencia"
        assert repaired[-1].importe == 1.00
        assert repaired[-1].precio_unitario == 1.00
        assert "linea_4_importe_ajustado_desde_resumen" in warnings

    def test_prefer_fallback_line_items_when_they_match_base_better(self):
        service = DocumentIntelligenceService()
        primary = [
            LineItem(descripcion="Plataforma", cantidad=1, precio_unitario=143.85, importe=143.85),
            LineItem(descripcion="Mantenimiento", cantidad=1, precio_unitario=114.00, importe=114.00),
            LineItem(descripcion="Otros", cantidad=1, precio_unitario=1.00, importe=1.00),
        ]
        fallback = [
            LineItem(descripcion="Plataforma", cantidad=1, precio_unitario=143.85, importe=143.85),
            LineItem(descripcion="Mantenimiento", cantidad=1, precio_unitario=114.00, importe=114.00),
            LineItem(descripcion="Otros", cantidad=1, precio_unitario=54.00, importe=54.00),
            LineItem(descripcion="Dipresencia", cantidad=1, precio_unitario=1.00, importe=1.00),
        ]

        selected, warnings = line_item_resolution_service.prefer_fallback_line_items(
            primary_line_items=primary,
            fallback_line_items=fallback,
            base_amount=312.85,
        )

        assert len(selected) == 4
        assert round(sum(line.importe for line in selected), 2) == 312.85
        assert "lineas_corregidas_con_fallback" in warnings

    def test_prefer_fallback_line_items_when_descriptions_are_clearly_richer(self):
        primary = [
            LineItem(descripcion="Continuidad", cantidad=1, precio_unitario=81.0, importe=81.0),
        ]
        fallback = [
            LineItem(descripcion="Continuidad - Tributos", cantidad=1, precio_unitario=81.0, importe=81.0),
        ]

        selected, warnings = line_item_resolution_service.prefer_fallback_line_items(
            primary_line_items=primary,
            fallback_line_items=fallback,
            base_amount=81.0,
        )

        assert len(selected) == 1
        assert selected[0].descripcion == "Continuidad - Tributos"
        assert "lineas_descripcion_mejorada_con_fallback" in warnings

    def test_keep_primary_line_items_when_fallback_description_is_not_better(self):
        primary = [
            LineItem(descripcion="Mantenimiento del Programa de Facturación Facdis", cantidad=1, precio_unitario=-25.0, importe=-25.0),
        ]
        fallback = [
            LineItem(descripcion="Mantenimiento Faodis", cantidad=1, precio_unitario=-25.0, importe=-25.0),
        ]

        selected, warnings = line_item_resolution_service.prefer_fallback_line_items(
            primary_line_items=primary,
            fallback_line_items=fallback,
            base_amount=25.0,
        )

        assert len(selected) == 1
        assert selected[0].descripcion == "Mantenimiento del Programa de Facturación Facdis"
        assert warnings == []

    def test_normalize_amounts_keeps_consistent_summary_when_lines_are_higher(self):
        service = DocumentIntelligenceService()
        invoice = InvoiceData(
            base_imponible=312.85,
            iva_porcentaje=7,
            iva=21.90,
            total=334.75,
            lineas=[
                {"descripcion": "Plataforma", "cantidad": 1, "precio_unitario": 143.85, "importe": 143.85},
                {"descripcion": "Mantenimiento", "cantidad": 1, "precio_unitario": 114.00, "importe": 114.00},
                {"descripcion": "Otros", "cantidad": 1, "precio_unitario": 54.00, "importe": 54.00},
                {"descripcion": "Dipresencia", "cantidad": 1, "precio_unitario": 312.85, "importe": 312.85},
            ],
        )

        warnings = amount_resolution_service.normalize_amounts(invoice)

        assert invoice.base_imponible == 312.85
        assert invoice.iva == 21.90
        assert invoice.total == 334.75
        assert "lineas_inconsistentes_con_resumen_fiscal" in warnings

    def test_infer_tax_regime_uses_rate_when_text_is_ambiguous(self):
        service = DocumentIntelligenceService()

        assert document_result_builder.infer_tax_regime("Factura de servicios", InvoiceData(iva_porcentaje=7)) == "IGIC"
        assert document_result_builder.infer_tax_regime("Factura de servicios", InvoiceData(iva_porcentaje=21)) == "IVA"

    def test_infer_tax_regime_prefers_unique_igic_rate_over_spurious_iva_text(self):
        service = DocumentIntelligenceService()

        result = document_result_builder.infer_tax_regime(
            "Factura rectificativa\nIVA incluido\ncuota\n",
            InvoiceData(iva_porcentaje=7, iva=-1.75),
        )

        assert result == "IGIC"

    def test_compare_source_candidates_flags_meaningful_discrepancies(self):
        service = DocumentIntelligenceService()
        heuristic = InvoiceData(
            numero_factura="FAC-1",
            proveedor="Proveedor Bueno SL",
            cif_proveedor="B12345678",
            total=121,
        )
        ai_candidate = InvoiceData(
            numero_factura="FAC-9",
            proveedor="Otro Proveedor SL",
            cif_proveedor="B12345678",
            total=131,
        )

        warnings = document_result_builder.compare_source_candidates(ai_candidate, heuristic)

        assert "discrepancia_numero_factura" in warnings
        assert "discrepancia_proveedor" in warnings
        assert "discrepancia_total" in warnings

    def test_build_field_confidence_rewards_source_agreement(self):
        service = DocumentIntelligenceService()
        final = InvoiceData(
            numero_factura="FAC-1",
            fecha="2026-03-19",
            proveedor="Proveedor Demo SL",
            cif_proveedor="B12345678",
            total=121,
            base_imponible=100,
            iva_porcentaje=21,
            iva=21,
            lineas=[{"descripcion": "Servicio", "cantidad": 1, "precio_unitario": 100, "importe": 100}],
        )
        heuristic = final.model_copy(deep=True)
        ai_candidate = final.model_copy(deep=True)

        field_confidence = document_result_builder.build_field_confidence(
            final=final,
            heuristic=heuristic,
            ai_candidate=ai_candidate,
        )

        assert field_confidence["numero_factura"] >= 0.9
        assert field_confidence["cif_proveedor"] >= 0.9
        assert field_confidence["lineas"] >= 0.8

    def test_build_field_confidence_drops_when_sources_disagree(self):
        service = DocumentIntelligenceService()
        final = InvoiceData(
            numero_factura="FAC-1",
            proveedor="Proveedor Demo SL",
            total=121,
            base_imponible=100,
            iva_porcentaje=21,
            iva=21,
        )
        heuristic = InvoiceData(
            numero_factura="FAC-9",
            proveedor="Otro Proveedor SL",
            total=131,
        )
        ai_candidate = InvoiceData(
            numero_factura="FAC-8",
            proveedor="Proveedor Dudoso SL",
            total=141,
        )

        field_confidence = document_result_builder.build_field_confidence(
            final=final,
            heuristic=heuristic,
            ai_candidate=ai_candidate,
        )

        assert field_confidence["numero_factura"] < 0.6
        assert field_confidence["proveedor"] < 0.6
        assert field_confidence["total"] < 0.6

    def test_refine_document_confidence_penalizes_critical_warnings_and_low_fields(self):
        service = DocumentIntelligenceService()
        invoice = InvoiceData(
            numero_factura="FI202600043",
            fecha="2026-01-07",
            proveedor="DISOFT SERVICIOS INFORMATICOS SL",
            cif_proveedor="J76022912",
            cliente="ASESORES, S.C.PROFESIONAL",
            cif_cliente="B35222249",
            base_imponible=312.85,
            iva_porcentaje=7,
            iva=21.90,
            total=334.75,
            lineas=[
                {"descripcion": "Linea 1", "cantidad": 1, "precio_unitario": 143.85, "importe": 143.85},
                {"descripcion": "Linea 2", "cantidad": 1, "precio_unitario": 114.00, "importe": 114.00},
                {"descripcion": "Linea 3", "cantidad": 1, "precio_unitario": 54.00, "importe": 54.00},
            ],
            confianza=1.0,
        )

        score = document_result_builder.refine_document_confidence(
            invoice=invoice,
            current_confidence=1.0,
            field_confidence={
                "numero_factura": 1.0,
                "fecha": 1.0,
                "proveedor": 1.0,
                "cif_proveedor": 0.6,
                "cliente": 0.65,
                "cif_cliente": 0.65,
                "base_imponible": 1.0,
                "iva_porcentaje": 0.65,
                "iva": 0.65,
                "total": 1.0,
                "lineas": 0.7,
            },
            warnings=["discrepancia_cif_proveedor", "discrepancia_lineas"],
        )

        assert 0.7 <= score < 0.9

    def test_refine_document_confidence_keeps_corrected_coherent_invoice_reasonably_high(self):
        service = DocumentIntelligenceService()
        invoice = InvoiceData(
            numero_factura="GC 26001163",
            fecha="2026-03-06",
            proveedor="Alberto Villacorta, S.L.U",
            cif_proveedor="B35246388",
            cliente="Disoft Servicios Informaticos SL",
            cif_cliente="B35222249",
            base_imponible=25.00,
            iva_porcentaje=7.0,
            iva=1.75,
            total=26.75,
            lineas=[
                {"descripcion": "Antivirus", "cantidad": 1, "precio_unitario": 25.00, "importe": 25.00},
            ],
            confianza=1.0,
        )

        score = document_result_builder.refine_document_confidence(
            invoice=invoice,
            current_confidence=1.0,
            field_confidence={
                "numero_factura": 1.0,
                "fecha": 1.0,
                "proveedor": 0.55,
                "cif_proveedor": 0.55,
                "cliente": 0.65,
                "cif_cliente": 0.65,
                "base_imponible": 0.55,
                "iva_porcentaje": 0.65,
                "iva": 0.65,
                "total": 1.0,
                "lineas": 1.0,
            },
            warnings=[
                "discrepancia_proveedor",
                "discrepancia_cif_proveedor",
                "discrepancia_base_imponible",
                "proveedor_desambiguado_con_fallback",
                "cif_proveedor_corregido_con_fallback",
                "base_reconciliada_con_lineas",
            ],
        )

        assert score >= 0.72

    def test_refine_document_confidence_does_not_collapse_for_coherent_ticket_without_customer(self):
        invoice = InvoiceData(
            numero_factura="T001-1235663",
            fecha="2025-01-09",
            proveedor="HOSTELERIA GRESSARA, S.L.",
            cif_proveedor="",
            cliente="",
            cif_cliente="",
            base_imponible=15.98,
            iva_porcentaje=7.01,
            iva=1.12,
            total=17.10,
            lineas=[
                {"descripcion": "PEQUENA AGUA", "cantidad": 1, "precio_unitario": 1.20, "importe": 1.20},
                {"descripcion": "RACION CROQUETAS", "cantidad": 1, "precio_unitario": 7.50, "importe": 7.50},
                {"descripcion": "1/2 RACION PESCADO", "cantidad": 1, "precio_unitario": 8.00, "importe": 8.00},
                {"descripcion": "ENVASES PARA LLEVAR", "cantidad": 1, "precio_unitario": 0.40, "importe": 0.40},
            ],
            confianza=0.61,
        )

        score = document_result_builder.refine_document_confidence(
            invoice=invoice,
            current_confidence=0.61,
            field_confidence={
                "numero_factura": 0.95,
                "fecha": 0.95,
                "proveedor": 0.95,
                "cif_proveedor": 0.0,
                "cliente": 0.0,
                "cif_cliente": 0.0,
                "base_imponible": 0.6,
                "iva_porcentaje": 0.6,
                "iva": 0.6,
                "total": 0.6,
                "lineas": 0.54,
            },
            warnings=[
                "iva_porcentaje_corregido_por_texto_igic",
                "lineas_enriquecidas_con_fallback",
                "iva_recalculado_desde_porcentaje",
                "total_reconstruido_desde_lineas",
                "importes_corregidos_con_resumen_fallback",
            ],
        )

        assert score >= 0.4

    def test_refine_document_confidence_penalizes_semantic_role_conflicts(self):
        invoice = InvoiceData(
            numero_factura="FAC-SEM-1",
            fecha="2026-03-19",
            proveedor="Proveedor Demo SL",
            cif_proveedor="B12345678",
            cliente="Cliente Demo SL",
            cif_cliente="B12345678",
            base_imponible=100.0,
            iva_porcentaje=21.0,
            iva=21.0,
            total=121.0,
            lineas=[{"descripcion": "Servicio", "cantidad": 1, "precio_unitario": 100.0, "importe": 100.0}],
        )

        score = document_result_builder.refine_document_confidence(
            invoice=invoice,
            current_confidence=1.0,
            field_confidence={
                "numero_factura": 1.0,
                "fecha": 1.0,
                "proveedor": 0.95,
                "cif_proveedor": 0.95,
                "cliente": 0.95,
                "cif_cliente": 0.95,
                "base_imponible": 1.0,
                "iva_porcentaje": 1.0,
                "iva": 1.0,
                "total": 1.0,
                "lineas": 1.0,
            },
            warnings=[],
            company_match={"matched_role": "ambiguous", "issuer_matches_company": True, "recipient_matches_company": True},
        )

        assert score <= 0.64

    def test_build_decision_flags_marks_same_tax_id_on_both_roles_for_review(self):
        flags = evidence_builder.build_decision_flags(
            invoice=InvoiceData(
                numero_factura="FAC-SEM-2",
                fecha="2026-03-19",
                proveedor="Proveedor Demo SL",
                cif_proveedor="B12345678",
                cliente="Cliente Demo SL",
                cif_cliente="B12345678",
                total=121.0,
            ),
            field_confidence={
                "numero_factura": 1.0,
                "fecha": 1.0,
                "proveedor": 0.95,
                "cif_proveedor": 0.95,
                "cliente": 0.95,
                "cif_cliente": 0.95,
                "total": 1.0,
            },
            warnings=[],
            company_match={"issuer_matches_company": False, "recipient_matches_company": False},
        )

        codes = {flag.code for flag in flags}

        assert "same_tax_id_both_roles" in codes

    def test_normalize_invoice_data_replaces_generic_party_names_with_fallback(self):
        service = DocumentIntelligenceService()
        primary = InvoiceData(
            proveedor="CLIENTE",
            cliente="EMISOR",
            total=121,
        )
        fallback = InvoiceData(
            proveedor="Proveedor Demo SL",
            cliente="Empresa Cliente SL",
        )

        normalized, warnings = invoice_normalization_service.normalize_invoice_data(primary, fallback)

        assert normalized.proveedor == "Proveedor Demo SL"
        assert normalized.cliente == "Empresa Cliente SL"
        assert "proveedor_corregido_con_fallback" in warnings
        assert "cliente_corregido_con_fallback" in warnings

    def test_normalize_tax_id_repairs_common_ocr_confusions(self):
        service = DocumentIntelligenceService()

        normalized_value, warnings = party_resolution_service.normalize_tax_id_value(
            "8I2345678",
            "",
            role="proveedor",
        )

        assert normalized_value == "B12345678"
        assert "cif_proveedor_reparado_ocr" in warnings

    def test_normalize_tax_id_warns_when_value_stays_invalid(self):
        service = DocumentIntelligenceService()

        normalized_value, warnings = party_resolution_service.normalize_tax_id_value(
            "255687788",
            "",
            role="cliente",
        )

        assert normalized_value == "255687788"
        assert "cif_cliente_no_valido" in warnings

    def test_normalize_invoice_data_prefers_fallback_invoice_number_and_igic_rate(self):
        service = DocumentIntelligenceService()
        primary = InvoiceData(
            numero_factura="2",
            fecha="2026-01-07",
            proveedor="DISOFT SERVICIOS INFORMATICOS SL",
            base_imponible=312.85,
            iva_porcentaje=21,
            iva=66.7,
            total=334.75,
        )
        fallback = InvoiceData(
            numero_factura="FI202600043",
            fecha="2026-01-07",
            base_imponible=312.85,
            iva_porcentaje=7,
            iva=21.9,
            total=334.75,
        )

        normalized, warnings = invoice_normalization_service.normalize_invoice_data(
            primary,
            fallback,
            raw_text="FACTURA\nDOCUMENTO\nFI202600043 07-01-2026\n%IGIC\n7.00\nTOTAL\n334,75",
        )

        assert normalized.numero_factura == "FI202600043"
        assert normalized.iva_porcentaje == 7
        assert normalized.iva == 21.9
        assert "numero_factura_corregido_con_fallback" in warnings
        assert "iva_porcentaje_corregido_por_texto_igic" in warnings

    def test_extract_invoice_number_from_raw_text_accepts_numeric_series_without_confusing_dates(self):
        service = DocumentIntelligenceService()

        invoice_number = invoice_normalization_service.extract_invoice_number_from_raw_text(
            "\n".join(
                [
                    "FACTURA",
                    "Número:",
                    "14/2025",
                    "Fecha:",
                    "21/12/2025",
                ]
            )
        )

        assert invoice_number == "14/2025"

    def test_normalize_invoice_data_prefers_footer_summary_amounts_from_fallback(self):
        service = DocumentIntelligenceService()
        primary = InvoiceData(
            numero_factura="FI202600043",
            fecha="2026-01-07",
            proveedor="DISOFT SERVICIOS INFORMATICOS SL",
            base_imponible=356.38,
            iva_porcentaje=7,
            iva=24.94,
            total=381.325,
            lineas=[
                {"descripcion": "Plataforma", "cantidad": 1, "precio_unitario": 143.85, "importe": 143.85},
                {"descripcion": "Mantenimiento", "cantidad": 1, "precio_unitario": 114.00, "importe": 114.00},
                {"descripcion": "Otros", "cantidad": 1, "precio_unitario": 1.00, "importe": 1.00},
            ],
        )
        fallback = InvoiceData(
            numero_factura="FI202600043",
            fecha="2026-01-07",
            proveedor="DISOFT SERVICIOS INFORMATICOS SL",
            base_imponible=312.85,
            iva_porcentaje=7,
            iva=21.90,
            total=334.75,
        )

        normalized, warnings = invoice_normalization_service.normalize_invoice_data(
            primary,
            fallback,
            raw_text="FACTURA\nSUBTOTAL\n312,85\nIMPUESTOS\n21,90\nTOTAL\n334,75\n%IGIC\n7,00",
        )

        assert normalized.base_imponible == 312.85
        assert normalized.iva == 21.90
        assert normalized.total == 334.75
        assert "importes_corregidos_con_resumen_fallback" in warnings

    def test_normalize_invoice_data_prefers_base_imponible_summary_amounts_from_fallback(self):
        service = DocumentIntelligenceService()
        primary = InvoiceData(
            numero_factura="GC 26000116",
            fecha="2026-01-09",
            proveedor="Alberto Villacorta, S.L.U",
            cif_proveedor="B35246388",
            cliente="DISOFT SERV. INFORM S.L",
            cif_cliente="B35222249",
            base_imponible=160.50,
            iva_porcentaje=7,
            iva=11.23,
            total=171.735,
            lineas=[
                {
                    "descripcion": "ANTIVIRUS AVAST PREMIUM BUSINESS SECURITY IYEAR 1-4 USUARIOS (KIT DIGITAL)",
                    "cantidad": 6,
                    "precio_unitario": 25.00,
                    "importe": 150.00,
                }
            ],
        )
        fallback = InvoiceData(
            numero_factura="GC 26000116",
            fecha="2026-01-09",
            proveedor="Alberto Villacorta, S.L.U",
            cif_proveedor="B35246388",
            cliente="DISOFT SERV. INFORM S.L",
            cif_cliente="B35222249",
            base_imponible=150.00,
            iva_porcentaje=7,
            iva=10.50,
            total=160.50,
            lineas=[
                {
                    "descripcion": "ANTIVIRUS AVAST PREMIUM BUSINESS SECURITY IYEAR 1-4 USUARIOS (KIT DIGITAL)",
                    "cantidad": 6,
                    "precio_unitario": 25.00,
                    "importe": 150.00,
                }
            ],
        )

        normalized, warnings = invoice_normalization_service.normalize_invoice_data(
            primary,
            fallback,
            raw_text=(
                "FACTURA\n"
                "BASE IMPONIBLE\n150,00\n"
                "IMPUESTOS\n10,50\n"
                "TOTAL\n160,50\n"
                "7%\n"
            ),
        )

        assert normalized.base_imponible == 150.00
        assert normalized.iva == 10.50
        assert normalized.total == 160.50
        assert "importes_corregidos_con_resumen_fallback" in warnings

    def test_normalize_amounts_supports_irpf_withholding(self):
        service = DocumentIntelligenceService()
        invoice = InvoiceData(
            base_imponible=15000,
            iva_porcentaje=7,
            iva=0,
            retencion_porcentaje=15,
            retencion=2250,
            total=13800,
        )

        warnings = amount_resolution_service.normalize_amounts(invoice)

        assert invoice.iva == 1050
        assert invoice.total == 13800
        assert "iva_inferido_desde_total" in warnings or "iva_recalculado_desde_porcentaje" in warnings

    def test_normalize_invoice_data_discards_withholding_without_textual_hints(self):
        service = DocumentIntelligenceService()
        primary = InvoiceData(
            numero_factura="FI202600043",
            fecha="2026-01-07",
            proveedor="DISOFT SERVICIOS INFORMATICOS SL",
            cliente="ASESORES, S.C.PROFESIONAL",
            cif_proveedor="B35222249",
            cif_cliente="J76022912",
            base_imponible=312.85,
            iva_porcentaje=7,
            iva=21.9,
            retencion_porcentaje=7,
            retencion=21.9,
            total=334.75,
            lineas=[
                {"descripcion": "Plataforma", "cantidad": 1, "precio_unitario": 312.85, "importe": 312.85},
            ],
        )
        fallback = InvoiceData(
            numero_factura="FI202600043",
            fecha="2026-01-07",
            proveedor="DISOFT SERVICIOS INFORMATICOS SL",
            cliente="ASESORES, S.C.PROFESIONAL",
            cif_proveedor="B35222249",
            cif_cliente="J76022912",
            base_imponible=312.85,
            iva_porcentaje=7,
            iva=21.9,
            total=334.75,
        )

        normalized, warnings = invoice_normalization_service.normalize_invoice_data(
            primary,
            fallback,
            raw_text="FACTURA\nDOCUMENTO\nFI202600043 07-01-2026\nCONCEPTO\nPlataforma\nBASE\n312,85\nIMPUESTOS\n21,90\nTOTAL\n334,75",
        )

        assert normalized.retencion == 0
        assert normalized.retencion_porcentaje == 0
        assert "retencion_descartada_sin_indicios_textuales" in warnings

    def test_enrich_single_line_item_from_amounts_uses_base_when_line_is_empty(self):
        service = DocumentIntelligenceService()
        invoice = InvoiceData(
            base_imponible=15000,
            lineas=[
                {
                    "descripcion": "Servicios de consultoría estratégica",
                    "cantidad": 0,
                    "precio_unitario": 0,
                    "importe": 0,
                }
            ],
        )

        warnings = line_item_resolution_service.enrich_single_line_item_from_amounts(invoice)

        assert invoice.lineas[0].cantidad == 1
        assert invoice.lineas[0].precio_unitario == 15000
        assert invoice.lineas[0].importe == 15000
        assert "linea_unica_completada_desde_base" in warnings

    def test_extract_retention_summary_from_ocr_text(self):
        service = DocumentIntelligenceService()
        summary = amount_resolution_service.extract_retention_summary(
            "\n".join(
                [
                    "15,000.00 €",
                    "Total",
                    "7.00%",
                    "1,050.00 €",
                    "IGIC",
                    "15.00%",
                    "-2,250.00 €",
                    "Rentención I.R.P.F.",
                    "13,800.00 €",
                    "Total Factura",
                ]
            )
        )

        assert summary["base"] == 15000.0
        assert summary["tax_rate"] == 7.0
        assert summary["tax_amount"] == 1050.0
        assert summary["withholding_rate"] == 15.0
        assert summary["withholding_amount"] == 2250.0
        assert summary["total_due"] == 13800.0

    def test_extract_retention_summary_from_mistral_style_text(self):
        service = DocumentIntelligenceService()
        summary = amount_resolution_service.extract_retention_summary(
            "\n".join(
                [
                    "Concepto",
                    "Importe",
                    "Servicios de consultoría estratégica y definición funcional",
                    "15,000.00 €",
                    "Total",
                    "15,000.00 €",
                    "IGIC",
                    "7.00% 1,050.00 €",
                    "Rentención I.R.P.F.",
                    "15.00% -2,250.00 €",
                    "Total Factura",
                    "13,800.00 €",
                ]
            )
        )

        assert summary["base"] == 15000.0
        assert summary["tax_rate"] == 7.0
        assert summary["tax_amount"] == 1050.0
        assert summary["withholding_rate"] == 15.0
        assert summary["withholding_amount"] == 2250.0
        assert summary["total_due"] == 13800.0

    def test_detect_document_family_uses_company_context_not_hardcoded_brand(self):
        service = DocumentIntelligenceService()
        company = document_semantic_resolver.normalize_company_context(
            {
                "name": "Tecnocanarias Soluciones Digitales SL",
                "tax_id": "B12345678",
            }
        )

        family = document_semantic_resolver.detect_document_family(
            raw_text="\n".join(
                [
                    "TECNOCANARIAS SOLUCIONES DIGITALES SL",
                    "B12345678",
                    "FACTURA",
                    "DOCUMENTO",
                    "FECHA",
                    "CONCEPTO",
                    "%IGIC",
                    "TOTAL",
                ]
            ),
            company_context=company,
        )

        assert family == "company_sale"

    def test_extract_provider_from_header_skips_linked_company_for_any_company(self):
        service = DocumentIntelligenceService()
        company = document_semantic_resolver.normalize_company_context(
            {
                "name": "Tecnocanarias Soluciones Digitales SL",
                "tax_id": "B12345678",
            }
        )

        provider = party_resolution_service.extract_provider_from_header(
            "\n".join(
                [
                    "(9747) FLORBRIC, S. L.",
                    "BENARTEMI, 37",
                    "35009 LAS PALMAS DE G. C.",
                    "NIF: B76099134",
                    "TECNOCANARIAS SOLUCIONES DIGITALES SL",
                    "C/ FEDERICO VIERA, 163",
                ]
            ),
            company,
        )

        assert provider == "FLORBRIC, S. L"

    def test_extract_ranked_provider_from_header_can_reach_supplier_name_before_address_block(self):
        service = DocumentIntelligenceService()
        company = document_semantic_resolver.normalize_company_context(
            {
                "name": "Disoft Servicios Informaticos SL",
                "tax_id": "B35222249",
            }
        )

        provider = party_resolution_service.extract_ranked_provider_from_header(
            "\n".join(
                [
                    "Disoft",
                    "Servicios informáticos",
                    "(9747) FLORBRIC, S. L.",
                    "DISOFT SERVICIOS INFORMATICOS SL",
                    "C/ Federico Viera, 163",
                    "35012 Las Palmas de Gran Canaria",
                    "BENARTEMI, 37",
                    "Tlf. (928) 470347",
                    "Mail: administracion@disoftweb.com",
                    "35009 LAS PALMAS DE G. C.",
                    "Web: www.disoft.es",
                    "LAS PALMAS",
                    "NIF: B76099134",
                ]
            ),
            company,
        )

        assert provider == "FLORBRIC, S. L"

    def test_extract_ranked_provider_from_header_allows_generic_service_companies_without_company_specific_veto(self):
        service = DocumentIntelligenceService()
        company = document_semantic_resolver.normalize_company_context(
            {
                "name": "Tecnocanarias Soluciones Digitales SL",
                "tax_id": "B12345678",
            }
        )

        provider = party_resolution_service.extract_ranked_provider_from_header(
            "\n".join(
                [
                    "Tecnocanarias Soluciones Digitales SL",
                    "Servicios Integrales Atlantico",
                    "BENARTEMI, 37",
                    "35009 LAS PALMAS DE G. C.",
                    "NIF: B76099134",
                ]
            ),
            company,
        )

        assert provider == "Servicios Integrales Atlantico"

    def test_extract_provider_from_header_handles_mojibake_stop_lines_without_needing_exact_broken_token(self):
        service = DocumentIntelligenceService()
        company = document_semantic_resolver.normalize_company_context(
            {
                "name": "Tecnocanarias Soluciones Digitales SL",
                "tax_id": "B12345678",
            }
        )

        provider = party_resolution_service.extract_provider_from_header(
            "\n".join(
                [
                    "Proveedor Atlantico de Servicios",
                    "DATOS DE FACTURACIÃ“N",
                    "Cliente Final SL",
                    "C/ Falsa, 123",
                ]
            ),
            company,
        )

        assert provider == "Proveedor Atlantico de Servicios"

    def test_infer_document_type_detects_simplified_receipts_and_tickets(self):
        service = DocumentIntelligenceService()

        simplified = document_result_builder.infer_document_type(
            "HOSTELERIA GRESSARA, S.L.\nFRA. SIMPLIFICADA\nT001-1235663 FECHA 09/01/2025\nTOTAL 17,10",
            InvoiceData(numero_factura="T001-1235663", total=17.10),
        )
        ticket = document_result_builder.infer_document_type(
            "DINOSOL SUPERMERCADOS, S.L.\nDOCUMENTO DE VENTA\nFACTURA SIMPLIFICADA\nTOTAL COMPRA 8,50",
            InvoiceData(numero_factura="2026/900213-00004245", total=8.50),
        )

        assert simplified == "factura_simplificada"
        assert ticket == "factura_simplificada"

    def test_party_candidate_score_penalizes_generic_address_lines_without_city_hardcodes(self):
        service = DocumentIntelligenceService()

        address_score = party_resolution_service.party_candidate_score("C/ Los Lopez, 47 35400 Arucas", "")
        company_score = party_resolution_service.party_candidate_score("Proveedor Atlantico SL", "B12345678")

        assert address_score < company_score

    def test_build_company_match_detects_associated_company_on_issuer(self):
        service = DocumentIntelligenceService()

        company_match = document_semantic_resolver.build_company_match(
            invoice=InvoiceData(
                proveedor="Tecnocanarias Soluciones Digitales SL",
                cif_proveedor="B12345678",
                cliente="Cliente Final SL",
                cif_cliente="B55555555",
            ),
            company_context={
                "name": "Tecnocanarias Soluciones Digitales SL",
                "tax_id": "B12345678",
            },
        )

        assert company_match["issuer_matches_company"] is True
        assert company_match["recipient_matches_company"] is False
        assert company_match["matched_role"] == "issuer"
        assert company_match["matched_by"] == "tax_id"

    def test_build_company_match_accepts_short_company_name_with_single_strong_anchor(self):
        company_match = document_semantic_resolver.build_company_match(
            invoice=InvoiceData(
                proveedor="Acme Servicios SL",
                cif_proveedor="",
                cliente="Cliente Final SL",
                cif_cliente="B55555555",
            ),
            company_context={
                "name": "Acme Servicios Digitales SL",
                "tax_id": "",
            },
        )

        assert company_match["issuer_matches_company"] is True
        assert company_match["matched_role"] == "issuer"
        assert company_match["matched_by"] in {"name_overlap", "name_single_overlap", "name_anchor"}

    def test_should_run_doc_ai_fallback_when_primary_result_is_doubtful(self):
        service = DocumentIntelligenceService()

        resolution = {
            "data": InvoiceData(numero_factura="", proveedor="", total=121, confianza=0.58),
            "coverage": ExtractionCoverage(
                required_fields_present=["totals.total"],
                missing_required_fields=["identity.invoice_number", "issuer.name"],
                completeness_ratio=0.45,
            ),
            "field_confidence": {
                "numero_factura": 0.2,
                "fecha": 0.4,
                "proveedor": 0.2,
                "cif_proveedor": 0.1,
                "total": 0.9,
            },
            "decision_flags": [
                DecisionFlag(
                    code="missing_numero_factura",
                    severity="warning",
                    requires_review=True,
                )
            ],
            "company_match": {"matched_role": ""},
        }

        with (
            patch.object(settings, "doc_ai_enabled", True),
            patch.object(settings, "doc_ai_selective_enabled", True),
        ):
            assert service._should_run_doc_ai_fallback(
                resolution=resolution,
                input_profile={"input_kind": "image_photo"},
                company_context={"name": "Disoft Servicios Informaticos SL", "tax_id": "B35222249"},
            ) is True

    def test_should_skip_doc_ai_fallback_when_primary_result_is_strong(self):
        service = DocumentIntelligenceService()

        resolution = {
            "data": InvoiceData(
                numero_factura="F-2026-001",
                fecha="2026-03-15",
                proveedor="Proveedor Demo SL",
                cif_proveedor="B12345678",
                total=121,
                confianza=0.92,
            ),
            "coverage": ExtractionCoverage(
                required_fields_present=["identity.invoice_number", "identity.issue_date", "issuer.name", "totals.total"],
                missing_required_fields=[],
                completeness_ratio=1.0,
            ),
            "field_confidence": {
                "numero_factura": 0.95,
                "fecha": 0.94,
                "proveedor": 0.91,
                "cif_proveedor": 0.93,
                "total": 0.97,
            },
            "decision_flags": [],
            "company_match": {"matched_role": "recipient"},
        }

        with (
            patch.object(settings, "doc_ai_enabled", True),
            patch.object(settings, "doc_ai_selective_enabled", True),
        ):
            assert service._should_run_doc_ai_fallback(
                resolution=resolution,
                input_profile={"input_kind": "pdf_digital"},
                company_context={"name": "Disoft Servicios Informaticos SL", "tax_id": "B35222249"},
            ) is False

    def test_should_skip_doc_ai_fallback_for_non_visual_input_even_if_doubtful(self):
        service = DocumentIntelligenceService()

        resolution = {
            "data": InvoiceData(numero_factura="", proveedor="", total=121, confianza=0.22),
            "coverage": ExtractionCoverage(
                required_fields_present=["totals.total"],
                missing_required_fields=["identity.invoice_number", "issuer.name", "identity.issue_date"],
                completeness_ratio=0.3,
            ),
            "field_confidence": {
                "numero_factura": 0.1,
                "fecha": 0.2,
                "proveedor": 0.2,
                "cif_proveedor": 0.1,
                "total": 0.9,
            },
            "decision_flags": [
                DecisionFlag(
                    code="missing_numero_factura",
                    severity="warning",
                    requires_review=True,
                )
            ],
            "company_match": {"matched_role": ""},
        }

        with (
            patch.object(settings, "doc_ai_enabled", True),
            patch.object(settings, "doc_ai_selective_enabled", True),
        ):
            assert service._should_run_doc_ai_fallback(
                resolution=resolution,
                input_profile={"input_kind": "pdf_digital"},
                company_context={"name": "Disoft Servicios Informaticos SL", "tax_id": "B35222249"},
            ) is False

    def test_should_skip_doc_ai_fallback_when_match_is_ambiguous_but_result_is_strong(self):
        service = DocumentIntelligenceService()

        resolution = {
            "data": InvoiceData(
                numero_factura="F-2026-001",
                fecha="2026-03-15",
                proveedor="Proveedor Demo SL",
                cif_proveedor="B12345678",
                total=121,
                confianza=0.86,
            ),
            "coverage": ExtractionCoverage(
                required_fields_present=["identity.invoice_number", "identity.issue_date", "issuer.name", "issuer.tax_id", "totals.total"],
                missing_required_fields=[],
                completeness_ratio=1.0,
            ),
            "field_confidence": {
                "numero_factura": 0.96,
                "fecha": 0.94,
                "proveedor": 0.91,
                "cif_proveedor": 0.92,
                "total": 0.95,
            },
            "decision_flags": [
                DecisionFlag(
                    code="company_match_ambiguous",
                    severity="warning",
                    requires_review=True,
                )
            ],
            "company_match": {"matched_role": "ambiguous"},
            "normalized_document": None,
        }

        with (
            patch.object(settings, "doc_ai_enabled", True),
            patch.object(settings, "doc_ai_selective_enabled", True),
        ):
            assert service._should_run_doc_ai_fallback(
                resolution=resolution,
                input_profile={"input_kind": "image_photo"},
                company_context={"name": "Disoft Servicios Informaticos SL", "tax_id": "B35222249"},
            ) is False

    def test_extract_runs_doc_ai_only_as_selective_fallback(self):
        service = DocumentIntelligenceService()
        bundle = DocumentBundle(raw_text="Factura\nTotal 121,00")

        async def run():
            with (
                patch(
                    "app.services.document_intelligence.document_loader.load",
                    return_value={
                        "raw_text": bundle.raw_text,
                        "pages": 1,
                        "method": "ocr",
                        "page_images": [],
                        "input_profile": {
                            "input_kind": "image_photo",
                            "text_source": "ocr",
                            "used_ocr": True,
                            "ocr_engine": "tesseract",
                            "preprocessing_steps": [],
                        },
                        "bundle": bundle,
                    },
                ),
                patch.object(
                    service,
                    "_heuristic_extract",
                    return_value=InvoiceData(
                        numero_factura="",
                        fecha="",
                        proveedor="",
                        cif_proveedor="",
                        total=121,
                    ),
                ),
                patch.object(
                    service,
                    "_extract_with_provider",
                    new=AsyncMock(
                        return_value=(
                            InvoiceData(
                                numero_factura="F-2026-001",
                                fecha="2026-03-15",
                                proveedor="Proveedor Demo SL",
                                cif_proveedor="B12345678",
                                base_imponible=100,
                                iva_porcentaje=21,
                                iva=21,
                                total=121,
                            ),
                            "ollama",
                        )
                    ),
                ) as mocked_provider,
                patch.object(settings, "doc_ai_enabled", True),
                patch.object(settings, "doc_ai_provider", "ollama"),
                patch.object(settings, "doc_ai_selective_enabled", True),
            ):
                result = await service.extract("invoice.png", "invoice.png", "image/png")
                assert mocked_provider.await_count == 1
                assert result.method == "doc_bundle_doc_ai_fallback"
                assert result.provider == "ollama"

        import asyncio

        asyncio.run(run())

    def test_extract_uses_document_bundle_from_loader_and_returns_evidence(self):
        service = DocumentIntelligenceService()
        bundle = DocumentBundle(raw_text="Factura F-1\nFecha 15/03/2026\nTotal 121,00")

        async def run():
            with (
                patch(
                    "app.services.document_intelligence.document_loader.load",
                    return_value={
                        "raw_text": bundle.raw_text,
                        "pages": 1,
                        "method": "ocr",
                        "page_images": [],
                        "input_profile": {
                            "input_kind": "image_scan",
                            "text_source": "ocr",
                            "used_ocr": True,
                            "ocr_engine": "tesseract",
                            "preprocessing_steps": [],
                        },
                        "bundle": bundle,
                    },
                ),
                patch.object(
                    service,
                    "_heuristic_extract",
                    return_value=InvoiceData(
                        numero_factura="F-1",
                        fecha="2026-03-15",
                        proveedor="Proveedor Demo SL",
                        cif_proveedor="B12345678",
                        base_imponible=100,
                        iva_porcentaje=21,
                        iva=21,
                        total=121,
                    ),
                ),
            ):
                result = await service.extract("invoice.png", "invoice.png", "image/png")
                assert result.evidence
                assert result.decision_flags is not None
                assert result.company_match is not None
                assert result.processing_trace is not None
                assert result.contract.name == "difactura.document_engine"
                assert result.engine_request.file_name == "invoice.png"
                assert result.document_input.input_kind == "image_scan"
                numero_items = result.evidence.get("numero_factura", [])
                assert any(item.value_kind == "resolved" and item.is_final for item in numero_items)
                assert all(item.value_kind in {"observed", "resolved", "inferred"} for item in numero_items)

        import asyncio

        asyncio.run(run())

    def test_build_bundle_candidate_groups_maps_region_candidates_to_internal_bundle(self):
        service = DocumentIntelligenceService()
        bundle = DocumentBundle(
            raw_text="Factura F-1\nFecha 15/03/2026\nProveedor Demo SL\nTotal 121,00",
            regions=[
                LayoutRegion(region_id="header-1", region_type="header", page=1, confidence=0.75),
                LayoutRegion(region_id="totals-1", region_type="totals", page=1, confidence=0.8),
            ],
        )
        bundle_sources = {
            "header": InvoiceData(numero_factura="F-1", fecha="2026-03-15"),
            "totals": InvoiceData(base_imponible=100, iva=21, total=121),
        }

        candidate_groups = region_hint_rescue_service.build_bundle_candidate_groups(bundle=bundle, bundle_sources=bundle_sources)

        assert candidate_groups["numero_factura"][0].field == "numero_factura"
        assert candidate_groups["numero_factura"][0].extractor == "header"
        assert candidate_groups["total"][0].value == "121"
        assert candidate_groups["total"][0].region_type == "totals"

    def test_should_run_region_hint_rescue_for_scanned_document_without_company_match(self):
        service = DocumentIntelligenceService()

        should_rescue = region_hint_rescue_service.should_run(
            base_candidate=InvoiceData(
                proveedor="Texto OCR roto que no parece una empresa real y ocupa demasiado espacio en la cabecera",
                cliente="",
                cif_proveedor="",
                cif_cliente="",
            ),
            input_profile={"input_kind": "pdf_scanned"},
            company_context={
                "name": "Disoft Servicios Informaticos SL",
                "tax_id": "B35222249",
            },
        )

        assert should_rescue is True

    def test_maybe_apply_region_hint_rescue_enriches_bundle_and_raw_text(self):
        service = DocumentIntelligenceService()
        bundle = DocumentBundle(
            raw_text="RECTIFICATIVA",
            page_count=1,
            page_texts=["RECTIFICATIVA"],
            pages=[
                DocumentPageBundle(
                    page_number=1,
                    reading_text="RECTIFICATIVA",
                    ocr_text="RECTIFICATIVA",
                    spans=[],
                )
            ],
        )

        with patch(
            "app.services.ocr_service.OCRService.extract_region_hints",
            return_value=[
                {
                    "page_number": 1,
                    "region_type": "header_left",
                    "text": "(9747) FLORBRIC, S. L.\nNIF: B76099134",
                    "bbox": {"x0": 0, "y0": 0, "x1": 400, "y1": 250},
                },
                {
                    "page_number": 1,
                    "region_type": "totals",
                    "text": "SUBTOTAL -25,00\nIMPUESTOS -1,75\nTOTAL -26,75",
                    "bbox": {"x0": 400, "y0": 700, "x1": 800, "y1": 1100},
                },
            ],
        ):
            rescued_bundle, rescued_raw_text, applied = region_hint_rescue_service.maybe_apply(
                file_path="invoice.pdf",
                input_profile={"input_kind": "pdf_scanned"},
                company_context={
                    "name": "Disoft Servicios Informaticos SL",
                    "tax_id": "B35222249",
                },
                bundle=bundle,
                raw_text=bundle.raw_text,
                base_candidate=InvoiceData(proveedor="", cliente="", cif_proveedor="", cif_cliente=""),
            )

        assert applied is True
        assert "FLORBRIC" in rescued_raw_text
        assert any(region.region_type == "totals" for region in rescued_bundle.regions)
        assert any(span.source == "ocr_region" for span in rescued_bundle.spans)
