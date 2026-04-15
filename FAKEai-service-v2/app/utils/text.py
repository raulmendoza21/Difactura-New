"""Text cleaning and amount parsing — compact, proven logic from v1."""

import re
import unicodedata


def normalize_text(text: str) -> str:
    text = unicodedata.normalize("NFKC", text or "")
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def normalize_keyword(text: str) -> str:
    d = unicodedata.normalize("NFKD", normalize_text(text))
    stripped = "".join(c for c in d if not unicodedata.combining(c))
    return re.sub(r"\s+", " ", re.sub(r"[^A-Z0-9]+", " ", stripped.upper())).strip()


def parse_amount(raw: str) -> float:
    if not raw:
        return 0.0
    raw = raw.strip().replace("\u00a0", "").replace(" ", "")
    raw = raw.replace("€", "").replace("$", "").replace("EUR", "")
    raw = raw.replace("−", "-").replace("–", "-").replace("—", "-")

    if "," in raw and "." in raw:
        if raw.rindex(",") > raw.rindex("."):
            raw = raw.replace(".", "").replace(",", ".")
        else:
            raw = raw.replace(",", "")
    elif "," in raw:
        parts = raw.split(",")
        if len(parts[-1]) == 2:
            raw = raw.replace(",", ".")
        else:
            raw = raw.replace(",", "")
    try:
        return round(float(raw), 2)
    except ValueError:
        return 0.0
