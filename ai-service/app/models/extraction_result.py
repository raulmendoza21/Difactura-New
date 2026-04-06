from typing import Literal

from pydantic import BaseModel, Field

from app.models.document_bundle import BoundingBox, BundleInputProfile
from app.models.document_contract import NormalizedInvoiceDocument
from app.models.invoice_model import InvoiceData


EngineContractName = Literal["difactura.document_engine"]
EngineContractVersion = Literal["2026-03-30"]
EngineCompatibilityMode = Literal["legacy_flattened_v1"]
PrimaryPayload = Literal["normalized_document"]
EvidenceValueKind = Literal["observed", "resolved", "inferred"]


class EngineContractInfo(BaseModel):
    name: EngineContractName = "difactura.document_engine"
    version: EngineContractVersion = "2026-03-30"
    primary_payload: PrimaryPayload = "normalized_document"
    compatibility_mode: EngineCompatibilityMode = "legacy_flattened_v1"


class EngineCompanyContext(BaseModel):
    name: str = ""
    tax_id: str = ""


class EngineRequestOptions(BaseModel):
    include_raw_text: bool = True
    include_evidence: bool = True
    include_processing_trace: bool = True


class EngineRequestContext(BaseModel):
    file_name: str = ""
    mime_type: str = ""
    company_context: EngineCompanyContext = Field(default_factory=EngineCompanyContext)
    options: EngineRequestOptions = Field(default_factory=EngineRequestOptions)


DocumentInputProfile = BundleInputProfile


class ExtractionCoverage(BaseModel):
    required_fields_present: list[str] = Field(default_factory=list)
    missing_required_fields: list[str] = Field(default_factory=list)
    completeness_ratio: float = 0


class FieldEvidence(BaseModel):
    field: str = ""
    value: str = ""
    value_kind: EvidenceValueKind = "observed"
    source: str = ""
    extractor: str = ""
    is_final: bool = False
    requires_review: bool = False
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
    contract: EngineContractInfo = Field(default_factory=EngineContractInfo)
    engine_request: EngineRequestContext = Field(default_factory=EngineRequestContext)
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
    warnings: list[str] = Field(default_factory=list)
    errors: list[str] = Field(default_factory=list)

    def to_api_payload(self) -> dict:
        legacy_data = self.data.model_dump()
        return {
            "contract": self.contract.model_dump(),
            "engine_request": self.engine_request.model_dump(),
            "success": self.success,
            "legacy_data": legacy_data,
            **legacy_data,
            "document_input": self.document_input.model_dump(),
            "field_confidence": self.field_confidence,
            "normalized_document": self.normalized_document.model_dump(),
            "coverage": self.coverage.model_dump(),
            "evidence": {
                key: [item.model_dump() for item in items]
                for key, items in self.evidence.items()
            },
            "decision_flags": [item.model_dump() for item in self.decision_flags],
            "company_match": self.company_match.model_dump(),
            "processing_trace": [item.model_dump() for item in self.processing_trace],
            "raw_text": self.raw_text,
            "method": self.method,
            "provider": self.provider,
            "pages": self.pages,
            "warnings": self.warnings,
        }
