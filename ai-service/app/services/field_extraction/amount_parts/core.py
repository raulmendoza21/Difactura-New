from __future__ import annotations

import re

from .candidates import (
    extract_amount,
    extract_amount_around_exact_label,
    extract_amount_from_label_lines,
    extract_numeric_candidates,
    extract_percentage_candidates,
)
from .summary import extract_footer_tax_summary

BASE_PATTERN = re.compile(r"\b(?:base\s+imponible|importe\s+neto|base)\b", re.IGNORECASE)
TOTAL_PATTERN = re.compile(r"\b(?:total(?:\s+factura|\s+compra)?|importe\s+total)\b", re.IGNORECASE)
TAX_AMOUNT_PATTERN = re.compile(r"\b(?:cuota\s+(?:iva|igic)|iva|igic|impuestos?)\b", re.IGNORECASE)
WITHHOLDING_PATTERN = re.compile(r"\b(?:retenci[oó]n|irpf)\b", re.IGNORECASE)


def extract_base_amount(text: str, lines: list[str]) -> float:
    summary = extract_footer_tax_summary(text)
    if summary["base_imponible"]:
        return summary["base_imponible"]
    return extract_amount_from_label_lines(lines, BASE_PATTERN)


def extract_iva_percent(text: str, lines: list[str]) -> float:
    summary = extract_footer_tax_summary(text)
    if summary["iva_porcentaje"]:
        return summary["iva_porcentaje"]

    contextual_percentages: list[float] = []
    for index, line in enumerate(lines):
        if "%" not in line:
            continue
        window = "\n".join(lines[max(0, index - 1):index + 2]).upper()
        percentages = extract_percentage_candidates(line)
        if any(token in window for token in ("IVA", "IGIC", "IMPUEST", "CUOTA")):
            contextual_percentages.extend(abs(value) for value in percentages)

    selected_contextual_rate = _select_indirect_tax_rate(contextual_percentages)
    if selected_contextual_rate:
        return selected_contextual_rate

    for line in lines:
        percentages = extract_percentage_candidates(line)
        selected_rate = _select_indirect_tax_rate(percentages)
        if selected_rate:
            return selected_rate
    return 0.0


def extract_iva_amount(text: str, lines: list[str]) -> float:
    summary = extract_footer_tax_summary(text)
    if summary["iva"]:
        return summary["iva"]

    value = extract_amount_from_label_lines(lines, re.compile(r"\bcuota\s+(?:iva|igic)\b", re.IGNORECASE))
    if value:
        return value

    for index, line in enumerate(lines):
        upper = line.upper()
        if "IMPUESTOS" not in upper and "IVA" not in upper and "IGIC" not in upper:
            continue
        window = "\n".join(lines[index:index + 3])
        amounts = extract_numeric_candidates(window)
        if not amounts:
            continue
        if "CUOTA" in upper and amounts:
            return amounts[0]
        percentages = extract_percentage_candidates(window)
        if percentages:
            filtered = [value for value in amounts if abs(value) != abs(percentages[0])]
            if filtered:
                return filtered[-1]
        if "IMPUESTOS" in upper:
            next_index = index + 1
            if next_index < len(lines):
                next_amounts = extract_numeric_candidates(lines[next_index])
                next_upper = lines[next_index].strip().upper()
                following_upper = lines[next_index + 1].strip().upper() if next_index + 1 < len(lines) else ""
                if next_amounts and "TOTAL" not in next_upper and "TOTAL" not in following_upper:
                    return next_amounts[0]

    summary_tokens = {"BASE", "SUBTOTAL", "%IGIC", "%IVA", "CUOTA", "IMPUESTOS", "TOTAL"}
    numeric_tail: list[float] = []
    in_summary = False
    for line in lines:
        stripped = line.strip()
        upper = stripped.upper()
        if upper in summary_tokens:
            in_summary = True
            continue
        if not in_summary:
            continue
        if "%" in stripped:
            numeric_tail.extend(extract_percentage_candidates(stripped))
        elif re.fullmatch(r"-?[\d.,]+", stripped):
            numeric_tail.extend(extract_numeric_candidates(stripped))
        elif numeric_tail:
            break

    if numeric_tail:
        base_value = numeric_tail[0]
        percent_value = next((abs(value) for value in numeric_tail[1:] if 0 < abs(value) <= 30), 0.0)
        for value in numeric_tail[1:]:
            if abs(value) in {0.0, abs(percent_value), abs(base_value)}:
                continue
            return value
    return 0.0


def extract_total_amount(text: str, lines: list[str]) -> float:
    summary = extract_footer_tax_summary(text)
    if summary["total"]:
        return summary["total"]

    value = extract_amount_from_label_lines(lines, TOTAL_PATTERN)
    if value:
        return value

    for index, line in enumerate(lines):
        upper = line.upper()
        if "TOTAL ENTREGADO" in upper or "A DEVOLVER" in upper or "CAMBIO" in upper:
            continue
        if "TOTAL" not in upper:
            continue
        window = "\n".join(lines[index:index + 3])
        amounts = extract_numeric_candidates(window)
        if amounts:
            return amounts[-1]
    return 0.0


def extract_withholding_percent(text: str, lines: list[str]) -> float:
    summary = extract_footer_tax_summary(text)
    if summary["retencion_porcentaje"]:
        return summary["retencion_porcentaje"]

    for index, line in enumerate(lines):
        if not WITHHOLDING_PATTERN.search(line):
            continue
        percentages = extract_percentage_candidates("\n".join(lines[index:index + 3]))
        if percentages:
            return abs(percentages[0])
    return 0.0


def extract_withholding_amount(text: str, lines: list[str]) -> float:
    summary = extract_footer_tax_summary(text)
    if summary["retencion"]:
        return summary["retencion"]

    for index, line in enumerate(lines):
        if not WITHHOLDING_PATTERN.search(line):
            continue
        amounts = extract_numeric_candidates("\n".join(lines[index:index + 4]))
        negative_amounts = [value for value in amounts if value < 0]
        if negative_amounts:
            return abs(negative_amounts[0])
        if amounts:
            return abs(amounts[-1])
    return 0.0


def extract_amounts_payload(text: str, lines: list[str]) -> dict[str, float]:
    return {
        "base_imponible": extract_base_amount(text, lines),
        "iva_porcentaje": extract_iva_percent(text, lines),
        "iva": extract_iva_amount(text, lines),
        "retencion_porcentaje": extract_withholding_percent(text, lines),
        "retencion": extract_withholding_amount(text, lines),
        "total": extract_total_amount(text, lines),
    }


def _select_indirect_tax_rate(values: list[float]) -> float:
    candidates = [round(abs(value), 2) for value in values if 0 < abs(value) <= 25]
    if not candidates:
        return 0.0

    preferred_rates = (3.0, 4.0, 5.0, 7.0, 9.5, 10.0, 21.0)
    for rate in preferred_rates:
        if any(abs(candidate - rate) <= 0.05 for candidate in candidates):
            return rate

    filtered = [candidate for candidate in candidates if candidate not in {15.0, 19.0}]
    if filtered:
        return filtered[0]
    return candidates[0]
