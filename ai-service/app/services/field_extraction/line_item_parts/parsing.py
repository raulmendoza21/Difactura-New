from __future__ import annotations

import re

from app.models.invoice_model import LineItem
from app.utils.text_processing import parse_amount

from .helpers import is_note_line, looks_like_item_description, looks_like_license_key_line


def parse_line_item(line: str) -> LineItem | None:
    if is_note_line(line) or looks_like_license_key_line(line):
        return None
    if not looks_like_item_description(line):
        return None
    amounts = re.findall(r"-?\d[\d.,]*", line)
    if len(amounts) < 1:
        return None

    desc_match = re.match(r"^(.+?)(?:\d)", line)
    description = desc_match.group(1).strip() if desc_match else line

    if not description or len(description) < 3:
        return None

    try:
        if len(amounts) >= 3:
            return LineItem(
                descripcion=description,
                cantidad=parse_amount(amounts[-3]),
                precio_unitario=parse_amount(amounts[-2]),
                importe=parse_amount(amounts[-1]),
            )
        return LineItem(
            descripcion=description,
            importe=parse_amount(amounts[-1]),
        )
    except (ValueError, IndexError):
        return None
