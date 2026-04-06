from __future__ import annotations

import logging
from pathlib import Path

from app.config import settings
from app.services.providers.base import DocumentParserProvider
from app.services.providers.mistral_parts.client import create_client
from app.services.providers.mistral_parts.files import (
    delete_file_quietly,
    extract_file_id,
    upload_file,
)
from app.services.providers.mistral_parts.response import (
    expand_page_text,
    markdown_to_spans,
    normalize_compare_text,
    normalize_ocr_response,
    should_include_section_text,
    table_to_plain_text,
    to_mapping,
)

logger = logging.getLogger(__name__)


class MistralDocumentParserProvider(DocumentParserProvider):
    name = "mistral"

    def extract_pdf(self, file_path: str, *, include_page_images: bool = True):
        return self._extract_document(file_path)

    def extract_image(
        self,
        file_path: str,
        *,
        mime_type: str = "",
        input_kind: str = "image_scan",
        include_page_images: bool = True,
    ):
        return self._extract_document(file_path)

    def extract_region_hints(self, file_path: str, *, input_kind: str = "pdf_scanned", max_pages: int = 1) -> list[dict]:
        from app.services.ocr_service import ocr_service

        return ocr_service.extract_region_hints(
            file_path,
            input_kind=input_kind,
            max_pages=max_pages,
        )

    def is_available(self) -> bool:
        if not settings.mistral_api_key:
            return False
        try:
            self._create_client()
            return True
        except Exception as exc:
            logger.warning("Mistral provider unavailable: %s", exc)
            return False

    def _extract_document(self, file_path: str):
        path = Path(file_path)
        if not path.exists():
            raise FileNotFoundError(f"File not found: {file_path}")
        if not settings.mistral_api_key:
            raise RuntimeError("MISTRAL_API_KEY no configurada")

        client = self._create_client()
        uploaded_file_id: str | None = None
        try:
            upload_response = self._upload_file(client, path)
            uploaded_file_id = self._extract_file_id(upload_response)
            ocr_response = client.ocr.process(
                model=settings.mistral_ocr_model,
                document={"file_id": uploaded_file_id},
                extract_header=settings.mistral_extract_header,
                extract_footer=settings.mistral_extract_footer,
                table_format=settings.mistral_table_format,
            )
            return self._normalize_ocr_response(ocr_response)
        finally:
            if uploaded_file_id:
                self._delete_file_quietly(client, uploaded_file_id)

    def _create_client(self):
        return create_client(
            api_key=settings.mistral_api_key,
            base_url=settings.mistral_base_url,
        )

    def _upload_file(self, client, path: Path):
        return upload_file(
            client,
            path,
            visibility=settings.mistral_file_visibility,
        )

    def _extract_file_id(self, upload_response) -> str:
        return extract_file_id(upload_response)

    def _delete_file_quietly(self, client, file_id: str) -> None:
        delete_file_quietly(client, file_id, logger)

    def _normalize_ocr_response(self, response):
        model_name = str(to_mapping(response).get("model", "") or settings.mistral_ocr_model)
        return normalize_ocr_response(
            response,
            model_name=model_name,
            table_format=settings.mistral_table_format,
        )

    def _expand_page_text(self, page_map: dict) -> str:
        return expand_page_text(page_map)

    def _should_include_section_text(self, section_text: str, body_text: str) -> bool:
        return should_include_section_text(section_text, body_text)

    def _normalize_compare_text(self, value: str) -> str:
        return normalize_compare_text(value)

    def _table_to_plain_text(self, table_map: dict) -> str:
        return table_to_plain_text(table_map)

    def _markdown_to_spans(
        self,
        *,
        markdown: str,
        page_number: int,
        page_width: float,
        page_height: float,
    ):
        return markdown_to_spans(
            markdown=markdown,
            page_number=page_number,
            page_width=page_width,
            page_height=page_height,
        )

    def _to_mapping(self, value):
        return to_mapping(value)


mistral_document_parser_provider = MistralDocumentParserProvider()
