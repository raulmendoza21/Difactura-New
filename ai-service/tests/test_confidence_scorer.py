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


def test_confidence_drops_hard_for_impossible_total_below_lines():
    score = confidence_scorer.score(
        InvoiceData(
            numero_factura="FAC-3",
            fecha="2026-03-19",
            proveedor="CLIENTE",
            cif_proveedor="255687788",
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
    )

    assert score < 0.6


def test_confidence_drops_when_line_sum_does_not_match_base():
    score = confidence_scorer.score(
        InvoiceData(
            numero_factura="FAC-4",
            fecha="2026-03-19",
            proveedor="Proveedor Demo SL",
            cif_proveedor="B12345678",
            base_imponible=312.85,
            iva_porcentaje=7,
            iva=21.90,
            total=334.75,
            lineas=[
                {"descripcion": "Servicio 1", "cantidad": 1, "precio_unitario": 143.85, "importe": 143.85},
                {"descripcion": "Servicio 2", "cantidad": 1, "precio_unitario": 114.00, "importe": 114.00},
                {"descripcion": "Servicio 3", "cantidad": 1, "precio_unitario": 54.00, "importe": 54.00},
            ],
        )
    )

    assert score < 0.9


def test_confidence_stays_reasonable_for_negative_rectificative():
    score = confidence_scorer.score(
        InvoiceData(
            numero_factura="AB202600002",
            fecha="2026-01-07",
            proveedor="FLORBRIC, S. L",
            cif_proveedor="B76099134",
            base_imponible=-25.00,
            iva_porcentaje=7,
            iva=-1.75,
            total=-26.75,
            lineas=[{"descripcion": "Mantenimiento del Programa de Facturación Facdis", "cantidad": 1, "precio_unitario": -25.00, "importe": -25.00}],
        )
    )

    assert score >= 0.85


def test_confidence_drops_for_same_tax_id_on_both_roles():
    score = confidence_scorer.score(
        InvoiceData(
            numero_factura="FAC-5",
            fecha="2026-03-19",
            proveedor="Proveedor Demo SL",
            cif_proveedor="B12345678",
            cliente="Cliente Demo SL",
            cif_cliente="B12345678",
            base_imponible=100,
            iva_porcentaje=21,
            iva=21,
            total=121,
            lineas=[{"descripcion": "Servicio", "cantidad": 1, "precio_unitario": 100, "importe": 100}],
        )
    )

    assert score < 0.8
