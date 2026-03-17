"""Regex patterns for extracting fields from Spanish invoices."""

import re

# Invoice number patterns.
# Accepts labels like "Factura", "Numero de factura", "Ref.", etc.
# Supports the value on the same line or the next one.
INVOICE_NUMBER = re.compile(
    r"(?:n[°ºo*.\s]*(?:de\s+)?factura|factura(?:\s*n[°ºo*.]?)?|fra\.?|invoice"
    r"|n[uú]mero\s+(?:de\s+)?factura|num\.?\s+(?:de\s+)?factura|ref\.?|№)"
    r"\s*[:.]?\s*\n?\s*"
    r"([A-Z]{0,6}[-/]?\d[\w/-]{0,20})",
    re.IGNORECASE | re.MULTILINE,
)

# Date patterns (DD/MM/YYYY, DD-MM-YYYY, DD.MM.YYYY, "12 de enero de 2024")
DATE_NUMERIC = re.compile(
    r"(?:fecha(?:\s+de)?(?:\s+(?:factura|emisi[oó]n|expedici[oó]n|vencimiento))?|date)"
    r"\s*[:.]?\s*\n?\s*"
    r"(\d{1,2}[/\-\.]\d{1,2}[/\-\.]\d{2,4})",
    re.IGNORECASE | re.MULTILINE,
)

DATE_TEXT = re.compile(
    r"(\d{1,2})\s+de\s+(enero|febrero|marzo|abril|mayo|junio|julio|agosto|"
    r"septiembre|octubre|noviembre|diciembre)\s+(?:de\s+)?(\d{4})",
    re.IGNORECASE,
)

# CIF/NIF patterns (Spanish tax IDs)
CIF_NIF = re.compile(
    r"\b([A-HJ-NP-SUVW][\s\-]?\d{7}[\s\-]?[0-9A-J])\b"
    r"|"
    r"\b(\d{8}[\s\-]?[A-Z])\b"
    r"|"
    r"\b([XYZ][\s\-]?\d{7}[\s\-]?[A-Z])\b",
    re.IGNORECASE,
)

AMOUNT_EU = re.compile(r"(\d{1,3}(?:[.\s]\d{3})*,\d{2})\b")
AMOUNT_US = re.compile(r"(\d{1,3}(?:,\d{3})*\.\d{2})\b")

BASE_IMPONIBLE = re.compile(
    r"(?:base\s+imp(?:onible|\.)?|subtotal|importe\s+neto|neto)"
    r"\s*[:.]?\s*\n?\s*(?:€|EUR|\$)?\s*([\d.,]+)",
    re.IGNORECASE | re.MULTILINE,
)

IVA_PERCENT = re.compile(
    r"(?:iva|i\.v\.a\.?)\s*[:.]?\s*(\d{1,2}(?:[.,]\d{1,2})?)\s*%",
    re.IGNORECASE,
)

IVA_AMOUNT = re.compile(
    r"(?:cuota\s+(?:iva|i\.v\.a\.?)|(?:iva|i\.v\.a\.?|cuota)\s*(?:\d{1,2}(?:[.,]\d{1,2})?\s*%)?)"
    r"\s*[:.]?\s*\n?\s*(?:€|EUR|\$)?\s*([\d.,]+)(?![\d.,]*\s*%)",
    re.IGNORECASE | re.MULTILINE,
)

TOTAL = re.compile(
    r"(?:total\s*(?:factura|a\s+pagar|documento|general)?|importe\s+total|total\s+(?:€|eur))"
    r"\s*[:.]?\s*\n?\s*(?:€|EUR|\$)?\s*([\d.,]+)",
    re.IGNORECASE | re.MULTILINE,
)

PROVEEDOR = re.compile(
    r"(?:proveedor|emisor|raz[oó]n\s+social|empresa|datos\s+del\s+emisor)"
    r"[ \t]*[:.;]?[ \t]*\n?\s*(.+?)(?:\n|$)",
    re.IGNORECASE,
)

CLIENTE = re.compile(
    r"(?:cliente|destinatario|comprador|facturar\s+a|datos\s+del\s+cliente)"
    r"[ \t]*[:.;]?[ \t]*\n?\s*(.+?)(?:\n|$)",
    re.IGNORECASE,
)
