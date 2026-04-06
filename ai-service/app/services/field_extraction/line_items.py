"""Invoice line item extraction facade."""

from __future__ import annotations

from app.models.invoice_model import LineItem

from .line_item_parts.helpers import (
    build_line_description,
    is_note_line,
    is_standalone_amount_line,
    looks_like_item_description,
    looks_like_license_key_line,
    looks_like_summary_block,
    parse_standalone_amount_line,
    resolve_vertical_amount_triplet,
    sanitize_standalone_amount_line,
)
from .line_item_parts.parsing import parse_line_item
from .line_item_parts.recovery import recover_single_description_amount_item
from .line_item_parts.table import build_footer_pattern, collect_table_lines
from .line_item_parts.ticket import extract_ticket_line_items
from .line_item_parts.vertical import extract_vertical_line_items
from .shared import looks_like_ticket_document


def extract_line_items(text: str) -> list[LineItem]:
    lines = [line.strip() for line in text.split("\n") if line.strip()]
    table_lines = collect_table_lines(lines)
    if not table_lines:
        return []

    footer_pattern = build_footer_pattern()
    if looks_like_ticket_document(text):
        ticket_items = extract_ticket_line_items(table_lines, footer_pattern)
        if ticket_items:
            return ticket_items

    items = extract_vertical_line_items(table_lines, footer_pattern)
    if items:
        return items

    fallback_items: list[LineItem] = []
    for index, stripped in enumerate(table_lines):
        item = parse_line_item(stripped)
        if item:
            if item.importe <= 0 and index + 1 < len(table_lines) and is_standalone_amount_line(table_lines[index + 1]):
                amount = parse_standalone_amount_line(table_lines[index + 1])
                if amount > 0 and looks_like_item_description(item.descripcion):
                    item.cantidad = item.cantidad or 1.0
                    item.precio_unitario = item.precio_unitario or amount
                    item.importe = amount
            fallback_items.append(item)
    if fallback_items:
        return fallback_items
    return recover_single_description_amount_item(table_lines, footer_pattern)
