from pydantic import BaseModel, Field

from app.models.document_bundle import DocumentSpan


class ProviderPageEntry(BaseModel):
    page_number: int = 0
    width: float = 0
    height: float = 0
    text: str = ""
    spans: list[DocumentSpan] = Field(default_factory=list)
    ocr_engine: str = ""


class ProviderDocumentResult(BaseModel):
    text: str = ""
    pages: int = 0
    is_digital: bool = False
    method: str = ""
    preprocessing_steps: list[str] = Field(default_factory=list)
    ocr_engine: str = ""
    page_entries: list[ProviderPageEntry] = Field(default_factory=list)
