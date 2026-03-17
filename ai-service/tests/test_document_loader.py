"""Tests for document loader helpers."""

from pathlib import Path
from unittest.mock import patch

from PIL import Image

from app.services.document_loader import DocumentLoader


class TestDocumentLoader:

    def test_load_image_without_page_images(self):
        temp_dir = Path(__file__).resolve().parent / "_tmp"
        temp_dir.mkdir(exist_ok=True)
        image_path = temp_dir / "invoice.png"
        try:
            Image.new("RGB", (20, 20), color="white").save(image_path)

            loader = DocumentLoader()
            with patch("app.services.ocr_service.OCRService.extract_text_from_image", return_value="Factura 1"):
                result = loader.load(str(image_path), "image/png", include_page_images=False)

            assert result["pages"] == 1
            assert result["page_images"] == []
        finally:
            if image_path.exists():
                image_path.unlink()
            if temp_dir.exists():
                temp_dir.rmdir()
