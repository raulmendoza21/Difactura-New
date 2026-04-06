from unittest.mock import patch

from app.config import settings
from app.services.providers.local_document_parser_provider import LocalDocumentParserProvider
from app.services.providers.mistral_document_parser_provider import MistralDocumentParserProvider
from app.services.providers.registry import get_document_parser_provider


class TestDocumentParserProvider:

    def test_registry_returns_local_provider_by_default(self):
        provider = get_document_parser_provider("local")

        assert provider.name == "local"

    def test_local_provider_extract_pdf_uses_native_pdf_when_available(self):
        provider = LocalDocumentParserProvider()

        with patch(
            "app.services.pdf_extractor.PDFExtractor.extract",
            return_value={
                "text": "Factura digital",
                "pages": 1,
                "is_digital": True,
                "page_entries": [],
            },
        ):
            result = provider.extract_pdf("invoice.pdf")

        assert result.is_digital is True
        assert result.method == "digital"
        assert result.text == "Factura digital"

    def test_local_provider_extract_image_returns_ocr_payload(self):
        provider = LocalDocumentParserProvider()

        with patch(
            "app.services.ocr_service.OCRService.extract_image_ocr",
            return_value={
                "text": "Factura foto",
                "preprocessing_steps": ["grayscale"],
                "ocr_engine": "tesseract",
                "page_entries": [
                    {
                        "page_number": 1,
                        "width": 2000,
                        "height": 1200,
                        "text": "Factura foto",
                        "spans": [],
                    }
                ],
            },
        ):
            result = provider.extract_image("invoice.jpg", input_kind="image_photo")

        assert result.method == "ocr"
        assert result.ocr_engine == "tesseract"
        assert result.pages == 1

    def test_registry_returns_mistral_provider_when_requested(self):
        with patch.object(settings, "mistral_api_key", ""), patch.object(settings, "document_parser_provider", "mistral"):
            provider = get_document_parser_provider()

        assert provider.name == "mistral"

    def test_mistral_provider_normalizes_ocr_response_into_page_entries(self):
        provider = MistralDocumentParserProvider()
        response = {
            "model": "mistral-ocr-latest",
            "pages": [
                {
                    "index": 0,
                    "markdown": "FACTURA\nTOTAL 121,00",
                    "dimensions": {"width": 1000, "height": 1400},
                }
            ],
        }

        result = provider._normalize_ocr_response(response)

        assert result.ocr_engine == "mistral_ocr"
        assert result.pages == 1
        assert result.page_entries[0].text == "FACTURA\nTOTAL 121,00"
        assert result.page_entries[0].spans[0].source == "ocr_mistral"

    def test_mistral_provider_extract_document_uses_upload_ocr_and_delete(self):
        provider = MistralDocumentParserProvider()

        class FakeFiles:
            def upload(self, **kwargs):
                return {"id": "file-123"}

            def delete(self, **kwargs):
                return {"deleted": True}

        class FakeOCR:
            def process(self, **kwargs):
                return {
                    "model": "mistral-ocr-latest",
                    "pages": [
                        {
                            "index": 0,
                            "markdown": "FACTURA\nTOTAL 26,75",
                            "dimensions": {"width": 1000, "height": 1200},
                        }
                    ],
                }

        class FakeClient:
            def __init__(self):
                self.files = FakeFiles()
                self.ocr = FakeOCR()

        with (
            patch.object(provider, "_create_client", return_value=FakeClient()),
            patch.object(settings, "mistral_api_key", "test-key"),
        ):
            result = provider._extract_document(__file__)

        assert result.method == "ocr"
        assert result.text.startswith("FACTURA")
