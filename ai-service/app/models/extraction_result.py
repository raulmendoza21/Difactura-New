from pydantic import BaseModel, Field
from app.models.document_contract import NormalizedInvoiceDocument
from app.models.invoice_model import InvoiceData


class ExtractionCoverage(BaseModel):
    required_fields_present: list[str] = Field(default_factory=list)
    missing_required_fields: list[str] = Field(default_factory=list)
    completeness_ratio: float = 0


class ExtractionResult(BaseModel):
    success: bool = True
    data: InvoiceData = Field(default_factory=InvoiceData)
    normalized_document: NormalizedInvoiceDocument = Field(default_factory=NormalizedInvoiceDocument)
    coverage: ExtractionCoverage = Field(default_factory=ExtractionCoverage)
    raw_text: str = ""
    method: str = ""
    pages: int = 0
    errors: list[str] = Field(default_factory=list)
