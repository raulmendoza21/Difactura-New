"""Extract structured invoice fields from raw text using regex patterns."""

import logging
import re

import dateparser

from app.models.invoice_model import InvoiceData, LineItem
from app.utils.regex_patterns import (
    BASE_IMPONIBLE,
    CIF_NIF,
    CLIENTE,
    DATE_NUMERIC,
    DATE_TEXT,
    INVOICE_NUMBER,
    IVA_AMOUNT,
    IVA_PERCENT,
    PROVEEDOR,
    TOTAL,
)
from app.utils.text_processing import normalize_text, parse_amount

logger = logging.getLogger(__name__)

MONTH_MAP = {
    "enero": "01",
    "febrero": "02",
    "marzo": "03",
    "abril": "04",
    "mayo": "05",
    "junio": "06",
    "julio": "07",
    "agosto": "08",
    "septiembre": "09",
    "octubre": "10",
    "noviembre": "11",
    "diciembre": "12",
}

_PROVEEDOR_LABELS = [
    re.compile(r"proveedor\s*:", re.IGNORECASE),
    re.compile(r"emisor\s*:", re.IGNORECASE),
    re.compile(r"raz[oó]n social\s*:", re.IGNORECASE),
]
_CLIENTE_LABELS = [
    re.compile(r"cliente\s*:", re.IGNORECASE),
    re.compile(r"destinatario\s*:", re.IGNORECASE),
    re.compile(r"comprador\s*:", re.IGNORECASE),
]


class FieldExtractor:
    """Extract invoice data fields from text using regex + heuristics."""

    def extract(self, text: str) -> InvoiceData:
        text = normalize_text(text)
        data = InvoiceData()

        data.numero_factura = self._extract_invoice_number(text)
        data.fecha = self._extract_date(text)

        cifs = self._extract_cifs(text)
        data.proveedor = self._extract_name(text, "proveedor")
        data.cliente = self._extract_name(text, "cliente")
        self._assign_cifs(data, cifs, text)

        data.base_imponible = self._extract_amount(text, BASE_IMPONIBLE)
        data.iva_porcentaje = self._extract_iva_percent(text)
        data.iva = self._extract_amount(text, IVA_AMOUNT)
        data.total = self._extract_amount(text, TOTAL)
        self._infer_amounts(data)

        data.lineas = self._extract_line_items(text)

        logger.info(
            "Extracted: invoice=%s, date=%s, total=%s",
            data.numero_factura,
            data.fecha,
            data.total,
        )
        return data

    def _extract_invoice_number(self, text: str) -> str:
        match = INVOICE_NUMBER.search(text)
        if match:
            return match.group(1).strip()

        line_patterns = [
            re.compile(
                r"^(?:factura|fra\.?|invoice|ref\.?)\s*[:#.]?\s*([A-Z]{0,6}[-/]?\d[\w/-]{1,20})$",
                re.IGNORECASE,
            ),
            re.compile(
                r"^(?:n[°ºo*.\s]*(?:de\s+)?factura|n[uú]mero\s+(?:de\s+)?factura)\s*[:#.]?\s*([A-Z]{0,6}[-/]?\d[\w/-]{1,20})$",
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
                    return line_match.group(1).strip()

        label_pat = re.compile(
            r"n[°ºo*.\s]*(?:de\s+)?factura|factura(?:\s*n[°ºo*.]?)?|invoice(?:\s*n[°ºo*.]?)?",
            re.IGNORECASE,
        )
        code_pat = re.compile(r"^[A-Z]{0,6}[-/]?\d[\w/-]{0,20}$", re.IGNORECASE)
        lines = text.split("\n")
        for i, line in enumerate(lines):
            if label_pat.search(line):
                for j in range(i + 1, len(lines)):
                    val = lines[j].strip()
                    if not val:
                        continue
                    if code_pat.match(val):
                        return val
                break

        generic_pat = re.compile(r"^[A-Z]{0,6}[-/]?\d[\w/-]{2,20}$", re.IGNORECASE)
        for line in lines:
            val = line.strip()
            if not generic_pat.match(val):
                continue
            if re.match(r"^\d{1,2}[/\-\.]\d{1,2}[/\-\.]\d{2,4}$", val):
                continue
            if re.match(r"^[\d.,]+$", val):
                continue
            return val

        return ""

    def _extract_date(self, text: str) -> str:
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

    def _extract_cifs(self, text: str) -> list[str]:
        results = []
        for match in CIF_NIF.finditer(text):
            cif = next(g for g in match.groups() if g is not None)
            cif_clean = re.sub(r"[\s\-]", "", cif).upper()
            if cif_clean not in results:
                results.append(cif_clean)
        return results

    def _extract_name(self, text: str, role: str) -> str:
        pattern = PROVEEDOR if role == "proveedor" else CLIENTE
        match = pattern.search(text)
        if match:
            name = match.group(1).strip().split("\t")[0].strip()
            return name[:200]
        return ""

    def _assign_cifs(self, data: InvoiceData, cifs: list[str], text: str) -> None:
        if not cifs:
            return
        if len(cifs) == 1:
            data.cif_proveedor = cifs[0]
            return

        def _last_match_pos(patterns: list[re.Pattern], value: str) -> int:
            pos = -1
            for pattern in patterns:
                for match in pattern.finditer(value):
                    if match.start() > pos:
                        pos = match.start()
            return pos

        for cif in cifs:
            cif_pos = text.upper().find(cif)
            if cif_pos < 0:
                continue
            context_before = text[max(0, cif_pos - 300):cif_pos]

            last_proveedor = _last_match_pos(_PROVEEDOR_LABELS, context_before)
            last_cliente = _last_match_pos(_CLIENTE_LABELS, context_before)

            if last_proveedor >= 0 and last_proveedor >= last_cliente:
                data.cif_proveedor = cif
            elif last_cliente >= 0 and last_cliente > last_proveedor:
                data.cif_cliente = cif

        if not data.cif_proveedor and len(cifs) >= 1:
            data.cif_proveedor = cifs[0]
        if not data.cif_cliente and len(cifs) >= 2:
            data.cif_cliente = cifs[1]

    def _extract_amount(self, text: str, pattern: re.Pattern) -> float:
        match = pattern.search(text)
        if match:
            return parse_amount(match.group(1))
        return 0.0

    def _extract_iva_percent(self, text: str) -> float:
        match = IVA_PERCENT.search(text)
        if match:
            try:
                raw = match.group(1).replace(",", ".")
                return float(raw)
            except ValueError:
                pass
        return 0.0

    def _infer_amounts(self, data: InvoiceData) -> None:
        if data.base_imponible > 0 and data.iva_porcentaje > 0 and data.iva == 0:
            data.iva = round(data.base_imponible * data.iva_porcentaje / 100, 2)
        if data.base_imponible > 0 and data.iva > 0 and data.total == 0:
            data.total = round(data.base_imponible + data.iva, 2)
        if data.total > 0 and data.iva_porcentaje > 0 and data.base_imponible == 0:
            data.base_imponible = round(data.total / (1 + data.iva_porcentaje / 100), 2)
            data.iva = round(data.total - data.base_imponible, 2)
        if data.total > 0 and data.base_imponible > 0 and data.iva == 0:
            data.iva = round(data.total - data.base_imponible, 2)

        if data.base_imponible > 0 and data.iva_porcentaje > 0:
            expected_iva = round(data.base_imponible * data.iva_porcentaje / 100, 2)
            if data.total > 0:
                if abs(data.base_imponible + expected_iva - data.total) < abs(
                    data.base_imponible + data.iva - data.total
                ):
                    data.iva = expected_iva
            elif data.iva == 0 or abs(data.iva - expected_iva) > 0.02:
                data.iva = expected_iva

    def _extract_line_items(self, text: str) -> list[LineItem]:
        lines = text.split("\n")
        items = []
        in_table = False

        header_pattern = re.compile(r"(?:descripci[oó]n|concepto|detalle|art[ií]culo)", re.IGNORECASE)
        footer_pattern = re.compile(
            r"(?:base\s+imponible|subtotal|total|iva|observaciones|notas|forma\s+de\s+pago)",
            re.IGNORECASE,
        )

        for line in lines:
            stripped = line.strip()
            if not stripped:
                continue
            if footer_pattern.search(stripped) and in_table:
                break
            if header_pattern.search(stripped) and not in_table:
                in_table = True
                continue
            if in_table:
                item = self._parse_line_item(stripped)
                if item:
                    items.append(item)
        return items

    def _parse_line_item(self, line: str) -> LineItem | None:
        amounts = re.findall(r"[\d.,]+", line)
        if len(amounts) < 1:
            return None

        desc_match = re.match(r"^(.+?)(?:\d)", line)
        description = desc_match.group(1).strip() if desc_match else line

        if not description or len(description) < 3:
            return None

        try:
            if len(amounts) >= 3:
                return LineItem(
                    descripcion=description,
                    cantidad=parse_amount(amounts[-3]),
                    precio_unitario=parse_amount(amounts[-2]),
                    importe=parse_amount(amounts[-1]),
                )
            return LineItem(
                descripcion=description,
                importe=parse_amount(amounts[-1]),
            )
        except (ValueError, IndexError):
            return None


field_extractor = FieldExtractor()
