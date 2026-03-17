"""Classify invoices by type using rules-based approach."""

import logging
import re

logger = logging.getLogger(__name__)

# Keywords that indicate invoice type
COMPRA_KEYWORDS = [
    "proveedor", "emisor", "suministro", "pedido",
    "albar[aá]n", "entrega", "su factura",
]

VENTA_KEYWORDS = [
    "cliente", "destinatario", "comprador",
    "nuestra factura", "le facturamos", "factura de venta",
]


class InvoiceClassifier:
    """Classify invoice type (compra/venta) based on text content."""

    def classify(self, text: str, proveedor: str = "", cliente: str = "") -> str:
        """Determine if an invoice is 'compra' or 'venta'.

        Uses keyword matching and entity analysis.
        Returns: 'compra', 'venta', or '' if uncertain.
        """
        text_lower = text.lower()

        compra_score = 0
        venta_score = 0

        # Check keyword presence
        for kw in COMPRA_KEYWORDS:
            if re.search(kw, text_lower):
                compra_score += 1

        for kw in VENTA_KEYWORDS:
            if re.search(kw, text_lower):
                venta_score += 1

        # If we have proveedor info but no cliente, likely a purchase invoice
        if proveedor and not cliente:
            compra_score += 2

        # If we have cliente info but no proveedor, likely a sales invoice
        if cliente and not proveedor:
            venta_score += 2

        logger.info(
            f"Classification scores: compra={compra_score}, venta={venta_score}"
        )

        if compra_score > venta_score:
            return "compra"
        elif venta_score > compra_score:
            return "venta"
        else:
            # Default to compra (more common use case for invoice processing)
            return "compra"


invoice_classifier = InvoiceClassifier()
