from __future__ import annotations

import re

from app.utils.regex_patterns import INVOICE_NUMBER

from .shared import looks_like_invoice_number_candidate, normalize_invoice_number_candidate

TOKEN_AFTER_DOCUMENT = re.compile(
    r"\b([A-Z]{1,6}(?:[\s-]?\d){4,}[\w/-]*)\b(?:\s+\d{1,2}[/\-\.]\d{1,2}[/\-\.]\d{2,4}\b)?",
    re.IGNORECASE,
)


def extract_invoice_number(text: str, lines: list[str] | None = None) -> str:
    lines = lines or [line.strip() for line in text.split("\n") if line.strip()]

    labeled_invoice_number = extract_labeled_invoice_number(text, lines)
    if labeled_invoice_number:
        return labeled_invoice_number

    return _extract_generic_invoice_number(text, lines)


def extract_labeled_invoice_number(text: str, lines: list[str] | None = None) -> str:
    lines = lines or [line.strip() for line in text.split("\n") if line.strip()]

    numero_label = re.compile(r"^(?:n(?:u|ú)mero|n[°ºo])\s*:?\s*$", re.IGNORECASE)
    numero_inline_label = re.compile(
        r"^(?:n(?:u|ú)mero(?:\s+de\s+factura)?|n[°ºo]\s*(?:de\s*)?factura?)\s*[:#.]?\s*([A-Z0-9][A-Z0-9 /.-]{2,30})$",
        re.IGNORECASE,
    )
    for index, line in enumerate(lines):
        inline_match = numero_inline_label.match(line.strip())
        if inline_match:
            extracted = normalize_invoice_number_candidate(inline_match.group(1))
            if looks_like_invoice_number_candidate(extracted):
                return extracted
        if not numero_label.match(line):
            continue
        for candidate in lines[index + 1:index + 4]:
            if "IBAN" in candidate.upper():
                continue
            extracted = normalize_invoice_number_candidate(candidate)
            if looks_like_invoice_number_candidate(extracted):
                return extracted

    document_label = re.compile(
        r"^(?:documento|doc\.?|n[°ºo]\s*(?:de\s*)?factura|factura\s*n(?:u|ú)m|factura\s*#?)$",
        re.IGNORECASE,
    )
    for index, line in enumerate(lines):
        if not document_label.match(line):
            continue
        for candidate in lines[index + 1:index + 4]:
            if "IBAN" in candidate.upper():
                continue
            match = TOKEN_AFTER_DOCUMENT.search(candidate)
            if match:
                extracted = normalize_invoice_number_candidate(match.group(1))
                if looks_like_invoice_number_candidate(extracted):
                    return extracted

    return ""


def extract_ticket_invoice_number(lines: list[str]) -> str:
    ticket_same_line = re.compile(
        r"\b((?:[A-Z]\d{3,}|[A-Z0-9]{1,6}[/-]\d{3,}[\w/-]*|\d{4}/\d{4,}-\d{4,}))\b(?:\s*FECHA(?:\b|\d{1,2}[/\-\.]\d{1,2}[/\-\.]\d{2,4})|\s+\d{1,2}[/\-\.]\d{1,2}[/\-\.]\d{2,4}\b)",
        re.IGNORECASE,
    )
    ticket_standalone = re.compile(
        r"^(?:[A-Z0-9]{1,6}[/-]\d{3,}[\w/-]*|\d{4}/\d{4,}-\d{4,})$",
        re.IGNORECASE,
    )
    for line in lines:
        if "IBAN" in line.upper():
            continue
        match = ticket_same_line.search(line)
        if not match:
            candidate = normalize_invoice_number_candidate(line)
            if ticket_standalone.match(candidate) and looks_like_invoice_number_candidate(candidate):
                return candidate
            continue
        extracted = normalize_invoice_number_candidate(match.group(1))
        if looks_like_invoice_number_candidate(extracted):
            return extracted
    return ""


def _extract_generic_invoice_number(text: str, lines: list[str]) -> str:
    for line in lines:
        if "IBAN" in line.upper():
            continue
        match = TOKEN_AFTER_DOCUMENT.search(line)
        if match:
            extracted = normalize_invoice_number_candidate(match.group(1))
            if looks_like_invoice_number_candidate(extracted):
                return extracted

    match = INVOICE_NUMBER.search(text)
    if match:
        extracted = normalize_invoice_number_candidate(match.group(1))
        if looks_like_invoice_number_candidate(extracted):
            return extracted

    line_patterns = [
        re.compile(
            r"^(?:factura|fra\.?|invoice|ref\.?)\s*[:#.]?\s*([A-Z]{0,6}(?:[\s/-]?\d){2,}[\w/-]{0,20})$",
            re.IGNORECASE,
        ),
        re.compile(
            r"^(?:n[°ºo*.\s]*(?:de\s+)?factura|n(?:u|ú)mero\s+(?:de\s+)?factura)\s*[:#.]?\s*([A-Z]{0,6}[-/]?\d[\w/-]{1,20})$",
            re.IGNORECASE,
        ),
    ]
    for line in text.split("\n"):
        candidate = line.strip()
        if not candidate:
            continue
        for pattern in line_patterns:
            line_match = pattern.search(candidate)
            if line_match:
                extracted = normalize_invoice_number_candidate(line_match.group(1))
                if looks_like_invoice_number_candidate(extracted):
                    return extracted

    label_pat = re.compile(
        r"n[°ºo*.\s]*(?:de\s+)?factura|factura(?:\s*n[°ºo*.]?)?|invoice(?:\s*n[°ºo*.]?)?",
        re.IGNORECASE,
    )
    code_pat = re.compile(r"^[A-Z]{0,6}(?:[\s/-]?\d){2,}[\w/-]{0,20}$", re.IGNORECASE)
    for index, line in enumerate(lines):
        if not label_pat.search(line):
            continue
        for candidate in lines[index + 1:]:
            value = candidate.strip()
            if not value:
                continue
            extracted = normalize_invoice_number_candidate(value)
            if code_pat.match(extracted) and looks_like_invoice_number_candidate(extracted):
                return extracted
        break

    generic_pat = re.compile(r"^[A-Z]{0,6}(?:[\s/-]?\d){2,}[\w/-]{0,20}$", re.IGNORECASE)
    for line in lines:
        value = normalize_invoice_number_candidate(line.strip())
        if not generic_pat.match(value):
            continue
        if re.match(r"^\d{1,2}[/\-\.]\d{1,2}[/\-\.]\d{2,4}$", value):
            continue
        if re.match(r"^[\d.,]+$", value):
            continue
        if looks_like_invoice_number_candidate(value):
            return value

    return ""
