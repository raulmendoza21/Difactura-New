"""Tests for confidence scoring quality."""

from app.models.invoice_model import InvoiceData
from app.services.confidence_scorer import confidence_scorer


def test_confidence_is_high_for_consistent_invoice():
    score = confidence_scorer.score(
        InvoiceData(
            numero_factura="FAC-1",
            fecha="2026-03-19",
            proveedor="Proveedor Demo SL",
            cif_proveedor="B12345678",
            base_imponible=100,
            iva_porcentaje=21,
            iva=21,
            total=121,
            lineas=[{"descripcion": "Servicio", "cantidad": 1, "precio_unitario": 100, "importe": 100}],
        )
    )

    assert score >= 0.9


def test_confidence_drops_for_inconsistent_amounts():
    score = confidence_scorer.score(
        InvoiceData(
            numero_factura="FAC-2",
            fecha="2026-03-19",
            proveedor="Proveedor Demo SL",
            cif_proveedor="B12345678",
            base_imponible=337.59,
            iva_porcentaje=21,
            iva=70.89,
            total=337.59,
            lineas=[{"descripcion": "Servicio", "cantidad": 1, "precio_unitario": 279, "importe": 279}],
        )
    )

    assert score < 0.8

