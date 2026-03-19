"""Tests for document intelligence service."""

from app.models.invoice_model import InvoiceData
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
            provider="ollama",
            method="doc_ai",
            warnings=[],
        )

        coverage = service._build_extraction_coverage(normalized)

        assert coverage.completeness_ratio == 1.0
        assert coverage.missing_required_fields == []

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

    def test_infer_tax_regime_uses_rate_when_text_is_ambiguous(self):
        service = DocumentIntelligenceService()

        assert service._infer_tax_regime("Factura de servicios", InvoiceData(iva_porcentaje=7)) == "IGIC"
        assert service._infer_tax_regime("Factura de servicios", InvoiceData(iva_porcentaje=21)) == "IVA"
