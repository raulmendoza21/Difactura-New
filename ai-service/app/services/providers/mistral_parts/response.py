from __future__ import annotations

import re

from app.models.document_bundle import BoundingBox, DocumentSpan
from app.models.document_provider import ProviderDocumentResult, ProviderPageEntry


def normalize_ocr_response(response, *, model_name: str, table_format: str) -> ProviderDocumentResult:
    response_dict = to_mapping(response)
    pages_payload = response_dict.get("pages", []) or []
    page_entries: list[ProviderPageEntry] = []
    full_text_parts: list[str] = []

    for page_index, page_payload in enumerate(pages_payload, start=1):
        page_map = to_mapping(page_payload)
        if "index" in page_map and page_map.get("index") is not None:
            page_number = int(page_map.get("index")) + 1
        else:
            page_number = page_index
        expanded_text = expand_page_text(page_map).strip()
        dimensions = to_mapping(page_map.get("dimensions", {}))
        width = float(dimensions.get("width", 0) or 0)
        height = float(dimensions.get("height", 0) or 0)
        spans = markdown_to_spans(
            markdown=expanded_text,
            page_number=page_number,
            page_width=width,
            page_height=height,
        )
        page_entries.append(
            ProviderPageEntry(
                page_number=page_number,
                width=width,
                height=height,
                text=expanded_text,
                spans=spans,
                ocr_engine="mistral_ocr",
            )
        )
        if expanded_text:
            full_text_parts.append(expanded_text)

    return ProviderDocumentResult(
        text="\n\n".join(full_text_parts).strip(),
        pages=len(page_entries),
        is_digital=False,
        method="ocr",
        preprocessing_steps=[
            "provider:mistral",
            f"mistral_model:{model_name}",
            f"mistral_table_format:{table_format}",
        ],
        ocr_engine="mistral_ocr",
        page_entries=page_entries,
    )


def expand_page_text(page_map: dict) -> str:
    markdown = str(page_map.get("markdown", "") or "")
    tables = page_map.get("tables", []) or []
    referenced_ids: set[str] = set()

    for table_payload in tables:
        table_map = to_mapping(table_payload)
        table_id = str(table_map.get("id", "") or "").strip()
        table_content = table_to_plain_text(table_map)
        if not table_id or not table_content:
            continue
        marker = f"[{table_id}]({table_id})"
        if marker in markdown:
            markdown = markdown.replace(marker, table_content)
            referenced_ids.add(table_id)

    extra_tables: list[str] = []
    for table_payload in tables:
        table_map = to_mapping(table_payload)
        table_id = str(table_map.get("id", "") or "").strip()
        if table_id in referenced_ids:
            continue
        table_content = table_to_plain_text(table_map)
        if table_content:
            extra_tables.append(table_content)

    sections: list[str] = []
    header_text = str(page_map.get("header", "") or "").strip()
    footer_text = str(page_map.get("footer", "") or "").strip()

    if should_include_section_text(header_text, markdown):
        sections.append(header_text)
    sections.append(markdown.strip())
    if extra_tables:
        sections.extend(extra_tables)
    if should_include_section_text(footer_text, "\n\n".join(sections)):
        sections.append(footer_text)
    return "\n\n".join(section for section in sections if section)


def should_include_section_text(section_text: str, body_text: str) -> bool:
    cleaned_section = str(section_text or "").strip()
    if not cleaned_section:
        return False

    normalized_body = normalize_compare_text(body_text)
    normalized_section = normalize_compare_text(cleaned_section)
    if normalized_section and normalized_section in normalized_body:
        return False

    if re.search(r"\b(N[UÃš]MERO|FECHA|NIF|CIF|FACTURA)\b", cleaned_section.upper()):
        return True

    section_lines = [line.strip() for line in cleaned_section.splitlines() if line.strip()]
    useful_new_lines = [
        line
        for line in section_lines
        if len(normalize_compare_text(line)) >= 6
        and normalize_compare_text(line) not in normalized_body
    ]
    return bool(useful_new_lines)


def normalize_compare_text(value: str) -> str:
    return re.sub(r"[^A-Z0-9]", "", str(value or "").upper())


def table_to_plain_text(table_map: dict) -> str:
    content = str(table_map.get("content", "") or "").strip()
    if not content:
        return ""

    lines = [line.strip() for line in content.splitlines() if line.strip()]
    plain_lines: list[str] = []
    for line in lines:
        if re.fullmatch(r"\|\s*[-:\s|]+\|?", line):
            continue
        if "|" not in line:
            plain_lines.append(line)
            continue
        cells = [cell.strip() for cell in line.strip("|").split("|")]
        cells = [cell for cell in cells if cell and cell != "---"]
        plain_lines.extend(cells)

    return "\n".join(plain_lines).strip()


def markdown_to_spans(
    *,
    markdown: str,
    page_number: int,
    page_width: float,
    page_height: float,
) -> list[DocumentSpan]:
    lines = [line.strip() for line in markdown.splitlines() if line.strip()]
    if not lines:
        return []

    width = page_width or 1000.0
    height = page_height or max(1000.0, float(len(lines) * 24))
    top_margin = 24.0
    line_height = max(18.0, min(42.0, (height - top_margin * 2) / max(len(lines), 1)))
    spans: list[DocumentSpan] = []

    for index, line in enumerate(lines):
        y0 = top_margin + index * line_height
        y1 = min(height, y0 + line_height)
        spans.append(
            DocumentSpan(
                span_id=f"mistral:p{page_number}:l{index}",
                page=page_number,
                text=line,
                bbox=BoundingBox.from_points(0.0, y0, width, y1),
                source="ocr_mistral",
                engine="mistral_ocr",
                block_no=index,
                line_no=0,
                confidence=0.92,
            )
        )
    return spans


def to_mapping(value):
    if isinstance(value, dict):
        return value
    if hasattr(value, "model_dump"):
        return value.model_dump()
    if hasattr(value, "dict"):
        return value.dict()
    if hasattr(value, "__dict__"):
        return dict(value.__dict__)
    return {}
