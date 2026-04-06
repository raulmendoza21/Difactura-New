from __future__ import annotations

import re

from .candidates import extract_amount, extract_numeric_candidates, extract_percentage_candidates
from .ticket import extract_ticket_tax_summary


def extract_footer_tax_summary(text: str) -> dict[str, float]:
    result = {
        "base_imponible": 0.0,
        "iva_porcentaje": 0.0,
        "iva": 0.0,
        "retencion_porcentaje": 0.0,
        "retencion": 0.0,
        "total": 0.0,
    }
    if not text:
        return result

    ticket_summary = extract_ticket_tax_summary(text)
    for key, value in ticket_summary.items():
        if value:
            result[key] = value

    lines = [line.strip() for line in text.splitlines() if line.strip()]
    upper_lines = [line.upper() for line in lines]

    for index, upper_line in enumerate(upper_lines):
        window_lines = lines[index:index + 4]
        window = "\n".join(window_lines)
        if "BASE IMPONIBLE" in upper_line or upper_line == "BASE":
            value = extract_amount(window)
            if value and not result["base_imponible"]:
                result["base_imponible"] = value
        if "TOTAL FACTURA" in upper_line or "TOTAL COMPRA" in upper_line or upper_line == "TOTAL":
            value = extract_amount(window)
            if value and not result["total"]:
                result["total"] = value
        if "RETENC" in upper_line or "IRPF" in upper_line:
            percentages = extract_percentage_candidates(window)
            amounts = extract_numeric_candidates(window)
            if percentages and not result["retencion_porcentaje"]:
                result["retencion_porcentaje"] = abs(percentages[0])
            signed_amounts = [value for value in amounts if value < 0]
            if signed_amounts and not result["retencion"]:
                result["retencion"] = abs(signed_amounts[0])
            elif amounts and not result["retencion"]:
                result["retencion"] = abs(amounts[-1])
        if "CUOTA IVA" in upper_line or "CUOTA IGIC" in upper_line:
            amounts = extract_numeric_candidates(window)
            if amounts and not result["iva"]:
                result["iva"] = amounts[0]
        elif re.search(r"\b(?:IVA|IGIC)\b", upper_line) and "%" in upper_line:
            line_percentages = extract_percentage_candidates(lines[index])
            line_amounts = extract_numeric_candidates(lines[index])
            percentages = extract_percentage_candidates(window)
            amounts = extract_numeric_candidates(window)
            if percentages and not result["iva_porcentaje"]:
                selected_rate = _select_indirect_tax_rate(percentages)
                if selected_rate:
                    result["iva_porcentaje"] = selected_rate
            if line_percentages and line_amounts and not result["iva"]:
                inline_tax_amounts = [
                    value
                    for value in line_amounts
                    if all(abs(abs(value) - abs(percent)) > 0.05 for percent in line_percentages)
                ]
                if inline_tax_amounts:
                    result["iva"] = inline_tax_amounts[-1]
            has_explicit_tax_quota = any(
                "CUOTA IVA" in candidate.upper() or "CUOTA IGIC" in candidate.upper()
                for candidate in window_lines[1:]
            )
            if has_explicit_tax_quota:
                continue
            if percentages and amounts and not result["iva"]:
                non_percent_amounts = [
                    value
                    for value in amounts
                    if all(abs(abs(value) - abs(percent)) > 0.05 for percent in percentages)
                ]
                if non_percent_amounts:
                    result["iva"] = non_percent_amounts[0] if len(non_percent_amounts) == 1 else min(non_percent_amounts, key=lambda value: abs(value))
    # Vertical summary blocks: BASE / %IGIC / CUOTA / SUBTOTAL / 312,85 / 7,00 / 21,90 / ...
    base_idx = next((i for i, line in enumerate(upper_lines) if line == "BASE"), -1)
    tax_idx = next((i for i, line in enumerate(upper_lines) if line in {"%IVA", "%IGIC", "IVA", "IGIC"}), -1)
    total_idx = next((i for i, line in enumerate(upper_lines) if line == "TOTAL"), -1)
    if base_idx >= 0 and tax_idx >= 0:
        numeric_tail: list[float] = []
        for line in lines[min(base_idx, tax_idx): min(len(lines), max(base_idx, tax_idx) + 10)]:
            stripped = line.strip()
            if not re.fullmatch(r"-?[\d.,%\s]+", stripped):
                continue
            if "%" in stripped:
                numeric_tail.extend(extract_percentage_candidates(stripped))
            else:
                numeric_tail.extend(extract_numeric_candidates(stripped))
        if numeric_tail and not result["base_imponible"]:
            result["base_imponible"] = numeric_tail[0]
        if not result["iva_porcentaje"]:
            percent_candidate = _select_indirect_tax_rate(numeric_tail[1:])
            if percent_candidate:
                result["iva_porcentaje"] = percent_candidate
        if not result["iva"]:
            tax_candidates = [
                value
                for value in numeric_tail[1:]
                if abs(value) > 0 and value != result["base_imponible"] and abs(value) != abs(result["iva_porcentaje"])
            ]
            if tax_candidates:
                result["iva"] = tax_candidates[0]
    if total_idx >= 0 and not result["total"]:
        totals_window = "\n".join(lines[total_idx:total_idx + 3])
        amounts = extract_numeric_candidates(totals_window)
        if amounts:
            result["total"] = amounts[-1]

    column_summary = extract_value_column_tax_summary(lines, upper_lines)
    for key, value in column_summary.items():
        if value and not result[key]:
            result[key] = value

    return result


def extract_value_column_tax_summary(lines: list[str], upper_lines: list[str]) -> dict[str, float]:
    result = {
        "base_imponible": 0.0,
        "iva_porcentaje": 0.0,
        "iva": 0.0,
        "retencion_porcentaje": 0.0,
        "retencion": 0.0,
        "total": 0.0,
    }
    value_idx = next((i for i, line in enumerate(upper_lines) if line == "VALOR"), -1)
    if value_idx < 0:
        return result

    label_window = upper_lines[max(0, value_idx - 10):value_idx]
    has_base = any("BASE IMPONIBLE" in line or line == "BASE" for line in label_window)
    has_total = any(line == "TOTAL" or "TOTAL FACTURA" in line for line in label_window)
    has_tax = any("IMPUEST" in line for line in label_window)
    if not (has_base and has_total and has_tax):
        return result

    parsed_values: list[tuple[str, float]] = []
    window_start = max(0, value_idx - 12)
    window_end = min(len(lines), value_idx + 12)
    for line in lines[window_start:window_end]:
        stripped = line.strip()
        if not stripped:
            continue
        percentages = extract_percentage_candidates(stripped)
        if percentages:
            parsed_values.append(("percent", abs(percentages[0])))
            continue
        amounts = extract_numeric_candidates(stripped)
        if amounts and re.fullmatch(r"-?[\d.,]+", stripped):
            parsed_values.append(("amount", amounts[-1]))
            continue
    if not parsed_values:
        return result

    percent_values = [value for kind, value in parsed_values if kind == "percent" and 0 < abs(value) <= 100]
    amount_values = [value for kind, value in parsed_values if kind == "amount"]

    selected_rate = _select_indirect_tax_rate(percent_values)
    if selected_rate:
        result["iva_porcentaje"] = selected_rate
    if len(amount_values) >= 2:
        inferred = infer_tax_summary_from_candidates(amount_values, percent_values)
        for key, value in inferred.items():
            if value:
                result[key] = value

    return result


def infer_tax_summary_from_candidates(amount_values: list[float], percent_values: list[float]) -> dict[str, float]:
    result = {
        "base_imponible": 0.0,
        "iva_porcentaje": _select_indirect_tax_rate(percent_values),
        "iva": 0.0,
        "total": 0.0,
    }
    positives = [round(value, 2) for value in amount_values if value >= 0]
    if len(positives) < 2:
        return result

    if result["iva_porcentaje"] > 0:
        best_match: tuple[float, float, float, float] | None = None
        for total in sorted(set(positives), reverse=True):
            for base in sorted(set(positives)):
                if total <= base:
                    continue
                tax = round(total - base, 2)
                if tax <= 0:
                    continue
                expected_tax = round(base * result["iva_porcentaje"] / 100, 2)
                diff = abs(expected_tax - tax)
                tolerance = max(0.08, abs(expected_tax) * 0.08)
                if diff <= tolerance:
                    candidate = (diff, -total, base, tax)
                    if best_match is None or candidate < best_match:
                        best_match = candidate
        if best_match is not None:
            _, neg_total, base, tax = best_match
            result["base_imponible"] = round(base, 2)
            result["iva"] = round(tax, 2)
            result["total"] = round(-neg_total, 2)
            return result

    ordered_positive = [value for value in positives if value > 0]
    if len(ordered_positive) >= 2:
        result["total"] = round(max(ordered_positive), 2)
        remaining = [value for value in ordered_positive if round(value, 2) != result["total"] or ordered_positive.count(value) > 1]
        if remaining:
            result["base_imponible"] = round(max(remaining), 2)
            if result["total"] > result["base_imponible"]:
                result["iva"] = round(result["total"] - result["base_imponible"], 2)
    return result


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
