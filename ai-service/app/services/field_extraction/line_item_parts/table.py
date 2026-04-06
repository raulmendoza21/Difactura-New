from __future__ import annotations

import re

from .helpers import looks_like_summary_block


TABLE_HEADER_RELAXED_PATTERN = re.compile(
    r"(?:\bdescripci\w*\b|\bconcepto\b|\bdetalle\b|\bart(?:[ií]culo)?\b)",
    re.IGNORECASE,
)
TABLE_HEADER_PATTERN = re.compile(
    r"(?:\bdescripci[oó]n\b|\bconcepto\b|\bdetalle\b|\bart[ií]culo\b)",
    re.IGNORECASE,
)
SUMMARY_SECTION_START = {"CONCEPTOS", "PORTES", "DESCUENTO", "AJUSTE", "VALOR"}


def collect_table_lines(lines: list[str]) -> list[str]:
    table_lines: list[str] = []
    in_table = False
    footer_pattern = build_footer_pattern()

    for index, stripped in enumerate(lines):
        if footer_pattern.search(stripped) and in_table:
            break
        if (TABLE_HEADER_PATTERN.search(stripped) or TABLE_HEADER_RELAXED_PATTERN.search(stripped)) and not in_table:
            in_table = True
            continue
        if in_table and stripped.upper() in SUMMARY_SECTION_START and table_lines:
            break
        if in_table and looks_like_summary_block(lines, index, footer_pattern):
            break
        if in_table:
            table_lines.append(stripped)

    return table_lines


def build_footer_pattern() -> re.Pattern[str]:
    return re.compile(
        r"(?:base\s+imponible|\bsubtotal\b|\btotal(?:\s+factura|\s+compra)?\b|\biva\b|\bigic\b|\bimpuestos\b|\bobservaciones\b|\bnotas\b|forma\s+de\s+pago|\bcuota\b|%ret|%igic|\bbase\b)",
        re.IGNORECASE,
    )
