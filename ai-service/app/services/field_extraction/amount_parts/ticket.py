from __future__ import annotations

import re

from app.services.field_extraction.shared import looks_like_ticket_document

from .candidates import extract_numeric_candidates, extract_percentage_candidates

PAYMENT_LINE_HINT = re.compile(r"\b(?:TOTAL\s+ENTREGADO|A\s+DEVOLVER|CAMBIO|FORMA\s+DE\s+PAGO|DETALLE\s+DE\s+PAGOS)\b", re.IGNORECASE)
TOTAL_LINE_HINT = re.compile(r"\b(?:TOTAL\s+COMPRA|TOTAL)\b", re.IGNORECASE)
INLINE_BASE_TAX_HINT = re.compile(
    r"\bBASE\s+(?P<base>-?\d[\d.,]*)\s+CUOTA\s+(?P<tax>-?\d[\d.,]*)",
    re.IGNORECASE,
)


def extract_ticket_tax_summary(text: str) -> dict[str, float]:
    result = {
        "base_imponible": 0.0,
        "iva_porcentaje": 0.0,
        "iva": 0.0,
        "total": 0.0,
    }
    if not looks_like_ticket_document(text):
        return result

    lines = [line.strip() for line in (text or "").splitlines() if line.strip()]
    upper_lines = [line.upper() for line in lines]

    result["total"] = _extract_ticket_total(lines, upper_lines)

    inline_base, inline_tax = _extract_inline_base_tax(lines)
    if inline_base > 0:
        result["base_imponible"] = inline_base
    if inline_tax > 0:
        result["iva"] = inline_tax

    vertical_summary = _extract_vertical_tax_block(lines, upper_lines)
    for key, value in vertical_summary.items():
        if value > 0 and result[key] <= 0:
            result[key] = value

    detected_rate = _extract_ticket_tax_rate(lines)
    if detected_rate > 0:
        result["iva_porcentaje"] = detected_rate
    elif result["base_imponible"] > 0 and result["iva"] > 0:
        result["iva_porcentaje"] = round(result["iva"] / result["base_imponible"] * 100, 2)
    return result


def has_explicit_ticket_tax_summary(text: str) -> bool:
    summary = extract_ticket_tax_summary(text)
    return summary["base_imponible"] > 0 or summary["iva"] > 0 or summary["iva_porcentaje"] > 0


def _extract_ticket_total(lines: list[str], upper_lines: list[str]) -> float:
    for index, upper_line in enumerate(upper_lines):
        if PAYMENT_LINE_HINT.search(upper_line):
            continue
        if not TOTAL_LINE_HINT.search(upper_line):
            continue
        same_line_amounts = extract_numeric_candidates(lines[index])
        if same_line_amounts:
            return same_line_amounts[-1]
        for next_line in lines[index + 1:index + 4]:
            next_upper = next_line.upper()
            if PAYMENT_LINE_HINT.search(next_upper):
                break
            if "%" in next_upper or TOTAL_LINE_HINT.search(next_upper):
                break
            if not re.fullmatch(r"-?[\d.,]+", next_line.strip()):
                continue
            amounts = extract_numeric_candidates(next_line)
            if amounts:
                return amounts[-1]
    return 0.0


def _extract_inline_base_tax(lines: list[str]) -> tuple[float, float]:
    for line in lines:
        match = INLINE_BASE_TAX_HINT.search(line)
        if not match:
            continue
        base_values = extract_numeric_candidates(match.group("base"))
        tax_values = extract_numeric_candidates(match.group("tax"))
        if base_values and tax_values:
            return base_values[0], tax_values[0]
    return 0.0, 0.0


def _extract_vertical_tax_block(lines: list[str], upper_lines: list[str]) -> dict[str, float]:
    result = {
        "base_imponible": 0.0,
        "iva_porcentaje": 0.0,
        "iva": 0.0,
        "total": 0.0,
    }

    summary_index = next(
        (
            index
            for index, line in enumerate(upper_lines)
            if "IGIC%" in line or "IVA%" in line or line.strip() in {"IGIC", "IVA"}
        ),
        -1,
    )
    if summary_index < 0:
        return result

    parsed_values: list[tuple[str, float]] = []
    for line in lines[summary_index:summary_index + 8]:
        percentages = extract_percentage_candidates(line)
        if percentages:
            parsed_values.append(("percent", abs(percentages[0])))
            continue
        amounts = extract_numeric_candidates(line)
        if amounts and re.fullmatch(r"-?[\d.,]+", line.strip()):
            parsed_values.append(("amount", amounts[-1]))

    if len(parsed_values) < 4:
        return result

    percent_values = [value for kind, value in parsed_values if kind == "percent" and 0 < value <= 25]
    amount_values = [value for kind, value in parsed_values if kind == "amount" and value > 0]
    if percent_values:
        result["iva_porcentaje"] = percent_values[0]
    if len(amount_values) >= 3:
        result["base_imponible"] = amount_values[0]
        result["iva"] = amount_values[1]
        result["total"] = amount_values[2]
    return result


def _extract_ticket_tax_rate(lines: list[str]) -> float:
    for line in lines:
        percentages = extract_percentage_candidates(line)
        if not percentages:
            continue
        if any(token in line.upper() for token in ("IGIC", "IVA", "IMPUEST")):
            candidate = abs(percentages[0])
            if 0 < candidate <= 25:
                return candidate
    return 0.0
