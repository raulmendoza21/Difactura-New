"""Document loading facade."""

from __future__ import annotations

from pathlib import Path

from PIL import Image

from app.services.document_loading.bundle_factory import build_image_bundle
from app.services.document_loading.image_loader import load_image_document
from app.services.document_loading.input_profile import classify_image_input
from app.services.document_loading.page_images import image_to_data_url, render_pdf_pages
from app.services.document_loading.pdf_loader import load_pdf_document


class DocumentLoader:
    """Prepare document payloads for extraction services."""

    def load(
        self,
        file_path: str,
        mime_type: str = "",
        include_page_images: bool = True,
        company_context: dict[str, str] | None = None,
    ) -> dict:
        path = Path(file_path)
        if not path.exists():
            raise FileNotFoundError(f"File not found: {file_path}")

        if path.suffix.lower() == ".pdf":
            return self._load_pdf(file_path, include_page_images=include_page_images, company_context=company_context)
        return self._load_image(file_path, mime_type, include_page_images=include_page_images, company_context=company_context)

    def _load_pdf(
        self,
        file_path: str,
        include_page_images: bool = True,
        company_context: dict[str, str] | None = None,
    ) -> dict:
        return load_pdf_document(
            file_path=file_path,
            include_page_images=include_page_images,
            company_context=company_context,
            render_pdf_pages=self._render_pdf_pages,
        )

    def _load_image(
        self,
        file_path: str,
        mime_type: str,
        include_page_images: bool = True,
        company_context: dict[str, str] | None = None,
    ) -> dict:
        return load_image_document(
            file_path=file_path,
            mime_type=mime_type,
            include_page_images=include_page_images,
            company_context=company_context,
            classify_input=self._classify_image_input,
            image_to_data_url=self._image_to_data_url,
            build_bundle=build_image_bundle,
        )

    def _classify_image_input(self, file_path: str) -> str:
        return classify_image_input(file_path)

    def _render_pdf_pages(self, file_path: str) -> list[str]:
        return render_pdf_pages(file_path, image_encoder=self._image_to_data_url)

    def _image_to_data_url(self, image: Image.Image, mime_type: str) -> str:
        return image_to_data_url(image, mime_type)


document_loader = DocumentLoader()
