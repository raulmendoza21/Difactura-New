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
            with patch(
                "app.services.ocr_service.OCRService.extract_image_ocr",
                return_value={
                    "text": "Factura 1",
                    "preprocessing_steps": ["grayscale", "adaptive_threshold", "ocr_variant:balanced_binary"],
                    "variant_name": "balanced_binary",
                    "ocr_engine": "tesseract",
                },
            ):
                result = loader.load(str(image_path), "image/png", include_page_images=False)

            assert result["pages"] == 1
            assert result["page_images"] == []
            assert result["input_profile"]["text_source"] == "ocr"
            assert result["input_profile"]["ocr_engine"] == "tesseract"
            assert "ocr_variant:balanced_binary" in result["input_profile"]["preprocessing_steps"]
        finally:
            if image_path.exists():
                image_path.unlink()
            if temp_dir.exists():
                temp_dir.rmdir()

    def test_load_pdf_marks_digital_profile(self):
        temp_dir = Path(__file__).resolve().parent / "_tmp_pdf"
        temp_dir.mkdir(exist_ok=True)
        pdf_path = temp_dir / "invoice.pdf"
        pdf_path.write_bytes(b"%PDF-1.4\n%mock\n")
        try:
            loader = DocumentLoader()

            with (
                patch("app.services.pdf_extractor.PDFExtractor.extract", return_value={"text": "Factura 1", "pages": 2, "is_digital": True}),
                patch.object(loader, "_render_pdf_pages", return_value=[]),
            ):
                result = loader.load(str(pdf_path), "application/pdf", include_page_images=False)

            assert result["method"] == "digital"
            assert result["input_profile"]["input_kind"] == "pdf_digital"
            assert result["input_profile"]["text_source"] == "digital_text"
            assert result["input_profile"]["used_ocr"] is False
        finally:
            if pdf_path.exists():
                pdf_path.unlink()
            if temp_dir.exists():
                temp_dir.rmdir()

    def test_classify_image_input_detects_photo_like_dimensions(self):
        temp_dir = Path(__file__).resolve().parent / "_tmp_photo"
        temp_dir.mkdir(exist_ok=True)
        image_path = temp_dir / "mobile.jpg"
        try:
            Image.new("RGB", (2400, 1200), color="white").save(image_path)
            loader = DocumentLoader()

            assert loader._classify_image_input(str(image_path)) == "image_photo"
        finally:
            if image_path.exists():
                image_path.unlink()
            if temp_dir.exists():
                temp_dir.rmdir()

    def test_load_scanned_pdf_uses_ocr_details(self):
        temp_dir = Path(__file__).resolve().parent / "_tmp_pdf_scanned"
        temp_dir.mkdir(exist_ok=True)
        pdf_path = temp_dir / "invoice.pdf"
        pdf_path.write_bytes(b"%PDF-1.4\n%mock\n")
        try:
            loader = DocumentLoader()

            with (
                patch("app.services.pdf_extractor.PDFExtractor.extract", return_value={"text": "", "pages": 1, "is_digital": False}),
                patch(
                    "app.services.ocr_service.OCRService.extract_pdf_ocr",
                    return_value={
                        "text": "Factura OCR",
                        "preprocessing_steps": ["pdf_page_render", "grayscale", "ocr_variant:photo_enhanced"],
                        "variant_name": "photo_enhanced",
                        "ocr_engine": "tesseract",
                    },
                ),
                patch.object(loader, "_render_pdf_pages", return_value=[]),
            ):
                result = loader.load(str(pdf_path), "application/pdf", include_page_images=False)

            assert result["method"] == "ocr"
            assert result["input_profile"]["input_kind"] == "pdf_scanned"
            assert result["input_profile"]["used_ocr"] is True
            assert "ocr_variant:photo_enhanced" in result["input_profile"]["preprocessing_steps"]
        finally:
            if pdf_path.exists():
                pdf_path.unlink()
            if temp_dir.exists():
                temp_dir.rmdir()
