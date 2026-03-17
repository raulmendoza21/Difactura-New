"""Tests for invoice_classifier."""

import pytest
from app.services.invoice_classifier import InvoiceClassifier


@pytest.fixture
def classifier():
    return InvoiceClassifier()


class TestInvoiceClassifier:

    def test_classify_compra(self, classifier):
        text = "Proveedor: Empresa ABC\nFecha: 01/01/2024\nAlbaran de entrega"
        result = classifier.classify(text, proveedor="Empresa ABC", cliente="")
        assert result == "compra"

    def test_classify_venta(self, classifier):
        text = "Cliente: Empresa XYZ\nFecha: 01/01/2024\nFactura de venta"
        result = classifier.classify(text, proveedor="", cliente="Empresa XYZ")
        assert result == "venta"

    def test_classify_default_compra(self, classifier):
        text = "Factura 001\nTotal: 100,00"
        result = classifier.classify(text)
        assert result == "compra"

    def test_classify_with_keywords(self, classifier):
        text = "Destinatario: Cliente S.L.\nLe facturamos los siguientes conceptos"
        result = classifier.classify(text)
        assert result == "venta"
