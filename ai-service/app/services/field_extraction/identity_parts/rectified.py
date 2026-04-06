from __future__ import annotations

import re

from .shared import normalize_invoice_number_candidate


def extract_rectified_invoice_number(text: str, lines: list[str] | None = None) -> str:
    lines = lines or [line.strip() for line in text.split("\n") if line.strip()]
    label_pattern = re.compile(r"^(?:rectifica\s+a|factura\s+rectificada)\s*:?\s*$", re.IGNORECASE)
    candidate_pattern = re.compile(r"[A-Z]{1,6}\d[\w/-]{3,25}", re.IGNORECASE)

    for index, line in enumerate(lines):
        if not label_pattern.match(line):
            continue
        for candidate in lines[index + 1:index + 4]:
            match = candidate_pattern.search(candidate)
            if match:
                return normalize_invoice_number_candidate(match.group(0))

    match = re.search(
        r"(?:rectifica\s+a|factura\s+rectificada)[^\n]*?([A-Z]{1,6}\d[\w/-]{3,25})",
        text,
        re.IGNORECASE,
    )
    if match:
        return normalize_invoice_number_candidate(match.group(1))

    return ""
