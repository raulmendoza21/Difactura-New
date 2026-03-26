"""Helpers to load documents as text and page images."""

from __future__ import annotations

import base64
import logging
from pathlib import Path

from PIL import Image

from app.models.document_bundle import DocumentBundle, DocumentPageBundle, DocumentSpan
from app.services.layout_analyzer import layout_analyzer

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
        ocr_page_entries: list[dict] = []
        if not raw_text.strip():
            ocr_result = ocr_service.extract_pdf_ocr(file_path, input_kind="pdf_scanned")
            raw_text = ocr_result["text"]
            used_ocr = True
            preprocessing_steps = ocr_result["preprocessing_steps"]
            ocr_page_entries = ocr_result.get("page_entries", []) or [
                {
                    "page_number": page_number,
                    "text": raw_text,
                    "spans": [],
                    "width": 0,
                    "height": 0,
                }
                for page_number in range(1, int(pdf_result.get("pages", 0) or 0) + 1)
            ]

        page_images = self._render_pdf_pages(file_path) if include_page_images else []
        bundle = self._build_pdf_bundle(
            pdf_result=pdf_result,
            raw_text=raw_text.strip(),
            ocr_page_entries=ocr_page_entries,
        )
        input_kind = "pdf_digital" if pdf_result["is_digital"] else "pdf_scanned"
        input_profile = {
            "input_kind": input_kind,
            "text_source": "digital_text" if pdf_result["is_digital"] else "ocr",
            "is_digital_pdf": pdf_result["is_digital"],
            "used_ocr": used_ocr or not pdf_result["is_digital"],
            "used_page_images": bool(page_images),
            "ocr_engine": "tesseract" if (used_ocr or not pdf_result["is_digital"]) else "",
            "preprocessing_steps": preprocessing_steps,
            "document_family_hint": self._detect_document_family_hint(bundle.raw_text),
            "low_resolution": any(page.width < 1200 and page.height < 1200 for page in bundle.pages),
            "rotation_hint": self._rotation_hint(bundle.pages),
            "input_route": "pdf_native_bundle" if pdf_result["is_digital"] else "pdf_ocr_bundle",
        }
        return {
            "raw_text": bundle.raw_text,
            "pages": pdf_result["pages"],
            "method": method,
            "page_images": page_images,
            "input_profile": input_profile,
            "bundle": bundle,
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
        page_entries = ocr_result.get("page_entries", []) or [
            {
                "page_number": 1,
                "text": ocr_result["text"],
                "spans": [],
                "width": 0,
                "height": 0,
            }
        ]
        bundle = self._build_image_bundle(page_entries, ocr_result["text"])
        input_profile = {
            "input_kind": input_kind,
            "text_source": "ocr",
            "is_digital_pdf": False,
            "used_ocr": True,
            "used_page_images": bool(page_images),
            "ocr_engine": ocr_result["ocr_engine"],
            "preprocessing_steps": ocr_result["preprocessing_steps"],
            "document_family_hint": self._detect_document_family_hint(bundle.raw_text),
            "low_resolution": any(page.width < 1200 and page.height < 1200 for page in bundle.pages),
            "rotation_hint": self._rotation_hint(bundle.pages),
            "input_route": "image_ocr_bundle",
        }
        return {
            "raw_text": bundle.raw_text,
            "pages": 1,
            "method": "ocr",
            "page_images": page_images,
            "input_profile": input_profile,
            "bundle": bundle,
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

    def _build_pdf_bundle(self, *, pdf_result: dict, raw_text: str, ocr_page_entries: list[dict]) -> DocumentBundle:
        pages: list[DocumentPageBundle] = []
        all_spans: list[DocumentSpan] = []
        ocr_map = {entry.get("page_number", index + 1): entry for index, entry in enumerate(ocr_page_entries)}

        for page_entry in pdf_result.get("page_entries", []):
            page_number = int(page_entry.get("page_number", 0) or 0)
            native_spans = list(page_entry.get("spans", []))
            ocr_entry = ocr_map.get(page_number, {})
            ocr_spans = list(ocr_entry.get("spans", []))
            page_spans = sorted(
                [
                    span.model_copy(update={"page": page_number}) if isinstance(span, DocumentSpan) else DocumentSpan(**span)
                    for span in [*native_spans, *ocr_spans]
                ],
                key=lambda span: (round(span.bbox.y0, 1), round(span.bbox.x0, 1)),
            )
            pages.append(
                DocumentPageBundle(
                    page_number=page_number,
                    width=float(page_entry.get("width", 0)),
                    height=float(page_entry.get("height", 0)),
                    native_text=str(page_entry.get("text", "") or "").strip(),
                    ocr_text=str(ocr_entry.get("text", "") or "").strip(),
                    reading_text="\n".join(span.text for span in page_spans if span.text).strip()
                    or str(page_entry.get("text", "") or "").strip()
                    or str(ocr_entry.get("text", "") or "").strip(),
                    spans=page_spans,
                )
            )
            all_spans.extend(page_spans)

        bundle = DocumentBundle(
            raw_text=raw_text,
            page_count=len(pages),
            page_texts=[page.reading_text for page in pages],
            pages=pages,
            spans=all_spans,
        )
        bundle.regions = layout_analyzer.analyze(bundle)
        return bundle

    def _build_image_bundle(self, page_entries: list[dict], raw_text: str) -> DocumentBundle:
        pages: list[DocumentPageBundle] = []
        all_spans: list[DocumentSpan] = []

        for index, page_entry in enumerate(page_entries, start=1):
            raw_spans = page_entry.get("spans", [])
            page_spans = sorted(
                [
                    span.model_copy(update={"page": index}) if isinstance(span, DocumentSpan) else DocumentSpan(**span)
                    for span in raw_spans
                ],
                key=lambda span: (round(span.bbox.y0, 1), round(span.bbox.x0, 1)),
            )
            pages.append(
                DocumentPageBundle(
                    page_number=index,
                    width=float(page_entry.get("width", 0)),
                    height=float(page_entry.get("height", 0)),
                    ocr_text=str(page_entry.get("text", "") or "").strip(),
                    reading_text="\n".join(span.text for span in page_spans if span.text).strip()
                    or str(page_entry.get("text", "") or "").strip(),
                    spans=page_spans,
                )
            )
            all_spans.extend(page_spans)

        bundle = DocumentBundle(
            raw_text=raw_text.strip(),
            page_count=len(pages),
            page_texts=[page.reading_text for page in pages],
            pages=pages,
            spans=all_spans,
        )
        bundle.regions = layout_analyzer.analyze(bundle)
        return bundle

    def _detect_document_family_hint(self, raw_text: str) -> str:
        upper_text = (raw_text or "").upper()
        if "FACTURA RECTIFICAT" in upper_text or "RECTIFICATIVA" in upper_text:
            return "factura_rectificativa"
        if "FACTURA SIMPLIFICADA" in upper_text or "FRA. SIMPLIFICADA" in upper_text:
            return "factura_simplificada"
        if "DOCUMENTO DE VENTA" in upper_text or "TICKET" in upper_text:
            return "ticket"
        return "invoice"

    def _rotation_hint(self, pages: list[DocumentPageBundle]) -> str:
        if not pages:
            return ""
        landscape_pages = sum(1 for page in pages if page.width > page.height and page.height > 0)
        if landscape_pages == len(pages):
            return "landscape"
        if landscape_pages > 0:
            return "mixed"
        return "portrait"


document_loader = DocumentLoader()
