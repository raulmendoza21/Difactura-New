from pydantic import BaseModel, Field
from app.models.invoice_model import InvoiceData


class ExtractionResult(BaseModel):
    success: bool = True
    data: InvoiceData = Field(default_factory=InvoiceData)
    raw_text: str = ""
    method: str = ""
    pages: int = 0
    errors: list[str] = []
