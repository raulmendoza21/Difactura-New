"""Tests for OCR service helpers."""

from PIL import Image
from PIL import ImageDraw

from app.services.ocr_service import OCRService
from app.utils.image_processing import build_ocr_variants


class TestOCRService:

    def test_build_ocr_variants_includes_photo_variant_for_mobile_photos(self):
        image = Image.new("RGB", (1200, 2200), color="white")

        variants = build_ocr_variants(image, input_kind="image_photo")

        variant_names = [variant["name"] for variant in variants]
        assert "full_photo_enhanced" in variant_names or "document_photo_enhanced" in variant_names
        assert "full_clahe_gray" in variant_names or "document_clahe_gray" in variant_names
        assert all("balanced_binary" not in variant_name for variant_name in variant_names)

    def test_build_ocr_variants_includes_scan_variant_for_scans(self):
        image = Image.new("RGB", (1800, 1200), color="white")

        variants = build_ocr_variants(image, input_kind="image_scan")

        variant_names = [variant["name"] for variant in variants]
        assert "base_scan_otsu" in variant_names
        assert "base_contrast_binary" in variant_names

    def test_build_ocr_variants_downscales_large_mobile_photos(self):
        image = Image.new("RGB", (3200, 4200), color="white")

        variants = build_ocr_variants(image, input_kind="image_photo")

        assert any("downscale_mobile_photo" in variant["preprocessing_steps"] for variant in variants)
        assert max(variants[0]["image"].size) <= 1700

    def test_build_ocr_variants_detects_document_in_photo(self):
        image = Image.new("RGB", (1600, 1200), color=(176, 124, 76))
        draw = ImageDraw.Draw(image)
        draw.polygon(
            [(240, 120), (1280, 170), (1360, 1030), (180, 980)],
            fill="white",
        )

        variants = build_ocr_variants(image, input_kind="image_photo")

        assert any("document_contour_detected" in variant["preprocessing_steps"] for variant in variants)
        assert any("perspective_corrected" in variant["preprocessing_steps"] for variant in variants)
        assert min(variants[0]["image"].size) >= 900
        assert all(variant["name"].startswith("document_") for variant in variants)

    def test_image_photo_ocr_uses_fewer_configs(self):
        service = OCRService()

        assert service._get_ocr_configs("image_photo") == ("--oem 3 --psm 6", "--oem 3 --psm 4")
        assert service._get_ocr_configs("image_scan") == service.OCR_CONFIGS

    def test_fast_photo_result_usable_requires_structure(self):
        service = OCRService()

        assert service._is_fast_photo_result_usable(
            {
                "text": "FACTURA\nFecha 06/03/2026\nDocumento GC26001163\nBase 25,00\nIGIC 1,75\nTotal 26,75",
                "score": 220,
            }
        )
        assert not service._is_fast_photo_result_usable(
            {
                "text": "Factura\n26,75",
                "score": 220,
            }
        )

    def test_score_ocr_candidate_rewards_confident_invoice_text(self):
        service = OCRService()

        strong_score = service._score_ocr_candidate(
            "Factura F-2026-1\nFecha 24/03/2026\nBase 100,00\nIVA 21,00\nTotal 121,00",
            [82, 79, 85, 81],
        )
        weak_score = service._score_ocr_candidate(
            "F?c|ur?\nT0ta1",
            [18, 12, 15],
        )

        assert strong_score > weak_score

    def test_score_ocr_candidate_penalizes_fragmented_text(self):
        service = OCRService()

        structured_score = service._score_ocr_candidate(
            "Factura\nFecha 24/03/2026\nTotal 121,00\nBase imponible 100,00",
            [70, 72, 74],
        )
        fragmented_score = service._score_ocr_candidate(
            "e\nA\n5\nQ\n2\n..\npa\nLa\nA\n.",
            [70, 72, 74],
        )

        assert structured_score > fragmented_score

    def test_score_ocr_candidate_rewards_invoice_like_text(self):
        service = OCRService()

        invoice_like = service._score_ocr_candidate(
            "FACTURA\nFECHA 07-01-2026\nBASE 312,85\nIGIC 7,00\nTOTAL 334,75\nIBAN ES3900491848732110337646",
            [86, 88, 89],
        )
        noisy = service._score_ocr_candidate(
            "e\nA\n54m\n>\n>\nEN\nsi\n2.\nA\n>\nMD iS ei",
            [86, 88, 89],
        )

        assert invoice_like > noisy
