"""Scan a document and discover ALL structured data: label-value pairs, tax IDs, amounts."""

from __future__ import annotations

import re

from app.models.fields import DiscoveredField, NumericCandidate, ScanResult, TaxIdHit
from app.utils.regex_lib import ANY_TAX_ID, AMOUNT_ANY, PERCENT
from app.utils.tax_id import clean_tax_id, is_valid_tax_id
from app.utils.text import normalize_text, parse_amount


# Label:Value separator — matches "Label: value", "Label value", "Label  value"
_LABEL_VALUE = re.compile(
    r"^([A-ZÁÉÍÓÚÑa-záéíóúñ][A-ZÁÉÍÓÚÑa-záéíóúñ\s.°º/]{2,40}?)\s*[:]\s*(.+)$"
)
# Standalone label on its own line, value on next line
_STANDALONE_LABEL = re.compile(
    r"^(FACTURA|FECHA|TOTAL|BASE(?:\s+IMPONIBLE)?|IVA|IGIC|SUBTOTAL|"
    r"CUOTA|RETENCI[ÓO]N|IRPF|PROVEEDOR|CLIENTE|EMISOR|DESTINATARIO|"
    r"N[°ºO.]\s*FACTURA|NUMERO\s+FACTURA|CIF|NIF|%\s*(?:IVA|IGIC)|IMPORTE|"
    r"DATOS\s+(?:DEL?\s+)?(?:PROVEEDOR|CLIENTE|EMISOR|DESTINATARIO))$",
    re.IGNORECASE,
)

# Common invoice/business terms — lines containing these aren't company names
_INVOICE_TERMS = re.compile(
    r"\b(?:factura|fecha|total|base|importe|p[aá]gina|datos|condiciones|"
    r"entrada|responsable|vencimiento|domiciliaci|transferencia|"
    r"forma\s+de\s+pago|concepto|observaciones|n[uú]mero|referencia|ref\b|"
    r"c[oó]d(?:igo)?\.?\s+de|art[ií]culo|descripci[oó]n|cantidad|precio|descuento|"
    r"plazo|cuenta|iban|pedido|albar[aá]n|portes|env[ií]o|recargo|"
    r"bonificaci[oó]n|retenci[oó]n|irpf|subtotal|cuota|"
    r"centro|vend(?:edor)?|documento|mesa|camarero|"
    r"consulta|borrador|no\s+valido|"
    r"CIF|NIF|DNI|C\.I\.F|N\.I\.F|partida|part\.\s*n|ficha)\b",
    re.IGNORECASE,
)


def scan(raw_text: str) -> ScanResult:
    """Scan the full document text and extract all discoverable structured data."""
    text = normalize_text(raw_text)
    lines = [line.strip() for line in text.split("\n") if line.strip()]
    result = ScanResult(lines=lines, raw_text=text)

    _discover_label_value_pairs(lines, result)
    _discover_tax_ids(lines, result)
    _discover_amounts(lines, result)

    return result


def _discover_label_value_pairs(lines: list[str], result: ScanResult) -> None:
    for i, line in enumerate(lines):
        # Inline "Label: Value" pattern
        m = _LABEL_VALUE.match(line)
        if m:
            label, value = m.group(1).strip(), m.group(2).strip()
            if len(label) > 2 and len(value) > 0:
                result.fields.append(DiscoveredField(
                    label=label, value=value, line_index=i, source="inline",
                ))
            continue

        # Standalone label on this line, value on next
        if _STANDALONE_LABEL.match(line) and i + 1 < len(lines):
            next_line = lines[i + 1].strip()
            if next_line and not _STANDALONE_LABEL.match(next_line):
                result.fields.append(DiscoveredField(
                    label=line.strip(), value=next_line, line_index=i, source="next_line",
                ))


def _discover_tax_ids(lines: list[str], result: ScanResult) -> None:
    seen: set[str] = set()
    for i, line in enumerate(lines):
        for m in ANY_TAX_ID.finditer(line):
            raw = clean_tax_id(m.group(0))
            if raw in seen or not is_valid_tax_id(raw):
                continue
            seen.add(raw)

            # Try to find a name near this tax ID
            name = _find_nearby_name(lines, i, raw)
            result.tax_ids.append(TaxIdHit(tax_id=raw, line_index=i, nearby_name=name))


def _find_nearby_name(lines: list[str], tax_id_line: int, tax_id: str) -> str:
    """Look in ±5 lines for a plausible company/person name near a tax ID.
    
    Prioritizes lines ABOVE the CIF (standard pattern: Name → Address → CIF).
    """
    candidates: list[tuple[int, str]] = []

    for offset in range(-5, 6):
        idx = tax_id_line + offset
        if idx < 0 or idx >= len(lines) or idx == tax_id_line:
            continue
        line = lines[idx].strip()
        cleaned = re.sub(r"\b" + re.escape(tax_id) + r"\b", "", line).strip()
        cleaned = re.sub(r"^(?:CIF|NIF|DNI|N\.?I\.?F\.?|C\.?I\.?F\.?)\s*:?\s*", "", cleaned, flags=re.IGNORECASE).strip()
        cleaned = re.sub(r"\s*(?:CIF|NIF|DNI)\s*:?\s*$", "", cleaned, flags=re.IGNORECASE).strip()
        # Strip residual markdown formatting
        cleaned = re.sub(r"^#{1,6}\s*", "", cleaned).strip()
        cleaned = re.sub(r"\*{1,3}(.+?)\*{1,3}", r"\1", cleaned).strip()
        # Clean parenthetical client codes like "(9747)"
        cleaned = re.sub(r"^\(\d+\)\s*", "", cleaned).strip()

        if not cleaned or len(cleaned) < 3:
            continue
        # Reject very long lines — likely legal disclaimers, not names
        if len(cleaned) > 80:
            continue
        # Skip lines that are purely numeric, addresses, emails, phones
        if re.match(r"^[\d\s\-+().]+$", cleaned):
            continue
        if re.match(r".*@.*\..*", cleaned):
            continue
        if re.match(r"^\d{5}\b", cleaned):  # postal code
            continue
        # Skip URLs
        if re.match(r"(?:www\.|https?://)", cleaned, re.IGNORECASE):
            continue
        # Skip street addresses (C/, CL/, AVDA, CALLE, etc.)
        if re.match(r"^(?:CL?/|AVDA\.?\s|CALLE\s|PZZA?\.?\s|PLAZA\s|PASEO\s|CTRA\.?\s|URB\.?\s)", cleaned, re.IGNORECASE):
            continue
        # Skip label:value lines (e.g. "Número: 14/2025", "Cód. de Cliente: 180")
        if re.match(r"^[^\d:][^:]{1,35}:\s+\S", cleaned):
            continue
        # Skip lines containing date patterns (DD/MM/YYYY)
        if re.search(r"\d{1,2}/\d{1,2}/\d{2,4}", cleaned):
            continue
        # Skip lines containing URLs anywhere
        if re.search(r"(?:www\.|https?://|\.com|\.es)", cleaned, re.IGNORECASE):
            continue
        # Skip lines that look like product descriptions (model numbers, specs)
        if re.search(r"\d+\s*(?:GB|MB|TB|GHZ|MHZ|W\d|/\d)", cleaned, re.IGNORECASE):
            continue
        # Skip lines containing common invoice/business terms (not company names)
        if _INVOICE_TERMS.search(cleaned):
            continue
        # Skip label-only lines (ending with ":" or common label words alone)
        if re.match(r"^.{2,30}:\s*$", cleaned):
            continue
        if _is_label_or_location(cleaned):
            continue

        # Priority: prefer lines ABOVE (name usually before CIF), then proximity
        priority = abs(offset)
        if offset < 0:
            priority -= 3  # strong bonus for lines above
        # Strong bonus for company suffixes (SL, SA, SLU, CB, SC)
        if re.search(r"\b(?:S\.?L\.?U?\.?|S\.?A\.?|C\.?B\.?|S\.?C\.?\s*(?:PROFESIONAL)?|SOCIEDAD)\b", cleaned, re.IGNORECASE):
            priority -= 10
        # Bonus for multi-word names (real names are usually 2+ words)
        if len(cleaned.split()) >= 2:
            priority -= 2
        candidates.append((priority, cleaned))

    if not candidates:
        return ""

    candidates.sort(key=lambda c: c[0])
    return candidates[0][1]


# Spanish provinces, islands, and common location words that aren't company names
_LOCATION_WORDS = re.compile(
    r"^(?:LAS\s+PALMAS(?:\s+DE\s+G(?:RAN)?\s*\.?\s*C(?:ANARIA)?\.?)?|TENERIFE|GRAN\s+CANARIA|"
    r"LANZAROTE|FUERTEVENTURA|LA\s+PALMA|LA\s+GOMERA|EL\s+HIERRO|"
    r"MADRID|BARCELONA|SEVILLA|VALENCIA|MALAGA|MURCIA|ALICANTE|"
    r"ZARAGOZA|BILBAO|VIGO|CADIZ|CORDOBA|GRANADA|TOLEDO|"
    r"SANTA\s+CRUZ(?:\s+DE\s+TENERIFE)?|CANARIAS|ISLAS\s+CANARIAS|"
    r"ESPA[ÑN]A|SPAIN)\s*$",
    re.IGNORECASE,
)
_LABEL_LINE = re.compile(
    r"^(?:Firma|Sello|Firma/Sello|Datos\s+de|Tel[éef]fono|Direcci[oó]n|"
    r"P[áa]gina|Importe|Total|Base|Factura|Fecha|Concepto|Observaciones|"
    r"Forma\s+de\s+pago|Cuenta|IBAN|Referencia|Pedido|Albar[áa]n|"
    r"Mail|Web|Correo|Email|Tlf|Fax|M[óo]vil|"
    r"Entrega\s+de\s+mercanc[íi]a|Condiciones|Portes|Env[íi]o|Dto|"
    r"Descuento|Bonificaci[óo]n|Recargo|Vencimiento|Plazo|"
    r"Unidades|Cantidad|Precio|Art[íi]culo|C[óo]digo)\s*:?\s*$",
    re.IGNORECASE,
)


def _is_label_or_location(text: str) -> bool:
    """Return True if the text is a province/city name or a standalone label — not a company name."""
    if _LOCATION_WORDS.match(text.strip()):
        return True
    if _LABEL_LINE.match(text.strip()):
        return True
    # Single word ≤15 chars with no company suffix → likely a location or label
    words = text.strip().split()
    if len(words) == 1 and len(text) <= 15 and not re.search(r"\b(?:S\.?L|S\.?A|C\.?B)\b", text, re.IGNORECASE):
        return True
    return False


def _discover_amounts(lines: list[str], result: ScanResult) -> None:
    for i, line in enumerate(lines):
        upper = line.upper()
        # Skip lines that look like metadata (CIF, phone, ref numbers)
        if re.search(r"\b(?:CIF|NIF|DNI|TEL|FAX|MOVIL|CORREO|EMAIL|REF|PEDIDO|ALBARAN)\b", upper):
            continue

        for m in AMOUNT_ANY.finditer(line):
            val = parse_amount(m.group(0))
            if val == 0:
                continue
            # Determine label context from the same line
            label = _extract_amount_label(line, m.start())
            result.amounts.append(NumericCandidate(value=val, label=label, line_index=i))

        for m in PERCENT.finditer(line):
            val = parse_amount(m.group(1))
            if 0 < abs(val) <= 100:
                label = _extract_amount_label(line, m.start())
                result.amounts.append(NumericCandidate(
                    value=val, label=f"percent:{label}" if label else "percent", line_index=i,
                ))


def _extract_amount_label(line: str, pos: int) -> str:
    """Extract the label context for a number found at position `pos` in a line."""
    prefix = line[:pos].strip()
    # Clean trailing colons, dots
    prefix = re.sub(r"[:\s.]+$", "", prefix).strip()
    if not prefix:
        return ""
    # Take last meaningful words (up to ~40 chars)
    words = prefix.split()
    result_words: list[str] = []
    total_len = 0
    for w in reversed(words):
        if total_len + len(w) > 40:
            break
        result_words.insert(0, w)
        total_len += len(w) + 1
    return " ".join(result_words)
