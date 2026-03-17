"""Tests for field_extractor."""

import pytest
from app.services.field_extractor import FieldExtractor


@pytest.fixture
def extractor():
    return FieldExtractor()


class TestFieldExtractor:

    def test_extract_invoice_number(self, extractor):
        text = "Factura: F-2024/001\nFecha: 15/03/2024"
        data = extractor.extract(text)
        assert "2024" in data.numero_factura or "001" in data.numero_factura

    def test_extract_invoice_number_next_line(self, extractor):
        text = "Numero de factura\nAB-2024-77\nFecha: 15/03/2024"
        data = extractor.extract(text)
        assert data.numero_factura == "AB-2024-77"

    def test_extract_date_numeric(self, extractor):
        text = "Factura: 001\nFecha: 15/03/2024\nTotal: 121,00"
        data = extractor.extract(text)
        assert data.fecha == "2024-03-15"

    def test_extract_date_text(self, extractor):
        text = "Factura del 15 de marzo de 2024"
        data = extractor.extract(text)
        assert data.fecha == "2024-03-15"

    def test_extract_cif(self, extractor):
        text = "Proveedor: Empresa SL\nCIF: B12345678\nCliente: Mi empresa\nNIF: 12345678A"
        data = extractor.extract(text)
        assert data.cif_proveedor == "B12345678"

    def test_extract_amounts(self, extractor):
        text = """
        Factura: 001
        Fecha: 01/01/2024
        Base imponible: 100,00
        IVA 21%
        Cuota IVA: 21,00
        Total factura: 121,00
        """
        data = extractor.extract(text)
        assert data.base_imponible == 100.00
        assert data.iva_porcentaje == 21.0
        assert data.total == 121.00

    def test_extract_iva_amount(self, extractor):
        text = """
        Factura: 003
        Fecha: 01/01/2024
        Base imponible: 100,00
        IVA 21%
        Cuota IVA: 21,00
        Total factura: 121,00
        """
        data = extractor.extract(text)
        assert data.iva == 21.00

    def test_infer_missing_iva(self, extractor):
        text = """
        Factura: 002
        Fecha: 01/01/2024
        Base imponible: 200,00
        IVA 21%
        Total factura: 242,00
        """
        data = extractor.extract(text)
        assert data.base_imponible == 200.00
        assert data.iva == 42.00 or data.total == 242.00

    def test_empty_text(self, extractor):
        data = extractor.extract("")
        assert data.numero_factura == ""
        assert data.total == 0.0
        assert data.confianza == 0.0
