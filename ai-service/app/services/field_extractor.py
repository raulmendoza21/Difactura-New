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
_PROVEEDOR_HEADER = re.compile(
    r"^(?:proveedor|emisor|raz[oÃ³]n\s+social|datos\s+del\s+emisor)\s*:?\s*$",
    re.IGNORECASE,
)
_CLIENTE_HEADER = re.compile(
    r"^(?:cliente|destinatario|comprador|facturar\s+a|datos\s+del\s+cliente)\s*:?\s*$",
    re.IGNORECASE,
)
_STOP_PARTY_LINE = re.compile(
    r"^(?:c/?|calle|avda\.?|avenida|cp\b|c[oÃ³]digo\s+postal|fecha|factura|forma\s+de\s+pago|email|tel[eÃ©]fono|observaciones)\b",
    re.IGNORECASE,
)


_SHIPPING_HEADER = re.compile(r"^datos\s+de\s+env[iÃÍ]o:?$", re.IGNORECASE)
_BILLING_HEADER = re.compile(r"^datos\s+de\s+facturaci[oÃÓ]n:?$", re.IGNORECASE)

_DOCUMENT_HEADER_LINE = re.compile(
    r"^(?:factura|invoice|documento|fecha|importe|concepto|base|%igic|%iva|cuota|subtotal|total)$",
    re.IGNORECASE,
)
_GENERIC_HEADER_NOISE = {
    "VENCIMIENTOS",
    "ENTIDADES",
    "TRANSPORTE",
    "TRACKING",
    "FACTURA NUM",
    "FACTURA NÚM",
    "FACTURA NUM.",
}


class FieldExtractor:
    """Extract invoice data fields from text using regex + heuristics."""

    def extract(self, text: str) -> InvoiceData:
        text = normalize_text(text)
        lines = [line.strip() for line in text.split("\n") if line.strip()]
        data = InvoiceData()

        data.numero_factura = self._extract_ticket_invoice_number(lines) or self._extract_invoice_number(text, lines)
        data.rectified_invoice_number = self._extract_rectified_invoice_number(text, lines)
        data.fecha = self._extract_date(text, lines)

        cifs = self._extract_cifs(text)
        parties = self._extract_parties(text)
        shipping_customer_name, shipping_customer_tax_id = self._extract_customer_from_shipping_billing(lines)
        data.proveedor = parties["proveedor"] or self._extract_name(text, "proveedor")
        data.cliente = shipping_customer_name or parties["cliente"] or self._extract_name(text, "cliente")
        data.cif_proveedor = parties["cif_proveedor"]
        data.cif_cliente = shipping_customer_tax_id or parties["cif_cliente"]
        self._apply_company_line_fallback(data, lines)
        self._promote_registry_supplier(data, text)
        self._assign_cifs(data, cifs, text)
        self._promote_registry_tax_id(data, text, cifs)
        self._fill_missing_counterparty_from_header(data, lines)
        self._normalize_ticket_parties(data, text, lines)

        data.base_imponible = self._extract_base_amount(text, lines)
        data.iva_porcentaje = self._extract_iva_percent(text, lines)
        data.iva = self._extract_iva_amount(text, lines)
        data.retencion_porcentaje = self._extract_withholding_percent(text, lines)
        data.retencion = self._extract_withholding_amount(text, lines)
        data.total = self._extract_total_amount(text, lines)
        self._infer_amounts(data)

        data.lineas = self._extract_line_items(text)

        logger.info(
            "Extracted: invoice=%s, date=%s, total=%s",
            data.numero_factura,
            data.fecha,
            data.total,
        )
        return data

    def _extract_invoice_number(self, text: str, lines: list[str] | None = None) -> str:
        lines = lines or [line.strip() for line in text.split("\n") if line.strip()]

        numero_label = re.compile(r"^(?:n[uú]mero|n[°ºo])\s*:?\s*$", re.IGNORECASE)
        for index, line in enumerate(lines):
            if not numero_label.match(line):
                continue
            for candidate in lines[index + 1:index + 4]:
                if "IBAN" in candidate.upper():
                    continue
                extracted = self._normalize_invoice_number_candidate(candidate)
                if self._looks_like_invoice_number_candidate(extracted):
                    return extracted

        token_after_document = re.compile(
            r"\b([A-Z]{1,6}(?:[\s-]?\d){4,}[\w/-]*)\b(?:\s+\d{1,2}[/\-\.]\d{1,2}[/\-\.]\d{2,4}\b)?",
            re.IGNORECASE,
        )
        document_label = re.compile(
            r"^(?:documento|doc\.?|n[°ºo]\s*(?:de\s*)?factura|factura\s*n[uú]m|factura\s*#?)$",
            re.IGNORECASE,
        )

        for index, line in enumerate(lines):
            if not document_label.match(line):
                continue
            for candidate in lines[index + 1:index + 4]:
                if "IBAN" in candidate.upper():
                    continue
                match = token_after_document.search(candidate)
                if match:
                    extracted = self._normalize_invoice_number_candidate(match.group(1))
                    if self._looks_like_invoice_number_candidate(extracted):
                        return extracted

        for line in lines:
            if "IBAN" in line.upper():
                continue
            match = token_after_document.search(line)
            if match:
                extracted = self._normalize_invoice_number_candidate(match.group(1))
                if self._looks_like_invoice_number_candidate(extracted):
                    return extracted

        match = INVOICE_NUMBER.search(text)
        if match:
            extracted = self._normalize_invoice_number_candidate(match.group(1))
            if self._looks_like_invoice_number_candidate(extracted):
                return extracted

        line_patterns = [
            re.compile(
                r"^(?:factura|fra\.?|invoice|ref\.?)\s*[:#.]?\s*([A-Z]{0,6}(?:[\s/-]?\d){2,}[\w/-]{0,20})$",
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
                    extracted = self._normalize_invoice_number_candidate(line_match.group(1))
                    if self._looks_like_invoice_number_candidate(extracted):
                        return extracted

        label_pat = re.compile(
            r"n[°ºo*.\s]*(?:de\s+)?factura|factura(?:\s*n[°ºo*.]?)?|invoice(?:\s*n[°ºo*.]?)?",
            re.IGNORECASE,
        )
        code_pat = re.compile(r"^[A-Z]{0,6}(?:[\s/-]?\d){2,}[\w/-]{0,20}$", re.IGNORECASE)
        for i, line in enumerate(lines):
            if label_pat.search(line):
                for j in range(i + 1, len(lines)):
                    val = lines[j].strip()
                    if not val:
                        continue
                    extracted = self._normalize_invoice_number_candidate(val)
                    if code_pat.match(extracted) and self._looks_like_invoice_number_candidate(extracted):
                        return extracted
                break

        generic_pat = re.compile(r"^[A-Z]{0,6}(?:[\s/-]?\d){2,}[\w/-]{0,20}$", re.IGNORECASE)
        for line in lines:
            val = self._normalize_invoice_number_candidate(line.strip())
            if not generic_pat.match(val):
                continue
            if re.match(r"^\d{1,2}[/\-\.]\d{1,2}[/\-\.]\d{2,4}$", val):
                continue
            if re.match(r"^[\d.,]+$", val):
                continue
            if self._looks_like_invoice_number_candidate(val):
                return val

        return ""

    def _normalize_invoice_number_candidate(self, value: str) -> str:
        cleaned = re.sub(r"\s+", " ", (value or "").strip())
        cleaned = re.sub(r"\s*([/-])\s*", r"\1", cleaned)
        cleaned = re.sub(r"\s+\d{1,2}[-/.]\d{1,2}[-/.]\d{2,4}$", "", cleaned)
        return cleaned.strip(" .,:;")

    def _looks_like_invoice_number_candidate(self, value: str) -> bool:
        cleaned = self._normalize_invoice_number_candidate(value).upper()
        if not cleaned or len(cleaned) < 4:
            return False
        if self._looks_like_tax_id_candidate(cleaned):
            return False
        if re.fullmatch(r"\d{1,3}", cleaned):
            return False
        if re.fullmatch(r"[A-Z0-9]{20,}", cleaned) and "-" not in cleaned and "/" not in cleaned and " " not in cleaned:
            return False
        if re.fullmatch(r"[A-Z0-9]{10,}", cleaned) and re.search(r"\d", cleaned) and not re.search(r"[/-]|\s", cleaned):
            letter_runs = re.findall(r"[A-Z]+", cleaned)
            digit_runs = re.findall(r"\d+", cleaned)
            if len(letter_runs) >= 2 and len(digit_runs) >= 2:
                return False
        return bool(
            re.fullmatch(r"[A-Z]{0,6}(?:[\s/-]?\d){2,}[A-Z0-9/-]*", cleaned)
            or re.fullmatch(r"[A-Z]{1,6}\d[\w/-]{3,18}", cleaned)
        )

    def _extract_date(self, text: str, lines: list[str] | None = None) -> str:
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

    def _extract_rectified_invoice_number(self, text: str, lines: list[str] | None = None) -> str:
        lines = lines or [line.strip() for line in text.split("\n") if line.strip()]
        label_pattern = re.compile(r"^(?:rectifica\s+a|factura\s+rectificada)\s*:?\s*$", re.IGNORECASE)
        candidate_pattern = re.compile(r"[A-Z]{1,6}\d[\w/-]{3,25}", re.IGNORECASE)

        for index, line in enumerate(lines):
            if not label_pattern.match(line):
                continue
            for candidate in lines[index + 1:index + 4]:
                match = candidate_pattern.search(candidate)
                if match:
                    return self._normalize_invoice_number_candidate(match.group(0))

        match = re.search(
            r"(?:rectifica\s+a|factura\s+rectificada)[^\n]*?([A-Z]{1,6}\d[\w/-]{3,25})",
            text,
            re.IGNORECASE,
        )
        if match:
            return self._normalize_invoice_number_candidate(match.group(1))

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
            if self._looks_like_party_name(name):
                return name[:200]
        return ""

    def _extract_parties(self, text: str) -> dict[str, str]:
        lines = [line.strip() for line in text.split("\n") if line.strip()]
        result = {
            "proveedor": "",
            "cliente": "",
            "cif_proveedor": "",
            "cif_cliente": "",
        }

        parallel = self._extract_parallel_party_sections(lines)
        result.update({key: value for key, value in parallel.items() if value})

        if not result["proveedor"]:
            result["proveedor"], result["cif_proveedor"] = self._extract_party_section(lines, role="proveedor")
        if not result["cliente"]:
            result["cliente"], result["cif_cliente"] = self._extract_party_section(lines, role="cliente")

        return result

    def _extract_customer_from_shipping_billing(self, lines: list[str]) -> tuple[str, str]:
        normalized_lines = [self._normalize_label_line(line) for line in lines]
        header_indexes = {
            "shipping": next((index for index, line in enumerate(normalized_lines) if line.startswith("datos de env")), -1),
            "billing": next((index for index, line in enumerate(normalized_lines) if line.startswith("datos de facturaci")), -1),
        }

        if header_indexes["shipping"] < 0 and header_indexes["billing"] < 0:
            return "", ""

        section_candidates: list[tuple[str, str]] = []
        for key, start in header_indexes.items():
            if start < 0:
                continue

            other_starts = [value for other_key, value in header_indexes.items() if other_key != key and value > start]
            stop_index = min(other_starts) if other_starts else min(len(lines), start + 24)
            section_lines = lines[start + 1:stop_index]

            name = ""
            tax_id = ""
            for index, line in enumerate(section_lines):
                if not name and (self._looks_like_company_name(line) or self._looks_like_party_name(line)):
                    name = line[:200]
                if not tax_id:
                    tax_ids = self._extract_line_tax_ids(line)
                    if tax_ids:
                        tax_id = tax_ids[0]
                    elif self._normalize_label_line(line) == "cif":
                        for candidate in section_lines[index + 1:index + 4]:
                            candidate_tax_ids = self._extract_line_tax_ids(candidate)
                            if candidate_tax_ids:
                                tax_id = candidate_tax_ids[0]
                                break
                if name and tax_id:
                    break

            if name or tax_id:
                section_candidates.append((name, tax_id))

        if not section_candidates:
            return "", ""

        for name, tax_id in section_candidates:
            if name and tax_id:
                return name, tax_id
        return section_candidates[0]

    def _promote_registry_supplier(self, data: InvoiceData, text: str) -> None:
        match = re.search(
            r"([A-ZÁÉÍÓÚÜÑ][^\n]{3,120}?)\s*-\s*REGISTRO\s+MERCANTIL[^\n]*?\bCIF\b\s*([A-Z0-9.\- ]{8,20})",
            text,
            re.IGNORECASE,
        )
        if not match:
            return

        supplier_name = re.sub(r"\s+", " ", match.group(1)).strip(" .,:;-")
        tax_ids = self._extract_line_tax_ids(match.group(0))
        supplier_tax_id = tax_ids[0] if tax_ids else re.sub(r"[\s.\-]", "", match.group(2).upper())

        if not supplier_name and not supplier_tax_id:
            return

        if not data.proveedor or self._normalize_party_value(data.proveedor) == self._normalize_party_value(data.cliente):
            data.proveedor = supplier_name or data.proveedor
            if supplier_tax_id:
                data.cif_proveedor = supplier_tax_id
            return

        if data.cif_cliente and supplier_tax_id and data.cif_cliente == supplier_tax_id:
            data.cif_cliente = ""

        if supplier_tax_id and data.cif_proveedor and data.cif_proveedor != supplier_tax_id and data.cif_cliente == data.cif_proveedor:
            data.cif_cliente = data.cif_proveedor
            data.proveedor = supplier_name or data.proveedor
            data.cif_proveedor = supplier_tax_id

    def _apply_company_line_fallback(self, data: InvoiceData, lines: list[str]) -> None:
        if data.proveedor and data.cliente:
            return

        company_candidates: list[str] = []
        for line in lines[:20]:
            if not self._looks_like_company_name(line):
                continue
            if line not in company_candidates:
                company_candidates.append(line[:200])

        if not data.proveedor and company_candidates:
            data.proveedor = company_candidates[0]
        if not data.cliente and len(company_candidates) > 1:
            data.cliente = company_candidates[1]

    def _extract_parallel_party_sections(self, lines: list[str]) -> dict[str, str]:
        result = {
            "proveedor": "",
            "cliente": "",
            "cif_proveedor": "",
            "cif_cliente": "",
        }

        for index in range(len(lines) - 1):
            current_line = lines[index]
            next_line = lines[index + 1]
            if not _PROVEEDOR_HEADER.match(current_line) or not _CLIENTE_HEADER.match(next_line):
                continue

            candidates: list[str] = []
            cifs: list[str] = []
            for candidate in lines[index + 2:index + 12]:
                if _PROVEEDOR_HEADER.match(candidate) or _CLIENTE_HEADER.match(candidate):
                    break
                for value in self._extract_line_tax_ids(candidate):
                    if value not in cifs:
                        cifs.append(value)
                if self._looks_like_party_name(candidate):
                    candidates.append(candidate[:200])

            if len(candidates) >= 2:
                result["proveedor"] = candidates[0]
                result["cliente"] = candidates[1]
            if len(cifs) >= 1:
                result["cif_proveedor"] = cifs[0]
            if len(cifs) >= 2:
                result["cif_cliente"] = cifs[1]
            if result["proveedor"] or result["cliente"]:
                return result

        return result

    def _extract_party_section(self, lines: list[str], role: str) -> tuple[str, str]:
        header_pattern = _PROVEEDOR_HEADER if role == "proveedor" else _CLIENTE_HEADER
        other_header_pattern = _CLIENTE_HEADER if role == "proveedor" else _PROVEEDOR_HEADER

        for index, line in enumerate(lines):
            if not header_pattern.match(line):
                continue

            name = ""
            tax_id = ""
            for candidate in lines[index + 1:index + 7]:
                if other_header_pattern.match(candidate) or header_pattern.match(candidate):
                    break
                if not tax_id:
                    line_tax_ids = self._extract_line_tax_ids(candidate)
                    if line_tax_ids:
                        tax_id = line_tax_ids[0]
                if not name and self._looks_like_party_name(candidate):
                    name = candidate[:200]
                if name and tax_id:
                    break

            if name or tax_id:
                return name, tax_id

        return "", ""

    def _extract_line_tax_ids(self, line: str) -> list[str]:
        values = []
        candidates = [line, re.sub(r"\.", "", line or "")]
        for candidate in candidates:
            for match in CIF_NIF.finditer(candidate):
                cif = next(group for group in match.groups() if group is not None)
                cleaned = re.sub(r"[\s\-.]", "", cif).upper()
                if cleaned not in values:
                    values.append(cleaned)
        return values

    def _looks_like_party_name(self, value: str) -> bool:
        cleaned = value.strip()
        if not cleaned or len(cleaned) < 4:
            return False
        if _PROVEEDOR_HEADER.match(cleaned) or _CLIENTE_HEADER.match(cleaned):
            return False
        if _STOP_PARTY_LINE.match(cleaned):
            return False
        if self._extract_line_tax_ids(cleaned):
            return False

        letters = sum(char.isalpha() for char in cleaned)
        digits = sum(char.isdigit() for char in cleaned)
        if letters < 3 or digits > max(2, letters // 2):
            return False

        upper_cleaned = cleaned.upper()
        blocked_tokens = {"FACTURA", "TOTAL", "BASE", "IVA", "IGIC", "TRANSFERENCIA"}
        if upper_cleaned in blocked_tokens:
            return False
        return True

    def _looks_like_company_name(self, value: str) -> bool:
        if not self._looks_like_party_name(value):
            return False

        upper_value = value.upper()
        if self._looks_like_address_or_contact_line(upper_value):
            return False

        return bool(
            re.search(
                r"(?:\bSL\b|S\.L\.|(?:\bSA\b)|S\.A\.|(?:\bSLU\b)|S\.L\.U\.|S\.C\.PROFESIONAL|S\.C\.|SCPROFESIONAL)",
                upper_value,
            )
        )

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

    def _promote_registry_tax_id(self, data: InvoiceData, text: str, cifs: list[str]) -> None:
        match = re.search(
            r"registrad[oa][^\n]{0,160}?\bcif\b[^\n]{0,20}",
            text,
            re.IGNORECASE,
        )
        if not match:
            return

        match_tax_ids = self._extract_line_tax_ids(match.group(0))
        registry_cif = match_tax_ids[0] if match_tax_ids else ""
        if registry_cif:
            data.cif_proveedor = registry_cif
            if not data.cif_cliente or data.cif_cliente == registry_cif:
                for cif in cifs:
                    if cif != registry_cif:
                        data.cif_cliente = cif
                        break

    def _fill_missing_counterparty_from_header(self, data: InvoiceData, lines: list[str]) -> None:
        if data.cliente and data.cif_cliente:
            return

        header_end = next(
            (index for index, line in enumerate(lines) if _DOCUMENT_HEADER_LINE.match(line.strip())),
            min(len(lines), 18),
        )
        header_lines = lines[:header_end]
        provider_index = -1
        provider_norm = self._normalize_party_value(data.proveedor)
        if provider_norm:
            for index, line in enumerate(header_lines):
                if provider_norm and provider_norm in self._normalize_party_value(line):
                    provider_index = index
                    break

        candidates: list[tuple[str, str]] = []

        for index, line in enumerate(header_lines):
            if provider_index >= 0 and index <= provider_index:
                continue

            candidate_name = self._clean_header_party_candidate(line)
            if not candidate_name:
                continue

            if self._normalize_party_value(candidate_name) == self._normalize_party_value(data.proveedor):
                continue

            nearby_tax_id = ""
            for candidate_line in header_lines[index + 1:index + 13]:
                tax_ids = self._extract_line_tax_ids(candidate_line)
                if tax_ids:
                    nearby_tax_id = tax_ids[0]
                    break

            has_context = any(
                re.search(r"\b(?:c/|calle|avda|avenida|urb\.?|pol\.?|cp\b|\d{5})", candidate_line, re.IGNORECASE)
                for candidate_line in header_lines[index + 1:index + 13]
            )

            if nearby_tax_id or has_context:
                candidates.append((candidate_name, nearby_tax_id))

        if not candidates:
            return

        best_name, best_tax_id = candidates[0]
        if not data.cliente:
            data.cliente = best_name
        if not data.cif_cliente and best_tax_id:
            if best_tax_id != data.cif_proveedor:
                data.cif_cliente = best_tax_id
            elif self._looks_like_company_name(data.proveedor) and not self._looks_like_company_name(best_name):
                data.cif_cliente = best_tax_id
                data.cif_proveedor = ""

    def _clean_header_party_candidate(self, line: str) -> str:
        cleaned = re.sub(r"^\(\d+\)\s*", "", line.strip())
        cleaned = re.sub(r"\s+", " ", cleaned).strip(" .,:;-")
        if not cleaned:
            return ""
        if cleaned.upper() in _GENERIC_HEADER_NOISE:
            return ""
        if _DOCUMENT_HEADER_LINE.match(cleaned) or _STOP_PARTY_LINE.match(cleaned):
            return ""
        if self._extract_line_tax_ids(cleaned):
            return ""
        if any(token in cleaned.upper() for token in ("MAIL:", "WEB:", "HTTP", "TLF", "TEL", "WWW.")):
            return ""
        if not self._looks_like_party_name(cleaned):
            return ""
        if len(cleaned.split()) < 2 and not self._looks_like_company_name(cleaned):
            return ""
        return cleaned[:200]

    def _normalize_party_value(self, value: str) -> str:
        return re.sub(r"[^A-Z0-9]", "", (value or "").upper())

    def _extract_amount(self, text: str, pattern: re.Pattern, *, prefer_last: bool = False) -> float:
        if prefer_last:
            matches = list(pattern.finditer(text))
            match = matches[-1] if matches else None
        else:
            match = pattern.search(text)
        if match:
            return parse_amount(match.group(1))
        return 0.0

    def _extract_base_amount(self, text: str, lines: list[str]) -> float:
        footer_summary = self._extract_footer_tax_summary(lines)
        if footer_summary["base"] > 0:
            return footer_summary["base"]
        footer_value = self._extract_amount_from_label_lines(
            lines,
            labels=("subtotal", "base"),
            window=8,
            require_full_label=True,
        )
        if footer_value > 0:
            return footer_value
        label_value = self._extract_amount_from_label_lines(
            lines,
            labels=("base imponible", "subtotal", "importe neto", "neto"),
            window=4,
        )
        if label_value > 0:
            return label_value
        return self._extract_amount(text, BASE_IMPONIBLE)

    def _extract_total_amount(self, text: str, lines: list[str]) -> float:
        footer_summary = self._extract_footer_tax_summary(lines)
        if footer_summary["total"] > 0:
            return footer_summary["total"]
        ticket_total = self._extract_amount_from_label_lines(
            lines,
            labels=("total compra", "total ticket", "total pagado"),
            window=3,
            require_full_label=False,
        )
        if ticket_total > 0:
            return ticket_total
        footer_value = self._extract_amount_around_exact_label(
            lines,
            label="total",
            window=4,
        )
        if footer_value > 0:
            return footer_value
        label_value = self._extract_amount_from_label_lines(
            lines,
            labels=("total factura", "total a pagar", "importe total", "total documento", "total general", "total"),
            window=4,
            require_full_label=True,
        )
        if label_value > 0:
            return label_value
        return self._extract_amount(text, TOTAL, prefer_last=True)

    def _extract_iva_percent(self, text: str, lines: list[str]) -> float:
        footer_summary = self._extract_footer_tax_summary(lines)
        if footer_summary["rate"] > 0:
            return footer_summary["rate"]
        match = IVA_PERCENT.search(text)
        if match:
            try:
                raw = match.group(1).replace(",", ".")
                return float(raw)
            except ValueError:
                pass

        known_igic = (0, 1, 3, 5, 7, 9.5, 15, 20)
        known_iva = (4, 10, 21)
        for index, line in enumerate(lines):
            upper_line = line.upper()
            nearby_values = self._extract_numeric_candidates(lines[index + 1:index + 7])
            if "IGIC" in upper_line:
                for candidate in nearby_values:
                    if any(abs(candidate - rate) <= 0.05 for rate in known_igic):
                        return round(candidate, 2)
            if re.search(r"\bIVA\b", upper_line):
                for candidate in nearby_values:
                    if any(abs(candidate - rate) <= 0.05 for rate in known_iva):
                        return round(candidate, 2)

        if "IGIC" in text.upper():
            for candidate in self._extract_numeric_candidates(lines):
                if any(abs(candidate - rate) <= 0.05 for rate in known_igic):
                    return round(candidate, 2)
        return 0.0

    def _extract_iva_amount(self, text: str, lines: list[str]) -> float:
        footer_summary = self._extract_footer_tax_summary(lines)
        if footer_summary["tax"] > 0:
            return footer_summary["tax"]
        footer_value = self._extract_amount_from_label_lines(
            lines,
            labels=("impuestos",),
            window=4,
            require_full_label=True,
            search_previous=True,
        )
        if footer_value > 0:
            return footer_value
        label_value = self._extract_amount_from_label_lines(
            lines,
            labels=("impuestos", "cuota igic", "cuota iva", "cuota"),
            window=3,
            require_full_label=True,
        )
        if label_value > 0:
            return label_value
        return self._extract_amount(text, IVA_AMOUNT, prefer_last=True)

    def _extract_withholding_percent(self, text: str, lines: list[str]) -> float:
        for index, line in enumerate(lines):
            if "IRPF" not in line.upper() and "RETEN" not in line.upper():
                continue
            nearby_values = self._extract_numeric_candidates(lines[index:index + 4])
            for value in nearby_values:
                if 0 < value <= 25:
                    return round(value, 2)
        match = re.search(r"(?:RETENCI[OÓ]N\s*I\.?R\.?P\.?F\.?|IRPF)[^\n]*?(\d{1,2}(?:[.,]\d{1,2})?)\s*%", text, re.IGNORECASE)
        if match:
            return float(match.group(1).replace(",", "."))
        return 0.0

    def _extract_withholding_amount(self, text: str, lines: list[str]) -> float:
        for index, line in enumerate(lines):
            if "IRPF" not in line.upper() and "RETEN" not in line.upper():
                continue
            amounts = self._extract_amount_candidates(lines[index:index + 4])
            if amounts:
                return round(max(amounts), 2)
        match = re.search(
            r"(?:RETENCI[OÓ]N\s*I\.?R\.?P\.?F\.?|IRPF)[^\n]*?(-?\d{1,3}(?:[.,]\d{3})*(?:[.,]\d{2}))",
            text,
            re.IGNORECASE,
        )
        if match:
            return abs(parse_amount(match.group(1)))
        return 0.0

    def _extract_amount_around_exact_label(self, lines: list[str], *, label: str, window: int = 3) -> float:
        candidates: list[float] = []

        for index, line in enumerate(lines):
            normalized = self._normalize_label_line(line)
            if normalized != label:
                continue

            same_line_amounts = self._extract_amount_candidates([line])
            if same_line_amounts:
                candidates.extend(same_line_amounts)

            previous_amounts = self._extract_amount_candidates(lines[max(0, index - window):index])
            next_amounts = self._extract_amount_candidates(lines[index + 1:index + 1 + window])
            candidates.extend(previous_amounts)
            candidates.extend(next_amounts)

        if not candidates:
            return 0.0

        return max(candidates)

    def _extract_amount_from_label_lines(
        self,
        lines: list[str],
        *,
        labels: tuple[str, ...],
        window: int = 3,
        require_full_label: bool = False,
        search_previous: bool = False,
    ) -> float:
        for index, line in enumerate(lines):
            normalized = self._normalize_label_line(line)
            if not normalized:
                continue

            matched = False
            for label in labels:
                if require_full_label:
                    if normalized == label:
                        matched = True
                        break
                elif label in normalized:
                    matched = True
                    break

            if not matched:
                continue

            same_line_amounts = self._extract_amount_candidates([line])
            if same_line_amounts:
                return same_line_amounts[-1]

            if search_previous:
                previous_amounts = self._extract_amount_candidates(lines[max(0, index - window):index])
                if previous_amounts:
                    return previous_amounts[-1]

            amounts = self._extract_amount_candidates(lines[index + 1:index + 1 + window])
            if amounts:
                return amounts[0]
        return 0.0

    def _normalize_label_line(self, line: str) -> str:
        normalized = re.sub(r"\s+", " ", line or "").strip().lower()
        return normalized.strip(" .:;,-")

    def _extract_amount_candidates(self, lines: list[str]) -> list[float]:
        values: list[float] = []
        for line in lines:
            for match in re.findall(r"-?\d{1,3}(?:[.,]\d{3})*(?:[.,]\d{2})|-?\d{1,6}(?:[.,]\d{2})", line):
                try:
                    values.append(abs(parse_amount(match)))
                except ValueError:
                    continue
        return values

    def _extract_numeric_candidates(self, lines: list[str]) -> list[float]:
        values: list[float] = []
        for line in lines:
            for match in re.findall(r"\b\d{1,2}(?:[.,]\d{1,2})?\b", line):
                try:
                    values.append(float(match.replace(",", ".")))
                except ValueError:
                    continue
        return values

    def _extract_footer_tax_summary(self, lines: list[str]) -> dict[str, float]:
        summary = {"base": 0.0, "rate": 0.0, "tax": 0.0, "total": 0.0}
        upper_lines = [line.upper() for line in lines]
        try:
            start = next(
                index
                for index, line in enumerate(upper_lines)
                if "BASE IMPONIBLE" in line
                or ("BASE" in line and any(token in line for token in ("CUOTA", "IGIC", "IVA")))
                or (line.strip() == "BASE" and "TOTAL" in upper_lines[index:index + 12])
                or ("IMPUESTOS" in line and "TOTAL" in upper_lines[min(len(upper_lines) - 1, index + 1): index + 5])
            )
        except StopIteration:
            return summary

        window_start = max(0, start - 6)
        window_lines = lines[window_start:start + 18]
        joined_window = " ".join(window_lines)
        same_line_base = re.search(
            r"\bBASE(?:\s+IMPONIBLE)?\s*(-?\d{1,3}(?:[.,]\d{3})*(?:[.,]\d{2})|-?\d+(?:[.,]\d{2}))",
            joined_window,
            re.IGNORECASE,
        )
        same_line_tax = re.search(
            r"\b(?:IMPUESTOS|IGIC|IVA|CUOTA)\s*(-?\d{1,3}(?:[.,]\d{3})*(?:[.,]\d{2})|-?\d+(?:[.,]\d{2}))",
            joined_window,
            re.IGNORECASE,
        )
        same_line_total = re.search(
            r"\bTOTAL(?:\s+FACTURA|\s+COMPRA)?\s*(-?\d{1,3}(?:[.,]\d{3})*(?:[.,]\d{2})|-?\d+(?:[.,]\d{2}))",
            joined_window,
            re.IGNORECASE,
        )
        same_line_rate = re.search(
            r"\b(?:IGIC%?|IVA%?)\s*(\d{1,2}(?:[.,]\d{1,2})?)",
            joined_window,
            re.IGNORECASE,
        )

        if same_line_base:
            summary["base"] = round(parse_amount(same_line_base.group(1)), 2)
        if same_line_tax:
            summary["tax"] = round(parse_amount(same_line_tax.group(1)), 2)
        if same_line_total:
            summary["total"] = round(parse_amount(same_line_total.group(1)), 2)
        if same_line_rate:
            summary["rate"] = float(same_line_rate.group(1).replace(",", "."))

        amount_values = self._extract_amount_candidates(window_lines)
        percent_values: list[float] = []
        for line in window_lines:
            upper_line = line.upper()
            if "%" not in upper_line and "IGIC" not in upper_line and not re.search(r"\bIVA\b", upper_line):
                continue
            for match in re.findall(r"\d{1,2}(?:[.,]\d{1,2})?", line):
                try:
                    value = float(match.replace(",", "."))
                except ValueError:
                    continue
                if any(abs(value - known) <= 0.05 for known in (0, 1, 3, 4, 5, 7, 9.5, 10, 15, 20, 21)):
                    percent_values.append(value)

        if not percent_values:
            for index, line in enumerate(window_lines):
                upper_line = line.upper()
                if "%" not in upper_line and "IGIC" not in upper_line and not re.search(r"\bIVA\b", upper_line):
                    continue
                nearby_values = self._extract_numeric_candidates(window_lines[index + 1:index + 7])
                for value in nearby_values:
                    if value <= 21.0 and any(abs(value - known) <= 0.05 for known in (0, 1, 3, 4, 5, 7, 9.5, 10, 15, 20, 21)):
                        percent_values.append(value)

        if not percent_values:
            percent_values = [
                value
                for value in self._extract_numeric_candidates(window_lines)
                if value <= 21.0 and any(abs(value - known) <= 0.05 for known in (0, 1, 3, 4, 5, 7, 9.5, 10, 15, 20, 21))
            ]

        if percent_values:
            non_zero_rates = [value for value in percent_values if value > 0.05]
            summary["rate"] = non_zero_rates[0] if non_zero_rates else percent_values[0]

        if amount_values and summary["total"] <= 0:
            summary["total"] = max(amount_values)

        if summary["rate"] > 0 and len(amount_values) >= 2 and summary["base"] <= 0:
            for candidate_base in sorted({round(value, 2) for value in amount_values if value > 0}):
                expected_tax = round(candidate_base * summary["rate"] / 100, 2)
                expected_total = round(candidate_base + expected_tax, 2)
                if summary["total"] > 0 and abs(expected_total - summary["total"]) <= 0.05:
                    summary["base"] = candidate_base
                    summary["tax"] = expected_tax
                    break

        if summary["base"] <= 0 and len(amount_values) >= 2:
            sorted_amounts = sorted(value for value in amount_values if value > 0)
            if sorted_amounts:
                summary["base"] = sorted_amounts[0]
            if len(sorted_amounts) >= 2:
                summary["tax"] = sorted_amounts[-1] - sorted_amounts[0]

        if summary["tax"] <= 0 and summary["total"] > 0 and summary["base"] > 0:
            inferred_tax = round(summary["total"] - summary["base"], 2)
            if inferred_tax > 0:
                summary["tax"] = inferred_tax

        if summary["rate"] <= 0 and summary["base"] > 0 and summary["tax"] > 0:
            summary["rate"] = round(summary["tax"] / summary["base"] * 100, 2)

        return summary

    def _infer_amounts(self, data: InvoiceData) -> None:
        withholding = round(max(0, data.retencion or 0), 2)
        if data.base_imponible > 0 and data.iva_porcentaje > 0 and data.iva == 0:
            data.iva = round(data.base_imponible * data.iva_porcentaje / 100, 2)
        if data.base_imponible > 0 and data.iva > 0 and data.total == 0:
            data.total = round(data.base_imponible + data.iva - withholding, 2)
        if data.total > 0 and data.iva_porcentaje > 0 and data.base_imponible == 0:
            gross_total = round(data.total + withholding, 2) if withholding > 0 else data.total
            data.base_imponible = round(gross_total / (1 + data.iva_porcentaje / 100), 2)
            data.iva = round(gross_total - data.base_imponible, 2)
        if data.total > 0 and data.base_imponible > 0 and data.iva == 0:
            gross_total = round(data.total + withholding, 2) if withholding > 0 else data.total
            data.iva = round(gross_total - data.base_imponible, 2)

        if data.base_imponible > 0 and data.iva_porcentaje > 0:
            expected_iva = round(data.base_imponible * data.iva_porcentaje / 100, 2)
            if data.total > 0:
                if abs(data.base_imponible + expected_iva - withholding - data.total) < abs(
                    data.base_imponible + data.iva - withholding - data.total
                ):
                    data.iva = expected_iva
            elif data.iva == 0 or abs(data.iva - expected_iva) > 0.02:
                data.iva = expected_iva

    def _extract_line_items(self, text: str) -> list[LineItem]:
        lines = [line.strip() for line in text.split("\n") if line.strip()]
        table_lines: list[str] = []
        in_table = False
        relaxed_header_pattern = re.compile(r"(?:descripci|concepto|detalle|art)", re.IGNORECASE)

        header_pattern = re.compile(r"(?:descripci[oó]n|concepto|detalle|art[ií]culo)", re.IGNORECASE)
        footer_pattern = re.compile(
            r"(?:base\s+imponible|subtotal|total|iva|igic|impuestos|observaciones|notas|forma\s+de\s+pago|cuota|%ret|%igic|base)",
            re.IGNORECASE,
        )

        for index, stripped in enumerate(lines):
            if footer_pattern.search(stripped) and in_table:
                break
            if (header_pattern.search(stripped) or relaxed_header_pattern.search(stripped)) and not in_table:
                in_table = True
                continue
            if in_table and self._looks_like_summary_block(lines, index, footer_pattern):
                break
            if in_table:
                table_lines.append(stripped)

        if not table_lines:
            return []

        items = self._extract_vertical_line_items(table_lines, footer_pattern)
        if items:
            return items

        fallback_items: list[LineItem] = []
        for stripped in table_lines:
            item = self._parse_line_item(stripped)
            if item:
                fallback_items.append(item)
        return fallback_items

    def _extract_vertical_line_items(self, lines: list[str], footer_pattern: re.Pattern) -> list[LineItem]:
        items: list[LineItem] = []
        index = 0

        while index < len(lines):
            current = lines[index]
            if footer_pattern.search(current):
                break

            if self._is_note_line(current):
                index += 1
                continue

            if (
                self._is_standalone_amount_line(current)
                and index + 2 < len(lines)
                and self._is_standalone_amount_line(lines[index + 1])
                and self._is_standalone_amount_line(lines[index + 2])
            ):
                triplet = self._resolve_vertical_amount_triplet(
                    parse_amount(current),
                    parse_amount(lines[index + 1]),
                    parse_amount(lines[index + 2]),
                )
                if triplet:
                    quantity, unit_price, amount = triplet
                else:
                    quantity = parse_amount(current)
                    unit_price = parse_amount(lines[index + 1])
                    amount = parse_amount(lines[index + 2])
                description_parts: list[str] = []
                lookahead = index + 3
                while lookahead < len(lines):
                    candidate = lines[lookahead]
                    if footer_pattern.search(candidate) or self._is_standalone_amount_line(candidate):
                        break
                    if not self._is_note_line(candidate) and not self._looks_like_license_key_line(candidate):
                        description_parts.append(candidate)
                    lookahead += 1

                description = self._build_line_description(description_parts)
                if description:
                    items.append(
                        LineItem(
                            descripcion=description,
                            cantidad=quantity or 1.0,
                            precio_unitario=unit_price,
                            importe=amount,
                        )
                    )
                    index = lookahead
                    continue

            if self._is_standalone_amount_line(current):
                amount = parse_amount(current)
                description_parts: list[str] = []
                lookahead = index + 1
                while lookahead < len(lines):
                    candidate = lines[lookahead]
                    if footer_pattern.search(candidate) or self._is_standalone_amount_line(candidate):
                        break
                    if not self._is_note_line(candidate) and not self._looks_like_license_key_line(candidate):
                        description_parts.append(candidate)
                    lookahead += 1

                description = self._build_line_description(description_parts)
                if description and self._looks_like_item_description(description):
                    items.append(
                        LineItem(
                            descripcion=description,
                            cantidad=1.0,
                            precio_unitario=amount,
                            importe=amount,
                        )
                    )
                    index = lookahead
                    continue

            item = self._parse_line_item(current)
            if item:
                items.append(item)

            index += 1

        return items

    def _is_standalone_amount_line(self, line: str) -> bool:
        stripped = (line or "").strip()
        if not stripped:
            return False
        if re.search(r"[A-Za-zÁÉÍÓÚÜÑáéíóúüñ]", stripped):
            return False
        return bool(re.fullmatch(r"-?[\d.,]+", stripped))

    def _looks_like_summary_block(self, lines: list[str], index: int, footer_pattern: re.Pattern) -> bool:
        current = lines[index]
        if not self._is_standalone_amount_line(current):
            return False
        next_line = lines[index + 1] if index + 1 < len(lines) else ""
        if next_line and self._looks_like_item_description(next_line):
            return False
        if abs(parse_amount(current)) <= 10:
            return False

        lookahead = lines[index + 1:index + 5]
        footer_hits = sum(1 for line in lookahead if footer_pattern.search(line))
        return footer_hits >= 2

    def _resolve_vertical_amount_triplet(self, first: float, second: float, third: float) -> tuple[float, float, float] | None:
        candidates = [
            (first, second, third),
            (second, third, first),
            (third, second, first),
        ]

        best_candidate: tuple[float, float, float] | None = None
        best_delta = float("inf")

        for quantity, unit_price, amount in candidates:
            if quantity <= 0 or unit_price <= 0 or amount <= 0:
                continue
            if quantity > 1000 or unit_price > amount * 10:
                continue
            delta = abs(round(quantity * unit_price, 2) - amount)
            if delta > max(0.05, amount * 0.03):
                continue
            if delta < best_delta:
                best_candidate = (quantity, unit_price, amount)
                best_delta = delta

        return best_candidate

    def _is_note_line(self, value: str) -> bool:
        normalized = self._normalize_label_line(value)
        return normalized.startswith("de albar") or normalized.startswith("observaciones")

    def _looks_like_license_key_line(self, value: str) -> bool:
        cleaned = re.sub(r"\s+", "", (value or "").upper())
        if len(cleaned) < 18:
            return False
        return bool(re.fullmatch(r"[A-Z0-9-]+", cleaned) and re.search(r"\d", cleaned))

    def _build_line_description(self, description_parts: list[str]) -> str:
        filtered: list[str] = []
        for part in description_parts:
            cleaned = re.sub(r"\s+", " ", (part or "").strip()).strip(" .,:;-")
            if not cleaned:
                continue
            if self._looks_like_license_key_line(cleaned):
                continue
            if re.fullmatch(r"[A-Z0-9-]{5,20}", cleaned):
                continue
            filtered.append(cleaned)
        return " ".join(filtered).strip()

    def _looks_like_item_description(self, value: str) -> bool:
        cleaned = re.sub(r"\s+", " ", value or "").strip()
        if len(cleaned) < 2:
            return False
        if self._is_note_line(cleaned):
            return False
        normalized = self._normalize_label_line(cleaned)
        compact = re.sub(r"[^a-z0-9]", "", normalized)
        if normalized in {"concepto", "detalle", "descripcion", "importe", "uds", "neto"}:
            return False
        if compact in {"partn", "partno", "partnum", "partnumero", "partnº"}:
            return False
        return True

    def _parse_line_item(self, line: str) -> LineItem | None:
        if self._is_note_line(line) or self._looks_like_license_key_line(line):
            return None
        if not self._looks_like_item_description(line):
            return None
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

    def _extract_ticket_invoice_number(self, lines: list[str]) -> str:
        ticket_same_line = re.compile(
            r"\b((?:[A-Z]\d{3,}|[A-Z0-9]{1,6}[/-]\d{3,}[\w/-]*|\d{4}/\d{4,}-\d{4,}))\b(?:\s+FECHA\b|\s+\d{1,2}[/\-\.]\d{1,2}[/\-\.]\d{2,4}\b)",
            re.IGNORECASE,
        )
        for line in lines:
            if "IBAN" in line.upper():
                continue
            match = ticket_same_line.search(line)
            if not match:
                continue
            extracted = self._normalize_invoice_number_candidate(match.group(1))
            if self._looks_like_invoice_number_candidate(extracted):
                return extracted
        return ""

    def _looks_like_tax_id_candidate(self, value: str) -> bool:
        cleaned = re.sub(r"[\s.\-]", "", (value or "").upper())
        return bool(
            re.fullmatch(r"[A-HJ-NP-SUVW]\d{7}[0-9A-J]", cleaned)
            or re.fullmatch(r"\d{8}[A-Z]", cleaned)
            or re.fullmatch(r"[XYZ]\d{7}[A-Z]", cleaned)
        )

    def _looks_like_address_or_contact_line(self, value: str) -> bool:
        upper_value = (value or "").upper()
        if not upper_value:
            return False
        if re.search(r"\b(?:MAIL|WEB|HTTP|TF|TEL|TLF|MOVIL|MÓVIL|EMAIL)\b", upper_value):
            return True
        if re.search(r"\b(?:C/|CALLE|AVDA\.?|AVENIDA|URB\.?|LOCAL|POL\.?|POLIGONO|POLÍGONO|CTRA\.?|PLAZA|PASEO)\b", upper_value):
            return True
        if re.search(r"\b\d{5}\b", upper_value):
            return True
        return False

    def _looks_like_ticket_document(self, text: str) -> bool:
        upper_text = (text or "").upper()
        return any(
            token in upper_text
            for token in (
                "FACTURA SIMPLIFICADA",
                "FRA. SIMPLIFICADA",
                "FRA SIMPLIFICADA",
                "DOCUMENTO DE VENTA",
                "CONSULTA BORRADOR",
                "NO VALIDO COMO FACTURA",
            )
        )

    def _normalize_ticket_parties(self, data: InvoiceData, text: str, lines: list[str]) -> None:
        if not self._looks_like_ticket_document(text):
            return
        legal_candidates = []
        for line in lines[:12]:
            if self._looks_like_company_name(line) and line not in legal_candidates:
                legal_candidates.append(line[:200])
        if legal_candidates:
            data.proveedor = legal_candidates[0]
            if data.cliente == data.proveedor:
                data.cliente = ""
        if not data.proveedor and data.cliente:
            data.proveedor = data.cliente
            data.cliente = ""
        if not data.cif_proveedor and data.cif_cliente:
            data.cif_proveedor = data.cif_cliente
            data.cif_cliente = ""
        data.cliente = ""
        data.cif_cliente = ""


field_extractor = FieldExtractor()
