from __future__ import annotations

import re

from app.models.invoice_model import LineItem

from .helpers import (
    build_line_description,
    is_note_line,
    is_standalone_amount_line,
    looks_like_item_description,
    looks_like_license_key_line,
    parse_standalone_amount_line,
)

TICKET_HEADER_NOISE = re.compile(
    r"^(?:UDS?|DESCRIPCION|DESCRIPCI[OÓ]N|IMPORTE|PVP|PRECIO|SALA\s+\d+|MESA\s+\d+|CAMARERO.*)$",
    re.IGNORECASE,
)
TICKET_DECORATION_NOISE = re.compile(r"^(?:\*{2,}.*|\[[A-Z0-9-]+\])$", re.IGNORECASE)
TICKET_COMBINED_ITEM = re.compile(r"^(?P<qty>\d+(?:[.,]\d+)?)\s+(?P<desc>.+)$")


def extract_ticket_line_items(lines: list[str], footer_pattern: re.Pattern[str]) -> list[LineItem]:
    items: list[LineItem] = []
    index = 0

    while index < len(lines):
        current = lines[index].strip()
        if footer_pattern.search(current):
            break
        if _is_ticket_noise_line(current):
            index += 1
            continue

        inline_match = _parse_inline_ticket_item(lines, index, footer_pattern)
        if inline_match is not None:
            item, next_index = inline_match
            items.append(item)
            index = next_index
            continue

        stacked_match = _parse_stacked_ticket_item(lines, index, footer_pattern)
        if stacked_match is not None:
            item, next_index = stacked_match
            items.append(item)
            index = next_index
            continue

        index += 1

    return items


def _parse_inline_ticket_item(
    lines: list[str],
    index: int,
    footer_pattern: re.Pattern[str],
) -> tuple[LineItem, int] | None:
    current = lines[index].strip()
    match = TICKET_COMBINED_ITEM.match(current)
    if not match:
        return None

    quantity = parse_standalone_amount_line(match.group("qty"))
    description = build_line_description([match.group("desc")])
    if quantity <= 0 or not description or not looks_like_item_description(description):
        return None

    amount_pair = _extract_ticket_amount_pair(lines, index + 1, footer_pattern, quantity=quantity)
    if amount_pair is None:
        return None

    unit_price, amount, next_index = amount_pair
    return (
        LineItem(
            descripcion=description,
            cantidad=quantity,
            precio_unitario=unit_price,
            importe=amount,
        ),
        next_index,
    )


def _parse_stacked_ticket_item(
    lines: list[str],
    index: int,
    footer_pattern: re.Pattern[str],
) -> tuple[LineItem, int] | None:
    current = lines[index].strip()
    if not is_standalone_amount_line(current):
        return None

    quantity = parse_standalone_amount_line(current)
    if quantity <= 0 or quantity > 500:
        return None
    if abs(quantity - round(quantity)) > 0.05:
        return None

    next_index = _next_meaningful_index(lines, index + 1, footer_pattern)
    if next_index < 0:
        return None

    description = build_line_description([lines[next_index]])
    if not description or not looks_like_item_description(description):
        return None

    amount_pair = _extract_ticket_amount_pair(lines, next_index + 1, footer_pattern, quantity=quantity)
    if amount_pair is None:
        return None

    unit_price, amount, final_index = amount_pair
    return (
        LineItem(
            descripcion=description,
            cantidad=quantity,
            precio_unitario=unit_price,
            importe=amount,
        ),
        final_index,
    )


def _extract_ticket_amount_pair(
    lines: list[str],
    start_index: int,
    footer_pattern: re.Pattern[str],
    *,
    quantity: float,
) -> tuple[float, float, int] | None:
    amount_values: list[float] = []
    index = start_index

    while index < len(lines) and len(amount_values) < 2:
        current = lines[index].strip()
        if footer_pattern.search(current):
            break
        if _is_ticket_noise_line(current):
            index += 1
            continue
        if not is_standalone_amount_line(current):
            break
        amount_values.append(parse_standalone_amount_line(current))
        index += 1

    if not amount_values:
        return None
    if len(amount_values) == 1:
        amount = amount_values[0]
        return amount, amount, index

    first, second = amount_values[:2]
    unit_price, amount = _resolve_ticket_amounts(quantity, first, second)
    return unit_price, amount, index


def _resolve_ticket_amounts(quantity: float, first: float, second: float) -> tuple[float, float]:
    if abs(first - second) <= 0.02:
        return round(first, 2), round(second, 2)
    if quantity > 0 and abs(round(quantity * first, 2) - second) <= max(0.05, abs(second) * 0.03):
        return round(first, 2), round(second, 2)
    if quantity > 0 and abs(round(quantity * second, 2) - first) <= max(0.05, abs(first) * 0.03):
        return round(second, 2), round(first, 2)
    if quantity <= 1.05:
        return round(max(first, second), 2), round(min(first, second), 2)
    return round(min(first, second), 2), round(max(first, second), 2)


def _next_meaningful_index(lines: list[str], start_index: int, footer_pattern: re.Pattern[str]) -> int:
    for index in range(start_index, len(lines)):
        current = lines[index].strip()
        if footer_pattern.search(current):
            return -1
        if _is_ticket_noise_line(current):
            continue
        return index
    return -1


def _is_ticket_noise_line(value: str) -> bool:
    cleaned = re.sub(r"\s+", " ", (value or "").strip())
    if not cleaned:
        return True
    if TICKET_HEADER_NOISE.match(cleaned):
        return True
    if TICKET_DECORATION_NOISE.match(cleaned):
        return True
    if is_note_line(cleaned) or looks_like_license_key_line(cleaned):
        return True
    if cleaned.upper().startswith(("TOTAL ", "ENTREGADO", "CAMBIO", "FORMA DE PAGO", "IGIC", "IVA", "BASE ", "CUOTA ")):
        return True
    return False
