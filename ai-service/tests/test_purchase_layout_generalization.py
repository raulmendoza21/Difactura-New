from app.models.document_bundle import DocumentBundle
from app.models.invoice_model import InvoiceData
from app.services.field_extraction.amount_parts.summary import extract_footer_tax_summary
from app.services.text_resolution.document_family import document_family_service
from app.services.text_resolution.family_corrections import family_correction_service


PURCHASE_LAYOUT_RAW_TEXT = "\n".join(
    [
        "Fecha: 06/03/2026",
        "Nº Factura: GC 26001163",
        "Importe: 26,75",
        "Factura",
        "Datos de ENVÍO",
        "DISOFT SERVICIOS INFORMATICOS",
        "Datos de FACTURACIÓN",
        "DISOFT SERV. INFORM S.L.",
        "CIF B-35.222.249",
        "Part. Nº",
        "DESCRIPCIÓN",
        "UDS.",
        "PRECIO % DTO.",
        "NETO",
        "ESDPBU1Y-1A4 ANTIVIRUS AVAST PREMIUM BUSINESS SECURITY 1YEAR 1-4 USUARIOS (XIT DIGITAL) WHQD3M9MKK3P6CXWV34MFTR2X",
        "1,00",
        "25,00",
        "25,00",
        "Conceptos",
        "Portes",
        "Impuestos % Impuestos",
        "Importe neto",
        "Descuento",
        "Ajuste",
        "Base imponible",
        "Total",
        "Valor",
        "0",
        "7%",
        "1,75",
        "25,00",
        "0,00",
        "25,00",
        "26,75",
        "Alberto Villacorta, S.L.U. - Registro Mercantil de Las Palmas - CIF B35246388",
    ]
)


def test_detect_document_family_handles_shipping_billing_headers_with_accents():
    family, trace = document_family_service.detect(
        raw_text=PURCHASE_LAYOUT_RAW_TEXT,
        invoice=InvoiceData(
            numero_factura="GC 26001163",
            fecha="2026-03-06",
            proveedor="Alberto Villacorta, S.L.U",
            cif_proveedor="B35246388",
            cliente="DISOFT SERV. INFORM S.L.",
            cif_cliente="B35222249",
        ),
        bundle=DocumentBundle(raw_text=PURCHASE_LAYOUT_RAW_TEXT),
        company_context={"name": "Disoft Servicios Informaticos SL", "tax_id": "B35222249"},
    )

    assert family == "shipping_billing_purchase"
    assert "family:shipping_billing_purchase" in trace


def test_extract_footer_tax_summary_reads_collapsed_value_column_layout():
    summary = extract_footer_tax_summary(PURCHASE_LAYOUT_RAW_TEXT)

    assert summary["base_imponible"] == 25.0
    assert summary["iva_porcentaje"] == 7.0
    assert summary["iva"] == 1.75
    assert summary["total"] == 26.75


PURCHASE_LAYOUT_MULTIUNIT_RAW_TEXT = "\n".join(
    [
        "Fecha: 09/01/2026",
        "NÂº Factura: GC 26000116",
        "Importe: 160,50",
        "Factura",
        "Datos de ENVIO",
        "DISOFT SERVICIOS INFORMATICOS",
        "Datos de FACTURACIÃ“N",
        "DISOFT SERV. INFORM S.L.",
        "CIF B-35.222.249",
        "Factura nÃºm GC 26000116",
        "Entrada factura TOMAS M.",
        "Part. NÂº",
        "DESCRIPCIÃ“N",
        "UDS.",
        "PRECIO % DTO.",
        "NETO",
        "ANTIVIRUS AVAST PREMIUM BUSINESS SECURITY 1YEAR 1-4 USUARIOS (KIT DIGITAL)",
        "6,00",
        "25,00",
        "150,00",
        "Conceptos",
        "Portes",
        "Impuestos % Impuestos",
        "Importe neto",
        "Descuento",
        "Ajuste",
        "Base imponible",
        "Total",
        "Valor",
        "0",
        "7%",
        "10,50",
        "150,00",
        "0,00",
        "150,00",
        "160,50",
        "Alberto Villacorta, S.L.U. - Registro Mercantil de Las Palmas - CIF B35246388",
    ]
)


def test_family_correction_shipping_billing_prefers_footer_supplier_over_company_billing_block():
    normalized = InvoiceData(
        numero_factura="GC 26000116",
        fecha="2026-01-09",
        proveedor="DISOFT SERV. INFORM S.L.",
        cif_proveedor="26000116E",
        cliente="DISOFT SERVICIOS INFORMATICOS",
        cif_cliente="B35222249",
        base_imponible=150.0,
        iva_porcentaje=7.0,
        iva=10.5,
        total=160.5,
    )
    fallback = normalized.model_copy(deep=True)

    warnings = family_correction_service.apply_family_corrections(
        normalized,
        fallback,
        raw_text=PURCHASE_LAYOUT_MULTIUNIT_RAW_TEXT,
        company_context={"name": "Disoft Servicios Informaticos SL", "tax_id": "B35222249"},
    )

    assert normalized.proveedor == "Alberto Villacorta, S.L.U."
    assert normalized.cif_proveedor == "B35246388"
    assert normalized.cliente == "Disoft Servicios Informaticos SL"
    assert normalized.cif_cliente == "B35222249"
    assert "familia_shipping_billing_proveedor_corregido" in warnings
