"""Vision Engine — send pages to OpenAI Vision and parse the structured JSON."""

from __future__ import annotations

import json
import logging
import re
import time

from openai import AsyncOpenAI

from app.config import Settings
from app.pdf_to_images import file_to_images
from app.schema import INVOICE_SCHEMA_PROMPT, InvoiceResult

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """\
Eres un sistema experto en extracción de datos de facturas españolas y de \
Canarias (IVA e IGIC). Recibes una o varias imágenes de una factura y debes \
extraer toda la información disponible siguiendo el esquema JSON indicado.

Definiciones importantes:
- EMISOR: la empresa o persona que EXPIDE la factura (el vendedor o prestador \
de servicio que cobra el dinero). Sus datos aparecen habitualmente en la \
cabecera, en un bloque "Emisor", "Proveedor" o "De:".
- RECEPTOR: la empresa o persona que RECIBE la factura (el comprador o \
cliente que paga). Sus datos aparecen en un bloque "Facturar a", "Cliente", \
"Destinatario" o similar. Extrae siempre quién figura en el documento como \
emisor y receptor, tal como están escritos.

Reglas:
- Lee con precisión todos los números, fechas e identificadores fiscales.
- En facturas con IGIC (Islas Canarias) usa "regimen_fiscal": "IGIC". El IGIC tiene tipos 0%, 3%, 7% y 15%. Si la factura es de un emisor o receptor en Canarias (Las Palmas, Santa Cruz de Tenerife, Islas Canarias) o el tipo impositivo es 7% o 15%, el régimen es IGIC, no IVA.
- Si hay varias páginas, consolida toda la información en un único JSON.
- Para campos no presentes en el documento usa null (numéricos) o "" (texto).
- No inventes ni deduzas datos que no estén explícitamente en el documento.
- El NIF/CIF español sigue el patrón: letra + 7 dígitos + letra/número.
- En el campo "desglose_impuestos" incluye UNA entrada por cada fila de la tabla de impuestos del documento. Si hay dos filas (p.ej. una al 7% y otra al 3%), genera dos objetos en el array. Nunca fusiones filas distintas en una sola.
- El campo "base_imponible" (raíz) debe ser la SUMA de todas las bases del desglose. Si hay varias bases, súmalas.
- El campo "iva_cuota" (raíz) debe ser la SUMA de todas las cuotas del desglose.
- Si todas las líneas tienen el mismo tipo impositivo, rellena "iva_porcentaje" con ese valor; si hay tipos mixtos, deja "iva_porcentaje" en null.
- Devuelve SOLO el objeto JSON, sin texto adicional, sin markdown, sin bloques ```.
"""


async def extract_invoice(
    file_path: str,
    settings: Settings,
    company_context: dict | None = None,
) -> dict:
    """Main entry point. Returns a dict ready for the API response."""
    t0 = time.time()

    # 1. Convert document to page images
    images_b64 = file_to_images(
        file_path, dpi=settings.image_dpi, max_pages=settings.max_pages
    )
    pages = len(images_b64)
    logger.info("Converted document to %d page image(s)", pages)

    # 2. Build message content: schema prompt + all page images
    content: list[dict] = [
        {"type": "text", "text": _build_user_prompt(company_context)},
    ]
    for i, b64 in enumerate(images_b64):
        if pages > 1:
            content.append({"type": "text", "text": f"--- Página {i + 1} ---"})
        content.append({
            "type": "image_url",
            "image_url": {"url": f"data:image/png;base64,{b64}", "detail": "high"},
        })

    # 3. Call OpenAI Vision
    client = AsyncOpenAI(
        api_key=settings.openai_api_key,
        base_url=settings.openai_base_url,
        timeout=settings.timeout_seconds,
    )

    # gpt-5.x models require max_completion_tokens instead of max_tokens
    is_5x = settings.openai_model.startswith("gpt-5")
    token_param = "max_completion_tokens" if is_5x else "max_tokens"

    response = await client.chat.completions.create(
        model=settings.openai_model,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": content},
        ],
        response_format={"type": "json_object"},
        temperature=0.1,
        **{token_param: 2048},
    )

    raw_json = response.choices[0].message.content or ""
    elapsed = round(time.time() - t0, 2)
    usage = response.usage
    logger.info(
        "Vision call done in %.2fs — tokens: %s in / %s out",
        elapsed,
        usage.prompt_tokens if usage else "?",
        usage.completion_tokens if usage else "?",
    )

    # 4. Parse and validate
    parsed = _parse_response(raw_json)

    return {
        "success": True,
        "data": parsed,
        "pages": pages,
        "model": settings.openai_model,
        "elapsed_seconds": elapsed,
        "usage": {
            "prompt_tokens": usage.prompt_tokens if usage else 0,
            "completion_tokens": usage.completion_tokens if usage else 0,
        },
    }


def _build_user_prompt(company_context: dict | None) -> str:
    ctx = ""
    if company_context:
        name = company_context.get("name", "")
        tax_id = company_context.get("tax_id", "")
        if name or tax_id:
            ctx = (
                f'\n\nContexto de la empresa usuaria: nombre="{name}", NIF="{tax_id}". '
                "Úsalo para identificar correctamente quién es el emisor y quién el receptor."
            )
    return INVOICE_SCHEMA_PROMPT + ctx


def _parse_response(raw: str) -> dict:
    """Parse the model JSON response into a validated InvoiceResult dict."""
    # Strip any accidental markdown fences the model may add despite instructions
    clean = re.sub(r"^```json\s*|^```\s*|```$", "", raw.strip(), flags=re.MULTILINE).strip()
    try:
        data = json.loads(clean)
    except json.JSONDecodeError as exc:
        logger.error("JSON parse error: %s\nRaw: %s", exc, raw[:500])
        raise ValueError(f"El modelo devolvió JSON inválido: {exc}") from exc

    # Validate through Pydantic — fills missing fields with defaults
    result = InvoiceResult.model_validate(data)
    return result.model_dump()
