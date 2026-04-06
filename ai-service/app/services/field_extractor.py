"""Extract structured invoice fields from raw text using modular resolvers."""

from __future__ import annotations

import logging

from app.models.document_bundle import DocumentBundle
from app.models.invoice_model import InvoiceData
from app.services.field_extraction.amounts import extract_amounts_payload, infer_amounts
from app.services.field_extraction.bundle import extract_from_bundle as extract_bundle_payload
from app.services.field_extraction.identity import extract_identity
from app.services.field_extraction.line_items import extract_line_items
from app.services.field_extraction.parties import (
    apply_party_postprocessing,
    extract_cifs,
    extract_customer_from_shipping_billing,
    extract_name,
    extract_parties_payload,
)
from app.utils.text_processing import normalize_text

logger = logging.getLogger(__name__)


class FieldExtractor:
    """Public facade for modular field extraction."""

    def extract(self, text: str) -> InvoiceData:
        normalized_text = normalize_text(text)
        lines = [line.strip() for line in normalized_text.split("\n") if line.strip()]
        data = InvoiceData()

        identity = extract_identity(normalized_text, lines)
        data.numero_factura = identity["numero_factura"]
        data.rectified_invoice_number = identity["rectified_invoice_number"]
        data.fecha = identity["fecha"]

        cifs = extract_cifs(normalized_text)
        parties = extract_parties_payload(normalized_text, lines)
        shipping_customer_name, shipping_customer_tax_id = extract_customer_from_shipping_billing(lines)
        data.proveedor = parties["proveedor"] or extract_name(normalized_text, "proveedor")
        data.cliente = shipping_customer_name or parties["cliente"] or extract_name(normalized_text, "cliente")
        data.cif_proveedor = parties["cif_proveedor"]
        data.cif_cliente = shipping_customer_tax_id or parties["cif_cliente"]
        apply_party_postprocessing(data, normalized_text, lines, cifs)

        amounts = extract_amounts_payload(normalized_text, lines)
        data.base_imponible = amounts["base_imponible"]
        data.iva_porcentaje = amounts["iva_porcentaje"]
        data.iva = amounts["iva"]
        data.retencion_porcentaje = amounts["retencion_porcentaje"]
        data.retencion = amounts["retencion"]
        data.total = amounts["total"]
        infer_amounts(data)

        data.lineas = extract_line_items(normalized_text)
        if not data.lineas and text and text != normalized_text:
            data.lineas = extract_line_items(text)
        if not data.lineas:
            from app.services.field_extraction.line_item_parts.recovery import (
                recover_single_description_amount_from_raw_text,
                recover_single_description_amount_item,
            )
            from app.services.field_extraction.line_item_parts.table import build_footer_pattern, collect_table_lines

            table_lines = collect_table_lines(lines)
            if table_lines:
                data.lineas = recover_single_description_amount_item(table_lines, build_footer_pattern())
            if not data.lineas:
                data.lineas = recover_single_description_amount_from_raw_text(text)

        logger.info(
            "Extracted: invoice=%s, date=%s, total=%s",
            data.numero_factura,
            data.fecha,
            data.total,
        )
        return data

    def extract_from_bundle(self, bundle: DocumentBundle) -> tuple[InvoiceData, dict[str, InvoiceData]]:
        return extract_bundle_payload(bundle, self.extract)


field_extractor = FieldExtractor()
