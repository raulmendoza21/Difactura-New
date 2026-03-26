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
        used_ocr = False
        preprocessing_steps = ["pdf_text_extraction"] if pdf_result["is_digital"] else ["pdf_page_render", "ocr_preprocess"]
        if not raw_text.strip():
            ocr_result = ocr_service.extract_pdf_ocr(file_path, input_kind="pdf_scanned")
            raw_text = ocr_result["text"]
            used_ocr = True
            preprocessing_steps = ocr_result["preprocessing_steps"]

        page_images = self._render_pdf_pages(file_path) if include_page_images else []
        return {
            "raw_text": raw_text.strip(),
            "pages": pdf_result["pages"],
            "method": method,
            "page_images": page_images,
            "input_profile": {
                "input_kind": "pdf_digital" if pdf_result["is_digital"] else "pdf_scanned",
                "text_source": "digital_text" if pdf_result["is_digital"] else "ocr",
                "is_digital_pdf": pdf_result["is_digital"],
                "used_ocr": used_ocr or not pdf_result["is_digital"],
                "used_page_images": bool(page_images),
                "ocr_engine": "tesseract" if (used_ocr or not pdf_result["is_digital"]) else "",
                "preprocessing_steps": preprocessing_steps,
            },
        }

    def _load_image(self, file_path: str, mime_type: str, include_page_images: bool = True) -> dict:
        from app.services.ocr_service import ocr_service

        page_images: list[str] = []
        input_kind = self._classify_image_input(file_path)
        if include_page_images:
            with Image.open(file_path) as image:
                rgb_image = image.convert("RGB")
                page_images = [self._image_to_data_url(rgb_image, mime_type or "image/png")]

        ocr_result = ocr_service.extract_image_ocr(file_path, input_kind=input_kind)
        raw_text = ocr_result["text"]
        return {
            "raw_text": raw_text.strip(),
            "pages": 1,
            "method": "ocr",
            "page_images": page_images,
            "input_profile": {
                "input_kind": input_kind,
                "text_source": "ocr",
                "is_digital_pdf": False,
                "used_ocr": True,
                "used_page_images": bool(page_images),
                "ocr_engine": ocr_result["ocr_engine"],
                "preprocessing_steps": ocr_result["preprocessing_steps"],
            },
        }

    def _classify_image_input(self, file_path: str) -> str:
        with Image.open(file_path) as image:
            width, height = image.size

        longest_side = max(width, height)
        aspect_ratio = longest_side / max(1, min(width, height))

        # Large images with irregular aspect ratio are usually mobile photos.
        if longest_side >= 1800 or aspect_ratio >= 1.45:
            return "image_photo"
        return "image_scan"

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
