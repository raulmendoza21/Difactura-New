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
        file_name="factura.pdf",
        mime_type="application/pdf",
        extraction_provider="ollama",
        extraction_method="doc_ai",
        tax_regime="IGIC",
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
