from __future__ import annotations

from pydantic import BaseModel, Field


class BoundingBox(BaseModel):
    x0: float = 0
    y0: float = 0
    x1: float = 0
    y1: float = 0

    @property
    def width(self) -> float:
        return max(0.0, self.x1 - self.x0)

    @property
    def height(self) -> float:
        return max(0.0, self.y1 - self.y0)

    @classmethod
    def from_points(cls, x0: float, y0: float, x1: float, y1: float) -> "BoundingBox":
        return cls(
            x0=min(x0, x1),
            y0=min(y0, y1),
            x1=max(x0, x1),
            y1=max(y0, y1),
        )


class DocumentSpan(BaseModel):
    span_id: str = ""
    page: int = 0
    text: str = ""
    bbox: BoundingBox = Field(default_factory=BoundingBox)
    source: str = ""
    engine: str = ""
    block_no: int = 0
    line_no: int = 0
    confidence: float | None = None


class DocumentPageBundle(BaseModel):
    page_number: int = 0
    width: float = 0
    height: float = 0
    native_text: str = ""
    ocr_text: str = ""
    reading_text: str = ""
    spans: list[DocumentSpan] = Field(default_factory=list)


class LayoutRegion(BaseModel):
    region_id: str = ""
    region_type: str = ""
    page: int = 0
    bbox: BoundingBox = Field(default_factory=BoundingBox)
    text: str = ""
    span_ids: list[str] = Field(default_factory=list)
    confidence: float = 0


class DocumentBundle(BaseModel):
    raw_text: str = ""
    page_count: int = 0
    page_texts: list[str] = Field(default_factory=list)
    pages: list[DocumentPageBundle] = Field(default_factory=list)
    spans: list[DocumentSpan] = Field(default_factory=list)
    regions: list[LayoutRegion] = Field(default_factory=list)
