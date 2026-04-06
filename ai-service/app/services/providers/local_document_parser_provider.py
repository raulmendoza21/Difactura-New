from __future__ import annotations

from app.models.document_bundle import DocumentSpan
from app.models.document_provider import ProviderDocumentResult, ProviderPageEntry
from app.services.providers.base import DocumentParserProvider


class LocalDocumentParserProvider(DocumentParserProvider):
    name = "local"

    def extract_pdf(self, file_path: str, *, include_page_images: bool = True) -> ProviderDocumentResult:
        from app.services.ocr_service import ocr_service
        from app.services.pdf_extractor import pdf_extractor

        pdf_result = pdf_extractor.extract(file_path)
        if pdf_result["is_digital"]:
            return ProviderDocumentResult(
                text=pdf_result["text"],
                pages=int(pdf_result["pages"]),
                is_digital=True,
                method="digital",
                preprocessing_steps=["pdf_text_extraction"],
                page_entries=self._normalize_page_entries(pdf_result.get("page_entries", [])),
            )

        ocr_result = ocr_service.extract_pdf_ocr(file_path, input_kind="pdf_scanned")
        return ProviderDocumentResult(
            text=ocr_result["text"],
            pages=max(int(pdf_result.get("pages", 0) or 0), len(ocr_result.get("page_entries", []) or [])),
            is_digital=False,
            method="ocr",
            preprocessing_steps=list(ocr_result.get("preprocessing_steps", []) or []),
            ocr_engine=str(ocr_result.get("ocr_engine", "") or ""),
            page_entries=self._normalize_page_entries(ocr_result.get("page_entries", [])),
        )

    def extract_image(
        self,
        file_path: str,
        *,
        mime_type: str = "",
        input_kind: str = "image_scan",
        include_page_images: bool = True,
    ) -> ProviderDocumentResult:
        from app.services.ocr_service import ocr_service

        ocr_result = ocr_service.extract_image_ocr(file_path, input_kind=input_kind)
        return ProviderDocumentResult(
            text=ocr_result["text"],
            pages=max(1, len(ocr_result.get("page_entries", []) or [])),
            is_digital=False,
            method="ocr",
            preprocessing_steps=list(ocr_result.get("preprocessing_steps", []) or []),
            ocr_engine=str(ocr_result.get("ocr_engine", "") or ""),
            page_entries=self._normalize_page_entries(ocr_result.get("page_entries", [])),
        )

    def extract_region_hints(self, file_path: str, *, input_kind: str = "pdf_scanned", max_pages: int = 1) -> list[dict]:
        from app.services.ocr_service import ocr_service

        return ocr_service.extract_region_hints(
            file_path,
            input_kind=input_kind,
            max_pages=max_pages,
        )

    def is_available(self) -> bool:
        from app.services.ocr_service import ocr_service

        return ocr_service.is_available()

    def _normalize_page_entries(self, entries: list[dict]) -> list[ProviderPageEntry]:
        normalized: list[ProviderPageEntry] = []
        for index, entry in enumerate(entries, start=1):
            spans = [
                span if isinstance(span, DocumentSpan) else DocumentSpan(**span)
                for span in entry.get("spans", [])
            ]
            normalized.append(
                ProviderPageEntry(
                    page_number=int(entry.get("page_number", index) or index),
                    width=float(entry.get("width", 0) or 0),
                    height=float(entry.get("height", 0) or 0),
                    text=str(entry.get("text", "") or "").strip(),
                    spans=spans,
                    ocr_engine=str(entry.get("ocr_engine", "") or ""),
                )
            )
        return normalized


local_document_parser_provider = LocalDocumentParserProvider()
