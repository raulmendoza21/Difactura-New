from __future__ import annotations

import json
from typing import Any

from app.models.invoice_model import InvoiceData, LineItem


def response_schema() -> dict[str, Any]:
    return InvoiceData.model_json_schema()


def build_text_prompt(raw_text: str, filename: str, prompt: str) -> str:
    return (
        f"{prompt}\n"
        f"Nombre de archivo: {filename or 'invoice'}\n"
        "Usa solo la informacion del texto; no inventes datos.\n"
        f"Texto OCR/extraido:\n{raw_text[:16000]}"
    )


def parse_json_payload(payload: Any) -> dict[str, Any]:
    if isinstance(payload, dict):
        return payload

    if isinstance(payload, list):
        text_parts = []
        for item in payload:
            if isinstance(item, dict) and item.get("type") == "text":
                text_parts.append(item.get("text", ""))
        payload = "\n".join(text_parts)

    if not isinstance(payload, str):
        raise ValueError("Respuesta no compatible del proveedor Doc AI")

    payload = payload.strip()
    if payload.startswith("```"):
        payload = payload.strip("`")
        payload = payload.replace("json\n", "", 1).strip()

    start = payload.find("{")
    end = payload.rfind("}")
    if start < 0 or end < 0:
        raise ValueError("No se encontro JSON en la respuesta")

    return json.loads(payload[start:end + 1])


def invoice_from_payload(payload: dict[str, Any]) -> InvoiceData:
    line_items = payload.get("lineas", []) or []
    payload["lineas"] = [
        item if isinstance(item, LineItem) else LineItem(**item)
        for item in line_items
        if isinstance(item, dict)
    ]
    return InvoiceData(**payload)


def is_empty_value(value: Any) -> bool:
    if value in ("", 0, 0.0, None):
        return True
    if isinstance(value, list) and not value:
        return True
    return False


def merge_with_fallback(primary: InvoiceData, fallback: InvoiceData) -> InvoiceData:
    merged = primary.model_copy(deep=True)
    for field_name in InvoiceData.model_fields:
        primary_value = getattr(primary, field_name)
        fallback_value = getattr(fallback, field_name)
        if is_empty_value(primary_value):
            setattr(merged, field_name, fallback_value)
    return merged


def format_exception(exc: Exception) -> str:
    message = str(exc).strip()
    if message:
        return message
    return exc.__class__.__name__
