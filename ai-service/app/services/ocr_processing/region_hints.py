from __future__ import annotations

import re

from PIL import Image, ImageFilter, ImageOps


def extract_pdf_region_hints(service, file_path: str, *, input_kind: str, max_pages: int) -> list[dict]:
    import fitz

    hints: list[dict] = []
    doc = fitz.open(file_path)
    try:
        for page_index in range(min(max_pages, len(doc))):
            page = doc[page_index]
            pix = page.get_pixmap(matrix=fitz.Matrix(600 / 72, 600 / 72), alpha=False)
            image = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
            hints.extend(
                extract_region_hints_from_image(
                    service,
                    image,
                    page_number=page_index + 1,
                    input_kind=input_kind,
                )
            )
    finally:
        doc.close()
    return hints


def extract_image_region_hints(service, image_path: str, *, input_kind: str) -> list[dict]:
    with Image.open(image_path) as image:
        rgb_image = image.convert("RGB")
    return extract_region_hints_from_image(service, rgb_image, page_number=1, input_kind=input_kind)


def extract_region_hints_from_image(service, image: Image.Image, *, page_number: int, input_kind: str) -> list[dict]:
    width, height = image.size
    if width <= 0 or height <= 0:
        return []

    crop_specs = (
        ("header", (0.0, 0.0, 1.0, 0.58)),
        ("header_left", (0.0, 0.02, 0.52, 0.34)),
        ("header_right", (0.45, 0.02, 1.0, 0.34)),
        ("totals", (0.70, 0.72, 1.0, 1.0)),
    )
    hints: list[dict] = []

    for region_type, ratios in crop_specs:
        x0 = int(width * ratios[0])
        y0 = int(height * ratios[1])
        x1 = int(width * ratios[2])
        y1 = int(height * ratios[3])
        if x1 <= x0 or y1 <= y0:
            continue

        crop = image.crop((x0, y0, x1, y1))
        text = extract_best_region_text(service, crop, region_type=region_type, input_kind=input_kind)
        if not is_region_hint_usable(region_type, text):
            continue

        hints.append(
            {
                "page_number": page_number,
                "region_type": region_type,
                "text": normalize_region_hint_text(region_type, text),
                "bbox": {
                    "x0": float(x0),
                    "y0": float(y0),
                    "x1": float(x1),
                    "y1": float(y1),
                },
            }
        )

    return hints


def extract_best_region_text(service, image: Image.Image, *, region_type: str, input_kind: str) -> str:
    grayscale = image.convert("L")
    variants = (
        ("autocontrast", ImageOps.autocontrast(grayscale)),
        (
            "sharp_autocontrast",
            ImageOps.autocontrast(grayscale.filter(ImageFilter.SHARPEN).filter(ImageFilter.SHARPEN)),
        ),
        ("equalize", ImageOps.equalize(grayscale)),
    )
    best_text = ""
    best_score = float("-inf")

    for _variant_name, variant_image in variants:
        for config in get_region_hint_configs(region_type, input_kind=input_kind):
            text, confidences, _ = service._run_ocr_candidate(variant_image, config)
            score = service._score_ocr_candidate(text, confidences) + region_hint_bonus(region_type, text)
            if score > best_score:
                best_score = score
                best_text = text

    return cleanup_hint_text(best_text)


def get_region_hint_configs(region_type: str, *, input_kind: str) -> tuple[str, ...]:
    if region_type == "totals":
        return (
            "--oem 3 --psm 6",
            "--oem 3 --psm 11",
        )
    if region_type in {"header_left", "header_right"}:
        return (
            "--oem 3 --psm 6",
            "--oem 3 --psm 11",
        )
    return (
        "--oem 3 --psm 6",
        "--oem 3 --psm 11",
    )


def region_hint_bonus(region_type: str, text: str) -> float:
    compact = " ".join((text or "").split()).upper()
    if not compact:
        return float("-inf")

    amount_like_count = len(re.findall(r"-?\d{1,3}(?:[.,]\d{3})*(?:[.,]\d{2})|-?\d+(?:[.,]\d{2})", compact))
    if region_type == "totals":
        bonus = 0.0
        if "SUBTOTAL" in compact:
            bonus += 80
        if "TOTAL" in compact or "TOT " in compact or compact.endswith("TOT"):
            bonus += 100
        if "IMPUEST" in compact or "IVA" in compact or "IGIC" in compact:
            bonus += 80
        bonus += amount_like_count * 45
        return bonus

    bonus = 0.0
    for keyword in ("FACTURA", "RECTIFICAT", "NIF", "CIF", "CLIENTE", "PROVEEDOR", "EMISOR", "RECEPTOR"):
        if keyword in compact:
            bonus += 35
    bonus += amount_like_count * 8
    return bonus


def is_region_hint_usable(region_type: str, text: str) -> bool:
    compact = " ".join((text or "").split())
    if len(compact) < 18:
        return False

    upper = compact.upper()
    amount_like_count = len(re.findall(r"-?\d{1,3}(?:[.,]\d{3})*(?:[.,]\d{2})|-?\d+(?:[.,]\d{2})", compact))
    if region_type == "totals":
        return amount_like_count >= 2 and any(
            token in upper for token in ("SUBTOTAL", "TOTAL", "TOT ", "IMPUEST", "IVA", "IGIC")
        )

    keyword_hits = sum(
        1
        for keyword in ("FACTURA", "RECTIFICAT", "NIF", "CIF", "MAIL", "WEB", "CLIENTE", "PROVEEDOR")
        if keyword in upper
    )
    return keyword_hits >= 1 or amount_like_count >= 2


def cleanup_hint_text(text: str) -> str:
    lines = []
    for raw_line in (text or "").splitlines():
        line = re.sub(r"\s+", " ", raw_line).strip(" |")
        if line:
            lines.append(line)
    return "\n".join(lines).strip()


def normalize_region_hint_text(region_type: str, text: str) -> str:
    normalized = cleanup_hint_text(text)
    if region_type == "totals":
        normalized = re.sub(r"\bTOTA[!I1]\b", "TOTAL", normalized, flags=re.IGNORECASE)
        normalized = re.sub(r"\bTOT\b", "TOTAL", normalized, flags=re.IGNORECASE)
        normalized = re.sub(r"\bIMPUE(?:S|5)T(?:O|0)S\b", "IMPUESTOS", normalized, flags=re.IGNORECASE)
    return normalized
