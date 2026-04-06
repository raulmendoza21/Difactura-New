from __future__ import annotations

from pydantic import BaseModel, Field

from app.models.document_contract import DocumentType, InvoiceSide, OperationKind, TaxRegime


class DocumentSemanticResolution(BaseModel):
    document_family: str = "generic"
    document_type: DocumentType = "desconocido"
    invoice_side: InvoiceSide = "desconocida"
    operation_kind: OperationKind = "desconocida"
    tax_regime: TaxRegime = "UNKNOWN"
    is_rectificative: bool = False
    is_simplified: bool = False
    counterparty_role: str = ""
    company_match: dict[str, object] = Field(default_factory=dict)
    decision_trace: list[str] = Field(default_factory=list)
