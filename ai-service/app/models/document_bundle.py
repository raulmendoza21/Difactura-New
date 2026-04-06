from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

BundleContractName = Literal["difactura.document_bundle"]
BundleContractVersion = Literal["2026-03-30"]


class BundleContractInfo(BaseModel):
    name: BundleContractName = "difactura.document_bundle"
    version: BundleContractVersion = "2026-03-30"


class BundleInputProfile(BaseModel):
    input_kind: str = ""
    text_source: str = ""
    requested_provider: str = ""
    document_provider: str = ""
    fallback_provider: str = ""
    fallback_applied: bool = False
    fallback_reason: str = ""
    is_digital_pdf: bool = False
    used_ocr: bool = False
    used_page_images: bool = False
    ocr_engine: str = ""
    preprocessing_steps: list[str] = Field(default_factory=list)
    document_family_hint: str = ""
    low_resolution: bool = False
    rotation_hint: str = ""
    input_route: str = ""


class BundleSourceStats(BaseModel):
    page_count: int = 0
    total_spans: int = 0
    native_span_count: int = 0
    ocr_span_count: int = 0
    region_count: int = 0


class BundleCandidate(BaseModel):
    candidate_id: str = ""
    field: str = ""
    value: str = ""
    source: str = ""
    extractor: str = ""
    page: int = 0
    region_type: str = ""
    bbox: "BoundingBox" = Field(default_factory=lambda: BoundingBox())
    score: float = 0


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
    contract: BundleContractInfo = Field(default_factory=BundleContractInfo)
    input_profile: BundleInputProfile = Field(default_factory=BundleInputProfile)
    source_stats: BundleSourceStats = Field(default_factory=BundleSourceStats)
    raw_text: str = ""
    page_count: int = 0
    page_texts: list[str] = Field(default_factory=list)
    pages: list[DocumentPageBundle] = Field(default_factory=list)
    spans: list[DocumentSpan] = Field(default_factory=list)
    regions: list[LayoutRegion] = Field(default_factory=list)
    candidate_groups: dict[str, list[BundleCandidate]] = Field(default_factory=dict)

    def refresh_derived_state(self) -> None:
        computed_page_count = len(self.pages) if self.pages else self.page_count
        computed_page_texts = [page.reading_text for page in self.pages] if self.pages else self.page_texts
        self.page_count = computed_page_count
        self.page_texts = computed_page_texts
        self.source_stats = BundleSourceStats(
            page_count=self.page_count,
            total_spans=len(self.spans),
            native_span_count=sum(1 for span in self.spans if span.source == "pdf_native"),
            ocr_span_count=sum(1 for span in self.spans if span.source.startswith("ocr")),
            region_count=len(self.regions),
        )
