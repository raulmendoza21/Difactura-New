from app.models.invoice_model import InvoiceData, LineItem
from app.models.extraction_result import ExtractionCoverage, ExtractionResult
from app.models.document_contract import (
    AccountingProposal,
    AccountingProposalLine,
    DocumentClassification,
    DocumentMeta,
    NormalizedInvoiceDocument,
    TaxBreakdownItem,
    ValidatedResult,
    WithholdingBreakdownItem,
    build_normalized_document_from_invoice_data,
)
