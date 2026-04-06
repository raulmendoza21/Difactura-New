from __future__ import annotations

import re

from app.utils.text_processing import parse_amount


def extract_retention_summary(raw_text: str) -> dict[str, float]:
    summary = {
        "base": 0.0,
        "tax_rate": 0.0,
        "tax_amount": 0.0,
        "withholding_rate": 0.0,
        "withholding_amount": 0.0,
        "gross_total": 0.0,
        "total_due": 0.0,
    }
    if not raw_text:
        return summary

    lines = [line.strip() for line in raw_text.splitlines() if line.strip()]
    normalized_lines = [re.sub(r"\s+", " ", line.lower()).strip(" .:;,-") for line in lines]
    compact_lines = [re.sub(r"[^a-z0-9]", "", line) for line in normalized_lines]

    def amount_candidates(window: list[str]) -> list[float]:
        values: list[float] = []
        for line in window:
            sanitized = re.sub(r"\d{1,2}(?:[.,]\d{1,2})?\s*%", " ", line)
            for match in re.findall(r"-?\d{1,3}(?:[.,]\d{3})*(?:[.,]\d{2})|-?\d{1,6}(?:[.,]\d{2})", sanitized):
                values.append(abs(parse_amount(match)))
        return [value for value in values if value > 0]

    def percent_candidates(window: list[str]) -> list[float]:
        values: list[float] = []
        for line in window:
            for match in re.findall(r"(\d{1,2}(?:[.,]\d{1,2})?)\s*%", line):
                values.append(float(match.replace(",", ".")))
        return values

    def line_amount(index: int, offset: int) -> float:
        target = index + offset
        if target < 0 or target >= len(lines):
            return 0.0
        values = amount_candidates([lines[target]])
        return values[0] if values else 0.0

    def line_percent(index: int, offset: int, *, max_value: float) -> float:
        target = index + offset
        if target < 0 or target >= len(lines):
            return 0.0
        values = [value for value in percent_candidates([lines[target]]) if 0 < value <= max_value]
        return values[0] if values else 0.0

    def first_amount(index: int, *, mode: str) -> float:
        current_line_value = line_amount(index, 0)
        if current_line_value:
            return current_line_value

        if mode == "total":
            for offset in (-1, 1, -2, 2, -3, 3):
                candidate = line_amount(index, offset)
                if candidate:
                    return candidate
            return 0.0

        if mode == "total_due":
            for offset in (1, -1, 2, -2, 3, -3):
                candidate = line_amount(index, offset)
                if candidate:
                    return candidate
            return 0.0

        if line_percent(index, 1, max_value=25) and line_amount(index, 1):
            return line_amount(index, 1)
        if line_percent(index, -1, max_value=25) and line_amount(index, -1):
            return line_amount(index, -1)
        if line_percent(index, -1, max_value=25) and line_amount(index, -2):
            return line_amount(index, -2)
        if line_percent(index, -2, max_value=25) and line_amount(index, -1):
            return line_amount(index, -1)

        for offset in (1, -1, 2, -2, 3, -3):
            candidate = line_amount(index, offset)
            if candidate:
                return candidate
        return 0.0

    def first_percent(index: int, *, max_value: float) -> float:
        current_line_value = line_percent(index, 0, max_value=max_value)
        if current_line_value:
            return current_line_value

        if line_percent(index, 1, max_value=max_value) and line_amount(index, 1):
            return line_percent(index, 1, max_value=max_value)
        if line_percent(index, -1, max_value=max_value) and line_amount(index, -1):
            return line_percent(index, -1, max_value=max_value)
        if line_percent(index, -2, max_value=max_value) and line_amount(index, -1):
            return line_percent(index, -2, max_value=max_value)
        if line_percent(index, -1, max_value=max_value) and line_amount(index, -2):
            return line_percent(index, -1, max_value=max_value)

        for offset in (1, -1, 2, -2, 3, -3):
            candidate = line_percent(index, offset, max_value=max_value)
            if candidate:
                return candidate
        return 0.0

    for index, compact_line in enumerate(compact_lines):
        if compact_line == "totalfactura":
            amount = first_amount(index, mode="total_due")
            if amount:
                summary["total_due"] = amount
        elif compact_line == "total":
            amount = first_amount(index, mode="total")
            if amount:
                summary["gross_total"] = amount
        elif compact_line in {"igic", "iva"}:
            amount = first_amount(index, mode="tax")
            percent = first_percent(index, max_value=21)
            if amount:
                summary["tax_amount"] = amount
            if percent:
                summary["tax_rate"] = percent
        elif "retenc" in compact_line or "irpf" in compact_line:
            amount = first_amount(index, mode="withholding")
            percent = first_percent(index, max_value=25)
            if amount:
                summary["withholding_amount"] = amount
            if percent:
                summary["withholding_rate"] = percent

    if (
        summary["gross_total"] > 0
        and summary["tax_amount"] > 0
        and summary["withholding_amount"] > 0
        and summary["total_due"] > 0
    ):
        if abs(summary["gross_total"] + summary["tax_amount"] - summary["withholding_amount"] - summary["total_due"]) <= 0.2:
            summary["base"] = summary["gross_total"]
            summary["gross_total"] = round(summary["base"] + summary["tax_amount"], 2)
        else:
            summary["base"] = round(summary["total_due"] + summary["withholding_amount"] - summary["tax_amount"], 2)
            summary["gross_total"] = round(summary["base"] + summary["tax_amount"], 2)
    elif summary["gross_total"] <= 0 and summary["total_due"] > 0 and summary["withholding_amount"] > 0:
        summary["gross_total"] = round(summary["total_due"] + summary["withholding_amount"], 2)
    if summary["base"] <= 0 and summary["gross_total"] > 0 and summary["tax_amount"] > 0:
        summary["base"] = round(summary["gross_total"] - summary["tax_amount"], 2)

    return summary
