from app.models.invoice_model import InvoiceData, LineItem
from app.models.document_bundle import BoundingBox, DocumentBundle, DocumentPageBundle, DocumentSpan, LayoutRegion
from app.models.extraction_result import (
    CompanyMatch,
    DecisionFlag,
    DocumentInputProfile,
    ExtractionCoverage,
    ExtractionResult,
    FieldEvidence,
    ProcessingTraceItem,
)
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
