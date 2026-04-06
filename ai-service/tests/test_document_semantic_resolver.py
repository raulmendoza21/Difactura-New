from app.models.document_bundle import BundleInputProfile, DocumentBundle
from app.models.invoice_model import InvoiceData
from app.services.document_semantic_resolver import document_semantic_resolver
from app.services.text_resolution.result_building import document_result_builder


def test_semantic_resolver_prefers_company_match_for_sales_documents():
    invoice = InvoiceData(
        proveedor="Tecnocanarias Soluciones Digitales SL",
        cif_proveedor="B12345678",
        cliente="Cliente Final SL",
        cif_cliente="B55555555",
        total=121.0,
    )
    bundle = DocumentBundle(raw_text="FACTURA\nDOCUMENTO\nFECHA\nCONCEPTO\nTOTAL")

    semantics = document_semantic_resolver.resolve(
        invoice=invoice,
        raw_text=bundle.raw_text,
        bundle=bundle,
        company_context={
            "name": "Tecnocanarias Soluciones Digitales SL",
            "tax_id": "B12345678",
        },
    )

    assert semantics.operation_kind == "venta"
    assert semantics.invoice_side == "emitida"
    assert semantics.counterparty_role == "recipient"
    assert semantics.company_match["matched_role"] == "issuer"


def test_semantic_resolver_marks_rectificative_purchases_when_company_is_recipient():
    invoice = InvoiceData(
        numero_factura="AB202600002",
        rectified_invoice_number="F-2025-122",
        proveedor="FLORBRIC, S. L",
        cif_proveedor="B76099134",
        cliente="Disoft Servicios Informaticos SL",
        cif_cliente="B35222249",
        base_imponible=-25.0,
        iva_porcentaje=7.0,
        iva=-1.75,
        total=-26.75,
    )
    bundle = DocumentBundle(raw_text="Factura rectificativa\nRectifica a F-2025-122\nTotal -26,75")

    semantics = document_semantic_resolver.resolve(
        invoice=invoice,
        raw_text=bundle.raw_text,
        bundle=bundle,
        company_context={
            "name": "Disoft Servicios Informaticos SL",
            "tax_id": "B35222249",
        },
    )

    assert semantics.document_type == "factura_rectificativa"
    assert semantics.is_rectificative is True
    assert semantics.operation_kind == "compra"
    assert semantics.invoice_side == "recibida"
    assert semantics.company_match["matched_role"] == "recipient"


def test_semantic_resolver_prefers_simplified_invoice_over_ticket_hint():
    invoice = InvoiceData(numero_factura="2026/900213-00004245", total=8.50)
    bundle = DocumentBundle(
        raw_text="DINOSOL SUPERMERCADOS, S.L.\nDOCUMENTO DE VENTA\nFACTURA SIMPLIFICADA\nTOTAL COMPRA 8,50",
        input_profile=BundleInputProfile(document_family_hint="ticket"),
    )

    document_type = document_semantic_resolver.resolve_document_type(
        raw_text=bundle.raw_text,
        invoice=invoice,
        bundle=bundle,
    )

    assert document_type == "factura_simplificada"


def test_semantic_resolver_keeps_sale_when_company_is_issuer_despite_purchase_keywords():
    invoice = InvoiceData(
        proveedor="Tecnocanarias Soluciones Digitales SL",
        cif_proveedor="B12345678",
        cliente="Cliente Final SL",
        cif_cliente="B55555555",
        total=121.0,
    )
    raw_text = (
        "FACTURA\n"
        "Datos de facturacion\n"
        "Datos de envio\n"
        "Proveedor\n"
        "Cliente\n"
        "Total 121,00\n"
    )

    semantics = document_semantic_resolver.resolve(
        invoice=invoice,
        raw_text=raw_text,
        bundle=DocumentBundle(raw_text=raw_text),
        company_context={
            "name": "Tecnocanarias Soluciones Digitales SL",
            "tax_id": "B12345678",
        },
    )

    assert semantics.operation_kind == "venta"
    assert semantics.invoice_side == "emitida"


def test_build_extraction_document_uses_semantic_resolution_for_invoice_side():
    invoice = InvoiceData(
        numero_factura="F-2026-001",
        fecha="2026-03-15",
        proveedor="Tecnocanarias Soluciones Digitales SL",
        cif_proveedor="B12345678",
        cliente="Cliente Final SL",
        cif_cliente="B55555555",
        base_imponible=100.0,
        iva_porcentaje=7.0,
        iva=7.0,
        total=107.0,
    )

    normalized = document_result_builder.build_extraction_document(
        invoice=invoice,
        raw_text="FACTURA\nDOCUMENTO\nFECHA\nCONCEPTO\nTOTAL",
        filename="factura.pdf",
        mime_type="application/pdf",
        pages=1,
        input_profile={
            "input_kind": "pdf_digital",
            "text_source": "digital_text",
            "ocr_engine": "",
            "preprocessing_steps": ["pdf_text_extraction"],
        },
        provider="heuristic",
        method="doc_bundle",
        warnings=[],
        company_context={
            "name": "Tecnocanarias Soluciones Digitales SL",
            "tax_id": "B12345678",
        },
    )

    assert normalized.classification.invoice_side == "emitida"
    assert normalized.classification.operation_kind == "venta"
