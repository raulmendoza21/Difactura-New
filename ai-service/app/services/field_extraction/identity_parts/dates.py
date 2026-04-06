from __future__ import annotations

import re

import dateparser

from app.utils.regex_patterns import DATE_NUMERIC, DATE_TEXT

from .shared import MONTH_MAP


def extract_date(text: str, lines: list[str] | None = None) -> str:
    lines = lines or [line.strip() for line in text.split("\n") if line.strip()]

    code_and_date = re.compile(
        r"\b[A-Z]{1,6}\d[\w/-]{4,}\b\s+(\d{1,2}[/\-\.]\d{1,2}[/\-\.]\d{2,4})\b",
        re.IGNORECASE,
    )
    for line in lines:
        match = code_and_date.search(line)
        if match:
            raw_date = match.group(1)
            parsed = dateparser.parse(raw_date, languages=["es"], settings={"DATE_ORDER": "DMY"})
            if parsed:
                return parsed.strftime("%Y-%m-%d")

    match = DATE_NUMERIC.search(text)
    if match:
        raw_date = match.group(1)
        parsed = dateparser.parse(raw_date, languages=["es"], settings={"DATE_ORDER": "DMY"})
        if parsed:
            return parsed.strftime("%Y-%m-%d")
        return raw_date

    match = DATE_TEXT.search(text)
    if match:
        day, month_name, year = match.groups()
        month = MONTH_MAP.get(month_name.lower(), "01")
        return f"{year}-{month}-{day.zfill(2)}"

    date_candidates = re.findall(r"\d{1,2}[/\-\.]\d{1,2}[/\-\.]\d{2,4}", text)
    for candidate in date_candidates:
        parsed = dateparser.parse(candidate, languages=["es"], settings={"DATE_ORDER": "DMY"})
        if parsed:
            return parsed.strftime("%Y-%m-%d")
    return ""
