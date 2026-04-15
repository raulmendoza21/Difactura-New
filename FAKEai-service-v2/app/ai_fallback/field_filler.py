"""AI layer — role assignment and weak-field filling via LLM.

Uses OpenAI-compatible chat/completions API (works with Ollama, OpenAI, Groq, etc.).
"""

from __future__ import annotations

import json
import logging
import re

import httpx

from app.config import Settings

logger = logging.getLogger(__name__)

_MAX_RETRIES = 2


async def fill_weak_fields(
    raw_text: str,
    current_data: dict,
    field_confidences: dict[str, float],
    settings: Settings,
    company_context: dict | None = None,
) -> dict:
    """Ask AI to fill fields whose confidence is below threshold.

    Returns a dict with only the filled fields.
    """
    if not settings.ai_enabled:
        return {}

    threshold = settings.ai_confidence_threshold
    weak = [f for f, c in field_confidences.items() if c < threshold and f in _FILLABLE]

    if not weak:
        return {}

    prompt = _build_prompt(raw_text, current_data, weak, company_context)

    # Resolve endpoint URL — Ollama needs /v1/, cloud APIs vary
    base = settings.ai_base_url.rstrip("/")
    if "/v1" not in base:
        url = f"{base}/v1/chat/completions"
    else:
        url = f"{base}/chat/completions"

    payload = {
        "model": settings.ai_model,
        "messages": [
            {"role": "system", "content": _SYSTEM_MSG},
            {"role": "user", "content": prompt},
        ],
        "temperature": 0.0,
        "max_tokens": 512,
        "response_format": {"type": "json_object"},
    }

    headers = {"Content-Type": "application/json"}
    if settings.ai_api_key:
        headers["Authorization"] = f"Bearer {settings.ai_api_key}"

    for attempt in range(_MAX_RETRIES):
        try:
            async with httpx.AsyncClient(timeout=settings.ai_timeout_seconds) as client:
                resp = await client.post(url, json=payload, headers=headers)
                resp.raise_for_status()

            data = resp.json()
            content = data["choices"][0]["message"]["content"]
            filled = _parse_response(content, weak)

            if filled:
                logger.info("AI filled %d/%d weak fields (attempt %d)", len(filled), len(weak), attempt + 1)
                return filled

            logger.warning("AI returned empty/invalid JSON (attempt %d)", attempt + 1)

        except Exception:
            logger.warning("AI call failed (attempt %d/%d)", attempt + 1, _MAX_RETRIES, exc_info=True)

    return {}


# ---------------------------------------------------------------------------
# Schema and prompt
# ---------------------------------------------------------------------------

_FILLABLE = {
    "numero_factura", "fecha", "base_imponible", "iva_porcentaje", "iva",
    "total", "proveedor", "cif_proveedor", "cliente", "cif_cliente",
    "retencion_porcentaje", "retencion",
}

_SYSTEM_MSG = """\
Analiza facturas españolas. Responde SOLO JSON, sin explicaciones.

REGLA CLAVE para proveedor/cliente:
- PROVEEDOR = empresa que EMITE la factura (aparece en la cabecera, tiene el logo, su CIF sale primero)
- CLIENTE = empresa que RECIBE la factura (aparece como "cliente", "destinatario", "facturar a")

Formatos: fechas YYYY-MM-DD, importes sin €."""


def _build_prompt(
    raw_text: str,
    current: dict,
    weak_fields: list[str],
    company_context: dict | None,
) -> str:
    parts: list[str] = []

    # Company context + pre-analysis of which CIF appears
    our_cifs: list[str] = []
    our_name = ""
    if company_context:
        our_name = company_context.get("name", "")
        our_cifs = company_context.get("tax_ids", [])
        if not our_cifs and company_context.get("tax_id"):
            our_cifs = [company_context["tax_id"]]
        parts.append(f"NUESTRA EMPRESA: {our_name} (CIFs: {', '.join(our_cifs)})")

        # Dynamic few-shot examples using the actual company name
        short = our_name.split()[0] if our_name else "Nosotros"
        parts.append(
            f"EJEMPLOS:\n"
            f"- Si Empresa X emite la factura y {short} la recibe → "
            f"proveedor=Empresa X, cliente={short}\n"
            f"- Si {short} emite la factura a Empresa Y → "
            f"proveedor={short}, cliente=Empresa Y"
        )

    # Pre-analyze: does our CIF appear in entities? Tell the model explicitly.
    entities = current.get("entities", [])
    our_entity_match = None
    other_entities = []
    for e in entities:
        cif = e.get("cif", "")
        if cif and any(cif == c for c in our_cifs):
            our_entity_match = e
        else:
            other_entities.append(e)

    if entities:
        ent_lines = [f"  {e.get('cif', '')} → {e.get('nombre', '')}" for e in entities]
        parts.append("ENTIDADES EN FACTURA:\n" + "\n".join(ent_lines))

    # Give the model an explicit hint about our company's position
    if our_entity_match:
        parts.append(
            f"NOTA: El CIF {our_entity_match.get('cif', '')} pertenece a NUESTRA EMPRESA. "
            f"Determina si aparece como EMISOR (proveedor) o como RECEPTOR (cliente)."
        )
    elif our_cifs:
        parts.append(
            "NOTA: Ningún CIF de nuestra empresa aparece. Probablemente es una factura "
            "que RECIBIMOS → compra."
        )

    # Current extracted data (compact, exclude noise)
    display = {
        k: v for k, v in current.items()
        if k not in ("entities", "lineas", "confianza") and v not in (None, "", 0, 0.0, [])
    }
    if display:
        parts.append("DATOS EXTRAÍDOS: " + json.dumps(display, ensure_ascii=False))

    # OCR text (truncated)
    parts.append("TEXTO OCR (el EMISOR suele aparecer arriba):\n" + raw_text[:2500])

    # What we need
    parts.append(f"CAMPOS A RELLENAR: {', '.join(weak_fields)}")
    parts.append("Responde JSON con esos campos.")

    return "\n\n".join(parts)


def _parse_response(content: str, expected_fields: list[str]) -> dict:
    """Extract JSON from AI response, filter to expected fields only."""
    content = content.strip()

    # Strip markdown code fences
    if "```" in content:
        m = re.search(r"```(?:json)?\s*\n?(.*?)```", content, re.DOTALL)
        if m:
            content = m.group(1).strip()

    # Try to find JSON object in response
    if not content.startswith("{"):
        m = re.search(r"\{[^{}]*\}", content, re.DOTALL)
        if m:
            content = m.group(0)

    try:
        data = json.loads(content)
    except json.JSONDecodeError:
        logger.warning("Could not parse AI JSON: %.200s", content)
        return {}

    if not isinstance(data, dict):
        return {}

    # Filter and validate
    result = {}
    for k, v in data.items():
        if k not in expected_fields or v is None:
            continue
        result[k] = v

    return result
