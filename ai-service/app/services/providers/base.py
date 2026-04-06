from __future__ import annotations

from abc import ABC, abstractmethod

from app.models.document_provider import ProviderDocumentResult


class DocumentParserProvider(ABC):
    name: str = ""

    @abstractmethod
    def extract_pdf(self, file_path: str, *, include_page_images: bool = True) -> ProviderDocumentResult:
        raise NotImplementedError

    @abstractmethod
    def extract_image(
        self,
        file_path: str,
        *,
        mime_type: str = "",
        input_kind: str = "image_scan",
        include_page_images: bool = True,
    ) -> ProviderDocumentResult:
        raise NotImplementedError

    @abstractmethod
    def extract_region_hints(self, file_path: str, *, input_kind: str = "pdf_scanned", max_pages: int = 1) -> list[dict]:
        raise NotImplementedError

    def is_available(self) -> bool:
        return True
