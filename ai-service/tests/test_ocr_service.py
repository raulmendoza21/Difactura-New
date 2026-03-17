"""Tests for OCR service."""

import pytest
from unittest.mock import patch, MagicMock
from app.services.ocr_service import OCRService


class TestOCRService:

    def test_is_available(self):
        service = OCRService()
        # In test environment, Tesseract may not be installed
        result = service.is_available()
        assert isinstance(result, bool)

    def test_extract_text_file_not_found(self):
        service = OCRService()
        with pytest.raises(FileNotFoundError):
            service.extract_text_from_image("/nonexistent/file.png")
