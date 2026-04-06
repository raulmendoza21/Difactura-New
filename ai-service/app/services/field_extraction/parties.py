"""Thin facade for party extraction helpers."""

from __future__ import annotations

from app.models.invoice_model import InvoiceData

from .party_parts.core import extract_cifs, extract_name, extract_parties_payload
from .party_parts.postprocessing import apply_party_postprocessing
from .party_parts.sections import (
    extract_customer_from_shipping_billing,
    extract_footer_legal_party,
    extract_parallel_party_sections,
    extract_party_section,
)

__all__ = [
    "InvoiceData",
    "apply_party_postprocessing",
    "extract_cifs",
    "extract_customer_from_shipping_billing",
    "extract_footer_legal_party",
    "extract_name",
    "extract_parallel_party_sections",
    "extract_parties_payload",
    "extract_party_section",
]
