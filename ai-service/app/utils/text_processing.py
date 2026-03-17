"""Text cleaning and normalization utilities."""

import re
import unicodedata


def normalize_text(text: str) -> str:
    """Normalize unicode, collapse whitespace, strip.

    Uses NFKC to normalize compatibility characters (e.g. ligatures)
    while keeping accented characters composed (e.g. 'ú' stays as one
    codepoint instead of being decomposed into 'u' + combining accent).
    NFKD was breaking all regex patterns that match accented Spanish words.
    """
    text = unicodedata.normalize("NFKC", text)
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def parse_amount(raw: str) -> float:
    """Parse a money string to float.

    Handles European format (1.234,56) and US format (1,234.56).
    """
    if not raw:
        return 0.0

    raw = raw.strip().replace(" ", "")

    # European format: dots as thousands separator, comma as decimal
    if "," in raw and "." in raw:
        if raw.rindex(",") > raw.rindex("."):
            # European: 1.234,56
            raw = raw.replace(".", "").replace(",", ".")
        else:
            # US: 1,234.56
            raw = raw.replace(",", "")
    elif "," in raw:
        # Could be European decimal or US thousands
        parts = raw.split(",")
        if len(parts[-1]) == 2:
            # Likely decimal: 1234,56
            raw = raw.replace(",", ".")
        else:
            # Likely thousands: 1,234
            raw = raw.replace(",", "")

    try:
        return round(float(raw), 2)
    except ValueError:
        return 0.0


def extract_lines_between(text: str, start_kw: str, end_kw: str) -> list[str]:
    """Extract text lines between two keyword markers."""
    lines = text.split("\n")
    capturing = False
    result = []

    start_pattern = re.compile(start_kw, re.IGNORECASE)
    end_pattern = re.compile(end_kw, re.IGNORECASE)

    for line in lines:
        if end_pattern.search(line) and capturing:
            break
        if capturing and line.strip():
            result.append(line.strip())
        if start_pattern.search(line):
            capturing = True

    return result
