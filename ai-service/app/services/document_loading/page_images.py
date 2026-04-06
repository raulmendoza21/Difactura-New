from __future__ import annotations

import base64
import logging
from io import BytesIO

from PIL import Image

logger = logging.getLogger(__name__)


def image_to_data_url(image: Image.Image, mime_type: str) -> str:
    buffer = BytesIO()
    fmt = "PNG" if mime_type == "image/png" else "JPEG"
    image.save(buffer, format=fmt)
    encoded = base64.b64encode(buffer.getvalue()).decode("ascii")
    return f"data:{mime_type};base64,{encoded}"


def render_pdf_pages(file_path: str, *, image_encoder=image_to_data_url) -> list[str]:
    import fitz

    doc = fitz.open(file_path)
    page_images: list[str] = []
    try:
        for page in doc:
            mat = fitz.Matrix(2, 2)
            pix = page.get_pixmap(matrix=mat, alpha=False)
            image = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
            page_images.append(image_encoder(image, "image/png"))
    finally:
        doc.close()

    logger.info("Rendered %s PDF pages as images", len(page_images))
    return page_images
