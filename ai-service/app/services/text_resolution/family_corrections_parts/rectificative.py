from __future__ import annotations

import re
from typing import Any

from app.models.invoice_model import InvoiceData, LineItem
from app.services.text_resolution.party_resolution import party_resolution_service
from app.utils.text_processing import parse_amount


def apply_rectificative_corrections(
    *,
    normalized: InvoiceData,
    raw_text: str,
    company: dict[str, str],
) -> list[str]:
    rect_data = extract_rectificative_data(raw_text, company)
    if rect_data["supplier_name"]:
        normalized.proveedor = rect_data["supplier_name"]
    if rect_data["supplier_tax_id"]:
        normalized.cif_proveedor = rect_data["supplier_tax_id"]
    if company["name"] or company["tax_id"]:
        normalized.cliente = company["name"] or normalized.cliente
        normalized.cif_cliente = company["tax_id"] or normalized.cif_cliente
    if rect_data["invoice_number"]:
        normalized.numero_factura = rect_data["invoice_number"]
    if rect_data["rectified_invoice_number"]:
        normalized.rectified_invoice_number = rect_data["rectified_invoice_number"]
    if rect_data["base"] != 0:
        normalized.base_imponible = rect_data["base"]
    if rect_data["tax_rate"] > 0:
        normalized.iva_porcentaje = rect_data["tax_rate"]
    if rect_data["tax_amount"] != 0:
        normalized.iva = rect_data["tax_amount"]
    if rect_data["total"] != 0:
        normalized.total = rect_data["total"]
    if rect_data["description"] and normalized.base_imponible != 0:
        normalized.lineas = [
            LineItem(
                descripcion=rect_data["description"],
                cantidad=1.0,
                precio_unitario=normalized.base_imponible,
                importe=normalized.base_imponible,
            )
        ]
    return ["familia_rectificativa_corregida"]


def extract_rectificative_data(raw_text: str, company_context: dict[str, str]) -> dict[str, Any]:
    lines = [line.strip() for line in raw_text.splitlines() if line.strip()]
    upper_lines = [line.upper() for line in lines]
    result = {
        "invoice_number": "",
        "rectified_invoice_number": "",
        "supplier_name": "",
        "supplier_tax_id": "",
        "base": 0.0,
        "tax_rate": 0.0,
        "tax_amount": 0.0,
        "total": 0.0,
        "description": "",
    }

    company = company_context or {}
    result["supplier_name"] = party_resolution_service.extract_ranked_provider_from_header(raw_text, company)

    for line in lines[:18]:
        if "NIF" not in line.upper() and "CIF" not in line.upper():
            continue
        tax_ids = re.findall(r"[A-Z]\d{7}[A-Z0-9]|\d{8}[A-Z]", re.sub(r"[\s.\-]", "", line.upper()))
        for candidate in tax_ids:
            if company.get("tax_id") and candidate == company["tax_id"]:
                continue
            result["supplier_tax_id"] = candidate
            break
        if result["supplier_tax_id"]:
            break

    invoice_match = re.search(r"\bAB[A-Z0-9/-]{6,}\b", raw_text, re.IGNORECASE)
    if invoice_match:
        result["invoice_number"] = invoice_match.group(0).upper()

    rectified_match = re.search(r"(?:RECTIFICA\s+A)\s*[\n ]*([A-Z]{1,6}\d[\w/-]{3,25})", raw_text, re.IGNORECASE)
    if rectified_match:
        result["rectified_invoice_number"] = rectified_match.group(1).upper()

    try:
        concept_index = next(index for index, line in enumerate(upper_lines) if line == "CONCEPTO")
    except StopIteration:
        concept_index = -1
    if concept_index >= 0:
        for candidate in lines[concept_index + 1:concept_index + 6]:
            cleaned = re.sub(r"\s+", " ", candidate).strip(" .,:;-")
            if not cleaned or cleaned.startswith("-") or re.fullmatch(r"-?[\d.,]+", cleaned):
                continue
            if cleaned.upper().startswith("SUBTOTAL") or cleaned.upper().startswith("TOTAL"):
                break
            if len(cleaned) >= 6:
                result["description"] = cleaned
                break

    if not result["description"]:
        trigger_index = next(
            (
                index
                for index, line in enumerate(upper_lines)
                if "CAUSA RECT" in line or line == "CONCEPTO"
            ),
            -1,
        )
        if trigger_index >= 0:
            for candidate in lines[trigger_index + 1:trigger_index + 8]:
                cleaned = re.sub(r"\s+", " ", candidate).strip(" .,:;-")
                upper_candidate = cleaned.upper()
                if not cleaned or cleaned.startswith("-") or re.fullmatch(r"-?[\d.,]+", cleaned):
                    continue
                if any(
                    token in upper_candidate
                    for token in ("SUBTOTAL", "IMPUEST", "TOTAL", "DOCUMENTO", "FECHA", "RECTIFICA", "NIF", "CIF")
                ):
                    continue
                if party_resolution_service.looks_like_address_or_contact_line(cleaned):
                    continue
                if len(cleaned) >= 10:
                    result["description"] = cleaned
                    break

    def signed_amount_for_label(label: str) -> float:
        for index in range(len(upper_lines) - 1, -1, -1):
            upper_line = upper_lines[index]
            if label not in upper_line:
                continue
            if label == "TOTAL":
                for candidate in lines[index + 1:index + 3]:
                    matches = re.findall(r"-?\d{1,3}(?:[.,]\d{3})*(?:[.,]\d{2})|-?\d+(?:[.,]\d{2})", candidate)
                    if matches:
                        return round(parse_amount(matches[-1]), 2)
            for candidate in reversed(lines[max(0, index - 2):index + 1]):
                matches = re.findall(r"-?\d{1,3}(?:[.,]\d{3})*(?:[.,]\d{2})|-?\d+(?:[.,]\d{2})", candidate)
                if matches:
                    return round(parse_amount(matches[-1]), 2)
            for candidate in lines[index + 1:index + 3]:
                matches = re.findall(r"-?\d{1,3}(?:[.,]\d{3})*(?:[.,]\d{2})|-?\d+(?:[.,]\d{2})", candidate)
                if matches:
                    return round(parse_amount(matches[-1]), 2)
        return 0.0

    result["base"] = signed_amount_for_label("SUBTOTAL")
    result["tax_amount"] = signed_amount_for_label("IMPUESTOS")
    result["total"] = signed_amount_for_label("TOTAL")

    if result["base"] != 0 and result["total"] != 0:
        inferred_tax = round(result["total"] - result["base"], 2)
        if inferred_tax != 0 and (
            result["tax_amount"] == 0 or abs(abs(result["tax_amount"]) - abs(inferred_tax)) > 0.05
        ):
            result["tax_amount"] = inferred_tax

    rate_match = re.search(r"(\d{1,2}(?:[.,]\d{1,2})?)\s*%[^\n]*IMPUESTOS", raw_text, re.IGNORECASE)
    if rate_match:
        result["tax_rate"] = float(rate_match.group(1).replace(",", "."))
    elif "%IGIC" in raw_text.upper():
        result["tax_rate"] = 7.0
    elif result["base"] and result["tax_amount"]:
        result["tax_rate"] = round(abs(result["tax_amount"] / result["base"]) * 100, 2)

    if result["base"] and result["tax_amount"]:
        inferred_rate = round(abs(result["tax_amount"] / result["base"]) * 100, 2)
        if result["tax_rate"] <= 0 or result["tax_rate"] > 35 or abs(result["tax_rate"] - inferred_rate) > 0.5:
            if inferred_rate <= 35:
                result["tax_rate"] = inferred_rate

    return result
