from app.models.document_contract import (
    AccountingProposal,
    AccountingProposalLine,
    build_normalized_document_from_invoice_data,
)
from app.models.invoice_model import InvoiceData, LineItem


def test_build_normalized_document_from_invoice_data_maps_basic_fields():
    invoice = InvoiceData(
        numero_factura="F-2026-001",
        tipo_factura="compra",
        fecha="2026-03-15",
        proveedor="Proveedor Demo SL",
        cif_proveedor="B12345678",
        cliente="Empresa Cliente SL",
        cif_cliente="B87654321",
        base_imponible=100.0,
        iva_porcentaje=7.0,
        iva=7.0,
        total=107.0,
        confianza=0.82,
        lineas=[
            LineItem(
                descripcion="Servicio mensual",
                cantidad=1,
                precio_unitario=100,
                importe=100,
            )
        ],
    )

    normalized = build_normalized_document_from_invoice_data(
        invoice,
        source_channel="web",
        input_kind="pdf_digital",
        text_source="digital_text",
        file_name="factura.pdf",
        mime_type="application/pdf",
        page_count=1,
        extraction_provider="ollama",
        extraction_method="doc_ai",
        tax_regime="IGIC",
        preprocessing_steps=["pdf_text_extraction"],
        warnings=["tax_regime_pendiente_revision"],
    )

    assert normalized.classification.invoice_side == "recibida"
    assert normalized.classification.operation_kind == "compra"
    assert normalized.identity.invoice_number == "F-2026-001"
    assert normalized.issuer.tax_id == "B12345678"
    assert normalized.recipient.tax_id == "B87654321"
    assert normalized.totals.total == 107.0
    assert normalized.primary_tax_regime() == "IGIC"
    assert normalized.tax_breakdown[0].rate == 7.0
    assert normalized.line_items[0].description == "Servicio mensual"
    assert normalized.document_meta.extraction_provider == "ollama"
    assert normalized.document_meta.input_kind == "pdf_digital"
    assert normalized.document_meta.text_source == "digital_text"
    assert normalized.document_meta.page_count == 1
    assert normalized.line_items[0].tax_regime == "IGIC"
    assert normalized.line_items[0].tax_rate == 7.0
    assert normalized.line_items[0].tax_amount == 7.0
    assert normalized.line_items[0].line_total == 107.0


def test_build_normalized_document_marks_exempt_tax_breakdown():
    invoice = InvoiceData(
        numero_factura="F-2026-EX-1",
        tipo_factura="compra",
        fecha="2026-03-15",
        proveedor="Proveedor Exento SL",
        total=100.0,
        base_imponible=100.0,
        iva_porcentaje=0.0,
        iva=0.0,
    )

    normalized = build_normalized_document_from_invoice_data(
        invoice,
        tax_regime="EXEMPT",
    )

    assert normalized.tax_breakdown[0].tax_regime == "EXEMPT"
    assert normalized.tax_breakdown[0].is_exempt is True
    assert normalized.tax_breakdown[0].taxable_base == 100.0


def test_build_normalized_document_preserves_negative_rectificative_amounts():
    invoice = InvoiceData(
        numero_factura="AB202600002",
        tipo_factura="compra",
        fecha="2026-01-07",
        proveedor="FLORBRIC, S. L",
        cif_proveedor="B76099134",
        cliente="Disoft Servicios Informaticos SL",
        cif_cliente="B35222249",
        base_imponible=-25.0,
        iva_porcentaje=7.0,
        iva=-1.75,
        total=-26.75,
        lineas=[
            LineItem(
                descripcion="Mantenimiento del Programa de Facturación Facdis",
                cantidad=1,
                precio_unitario=-25.0,
                importe=-25.0,
            )
        ],
    )

    normalized = build_normalized_document_from_invoice_data(
        invoice,
        document_type="factura_rectificativa",
        tax_regime="IGIC",
    )

    assert normalized.totals.subtotal == -25.0
    assert normalized.totals.tax_total == -1.75
    assert normalized.totals.total == -26.75
    assert normalized.classification.is_rectificative is True
    assert normalized.tax_breakdown[0].taxable_base == -25.0
    assert normalized.tax_breakdown[0].tax_amount == -1.75
    assert normalized.line_items[0].line_base == -25.0
    assert normalized.line_items[0].line_total == -26.75


def test_accounting_proposal_balance_helpers_work():
    proposal = AccountingProposal(
        scenario="factura_recibida_gasto_corriente",
        lines=[
            AccountingProposalLine(line_no=1, account_code="62800000", side="DEBE", amount=100.0),
            AccountingProposalLine(line_no=2, account_code="47200007", side="DEBE", amount=7.0),
            AccountingProposalLine(line_no=3, account_code="41000000", side="HABER", amount=107.0),
        ],
    )

    assert proposal.total_debe() == 107.0
    assert proposal.total_haber() == 107.0
    assert proposal.is_balanced() is True


def test_accounting_proposal_detects_unbalanced_entry():
    proposal = AccountingProposal(
        scenario="factura_emitida_ingreso",
        lines=[
            AccountingProposalLine(line_no=1, account_code="43000000", side="DEBE", amount=121.0),
            AccountingProposalLine(line_no=2, account_code="70000000", side="HABER", amount=100.0),
        ],
    )

    assert proposal.is_balanced() is False
