from __future__ import annotations

from app.models.invoice_model import LineItem

from .helpers import (
    build_line_description,
    is_note_line,
    is_standalone_amount_line,
    is_table_header_noise,
    looks_like_item_description,
    looks_like_license_key_line,
    parse_standalone_amount_line,
    resolve_vertical_amount_triplet,
)
from .parsing import parse_line_item


def extract_vertical_line_items(lines: list[str], footer_pattern) -> list[LineItem]:
    items: list[LineItem] = []
    index = 0

    while index < len(lines):
        current = lines[index]
        if footer_pattern.search(current):
            break

        if is_note_line(current):
            index += 1
            continue

        if (
            not is_standalone_amount_line(current)
            and not looks_like_license_key_line(current)
            and looks_like_item_description(current)
            and not is_table_header_noise(current)
            and index + 1 < len(lines)
        ):
            if (
                index + 3 < len(lines)
                and is_standalone_amount_line(lines[index + 1])
                and is_standalone_amount_line(lines[index + 2])
                and is_standalone_amount_line(lines[index + 3])
            ):
                triplet = resolve_vertical_amount_triplet(
                    parse_standalone_amount_line(lines[index + 1]),
                    parse_standalone_amount_line(lines[index + 2]),
                    parse_standalone_amount_line(lines[index + 3]),
                )
                if triplet:
                    quantity, unit_price, amount = triplet
                    description = build_line_description([current])
                    if description:
                        items.append(
                            LineItem(
                                descripcion=description,
                                cantidad=quantity or 1.0,
                                precio_unitario=unit_price,
                                importe=amount,
                            )
                        )
                        index += 4
                        continue

            description_parts = [current]
            amount = None
            lookahead = index + 1
            while lookahead < len(lines):
                candidate = lines[lookahead]
                if footer_pattern.search(candidate):
                    break
                if is_standalone_amount_line(candidate):
                    amount = parse_standalone_amount_line(candidate)
                    lookahead += 1
                    break
                if not is_note_line(candidate) and not looks_like_license_key_line(candidate):
                    description_parts.append(candidate)
                lookahead += 1

            description = build_line_description(description_parts)
            if amount is not None and description and looks_like_item_description(description):
                items.append(
                    LineItem(
                        descripcion=description,
                        cantidad=1.0,
                        precio_unitario=amount,
                        importe=amount,
                    )
                )
                index = lookahead
                continue

        if (
            looks_like_license_key_line(current)
            and index + 4 < len(lines)
            and not is_table_header_noise(lines[index + 1])
            and looks_like_item_description(lines[index + 1])
            and is_standalone_amount_line(lines[index + 2])
            and is_standalone_amount_line(lines[index + 3])
            and is_standalone_amount_line(lines[index + 4])
        ):
            triplet = resolve_vertical_amount_triplet(
                parse_standalone_amount_line(lines[index + 2]),
                parse_standalone_amount_line(lines[index + 3]),
                parse_standalone_amount_line(lines[index + 4]),
            )
            if triplet:
                quantity, unit_price, amount = triplet
                description = build_line_description([lines[index + 1]])
                if description:
                    items.append(
                        LineItem(
                            descripcion=description,
                            cantidad=quantity or 1.0,
                            precio_unitario=unit_price,
                            importe=amount,
                        )
                    )
                    index += 5
                    continue

        if (
            is_standalone_amount_line(current)
            and index + 2 < len(lines)
            and is_standalone_amount_line(lines[index + 1])
            and is_standalone_amount_line(lines[index + 2])
        ):
            triplet = resolve_vertical_amount_triplet(
                parse_standalone_amount_line(current),
                parse_standalone_amount_line(lines[index + 1]),
                parse_standalone_amount_line(lines[index + 2]),
            )
            if triplet:
                quantity, unit_price, amount = triplet
            else:
                quantity = parse_standalone_amount_line(current)
                unit_price = parse_standalone_amount_line(lines[index + 1])
                amount = parse_standalone_amount_line(lines[index + 2])
            description_parts: list[str] = []
            lookahead = index + 3
            while lookahead < len(lines):
                candidate = lines[lookahead]
                if footer_pattern.search(candidate) or is_standalone_amount_line(candidate):
                    break
                if not is_note_line(candidate) and not looks_like_license_key_line(candidate):
                    description_parts.append(candidate)
                lookahead += 1

            description = build_line_description(description_parts)
            if description:
                items.append(
                    LineItem(
                        descripcion=description,
                        cantidad=quantity or 1.0,
                        precio_unitario=unit_price,
                        importe=amount,
                    )
                )
                index = lookahead
                continue

        if is_standalone_amount_line(current):
            amount = parse_standalone_amount_line(current)
            description_parts: list[str] = []
            lookahead = index + 1
            while lookahead < len(lines):
                candidate = lines[lookahead]
                if footer_pattern.search(candidate) or is_standalone_amount_line(candidate):
                    break
                if not is_note_line(candidate) and not looks_like_license_key_line(candidate):
                    description_parts.append(candidate)
                lookahead += 1

            description = build_line_description(description_parts)
            if description and looks_like_item_description(description):
                items.append(
                    LineItem(
                        descripcion=description,
                        cantidad=1.0,
                        precio_unitario=amount,
                        importe=amount,
                    )
                )
                index = lookahead
                continue

        item = parse_line_item(current)
        if item:
            items.append(item)

        index += 1

    return items
