from pydantic import BaseModel, Field

from app.models.document_bundle import BoundingBox
from app.models.document_contract import NormalizedInvoiceDocument
from app.models.invoice_model import InvoiceData


class DocumentInputProfile(BaseModel):
    input_kind: str = ""
    text_source: str = ""
    is_digital_pdf: bool = False
    used_ocr: bool = False
    used_page_images: bool = False
    ocr_engine: str = ""
    preprocessing_steps: list[str] = Field(default_factory=list)
    document_family_hint: str = ""
    low_resolution: bool = False
    rotation_hint: str = ""
    input_route: str = ""


class ExtractionCoverage(BaseModel):
    required_fields_present: list[str] = Field(default_factory=list)
    missing_required_fields: list[str] = Field(default_factory=list)
    completeness_ratio: float = 0


class FieldEvidence(BaseModel):
    field: str = ""
    value: str = ""
    source: str = ""
    extractor: str = ""
    page: int = 0
    bbox: BoundingBox = Field(default_factory=BoundingBox)
    score: float = 0
    text: str = ""


class DecisionFlag(BaseModel):
    code: str = ""
    severity: str = "info"
    message: str = ""
    field: str = ""
    requires_review: bool = False


class CompanyMatch(BaseModel):
    issuer_matches_company: bool = False
    recipient_matches_company: bool = False
    matched_role: str = ""
    matched_by: str = ""
    confidence: float = 0


class ProcessingTraceItem(BaseModel):
    stage: str = ""
    summary: str = ""
    engine: str = ""


class ExtractionResult(BaseModel):
    success: bool = True
    data: InvoiceData = Field(default_factory=InvoiceData)
    document_input: DocumentInputProfile = Field(default_factory=DocumentInputProfile)
    field_confidence: dict[str, float] = Field(default_factory=dict)
    normalized_document: NormalizedInvoiceDocument = Field(default_factory=NormalizedInvoiceDocument)
    coverage: ExtractionCoverage = Field(default_factory=ExtractionCoverage)
    evidence: dict[str, list[FieldEvidence]] = Field(default_factory=dict)
    decision_flags: list[DecisionFlag] = Field(default_factory=list)
    company_match: CompanyMatch = Field(default_factory=CompanyMatch)
    processing_trace: list[ProcessingTraceItem] = Field(default_factory=list)
    raw_text: str = ""
    method: str = ""
    provider: str = ""
    pages: int = 0
    errors: list[str] = Field(default_factory=list)
