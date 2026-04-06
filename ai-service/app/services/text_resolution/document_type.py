from __future__ import annotations

from app.models.document_bundle import DocumentBundle
from app.models.document_contract import DocumentType
from app.models.invoice_model import InvoiceData
from app.services.text_resolution.document_family import document_family_service


class DocumentTypeService:
    def resolve(self, *, raw_text: str, invoice: InvoiceData, bundle: DocumentBundle) -> tuple[DocumentType, list[str]]:
        upper_text = (raw_text or "").upper()
        hint = bundle.input_profile.document_family_hint or ""

        if invoice.rectified_invoice_number:
            return "factura_rectificativa", ["document_type:rectified_reference"]
        if any(token in upper_text for token in ("FACTURA RECTIFICAT", "RECTIFICATIVA")):
            return "factura_rectificativa", ["document_type:rectificative_keyword"]
        if "ABONO" in upper_text:
            return "abono", ["document_type:abono_keyword"]
        if hint == "factura_simplificada" or document_family_service.looks_like_simplified_invoice(raw_text, invoice):
            return "factura_simplificada", [f"document_type:{hint or 'factura_simplificada'}"]
        if hint == "ticket" or document_family_service.looks_like_ticket(raw_text, invoice):
            return "ticket", [f"document_type:{hint or 'ticket'}"]
        if "PROFORMA" in upper_text:
            return "proforma", ["document_type:proforma_keyword"]
        if "DUA" in upper_text:
            return "dua", ["document_type:dua_keyword"]
        if invoice.numero_factura or invoice.fecha or abs(invoice.total) > 0:
            return "factura_completa", ["document_type:complete_invoice_fields"]
        return "desconocido", ["document_type:unknown"]


document_type_service = DocumentTypeService()
