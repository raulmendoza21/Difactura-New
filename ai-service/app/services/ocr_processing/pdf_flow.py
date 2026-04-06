from __future__ import annotations

import logging

from PIL import Image

logger = logging.getLogger(__name__)


def extract_text_from_pdf_pages(service, file_path: str, *, input_kind: str = "pdf_scanned") -> str:
    return extract_pdf_ocr(service, file_path, input_kind=input_kind)["text"]


def extract_pdf_ocr(service, file_path: str, *, input_kind: str = "pdf_scanned") -> dict:
    import fitz

    doc = fitz.open(file_path)
    all_text: list[str] = []
    page_entries: list[dict] = []
    preprocessing_steps = ["pdf_page_render"]
    best_variant_name = ""

    try:
        for page_num, page in enumerate(doc):
            mat = fitz.Matrix(300 / 72, 300 / 72)
            pix = page.get_pixmap(matrix=mat)
            img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
            result = service._extract_best_text_from_variants(img, input_kind=input_kind)

            all_text.append(result["text"].strip())
            page_entries.append(
                {
                    "page_number": page_num + 1,
                    "width": float(pix.width),
                    "height": float(pix.height),
                    "text": result["text"].strip(),
                    "spans": [
                        span.model_copy(update={"page": page_num + 1})
                        for span in result.get("spans", [])
                    ],
                    "ocr_engine": result.get("ocr_engine", ""),
                }
            )
            for step in result["preprocessing_steps"]:
                if step not in preprocessing_steps:
                    preprocessing_steps.append(step)
            best_variant_name = result["variant_name"] or best_variant_name
            logger.info(
                "OCR page %s: %s chars using %s",
                page_num + 1,
                len(result["text"]),
                result["variant_name"],
            )
    finally:
        doc.close()

    return {
        "text": "\n\n".join(filter(None, all_text)).strip(),
        "preprocessing_steps": preprocessing_steps,
        "variant_name": best_variant_name,
        "ocr_engine": "tesseract",
        "page_entries": page_entries,
    }
