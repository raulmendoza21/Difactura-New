"""Thin facade for amount field extraction."""

from __future__ import annotations

from app.models.invoice_model import InvoiceData

from .amount_parts.candidates import (
    extract_amount,
    extract_amount_around_exact_label,
    extract_amount_candidates,
    extract_amount_from_label_lines,
    extract_numeric_candidates,
)
from .amount_parts.core import (
    extract_amounts_payload,
    extract_base_amount,
    extract_iva_amount,
    extract_iva_percent,
    extract_total_amount,
    extract_withholding_amount,
    extract_withholding_percent,
)
from .amount_parts.inference import infer_amounts
from .amount_parts.summary import extract_footer_tax_summary

__all__ = [
    "InvoiceData",
    "extract_amount",
    "extract_amount_around_exact_label",
    "extract_amount_candidates",
    "extract_amount_from_label_lines",
    "extract_numeric_candidates",
    "extract_amounts_payload",
    "extract_base_amount",
    "extract_iva_amount",
    "extract_iva_percent",
    "extract_total_amount",
    "extract_withholding_amount",
    "extract_withholding_percent",
    "extract_footer_tax_summary",
    "infer_amounts",
]
