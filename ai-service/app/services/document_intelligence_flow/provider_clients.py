from __future__ import annotations

from typing import Any

from app.config import settings
from app.models.invoice_model import InvoiceData

from .helpers import build_text_prompt, invoice_from_payload, parse_json_payload, response_schema


async def extract_with_openai_compatible(
    *,
    raw_text: str,
    page_images: list[str],
    filename: str,
    prompt: str,
) -> InvoiceData:
    if not settings.doc_ai_base_url or not settings.doc_ai_model:
        raise RuntimeError("DOC_AI_BASE_URL y DOC_AI_MODEL son obligatorios")

    content: list[dict[str, Any]] = [
        {
            "type": "text",
            "text": (
                f"{prompt}\n"
                f"Nombre de archivo: {filename or 'invoice'}\n"
                f"Texto OCR/extraido:\n{raw_text[:12000]}"
            ),
        }
    ]
    for page_image in page_images:
        content.append(
            {
                "type": "image_url",
                "image_url": {"url": page_image},
            }
        )

    payload = {
        "model": settings.doc_ai_model,
        "temperature": 0,
        "response_format": {"type": "json_object"},
        "messages": [
            {
                "role": "system",
                "content": "Eres un extractor preciso de facturas. Responde solo JSON.",
            },
            {
                "role": "user",
                "content": content,
            },
        ],
    }

    headers = {}
    if settings.doc_ai_api_key:
        headers["Authorization"] = f"Bearer {settings.doc_ai_api_key}"

    import httpx

    async with httpx.AsyncClient(timeout=settings.doc_ai_timeout_seconds) as client:
        response = await client.post(
            f"{settings.doc_ai_base_url.rstrip('/')}/chat/completions",
            headers=headers,
            json=payload,
        )
        response.raise_for_status()

    response_json = response.json()
    message_content = response_json["choices"][0]["message"]["content"]
    parsed = parse_json_payload(message_content)
    return invoice_from_payload(parsed)


async def extract_with_ollama(
    *,
    raw_text: str,
    filename: str,
    prompt: str,
) -> InvoiceData:
    if not settings.doc_ai_base_url or not settings.doc_ai_model:
        raise RuntimeError("DOC_AI_BASE_URL y DOC_AI_MODEL son obligatorios")
    if not raw_text.strip():
        raise RuntimeError("No hay texto OCR para estructurar con Ollama")

    payload = {
        "model": settings.doc_ai_model,
        "stream": False,
        "format": response_schema(),
        "keep_alive": settings.doc_ai_keep_alive,
        "options": {
            "temperature": 0,
        },
        "messages": [
            {
                "role": "system",
                "content": "Eres un extractor preciso de facturas. Responde solo JSON valido.",
            },
            {
                "role": "user",
                "content": build_text_prompt(raw_text=raw_text, filename=filename, prompt=prompt),
            },
        ],
    }

    import httpx

    async with httpx.AsyncClient(timeout=settings.doc_ai_timeout_seconds) as client:
        response = await client.post(
            f"{settings.doc_ai_base_url.rstrip('/')}/api/chat",
            json=payload,
        )
        response.raise_for_status()

    response_json = response.json()
    message_content = response_json["message"]["content"]
    parsed = parse_json_payload(message_content)
    return invoice_from_payload(parsed)
