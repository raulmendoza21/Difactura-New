from __future__ import annotations

import re
from typing import Any

from app.models.document_bundle import DocumentBundle
from app.models.document_contract import DocumentType, NormalizedInvoiceDocument, build_normalized_document_from_invoice_data
from app.models.extraction_result import ExtractionCoverage
from app.models.invoice_model import InvoiceData
from app.services.document_semantic_resolver import (
    DocumentSemanticResolution,
    document_semantic_resolver,
)

PRIORITY_CONTRACT_FIELDS = (
    "classification.document_type",
    "classification.invoice_side",
    "identity.issue_date",
    "identity.invoice_number",
    "issuer.name",
    "issuer.tax_id",
    "totals.subtotal",
    "totals.total",
    "tax_breakdown",
    "line_items",
)


def infer_document_type(
    raw_text: str,
    invoice: InvoiceData,
    *,
    bundle: DocumentBundle | None = None,
) -> DocumentType:
    return document_semantic_resolver.resolve_document_type(
        raw_text=raw_text,
        invoice=invoice,
        bundle=bundle or DocumentBundle(raw_text=raw_text),
    )


def infer_tax_regime(
    raw_text: str,
    invoice: InvoiceData,
    *,
    bundle: DocumentBundle | None = None,
) -> str:
    document_type = infer_document_type(raw_text, invoice, bundle=bundle)
    return document_semantic_resolver.resolve_tax_regime(
        raw_text=raw_text,
        invoice=invoice,
        document_type=document_type,
    )


def extract_due_date(raw_text: str) -> str:
    match = re.search(
        r"(?:fecha\s+vencim(?:iento|ienta)?|vencimiento|vence)\s*[:.]?\s*(\d{1,2}[/\-\.]\d{1,2}[/\-\.]\d{2,4})",
        raw_text,
        re.IGNORECASE,
    )
    if not match:
        return ""

    raw_date = match.group(1)
    if re.fullmatch(r"\d{2}/\d{2}/\d{4}", raw_date):
        day, month, year = raw_date.split("/")
        return f"{year}-{month}-{day}"
    if re.fullmatch(r"\d{2}-\d{2}-\d{4}", raw_date):
        day, month, year = raw_date.split("-")
        return f"{year}-{month}-{day}"
    if re.fullmatch(r"\d{2}\.\d{2}\.\d{4}", raw_date):
        day, month, year = raw_date.split(".")
        return f"{year}-{month}-{day}"
    return raw_date


def extract_payment_method(raw_text: str) -> str:
    match = re.search(
        r"(?:forma\s+de\s+pago|metodo\s+de\s+pago|payment\s+method)\s*[:.]?\s*([^\n]+)",
        raw_text,
        re.IGNORECASE,
    )
    candidate = (match.group(1).strip() if match else "").strip(" .,:;-")
    normalized_text = raw_text.upper()

    if not candidate:
        if "TRANSFERENCIA" in normalized_text:
            return "Transferencia"
        if "DOMICILIACION" in normalized_text:
            return "Domiciliacion"
        if "TARJETA" in normalized_text:
            return "Tarjeta"
        if "EFECTIVO" in normalized_text:
            return "Efectivo"
        return ""

    lowered = candidate.lower()
    if "transfer" in lowered:
        return "Transferencia"
    if "domic" in lowered or "recibo" in lowered:
        return "Domiciliacion"
    if "tarjeta" in lowered:
        return "Tarjeta"
    if "efectivo" in lowered or "contado" in lowered:
        return "Efectivo"
    return candidate[:80]


def extract_iban(raw_text: str) -> str:
    match = re.search(r"\b([A-Z]{2}\d{2}(?:[\s-]?\d{4}){5})\b", raw_text, re.IGNORECASE)
    if not match:
        return ""
    return re.sub(r"[\s-]", "", match.group(1).upper())


def build_extraction_document(
    *,
    invoice: InvoiceData,
    raw_text: str,
    filename: str,
    mime_type: str,
    pages: int,
    input_profile: dict[str, Any],
    provider: str,
    method: str,
    warnings: list[str],
    bundle: DocumentBundle | None = None,
    company_context: dict[str, str] | None = None,
    company_match: dict[str, Any] | None = None,
    semantics: DocumentSemanticResolution | None = None,
) -> NormalizedInvoiceDocument:
    bundle = bundle or DocumentBundle(raw_text=raw_text)
    if input_profile.get("document_family_hint"):
        bundle.input_profile.document_family_hint = input_profile.get("document_family_hint", "")
    semantics = semantics or document_semantic_resolver.resolve(
        invoice=invoice,
        raw_text=raw_text,
        bundle=bundle,
        company_match=company_match,
        company_context=company_context,
    )
    return build_normalized_document_from_invoice_data(
        invoice,
        source_channel="web",
        input_kind=input_profile.get("input_kind", ""),
        text_source=input_profile.get("text_source", ""),
        file_name=filename,
        mime_type=mime_type,
        page_count=pages,
        ocr_engine=input_profile.get("ocr_engine", ""),
        preprocessing_steps=input_profile.get("preprocessing_steps", []),
        extraction_provider=provider,
        extraction_method=method,
        document_type=semantics.document_type,
        tax_regime=semantics.tax_regime,
        due_date=extract_due_date(raw_text),
        payment_method=extract_payment_method(raw_text),
        iban=extract_iban(raw_text),
        invoice_side=semantics.invoice_side,
        operation_kind=semantics.operation_kind,
        is_rectificative=semantics.is_rectificative,
        is_simplified=semantics.is_simplified,
        warnings=warnings,
        raw_text_excerpt=raw_text[:400],
    )


def build_extraction_coverage(normalized_document: NormalizedInvoiceDocument) -> ExtractionCoverage:
    field_checks = {
        "classification.document_type": normalized_document.classification.document_type != "desconocido",
        "classification.invoice_side": normalized_document.classification.invoice_side != "desconocida",
        "identity.issue_date": bool(normalized_document.identity.issue_date),
        "identity.invoice_number": bool(normalized_document.identity.invoice_number),
        "issuer.name": bool(normalized_document.issuer.name),
        "issuer.tax_id": bool(normalized_document.issuer.tax_id),
        "totals.subtotal": abs(normalized_document.totals.subtotal) > 0,
        "totals.total": abs(normalized_document.totals.total) > 0,
        "tax_breakdown": bool(normalized_document.tax_breakdown),
        "line_items": bool(normalized_document.line_items),
    }
    present_fields = [field_name for field_name in PRIORITY_CONTRACT_FIELDS if field_checks[field_name]]
    missing_fields = [field_name for field_name in PRIORITY_CONTRACT_FIELDS if not field_checks[field_name]]
    ratio = round(len(present_fields) / len(PRIORITY_CONTRACT_FIELDS), 2)
    return ExtractionCoverage(
        required_fields_present=present_fields,
        missing_required_fields=missing_fields,
        completeness_ratio=ratio,
    )
