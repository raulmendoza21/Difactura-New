from __future__ import annotations

from pathlib import Path

from PIL import Image

from app.models.document_bundle import DocumentPageBundle


def classify_image_input(file_path: str) -> str:
    with Image.open(file_path) as image:
        width, height = image.size

    longest_side = max(width, height)
    aspect_ratio = longest_side / max(1, min(width, height))

    if longest_side >= 1800 or aspect_ratio >= 1.45:
        return "image_photo"
    return "image_scan"


def detect_document_family_hint(raw_text: str) -> str:
    upper_text = (raw_text or "").upper()
    if "FACTURA RECTIFICAT" in upper_text or "RECTIFICATIVA" in upper_text:
        return "factura_rectificativa"
    if "FACTURA SIMPLIFICADA" in upper_text or "FRA. SIMPLIFICADA" in upper_text:
        return "factura_simplificada"
    if "DOCUMENTO DE VENTA" in upper_text or "TICKET" in upper_text:
        return "ticket"
    return "invoice"


def rotation_hint(pages: list[DocumentPageBundle]) -> str:
    if not pages:
        return ""
    landscape_pages = sum(1 for page in pages if page.width > page.height and page.height > 0)
    if landscape_pages == len(pages):
        return "landscape"
    if landscape_pages > 0:
        return "mixed"
    return "portrait"


def has_low_resolution_pages(pages: list[DocumentPageBundle]) -> bool:
    sized_pages = [page for page in pages if page.width > 0 and page.height > 0]
    if not sized_pages:
        return False
    return any(page.width < 1200 and page.height < 1200 for page in sized_pages)


def augment_preprocessing_steps(steps: list[str], provider_trace: dict[str, str | bool]) -> list[str]:
    enriched = list(steps or [])
    requested = str(provider_trace.get("requested_provider", "") or "")
    used = str(provider_trace.get("document_provider", "") or "")
    fallback_provider = str(provider_trace.get("fallback_provider", "") or "")

    for item in (
        f"provider_requested:{requested}" if requested else "",
        f"provider_used:{used}" if used else "",
        f"provider_fallback:{fallback_provider}" if fallback_provider else "",
    ):
        if item and item not in enriched:
            enriched.append(item)
    return enriched
