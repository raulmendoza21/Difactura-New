"""Operation resolver — document type and tax regime.

Side (compra/venta) is delegated to the AI layer.
"""

from __future__ import annotations

import re

from app.models.fields import ScanResult
from app.utils.regex_lib import IGIC_RATES, IVA_RATES, RECTIFICATIVA_MARKERS, TICKET_MARKERS


def resolve(scan: ScanResult, iva_porcentaje: float | None = None) -> dict:
    """Return {tipo_factura, tax_regime} + confidence."""
    tipo = _resolve_tipo(scan)
    regime = _resolve_tax_regime(scan, iva_porcentaje)

    return {
        "tipo_factura": tipo,
        "tax_regime": regime,
        "confidence": {
            "tipo_factura": 0.9 if tipo != "factura" else 0.5,
            "tax_regime": 0.95 if regime != "unknown" else 0.3,
        },
    }


def _resolve_tipo(scan: ScanResult) -> str:
    text = scan.raw_text.lower()
    if RECTIFICATIVA_MARKERS.search(text):
        return "rectificativa"
    if TICKET_MARKERS.search(text):
        return "ticket"
    return "factura"


def _resolve_tax_regime(scan: ScanResult, rate: float | None) -> str:
    text = scan.raw_text.lower()

    if re.search(r"\bigic\b", text):
        return "igic"
    if re.search(r"\biva\b", text):
        return "iva"

    if rate is not None:
        if rate in IGIC_RATES and rate not in IVA_RATES:
            return "igic"
        if rate in IVA_RATES:
            return "iva"

    return "unknown"
