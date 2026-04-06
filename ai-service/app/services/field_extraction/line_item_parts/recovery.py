from __future__ import annotations

import re

from app.models.invoice_model import LineItem
from app.utils.text_processing import parse_amount

from .helpers import (
    build_line_description,
    is_note_line,
    is_standalone_amount_line,
    looks_like_item_description,
    looks_like_license_key_line,
    parse_standalone_amount_line,
)


def recover_single_description_amount_item(lines: list[str], footer_pattern) -> list[LineItem]:
    best_description: str = ""
    best_amount = 0.0

    for index, current in enumerate(lines):
        if footer_pattern.search(current):
            break
        if is_note_line(current) or looks_like_license_key_line(current):
            continue
        if not looks_like_item_description(current):
            continue

        description = build_line_description([current])
        if len(description) < 10:
            continue

        for lookahead in range(index + 1, len(lines)):
            candidate = lines[lookahead]
            if footer_pattern.search(candidate):
                break
            if is_standalone_amount_line(candidate):
                amount = parse_standalone_amount_line(candidate)
                if amount > best_amount:
                    best_description = description
                    best_amount = amount
                break

    if best_description and best_amount > 0:
        return [
            LineItem(
                descripcion=best_description,
                cantidad=1.0,
                precio_unitario=best_amount,
                importe=best_amount,
            )
        ]

    return []


def recover_single_description_amount_from_raw_text(text: str) -> list[LineItem]:
    lines = [line.strip() for line in (text or "").splitlines() if line.strip()]
    if not lines:
        return []

    trigger_index = next(
        (
            index
            for index, line in enumerate(lines)
            if re.search(r"(?:concepto|detalle|descripci|art[ií]culo)", line, re.IGNORECASE)
        ),
        -1,
    )
    if trigger_index < 0:
        return []

    footer_pattern = re.compile(
        r"(?:\bsubtotal\b|\btotal(?:\s+factura|\s+compra)?\b|\biva\b|\bigic\b|\bimpuestos\b|\bbase\b|%ret|%igic)",
        re.IGNORECASE,
    )
    description = ""
    amount = 0.0
    for index in range(trigger_index + 1, len(lines)):
        line = lines[index]
        if footer_pattern.search(line):
            break
        if not description:
            if looks_like_item_description(line) and not is_note_line(line):
                candidate = build_line_description([line])
                if len(candidate) >= 10:
                    description = candidate
            continue
        matches = re.findall(r"-?\d[\d.,]*", line)
        if matches:
            try:
                candidate_amount = parse_amount(matches[-1])
            except Exception:
                candidate_amount = 0.0
            if candidate_amount > 0:
                amount = candidate_amount
                break

    if description and amount > 0:
        return [
            LineItem(
                descripcion=description,
                cantidad=1.0,
                precio_unitario=amount,
                importe=amount,
            )
        ]
    return []
