"""All regex patterns for Spanish invoices — CIF/NIF, dates, amounts."""

import re

# --- Tax ID (CIF / NIF / NIE) ---
# Allow optional dashes/dots/spaces within tax IDs (common in Spanish docs)
CIF = re.compile(r"\b([A-HJ-NP-SUVW][\s.\-]*(?:\d[\s.\-]*){7}[0-9A-J])\b", re.IGNORECASE)
NIF = re.compile(r"\b(\d{8}\s*[A-Z])\b")
NIE = re.compile(r"\b([XYZ][\s.\-]*(?:\d[\s.\-]*){7}[A-Z])\b", re.IGNORECASE)
ANY_TAX_ID = re.compile(
    r"\b(?:[A-HJ-NP-SUVW][\s.\-]*(?:\d[\s.\-]*){7}[0-9A-J]|"
    r"\d{8}\s*[A-Z]|"
    r"[XYZ][\s.\-]*(?:\d[\s.\-]*){7}[A-Z])\b",
    re.IGNORECASE,
)

# --- Invoice number ---
INVOICE_NUMBER = re.compile(
    r"(?:n[°ºo.\s]*(?:de\s+)?factura|factura\s*(?:n[°ºo.]?\s*)?|fra\.?\s*n?[°ºo.]?\s*|"
    r"n[°º]?\s*factura|invoice\s*(?:no?\.?\s*)?|factura\s*:)"
    r"\s*[:.]?\s*([A-Z0-9][\w\-/. ]{1,30}[A-Z0-9])",
    re.IGNORECASE,
)
INVOICE_CODE = re.compile(
    r"\b([A-Z]{1,4}[\-/]?\d{4,}(?:[\-/]\d+)*)\b"
)

# --- Dates ---
DATE_DMY = re.compile(
    r"(?:fecha(?:\s+de)?(?:\s+(?:factura|emisi[oó]n|expedici[oó]n))?|date)\s*:?\s*"
    r"(\d{1,2})[/\-.](\d{1,2})[/\-.](\d{2,4})",
    re.IGNORECASE,
)
DATE_STANDALONE = re.compile(r"\b(\d{1,2})[/\-.](\d{1,2})[/\-.](\d{2,4})\b")

MONTHS_ES = {
    "enero": 1, "febrero": 2, "marzo": 3, "abril": 4, "mayo": 5, "junio": 6,
    "julio": 7, "agosto": 8, "septiembre": 9, "octubre": 10, "noviembre": 11, "diciembre": 12,
}
DATE_TEXT_ES = re.compile(
    r"(\d{1,2})\s+de\s+(" + "|".join(MONTHS_ES) + r")\s+(?:de\s+)?(\d{4})",
    re.IGNORECASE,
)

# --- Amounts ---
AMOUNT_EU = re.compile(r"(-?\d{1,3}(?:[.]\d{3})*,\d{2})\b")
AMOUNT_ANY = re.compile(r"(-?\d{1,3}(?:[.,]\d{3})*(?:[.,]\d{2})|-?\d+(?:[.,]\d{2}))")
PERCENT = re.compile(r"(-?\d+(?:[.,]\d{1,2})?)\s*%")

# --- Amount labels (Spanish) ---
LABEL_BASE = re.compile(r"\b(?:base\s+imponible|importe\s+neto|subtotal|base)\b", re.IGNORECASE)
LABEL_TOTAL = re.compile(r"\b(?:total(?:\s+factura|\s+compra)?|importe\s+total)\b", re.IGNORECASE)
LABEL_TAX = re.compile(r"\b(?:cuota\s+(?:iva|igic)|iva|igic)\b", re.IGNORECASE)
LABEL_WITHHOLDING = re.compile(r"\b(?:retenci[oó]n|irpf)\b", re.IGNORECASE)
LABEL_RECTIFIED = re.compile(
    r"(?:factura\s+(?:rectificada|original|que\s+se\s+rectifica))\s*:?\s*([A-Z0-9][\w\-/. ]+)",
    re.IGNORECASE,
)

# --- Party labels ---
LABEL_PROVIDER = re.compile(
    r"(?:proveedor|emisor|vendedor|empresa\s+emisora|datos\s+del?\s+proveedor)\s*:?",
    re.IGNORECASE,
)
LABEL_CLIENT = re.compile(
    r"(?:cliente|destinatario|receptor|comprador|datos\s+del?\s+cliente)\s*:?",
    re.IGNORECASE,
)

# --- Ticket / simplified ---
TICKET_MARKERS = re.compile(
    r"\b(?:DOCUMENTO\s+DE\s+VENTA|TICKET|NO\s+VALIDO\s+COMO\s+FACTURA|TOTAL\s+COMPRA|"
    r"FACTURA\s+SIMPLIFICADA|FRA\.?\s+SIMPLIFICADA)\b",
    re.IGNORECASE,
)
RECTIFICATIVA_MARKERS = re.compile(
    r"\b(?:RECTIFICAT|ABONO|FACTURA\s+RECTIFICATIVA|FACTURA\s+ABONO)\b",
    re.IGNORECASE,
)

# Known indirect tax rates
IVA_RATES = frozenset({4.0, 10.0, 21.0})
IGIC_RATES = frozenset({0.0, 3.0, 5.0, 7.0, 9.5, 15.0})
ALL_TAX_RATES = IVA_RATES | IGIC_RATES
