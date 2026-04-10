"""Detect and parse tables from document text.

Handles Mistral OCR output where each column header and each cell value
appears on its own line (multi-line format), as well as traditional
single-line tabular formats.
"""

from __future__ import annotations

import re

from app.models.fields import TableRow
from app.utils.text import parse_amount

# ---------------------------------------------------------------------------
# Keyword patterns
# ---------------------------------------------------------------------------
_DESC_KW = re.compile(
    r"\b(?:CONCEPTO|DESCRIPCI[ÓO]N|DETALLE|ART[ÍI]CULO|SERVICIO)\b",
    re.IGNORECASE,
)
_AMT_KW = re.compile(
    r"\b(?:IMPORTE|PRECIO|TOTAL|NETO|CANTIDAD|CANT|UDS|UND|UNIDADES?|VALOR)\b",
    re.IGNORECASE,
)
_HEADER_KW = re.compile(
    r"\b(?:CONCEPTO|DESCRIPCI[ÓO]N|DETALLE|ART[ÍI]CULO|SERVICIO|REFERENCIA|"
    r"IMPORTE|PRECIO|TOTAL|NETO|CANTIDAD|CANT|UDS|UND|UNIDADES?|UNIT(?:ARIO)?|"
    r"SUBTOTAL|DTO|DESCUENTO|BASE|I[GV][AI]C|VALOR|COD\.?|REF\.?)\b",
    re.IGNORECASE,
)
_FOOTER = re.compile(
    r"\b(?:BASE\s+IMPONIBLE|SUBTOTAL|TOTAL\b|"
    r"IVA\b|I\.?G\.?I\.?C\.?\b|CUOTA|RETENCI|IRPF|"
    r"FORMA\s+(?:DE\s+)?PAGO|CONDICIONES|OBSERVACIONES|NOTA\b|"
    r"VENCIMIENTO|DESGLOSE\s+IMPUESTO|TRANSFERENCIA|IBAN|CUENTA|"
    r"GRACIAS\s+POR|SUMA\s+TOTAL)\b",
    re.IGNORECASE,
)
# A line that is just a number (possibly negative, with comma decimals)
_NUMBER_LINE = re.compile(r"^\s*[−–\-]?\d[\d.,]*\s*€?\s*$")
# Markdown table separator
_MD_SEP = re.compile(r"^[\-|:\s]+$")
# Ticket qty embedded in description: "2 NIGIRI SAKE" or "2 x LECHE"
_QTY_PREFIX = re.compile(r"^(\d+)\s+(?:[xX×]\s+)?(.+)$")

# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def scan_table(lines: list[str]) -> list[TableRow]:
    """Try to extract table rows from the document lines."""
    # Strategy 1: Multi-line column format (typical Mistral OCR)
    rows = _parse_multiline_table(lines)
    if rows:
        return rows

    # Strategy 2: Single-line "desc  amount" pairs
    rows = _parse_inline_pairs(lines)
    if rows:
        return rows

    return []


# ---------------------------------------------------------------------------
# Strategy 1 — Multi-line table (header cluster then grouped values)
# ---------------------------------------------------------------------------

def _looks_like_header(line: str) -> bool:
    s = line.strip()
    return 0 < len(s) < 30 and bool(_HEADER_KW.search(s))


def _find_header_cluster(lines: list[str]) -> int:
    """Return index of the first data line after a header cluster, or -1."""
    for i in range(len(lines)):
        if not _looks_like_header(lines[i]):
            continue
        has_desc = bool(_DESC_KW.search(lines[i]))
        has_amt = bool(_AMT_KW.search(lines[i]))
        j = i + 1
        while j < min(i + 12, len(lines)):
            lj = lines[j].strip()
            if not lj or _MD_SEP.match(lj):
                j += 1
                continue
            if _looks_like_header(lj):
                if _DESC_KW.search(lj):
                    has_desc = True
                if _AMT_KW.search(lj):
                    has_amt = True
                j += 1
                continue
            break
        if has_desc and has_amt:
            return j

    # Fallback: single-line header with both desc and amount keywords
    for i, line in enumerate(lines):
        if _DESC_KW.search(line) and _AMT_KW.search(line):
            return i + 1

    return -1


def _find_table_end(lines: list[str], start: int) -> int:
    for i in range(start, len(lines)):
        if _FOOTER.search(lines[i]):
            return i
    return len(lines)


def _is_number_line(line: str) -> bool:
    return bool(_NUMBER_LINE.match(line.strip()))


def _parse_number(line: str) -> float:
    s = line.strip().replace("\u2212", "-").replace("\u2013", "-").rstrip("€").strip()
    return parse_amount(s)


def _parse_multiline_table(lines: list[str]) -> list[TableRow]:
    """Parse table where each column value is on its own line."""
    start = _find_header_cluster(lines)
    if start < 0:
        return []
    end = _find_table_end(lines, start)

    # Classify lines in the zone
    zone: list[str] = []
    for line in lines[start:end]:
        stripped = line.strip()
        if stripped and not _MD_SEP.match(stripped):
            zone.append(stripped)
    if not zone:
        return []

    # Try column-major layout (all descriptions then all numbers)
    col_rows = _try_column_major(zone)
    if col_rows:
        return col_rows

    # Standard row-major: text + following numbers grouped per item
    return _group_row_major(zone)


def _try_column_major(zone: list[str]) -> list[TableRow] | None:
    """Detect column-major layout: N consecutive descriptions then N*k numbers."""
    # Build segments of consecutive text / number runs
    segments: list[tuple[str, list]] = []  # ('text', [...]) or ('nums', [...])
    i = 0
    while i < len(zone):
        if _is_number_line(zone[i]):
            nums = []
            while i < len(zone) and _is_number_line(zone[i]):
                nums.append(_parse_number(zone[i]))
                i += 1
            segments.append(("nums", nums))
        else:
            texts = []
            while i < len(zone) and not _is_number_line(zone[i]):
                texts.append(zone[i])
                i += 1
            segments.append(("text", texts))

    # Find pattern: text(N≥2) followed by nums(M) where M = N*k, k ≥ 2
    for si in range(len(segments)):
        if segments[si][0] != "text":
            continue
        descs = segments[si][1]
        if len(descs) < 2:
            continue
        if si + 1 >= len(segments) or segments[si + 1][0] != "nums":
            continue
        nums = segments[si + 1][1]
        n_items = len(descs)
        if len(nums) < n_items * 2 or len(nums) % n_items != 0:
            continue

        # Column-major: deinterleave numbers
        cols = len(nums) // n_items
        rows: list[TableRow] = []
        for j, desc in enumerate(descs):
            item_nums = [nums[j + k * n_items] for k in range(cols)]
            row = _build_row(desc, item_nums)
            if row:
                rows.append(row)
        if rows:
            return rows

    return None


def _group_row_major(zone: list[str]) -> list[TableRow]:
    """Group text + number lines sequentially into rows."""
    rows: list[TableRow] = []
    cur_desc: str | None = None
    cur_nums: list[float] = []

    for stripped in zone:
        if _is_number_line(stripped):
            cur_nums.append(_parse_number(stripped))
        else:
            if cur_desc is not None and cur_nums:
                row = _build_row(cur_desc, cur_nums)
                if row:
                    rows.append(row)
            cur_desc = stripped
            cur_nums = []

    if cur_desc is not None and cur_nums:
        row = _build_row(cur_desc, cur_nums)
        if row:
            rows.append(row)

    return rows


def _build_row(desc: str, nums: list[float]) -> TableRow | None:
    """Build a TableRow from a description and its number values."""
    if not nums:
        return None

    # Skip percentage-only descriptions (tax lines like "7%")
    if re.match(r"^\d+(?:[.,]\d+)?\s*%$", desc.strip()):
        return None
    # Skip descriptions that look like footer labels
    if _FOOTER.search(desc):
        return None
    # Skip descriptions that are just a header keyword (not real items)
    if len(desc) < 20 and _HEADER_KW.search(desc) and not re.search(r"\d", desc):
        return None

    # Check for qty embedded in description: "2 NIGIRI SAKE"
    qty_from_desc = None
    m = _QTY_PREFIX.match(desc)
    if m:
        qty_from_desc = float(m.group(1))
        desc = m.group(2).strip()

    row = TableRow(raw_text=desc, description=desc)

    if qty_from_desc is not None:
        row.quantity = qty_from_desc
        if len(nums) >= 2:
            row.unit_price = nums[0]
            row.amount = nums[-1]
        else:
            row.amount = nums[0]
            row.unit_price = round(nums[0] / qty_from_desc, 2) if qty_from_desc else nums[0]
    elif len(nums) >= 3:
        # [qty, unit_price, amount, ...extra tax cols ignored]
        row.quantity = nums[0]
        row.unit_price = nums[1]
        row.amount = nums[2]
    elif len(nums) == 2:
        if nums[0] == int(nums[0]) and nums[0] < 100 and nums[0] != nums[1]:
            row.quantity = nums[0]
            row.amount = nums[1]
            row.unit_price = round(nums[1] / nums[0], 2) if nums[0] else nums[1]
        else:
            row.quantity = 1
            row.unit_price = nums[0]
            row.amount = nums[1]
    else:
        row.amount = nums[0]
        row.quantity = 1
        row.unit_price = nums[0]

    return row


# ---------------------------------------------------------------------------
# Strategy 2 — Inline pairs: "Servicio mensual  100,00"
# ---------------------------------------------------------------------------

def _parse_inline_pairs(lines: list[str]) -> list[TableRow]:
    """Parse lines where description + amount appear on the same line."""
    start = _find_header_cluster(lines)
    if start < 0:
        start = _guess_items_start(lines)
    if start < 0:
        return []
    end = _find_table_end(lines, start)

    rows: list[TableRow] = []
    for line in lines[start:end]:
        m = re.match(r"^(.+?)\s{2,}(-?\d[\d.,]*)\s*€?\s*$", line.strip())
        if not m:
            continue
        desc = m.group(1).strip()
        amount = parse_amount(m.group(2))
        if desc and amount:
            rows.append(TableRow(
                description=desc, quantity=1, unit_price=amount,
                amount=amount, raw_text=line.strip(),
            ))
    return rows


def _guess_items_start(lines: list[str]) -> int:
    for i, line in enumerate(lines):
        if i < 3:
            continue
        stripped = line.strip()
        if re.search(r"\d[\d.,]+\s*€?\s*$", stripped) and len(stripped) > 15:
            if not _FOOTER.search(stripped):
                return i
    return -1
