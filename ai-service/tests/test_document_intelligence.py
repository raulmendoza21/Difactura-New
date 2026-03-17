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
