from __future__ import annotations

from pathlib import Path

from app.services.ocr_processing.region_hints import (
    extract_image_region_hints,
    extract_pdf_region_hints,
)


def extract_region_hints(service, file_path: str, *, input_kind: str = "pdf_scanned", max_pages: int = 1) -> list[dict]:
    path = Path(file_path)
    if not path.exists():
        raise FileNotFoundError(f"File not found: {file_path}")

    if path.suffix.lower() == ".pdf":
        return extract_pdf_region_hints(service, file_path, input_kind=input_kind, max_pages=max_pages)
    return extract_image_region_hints(service, file_path, input_kind=input_kind)
