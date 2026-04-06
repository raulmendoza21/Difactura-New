from __future__ import annotations

import unicodedata

from app.models.document_contract import InvoiceSide, OperationKind
from app.models.invoice_model import InvoiceData
from app.services.text_resolution.company_matching import company_matching_service


class OperationKindService:
    _SALE_KEYWORDS = (
        "cliente",
        "destinatario",
        "comprador",
        "nuestra factura",
        "le facturamos",
        "factura de venta",
    )
    _PURCHASE_KEYWORDS = (
        "proveedor",
        "emisor",
        "datos de facturacion",
        "datos de envio",
        "albaran",
        "su factura",
        "retencion irpf",
    )

    def resolve(
        self,
        *,
        invoice: InvoiceData,
        raw_text: str,
        document_type: str,
        document_family: str,
        company_match: dict[str, object],
        company_context: dict[str, str] | None = None,
    ) -> tuple[OperationKind, list[str]]:
        purchase_score = 0
        sale_score = 0
        trace: list[str] = []
        company = company_matching_service.normalize_company_context(company_context)
        normalized_text = self._normalize_text(raw_text)

        matched_role = str(company_match.get("matched_role", "") or "")
        if matched_role == "issuer":
            sale_score += 120
            trace.append("operation:issuer_matches_company:+120_sale")
        elif matched_role == "recipient":
            purchase_score += 120
            trace.append("operation:recipient_matches_company:+120_purchase")
        elif matched_role == "ambiguous":
            trace.append("operation:ambiguous_company_match")

        declared_kind = str(invoice.tipo_factura or "").strip().lower()
        if not matched_role:
            if declared_kind == "venta":
                sale_score += 2
                trace.append("operation:declared_sale:+2_sale")
            elif declared_kind == "compra":
                purchase_score += 2
                trace.append("operation:declared_purchase:+2_purchase")

        if document_family == "shipping_billing_purchase":
            purchase_score += 24
            trace.append("operation:shipping_billing:+24_purchase")
        elif document_family == "withholding_purchase":
            purchase_score += 12
            trace.append("operation:withholding:+12_purchase")
        elif document_family == "company_sale" and matched_role == "issuer":
            sale_score += 18
            trace.append("operation:visual_summary_with_company_issuer:+18_sale")

        if document_type in {"ticket", "factura_simplificada"}:
            if matched_role == "recipient":
                purchase_score += 8
                trace.append("operation:simplified_recipient_match:+8_purchase")
            elif matched_role == "issuer":
                sale_score += 8
                trace.append("operation:simplified_issuer_match:+8_sale")
            elif invoice.proveedor and not invoice.cliente:
                purchase_score += 5
                trace.append("operation:simplified_provider_only:+5_purchase")

        if invoice.proveedor and not invoice.cliente:
            purchase_score += 3
            trace.append("operation:provider_only:+3_purchase")
        if invoice.cliente and not invoice.proveedor:
            sale_score += 3
            trace.append("operation:client_only:+3_sale")

        purchase_lexical = self._keyword_score(normalized_text, self._PURCHASE_KEYWORDS)
        sale_lexical = self._keyword_score(normalized_text, self._SALE_KEYWORDS)
        if purchase_lexical:
            purchase_score += purchase_lexical
            trace.append(f"operation:purchase_lexical:+{purchase_lexical}_purchase")
        if sale_lexical:
            sale_score += sale_lexical
            trace.append(f"operation:sale_lexical:+{sale_lexical}_sale")

        provider_matches_context = company_matching_service.matches_company_context(
            invoice.proveedor,
            invoice.cif_proveedor,
            company,
        )
        client_matches_context = company_matching_service.matches_company_context(
            invoice.cliente,
            invoice.cif_cliente,
            company,
        )
        if provider_matches_context:
            sale_score += 35
            trace.append("operation:provider_matches_context:+35_sale")
        if client_matches_context:
            purchase_score += 35
            trace.append("operation:client_matches_context:+35_purchase")

        if sale_score <= 0 and purchase_score <= 0:
            trace.append("operation:no_signal")
            return "desconocida", trace
        if abs(sale_score - purchase_score) < 15:
            trace.append(f"operation:ambiguous_scores sale={sale_score} purchase={purchase_score}")
            return "desconocida", trace
        if sale_score > purchase_score:
            trace.append(f"operation:resolved_sale sale={sale_score} purchase={purchase_score}")
            return "venta", trace
        trace.append(f"operation:resolved_purchase sale={sale_score} purchase={purchase_score}")
        return "compra", trace

    def resolve_invoice_side(self, *, operation_kind: OperationKind, company_match: dict[str, object]) -> tuple[InvoiceSide, list[str]]:
        if operation_kind == "venta":
            return "emitida", ["invoice_side:emitida_from_sale"]
        if operation_kind == "compra":
            return "recibida", ["invoice_side:recibida_from_purchase"]
        matched_role = str(company_match.get("matched_role", "") or "")
        if matched_role == "issuer":
            return "emitida", ["invoice_side:emitida_from_company_match"]
        if matched_role == "recipient":
            return "recibida", ["invoice_side:recibida_from_company_match"]
        return "desconocida", ["invoice_side:unknown"]

    def resolve_counterparty_role(self, *, operation_kind: OperationKind) -> str:
        if operation_kind == "venta":
            return "recipient"
        if operation_kind == "compra":
            return "issuer"
        return ""

    def _keyword_score(self, normalized_text: str, keywords: tuple[str, ...]) -> int:
        return sum(3 for keyword in keywords if keyword in normalized_text)

    def _normalize_text(self, raw_text: str) -> str:
        return "".join(
            char
            for char in unicodedata.normalize("NFKD", (raw_text or "").lower())
            if not unicodedata.combining(char)
        )


operation_kind_service = OperationKindService()
