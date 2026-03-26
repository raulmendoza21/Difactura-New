import logging
from pathlib import Path

from app.models.document_bundle import BoundingBox, DocumentSpan

logger = logging.getLogger(__name__)


class PDFExtractor:
    """Extract text from digital PDFs using PyMuPDF."""

    def extract(self, file_path: str) -> dict:
        """Extract text from a PDF file."""
        path = Path(file_path)
        if not path.exists():
            raise FileNotFoundError(f"File not found: {file_path}")

        try:
            import fitz  # PyMuPDF

            doc = fitz.open(file_path)
            pages_text = []
            page_entries = []

            for page_index, page in enumerate(doc, start=1):
                page_entry = self._extract_page_payload(page, page_index)
                pages_text.append(page_entry["text"].strip())
                page_entries.append(page_entry)

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
                "page_entries": page_entries,
            }
        except Exception as exc:
            logger.error("PDF extraction failed: %s", exc)
            raise

    def _extract_page_payload(self, page, page_index: int) -> dict:
        spans = self._extract_page_spans(page, page_index)
        text = "\n".join(span.text for span in spans if span.text).strip()
        if not text:
            text = page.get_text("text").strip()
        return {
            "page_number": page_index,
            "width": float(page.rect.width),
            "height": float(page.rect.height),
            "text": text,
            "spans": spans,
        }

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

    def _extract_page_spans(self, page, page_index: int) -> list[DocumentSpan]:
        words = page.get_text("words")
        if not words:
            blocks = page.get_text("blocks")
            spans: list[DocumentSpan] = []
            for block_index, block in enumerate(blocks):
                block_text = (block[4] or "").strip()
                if not block_text:
                    continue
                spans.append(
                    DocumentSpan(
                        span_id=f"pdf:p{page_index}:b{block_index}:l0",
                        page=page_index,
                        text=block_text,
                        bbox=BoundingBox.from_points(float(block[0]), float(block[1]), float(block[2]), float(block[3])),
                        source="pdf_native",
                        engine="pymupdf",
                        block_no=block_index,
                        line_no=0,
                        confidence=1.0,
                    )
                )
            return spans

        line_map: dict[tuple[int, int], dict] = {}
        for word in words:
            x0, y0, x1, y1, text, block_no, line_no, _word_no = word
            normalized_text = str(text or "").strip()
            if not normalized_text:
                continue
            key = (int(block_no), int(line_no))
            current = line_map.setdefault(
                key,
                {
                    "texts": [],
                    "x0": float(x0),
                    "y0": float(y0),
                    "x1": float(x1),
                    "y1": float(y1),
                },
            )
            current["texts"].append(normalized_text)
            current["x0"] = min(current["x0"], float(x0))
            current["y0"] = min(current["y0"], float(y0))
            current["x1"] = max(current["x1"], float(x1))
            current["y1"] = max(current["y1"], float(y1))

        spans = []
        for (block_no, line_no), payload in sorted(line_map.items(), key=lambda item: (item[1]["y0"], item[1]["x0"])):
            spans.append(
                DocumentSpan(
                    span_id=f"pdf:p{page_index}:b{block_no}:l{line_no}",
                    page=page_index,
                    text=" ".join(payload["texts"]).strip(),
                    bbox=BoundingBox.from_points(payload["x0"], payload["y0"], payload["x1"], payload["y1"]),
                    source="pdf_native",
                    engine="pymupdf",
                    block_no=block_no,
                    line_no=line_no,
                    confidence=1.0,
                )
            )
        return spans


pdf_extractor = PDFExtractor()
