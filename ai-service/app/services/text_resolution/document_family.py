from __future__ import annotations

import re
import unicodedata

from app.models.document_bundle import DocumentBundle
from app.models.invoice_model import InvoiceData
from app.services.text_resolution.company_matching import company_matching_service


class DocumentFamilyService:
    def detect(
        self,
        *,
        raw_text: str,
        invoice: InvoiceData,
        bundle: DocumentBundle,
        company_context: dict[str, str] | None = None,
    ) -> tuple[str, list[str]]:
        upper_text = (raw_text or "").upper()
        compact_text = self._normalize_keyword_text(raw_text)
        hint = bundle.input_profile.document_family_hint or ""
        company = company_matching_service.normalize_company_context(company_context)

        if invoice.rectified_invoice_number or any(token in upper_text for token in ("RECTIFICAT", "FACTURA ABONO", "ABONO")):
            return "rectificativa", ["family:rectificativa"]
        if hint == "ticket" or self.looks_like_ticket(raw_text, invoice):
            return "ticket", [f"family:{hint or 'ticket'}"]
        if hint == "factura_simplificada" or self.looks_like_simplified_invoice(raw_text, invoice):
            return "factura_simplificada", [f"family:{hint or 'factura_simplificada'}"]
        if self.looks_like_shipping_billing_purchase(compact_text):
            return "shipping_billing_purchase", ["family:shipping_billing_purchase"]
        if "IRPF" in upper_text or "RETENCI" in upper_text or "RENTENCI" in upper_text:
            return "withholding_purchase", ["family:withholding_purchase"]
        if self.looks_like_visual_summary_invoice(raw_text, company):
            return "company_sale", ["family:company_sale"]
        if self.looks_like_tabular_invoice(raw_text):
            return "tabular_invoice", ["family:tabular_invoice"]
        return "generic", ["family:generic"]

    def looks_like_ticket(self, raw_text: str, invoice: InvoiceData) -> bool:
        upper_text = (raw_text or "").upper()
        return bool(
            "DOCUMENTO DE VENTA" in upper_text
            or "NO VALIDO COMO FACTURA" in upper_text
            or (
                any(token in upper_text for token in ("TICKET", "TOTAL COMPRA", "A DEVOLVER", "ENTREGADO"))
                and not invoice.cliente
                and abs(invoice.total) > 0
            )
        )

    def looks_like_simplified_invoice(self, raw_text: str, invoice: InvoiceData) -> bool:
        upper_text = (raw_text or "").upper()
        return bool(
            any(token in upper_text for token in ("FACTURA SIMPLIFICADA", "FRA. SIMPLIFICADA", "FRA SIMPLIFICADA"))
            or (abs(invoice.total) > 0 and not invoice.cliente and re.search(r"\bT\d{3,}-", upper_text))
        )

    def looks_like_shipping_billing_purchase(self, normalized_text: str) -> bool:
        upper_text = (normalized_text or "").upper()
        compact_letters = re.sub(r"[^A-Z]", "", upper_text)

        has_shipping = "DATOS DE ENV" in upper_text or "DATOSDEENV" in compact_letters
        has_billing = "DATOS DE FACTUR" in upper_text or "DATOSDEFACTUR" in compact_letters
        return has_shipping and has_billing

    def looks_like_visual_summary_invoice(self, raw_text: str, company_context: dict[str, str]) -> bool:
        upper_text = (raw_text or "").upper()
        keyword_text = self._normalize_keyword_text(raw_text)
        normalized_text = company_matching_service.normalize_party_value(raw_text)
        company_tax_id = company_matching_service.clean_tax_id(company_context.get("tax_id", ""))
        company_anchor = company_matching_service.company_anchor_token(company_context.get("name", ""))
        has_company_anchor = bool(
            (company_tax_id and company_tax_id in normalized_text)
            or (company_anchor and company_anchor in normalized_text)
        )
        has_explicit_party_labels = (
            ("PROVEEDOR" in keyword_text and "CLIENTE" in keyword_text)
            or ("EMISOR" in keyword_text and ("CLIENTE" in keyword_text or "DESTINATARIO" in keyword_text))
        )
        has_header = all(token in upper_text for token in ("FACTURA", "FECHA"))
        has_summary = any(token in upper_text for token in ("%IGIC", "%IVA", "SUBTOTAL", "BASE", "TOTAL"))
        has_body = any(token in upper_text for token in ("CONCEPTO", "IMPORTE", "DESCRIPCI"))
        return has_company_anchor and has_header and has_summary and has_body and not has_explicit_party_labels

    def looks_like_tabular_invoice(self, raw_text: str) -> bool:
        upper_text = (raw_text or "").upper()
        has_description = any(token in upper_text for token in ("CONCEPTO", "DESCRIPCI", "DETALLE", "ARTICULO"))
        has_amount = any(token in upper_text for token in ("IMPORTE", "PRECIO", "NETO", "TOTAL"))
        return has_description and has_amount

    def _normalize_keyword_text(self, value: str) -> str:
        normalized = unicodedata.normalize("NFKD", str(value or ""))
        ascii_text = "".join(char for char in normalized if not unicodedata.combining(char))
        return ascii_text.upper()


document_family_service = DocumentFamilyService()
