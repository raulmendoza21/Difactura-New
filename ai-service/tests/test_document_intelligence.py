"""Tests for document intelligence service."""

from unittest.mock import patch

from app.models.document_bundle import DocumentBundle, DocumentPageBundle
from app.models.invoice_model import InvoiceData, LineItem
from app.services.document_intelligence import DocumentIntelligenceService


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

        normalized, warnings = service._normalize_invoice_data(primary, fallback)

        assert normalized.cif_proveedor == "E9988776A"
        assert normalized.iva == 44.73
        assert normalized.lineas[0].cantidad == 1
        assert normalized.lineas[0].importe == 95
        assert "cif_proveedor_corregido_con_fallback" in warnings
        assert "iva_recalculado_desde_porcentaje" in warnings

    def test_infer_tax_regime_detects_igic_from_text(self):
        service = DocumentIntelligenceService()
        invoice = InvoiceData(base_imponible=100, iva=7, iva_porcentaje=7)

        result = service._infer_tax_regime("Factura con IGIC general al 7%", invoice)

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

        normalized = service._build_extraction_document(
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

        coverage = service._build_extraction_coverage(normalized)

        assert coverage.completeness_ratio == 1.0
        assert coverage.missing_required_fields == []
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

        normalized = service._build_extraction_document(
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

        warnings = service._normalize_amounts(invoice)

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

        warnings = service._normalize_amounts(invoice)

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

        warnings = service._normalize_amounts(invoice)

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

        repaired, warnings = service._repair_summary_leak_lines(
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

        selected, warnings = service._prefer_fallback_line_items(
            primary_line_items=primary,
            fallback_line_items=fallback,
            base_amount=312.85,
        )

        assert len(selected) == 4
        assert round(sum(line.importe for line in selected), 2) == 312.85
        assert "lineas_corregidas_con_fallback" in warnings

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

        warnings = service._normalize_amounts(invoice)

        assert invoice.base_imponible == 312.85
        assert invoice.iva == 21.90
        assert invoice.total == 334.75
        assert "lineas_inconsistentes_con_resumen_fiscal" in warnings

    def test_infer_tax_regime_uses_rate_when_text_is_ambiguous(self):
        service = DocumentIntelligenceService()

        assert service._infer_tax_regime("Factura de servicios", InvoiceData(iva_porcentaje=7)) == "IGIC"
        assert service._infer_tax_regime("Factura de servicios", InvoiceData(iva_porcentaje=21)) == "IVA"

    def test_infer_tax_regime_prefers_unique_igic_rate_over_spurious_iva_text(self):
        service = DocumentIntelligenceService()

        result = service._infer_tax_regime(
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

        warnings = service._compare_source_candidates(ai_candidate, heuristic)

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

        field_confidence = service._build_field_confidence(
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

        field_confidence = service._build_field_confidence(
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

        score = service._refine_document_confidence(
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

        score = service._refine_document_confidence(
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

        normalized, warnings = service._normalize_invoice_data(primary, fallback)

        assert normalized.proveedor == "Proveedor Demo SL"
        assert normalized.cliente == "Empresa Cliente SL"
        assert "proveedor_corregido_con_fallback" in warnings
        assert "cliente_corregido_con_fallback" in warnings

    def test_normalize_tax_id_repairs_common_ocr_confusions(self):
        service = DocumentIntelligenceService()

        normalized_value, warnings = service._normalize_tax_id_value(
            "8I2345678",
            "",
            role="proveedor",
        )

        assert normalized_value == "B12345678"
        assert "cif_proveedor_reparado_ocr" in warnings

    def test_normalize_tax_id_warns_when_value_stays_invalid(self):
        service = DocumentIntelligenceService()

        normalized_value, warnings = service._normalize_tax_id_value(
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

        normalized, warnings = service._normalize_invoice_data(
            primary,
            fallback,
            raw_text="FACTURA\nDOCUMENTO\nFI202600043 07-01-2026\n%IGIC\n7.00\nTOTAL\n334,75",
        )

        assert normalized.numero_factura == "FI202600043"
        assert normalized.iva_porcentaje == 7
        assert normalized.iva == 21.9
        assert "numero_factura_corregido_con_fallback" in warnings
        assert "iva_porcentaje_corregido_por_texto_igic" in warnings

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

        normalized, warnings = service._normalize_invoice_data(
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

        normalized, warnings = service._normalize_invoice_data(
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

        warnings = service._normalize_amounts(invoice)

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

        normalized, warnings = service._normalize_invoice_data(
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

        warnings = service._enrich_single_line_item_from_amounts(invoice)

        assert invoice.lineas[0].cantidad == 1
        assert invoice.lineas[0].precio_unitario == 15000
        assert invoice.lineas[0].importe == 15000
        assert "linea_unica_completada_desde_base" in warnings

    def test_extract_retention_summary_from_ocr_text(self):
        service = DocumentIntelligenceService()
        summary = service._extract_retention_summary(
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

    def test_detect_document_family_uses_company_context_not_hardcoded_brand(self):
        service = DocumentIntelligenceService()
        company = service._normalize_company_context(
            {
                "name": "Tecnocanarias Soluciones Digitales SL",
                "tax_id": "B12345678",
            }
        )

        family = service._detect_document_family(
            "\n".join(
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
            company,
        )

        assert family == "company_sale"

    def test_extract_provider_from_header_skips_linked_company_for_any_company(self):
        service = DocumentIntelligenceService()
        company = service._normalize_company_context(
            {
                "name": "Tecnocanarias Soluciones Digitales SL",
                "tax_id": "B12345678",
            }
        )

        provider = service._extract_provider_from_header(
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

    def test_infer_document_type_detects_simplified_receipts_and_tickets(self):
        service = DocumentIntelligenceService()

        simplified = service._infer_document_type(
            "HOSTELERIA GRESSARA, S.L.\nFRA. SIMPLIFICADA\nT001-1235663 FECHA 09/01/2025\nTOTAL 17,10",
            InvoiceData(numero_factura="T001-1235663", total=17.10),
        )
        ticket = service._infer_document_type(
            "DINOSOL SUPERMERCADOS, S.L.\nDOCUMENTO DE VENTA\nFACTURA SIMPLIFICADA\nTOTAL COMPRA 8,50",
            InvoiceData(numero_factura="2026/900213-00004245", total=8.50),
        )

        assert simplified == "factura_simplificada"
        assert ticket == "factura_simplificada"

    def test_party_candidate_score_penalizes_generic_address_lines_without_city_hardcodes(self):
        service = DocumentIntelligenceService()

        address_score = service._party_candidate_score("C/ Los Lopez, 47 35400 Arucas", "")
        company_score = service._party_candidate_score("Proveedor Atlantico SL", "B12345678")

        assert address_score < company_score

    def test_build_company_match_detects_associated_company_on_issuer(self):
        service = DocumentIntelligenceService()

        company_match = service._build_company_match(
            data=InvoiceData(
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
                assert "evidence" in result
                assert "decision_flags" in result
                assert "company_match" in result
                assert "processing_trace" in result

        import asyncio

        asyncio.run(run())

    def test_should_run_region_hint_rescue_for_scanned_document_without_company_match(self):
        service = DocumentIntelligenceService()

        should_rescue = service._should_run_region_hint_rescue(
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
            rescued_bundle, rescued_raw_text, applied = service._maybe_apply_region_hint_rescue(
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
