from pydantic import BaseModel, Field

from app.models.invoice import InvoiceData


class ExtractionResult(BaseModel):
    success: bool = True
    data: InvoiceData = Field(default_factory=InvoiceData)
    field_confidence: dict[str, float] = Field(default_factory=dict)
    document_type: str = "factura_completa"
    tax_regime: str = "UNKNOWN"
    operation_side: str = "unknown"
    raw_text: str = ""
    method: str = "heuristic"
    provider: str = "v2_pipeline"
    pages: int = 0
    warnings: list[str] = Field(default_factory=list)

    def to_api_payload(self) -> dict:
        data = self.data.model_dump()
        return {
            "success": self.success,
            **data,
            "field_confidence": self.field_confidence,
            "document_type": self.document_type,
            "tax_regime": self.tax_regime,
            "operation_side": self.operation_side,
            "raw_text": self.raw_text,
            "method": self.method,
            "provider": self.provider,
            "pages": self.pages,
            "warnings": self.warnings,
        }
