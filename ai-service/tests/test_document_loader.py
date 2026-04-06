"""Tests for document loader helpers."""

from pathlib import Path
from unittest.mock import patch

from PIL import Image

from app.config import settings
from app.models.document_bundle import DocumentBundle, DocumentPageBundle
from app.models.document_provider import ProviderDocumentResult
from app.services.document_loading.bundle_factory import build_image_bundle
from app.services.document_loader import DocumentLoader
from app.services.providers.local_document_parser_provider import LocalDocumentParserProvider


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
            assert result["input_profile"]["requested_provider"] == settings.document_parser_provider
            assert result["input_profile"]["document_provider"] == "local"
            assert result["input_profile"]["fallback_applied"] is (settings.document_parser_provider != "local")
            assert result["bundle"].contract.name == "difactura.document_bundle"
            assert result["bundle"].input_profile.input_kind == "image_scan"
            assert result["bundle"].source_stats.page_count == 1
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
            assert result["bundle"].page_count == 2
            assert result["bundle"].input_profile.input_route == "pdf_native_bundle"
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
            assert result["bundle"].page_count == 1
            assert result["bundle"].source_stats.page_count == 1
            assert result["bundle"].input_profile.input_route == "pdf_ocr_bundle"
        finally:
            if pdf_path.exists():
                pdf_path.unlink()
            if temp_dir.exists():
                temp_dir.rmdir()

    def test_load_image_falls_back_to_local_provider_when_primary_fails(self):
        temp_dir = Path(__file__).resolve().parent / "_tmp_provider_fallback"
        temp_dir.mkdir(exist_ok=True)
        image_path = temp_dir / "invoice.jpg"
        try:
            Image.new("RGB", (1800, 1200), color="white").save(image_path)
            loader = DocumentLoader()

            class BrokenProvider:
                name = "mistral"

                def extract_image(self, *args, **kwargs):
                    raise RuntimeError("provider down")

            local_provider = LocalDocumentParserProvider()
            local_result = ProviderDocumentResult(
                text="Factura fallback",
                pages=1,
                is_digital=False,
                method="ocr",
                preprocessing_steps=["provider:local"],
                ocr_engine="tesseract",
            )

            with (
                patch.object(settings, "document_parser_provider", "mistral"),
                patch(
                    "app.services.document_loading.provider_flow.get_document_parser_provider",
                    side_effect=lambda name=None: local_provider if name == "local" else BrokenProvider(),
                ),
                patch.object(local_provider, "extract_image", return_value=local_result),
            ):
                result = loader.load(str(image_path), "image/jpeg", include_page_images=False)

            assert result["raw_text"] == "Factura fallback"
            assert result["input_profile"]["input_kind"] == "image_photo"
            assert result["input_profile"]["requested_provider"] == "mistral"
            assert result["input_profile"]["document_provider"] == "local"
            assert result["input_profile"]["fallback_applied"] is True
            assert result["input_profile"]["fallback_reason"] == "provider_error"
            assert "provider_fallback:local" in result["input_profile"]["preprocessing_steps"]
        finally:
            if image_path.exists():
                image_path.unlink()
            if temp_dir.exists():
                temp_dir.rmdir()

    def test_load_image_passes_company_context_to_bundle_factory(self):
        temp_dir = Path(__file__).resolve().parent / "_tmp_company_context"
        temp_dir.mkdir(exist_ok=True)
        image_path = temp_dir / "invoice.png"
        try:
            Image.new("RGB", (20, 20), color="white").save(image_path)
            loader = DocumentLoader()
            company_context = {"name": "Acme Demo SL", "tax_id": "B12345678"}
            fake_bundle = DocumentBundle(raw_text="Factura 1")
            fake_bundle.refresh_derived_state()

            with (
                patch(
                    "app.services.ocr_service.OCRService.extract_image_ocr",
                    return_value={
                        "text": "Factura 1",
                        "preprocessing_steps": ["grayscale"],
                        "variant_name": "balanced_binary",
                        "ocr_engine": "tesseract",
                    },
                ),
                patch("app.services.document_loader.build_image_bundle", return_value=fake_bundle) as build_bundle,
            ):
                loader.load(
                    str(image_path),
                    "image/png",
                    include_page_images=False,
                    company_context=company_context,
                )

            assert build_bundle.call_args.kwargs["company_context"] == company_context
        finally:
            if image_path.exists():
                image_path.unlink()
            if temp_dir.exists():
                temp_dir.rmdir()


def test_build_image_bundle_passes_company_context_to_layout_analyzer():
    company_context = {"name": "Acme Demo SL", "tax_id": "B12345678"}
    page_entries = [
        {
            "page_number": 1,
            "text": "Acme Demo SL\nFACTURA",
            "spans": [],
            "width": 800,
            "height": 1200,
        }
    ]

    with patch("app.services.document_loading.bundle_factory.layout_analyzer.analyze", return_value=[]) as analyze:
        bundle = build_image_bundle(page_entries, "Acme Demo SL\nFACTURA", company_context=company_context)

    analyze.assert_called_once()
    assert analyze.call_args.kwargs["company_context"] == company_context
    assert bundle.page_count == 1
