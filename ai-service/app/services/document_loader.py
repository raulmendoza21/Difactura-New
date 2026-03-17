"""Helpers to load documents as text and page images."""

from __future__ import annotations

import base64
import logging
from pathlib import Path

from PIL import Image

logger = logging.getLogger(__name__)


class DocumentLoader:
    """Prepare document payloads for extraction services."""

    def load(self, file_path: str, mime_type: str = "", include_page_images: bool = True) -> dict:
        path = Path(file_path)
        if not path.exists():
            raise FileNotFoundError(f"File not found: {file_path}")

        ext = path.suffix.lower()
        if ext == ".pdf":
            return self._load_pdf(file_path, include_page_images=include_page_images)
        return self._load_image(file_path, mime_type, include_page_images=include_page_images)

    def _load_pdf(self, file_path: str, include_page_images: bool = True) -> dict:
        from app.services.ocr_service import ocr_service
        from app.services.pdf_extractor import pdf_extractor

        pdf_result = pdf_extractor.extract(file_path)
        raw_text = pdf_result["text"] if pdf_result["is_digital"] else ""
        method = "digital" if pdf_result["is_digital"] else "ocr"
        if not raw_text.strip():
            raw_text = ocr_service.extract_text_from_pdf_pages(file_path)

        page_images = self._render_pdf_pages(file_path) if include_page_images else []
        return {
            "raw_text": raw_text.strip(),
            "pages": pdf_result["pages"],
            "method": method,
            "page_images": page_images,
        }

    def _load_image(self, file_path: str, mime_type: str, include_page_images: bool = True) -> dict:
        from app.services.ocr_service import ocr_service

        page_images: list[str] = []
        if include_page_images:
            with Image.open(file_path) as image:
                rgb_image = image.convert("RGB")
                page_images = [self._image_to_data_url(rgb_image, mime_type or "image/png")]

        raw_text = ocr_service.extract_text_from_image(file_path)
        return {
            "raw_text": raw_text.strip(),
            "pages": 1,
            "method": "ocr",
            "page_images": page_images,
        }

    def _render_pdf_pages(self, file_path: str) -> list[str]:
        import fitz

        doc = fitz.open(file_path)
        page_images: list[str] = []
        try:
            for page in doc:
                mat = fitz.Matrix(2, 2)
                pix = page.get_pixmap(matrix=mat, alpha=False)
                image = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
                page_images.append(self._image_to_data_url(image, "image/png"))
        finally:
            doc.close()

        logger.info("Rendered %s PDF pages as images", len(page_images))
        return page_images

    def _image_to_data_url(self, image: Image.Image, mime_type: str) -> str:
        from io import BytesIO

        buffer = BytesIO()
        fmt = "PNG" if mime_type == "image/png" else "JPEG"
        image.save(buffer, format=fmt)
        encoded = base64.b64encode(buffer.getvalue()).decode("ascii")
        return f"data:{mime_type};base64,{encoded}"


document_loader = DocumentLoader()
