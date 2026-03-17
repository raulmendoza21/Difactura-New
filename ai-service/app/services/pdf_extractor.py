import logging
from pathlib import Path

import fitz  # PyMuPDF

logger = logging.getLogger(__name__)


class PDFExtractor:
    """Extract text from digital PDFs using PyMuPDF."""

    def extract(self, file_path: str) -> dict:
        """Extract text from a PDF file."""
        path = Path(file_path)
        if not path.exists():
            raise FileNotFoundError(f"File not found: {file_path}")

        try:
            doc = fitz.open(file_path)
            pages_text = []

            for page in doc:
                pages_text.append(self._extract_page_text(page).strip())

            doc.close()

            full_text = "\n\n".join(pages_text)
            avg_chars = len(full_text.replace("\n", "").replace(" ", "")) / max(len(pages_text), 1)
            is_digital = avg_chars > 50

            logger.info(
                "PDF extraction: %s pages, avg %.0f chars/page, digital=%s",
                len(pages_text),
                avg_chars,
                is_digital,
            )

            return {
                "text": full_text,
                "pages": len(pages_text),
                "is_digital": is_digital,
            }
        except Exception as exc:
            logger.error("PDF extraction failed: %s", exc)
            raise

    def _extract_page_text(self, page) -> str:
        """Prefer sorted text blocks to preserve reading order."""
        blocks = page.get_text("blocks")
        if not blocks:
            return page.get_text("text")

        ordered_blocks = sorted(blocks, key=lambda block: (round(block[1], 1), round(block[0], 1)))
        parts = []
        for block in ordered_blocks:
            block_text = (block[4] or "").strip()
            if block_text:
                parts.append(block_text)

        text = "\n".join(parts).strip()
        return text or page.get_text("text")


pdf_extractor = PDFExtractor()
