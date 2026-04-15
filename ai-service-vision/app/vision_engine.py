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

DEFINICIONES CRÍTICAS:
- EMISOR: la empresa o persona que EXPIDE la factura (el vendedor/prestador que COBRA). \
Sus datos aparecen en la cabecera, en un bloque "Emisor", "Proveedor" o "De:".
- RECEPTOR: la empresa o persona que RECIBE la factura (el comprador/cliente que PAGA). \
Sus datos aparecen en "Facturar a", "Cliente", "Destinatario" o similar.

REGLAS OBLIGATORIAS — léelas todas antes de extraer:
1. CAMPO _razonamiento (OBLIGATORIO): El JSON DEBE comenzar con el campo "_razonamiento". \
   Escríbelo ANTES de cualquier otro campo con este formato exacto: \
   "1.Nº: etiqueta=<etiqueta vista>, valor=<valor>. 2.Fecha: etiqueta=<etiqueta>, valor=<YYYY-MM-DD>. \
   3.Impuestos: <N> fila(s) → [base=X tipo=Y% cuota=Z] ... \
   4.Líneas: <N> fila(s). Columnas detectadas: [col1, col2, ...]. Verificación: \
   línea1 importe=cant×precio ✓/✗, línea2 ... (al menos las 3 primeras)."
2. NÚMERO DE FACTURA: busca etiquetas "Nº Factura", "Factura Nº", "N° Factura", "Número:", \
   "Factura N.". NO confundas con: nº de pedido, nº de albarán, nº de referencia del cliente, \
   nº de expediente ni nº de presupuesto. Si hay ambigüedad elige el explícitamente etiquetado \
   como factura.
3. FECHA: extrae ÚNICAMENTE la fecha de EMISIÓN de la factura. Ignora fechas de pedido, \
   entrega, vencimiento o albarán salvo que sea la única disponible. Formato YYYY-MM-DD.
4. NIF/CIF: patrón letra+7dígitos+letra/número (ej. B35222249). Cópialo exacto sin espacios.
5. DESGLOSE DE IMPUESTOS — REGLA CRÍTICA: la tabla de impuestos puede tener VARIAS filas. \
   Cuenta físicamente cuántas filas hay. Genera UNA entrada en "desglose_impuestos" por \
   cada fila. NUNCA fusiones dos filas distintas. Si ves "IGIC 7%" e "IGIC 3%" → DOS objetos.
6. base_imponible (raíz) = SUMA exacta de todas las bases del desglose. \
   iva_cuota (raíz) = SUMA exacta de todas las cuotas del desglose.
7. LÍNEAS — LEE COLUMNA POR COLUMNA:
   a) Identifica las columnas de la tabla (típicamente: Referencia, Descripción, Cantidad, \
      Precio unitario, Descuento, Importe). Localiza la posición de cada columna por su \
      cabecera ANTES de leer las filas.
   b) ATENCIÓN AL ERROR MÁS COMÚN: NO confundas IMPORTE (=última columna, valor total de la \
      línea) con PRECIO UNITARIO (=coste de UNA sola unidad). El precio unitario suele ser \
      un número pequeño; el importe suele ser mayor (cantidad × precio). Si una tabla tiene \
      columnas "CANTIDAD | PRECIO | DESCUENTO | IMPORTE", lee CADA valor bajo SU cabecera.
   c) Si hay una columna DESCUENTO vacía (guiones o en blanco), no la saltes ni desplaces \
      las demás columnas. Mantén la alineación cabecera→valor.
   d) El campo "importe_total" corresponde a la ÚLTIMA columna numérica de cada fila. \
      SIEMPRE debe rellenarse si aparece en la factura; nunca lo dejes en null.
   e) Verificación: importe_total ≈ cantidad × precio_unitario (± descuento). Si no cuadra, \
      relee esa fila prestando atención a la alineación de columnas.
   f) Extrae TODAS las filas sin omitir ninguna. Cuenta las filas físicamente. \
      No inventes líneas. Si un valor no es legible con certeza usa null.
8. IGIC: si el emisor/receptor está en Canarias (Las Palmas, Santa Cruz de Tenerife) o el \
   tipo impositivo es 3%, 7% o 15%, usa "regimen_fiscal": "IGIC".
9. Si hay varias páginas consolida todo en un único JSON (todas las líneas en el mismo array).
10. Devuelve SOLO el objeto JSON. Sin texto adicional, sin markdown, sin bloques ```.
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
        temperature=0,
        **{token_param: 4096},
    )

    raw_json = response.choices[0].message.content or ""
    usage = response.usage
    first_call_elapsed = round(time.time() - t0, 2)
    logger.info(
        "Vision call done in %.2fs — tokens: %s in / %s out",
        first_call_elapsed,
        usage.prompt_tokens if usage else "?",
        usage.completion_tokens if usage else "?",
    )

    # 4. Parse and validate
    parsed = _parse_response(raw_json)

    # 5. Auto-correction: if totals don't add up, ask the model to re-check
    #    the tax breakdown table — this catches missed IGIC/IVA rates.
    parsed, raw_json, usage = await _maybe_retry_for_totals(
        parsed, raw_json, content, client, settings, token_param, usage,
    )

    # 6. Auto-correction: if sum(line importes) doesn't match base_imponible,
    #    ask the model to re-read the line items table column by column.
    parsed, usage = await _maybe_retry_for_lines(
        parsed, raw_json, content, client, settings, token_param, usage,
    )

    # 7. Arithmetic fix: fill missing importe_total, fix cant/precio consistency
    _fix_lines_arithmetic(parsed)

    elapsed = round(time.time() - t0, 2)

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


async def _maybe_retry_for_totals(
    parsed: dict,
    original_json: str,
    image_content: list[dict],
    client,
    settings,
    token_param: str,
    usage,
) -> tuple[dict, str, object]:
    """If base_imponible + iva_cuota doesn't match total_factura, ask the model
    to re-examine the tax breakdown table. Returns (parsed, raw_json, usage)."""
    base = float(parsed.get("base_imponible") or 0)
    iva = float(parsed.get("iva_cuota") or 0)
    total = float(parsed.get("total_factura") or 0)
    retencion = float(parsed.get("retencion_importe") or 0)
    recargo = float(parsed.get("recargo_importe") or 0)
    desglose = parsed.get("desglose_impuestos") or []

    if total == 0:
        return parsed, original_json, usage

    expected = base + iva + recargo - retencion
    diff = abs(expected - total)

    # Trigger retry also when there's iva_cuota but no tax breakdown rows
    missing_desglose = iva > 0 and len(desglose) == 0

    # Allow small rounding tolerance
    if diff < 0.10 and not missing_desglose:
        return parsed, original_json, usage

    if missing_desglose:
        logger.warning(
            "Missing desglose: iva_cuota=%.2f but desglose_impuestos is empty. Retrying.",
            iva,
        )
    else:
        logger.warning(
            "Totals mismatch: base(%.2f) + iva(%.2f) + rec(%.2f) - ret(%.2f) = %.2f "
            "but total=%.2f (diff=%.2f). Retrying with correction prompt.",
            base, iva, recargo, retencion, expected, total, diff,
        )

    if missing_desglose:
        correction_prompt = (
            f"Tu extracción anterior tiene iva_cuota={iva} pero desglose_impuestos está vacío.\n"
            f"Vuelve a mirar la imagen. Busca la tabla de desglose de impuestos al pie de la factura.\n"
            f"Cuenta cuántas filas tiene esa tabla e incluye UNA entrada por cada fila.\n"
            f"Recalcula base_imponible (suma de bases) e iva_cuota (suma de cuotas).\n"
            f"Devuelve el JSON completo corregido incluyendo el campo _razonamiento actualizado."
        )
    else:
        correction_prompt = (
            f"Tu extracción anterior tiene un error en los importes:\n"
            f"- base_imponible={base}, iva_cuota={iva}, recargo={recargo}, "
            f"retencion={retencion}, total_factura={total}\n"
            f"- Calculado: base+iva+recargo-retencion = {base+iva+recargo-retencion:.2f}, "
            f"pero total_factura={total} (diferencia {diff:.2f})\n\n"
            f"Esto suele ocurrir cuando la tabla de desglose de impuestos tiene MÁS DE UNA fila "
            f"(ej. IGIC 7% y IGIC 3%) y solo extrajiste una.\n\n"
            f"Vuelve a mirar la imagen COMPLETA. Busca la tabla al pie de la factura. "
            f"Cuenta cuántas filas tiene e incluye TODAS en desglose_impuestos.\n"
            f"Recalcula base_imponible (suma de bases) e iva_cuota (suma de cuotas).\n"
            f"Si hay varios tipos, pon iva_porcentaje en null.\n\n"
            f"Devuelve el JSON completo corregido incluyendo el campo _razonamiento actualizado."
        )

    try:
        retry_response = await client.chat.completions.create(
            model=settings.openai_model,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": image_content},
                {"role": "assistant", "content": original_json},
                {"role": "user", "content": correction_prompt},
            ],
            response_format={"type": "json_object"},
            temperature=0,
            **{token_param: 4096},
        )

        retry_json = retry_response.choices[0].message.content or ""
        retry_parsed = _parse_response(retry_json)
        retry_usage = retry_response.usage

        # Check if the retry is actually better
        retry_base = float(retry_parsed.get("base_imponible") or 0)
        retry_iva = float(retry_parsed.get("iva_cuota") or 0)
        retry_total = float(retry_parsed.get("total_factura") or 0)
        retry_ret = float(retry_parsed.get("retencion_importe") or 0)
        retry_rec = float(retry_parsed.get("recargo_importe") or 0)
        retry_expected = retry_base + retry_iva + retry_rec - retry_ret
        retry_diff = abs(retry_expected - retry_total)
        retry_desglose_count = len(retry_parsed.get("desglose_impuestos") or [])

        logger.info(
            "Retry result: base=%.2f iva=%.2f total=%.2f diff=%.2f desglose=%d",
            retry_base, retry_iva, retry_total, retry_diff, retry_desglose_count,
        )

        # Use retry if it's closer to matching OR if it filled in the missing desglose
        retry_fixed_desglose = missing_desglose and retry_desglose_count > 0
        if retry_diff < diff or retry_fixed_desglose:
            logger.info("Retry improved totals (diff %.2f → %.2f), using corrected extraction.", diff, retry_diff)
            # Merge usage tokens
            if usage and retry_usage:
                usage.prompt_tokens += retry_usage.prompt_tokens
                usage.completion_tokens += retry_usage.completion_tokens
            return retry_parsed, retry_json, usage
        else:
            logger.info("Retry did not improve (diff %.2f → %.2f), keeping original.", diff, retry_diff)
            return parsed, original_json, usage

    except Exception as exc:
        logger.warning("Retry failed: %s — keeping original extraction.", exc)
        return parsed, original_json, usage


async def _maybe_retry_for_lines(
    parsed: dict,
    last_json: str,
    image_content: list[dict],
    client,
    settings,
    token_param: str,
    usage,
) -> tuple[dict, object]:
    """If sum(line importe_total) diverges significantly from base_imponible,
    ask the model to re-read the line items table carefully. Returns (parsed, usage)."""
    base = float(parsed.get("base_imponible") or 0)
    lineas = parsed.get("lineas") or []

    if not lineas or base == 0:
        return parsed, usage

    line_sum = sum(float(ln.get("importe_total") or 0) for ln in lineas)

    # Tolerance: 5% or €2, whichever is larger
    tolerance = max(base * 0.05, 2.0)
    diff = abs(line_sum - base)

    if diff <= tolerance:
        return parsed, usage

    logger.warning(
        "Lines mismatch: sum(importe_total)=%.2f but base_imponible=%.2f (diff=%.2f, tol=%.2f). "
        "Retrying with line correction prompt.",
        line_sum, base, diff, tolerance,
    )

    # Build a compact summary of extracted lines
    line_details = []
    for i, ln in enumerate(lineas):
        cant = ln.get("cantidad") or 0
        precio = ln.get("precio_unitario") or 0
        imp = ln.get("importe_total") or 0
        line_details.append(
            f"  {i+1}. {ln.get('descripcion','?')[:40]}: cant={cant}, precio={precio}, importe={imp}"
        )

    correction_prompt = (
        f"La suma de importe_total de las líneas ({line_sum:.2f}) no coincide con "
        f"base_imponible ({base:.2f}). Diferencia: {diff:.2f}.\n\n"
        f"Líneas extraídas:\n" + "\n".join(line_details) + "\n\n"
        f"Vuelve a leer la tabla de líneas de la imagen desde cero.\n"
        f"- Cuenta TODAS las filas (¿omitiste alguna?).\n"
        f"- Lee cada columna bajo su cabecera: CANTIDAD, PRECIO, IMPORTE.\n"
        f"- importe_total = cantidad × precio_unitario.\n"
        f"Devuelve el JSON completo corregido."
    )

    try:
        retry_response = await client.chat.completions.create(
            model=settings.openai_model,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": image_content},
                {"role": "assistant", "content": last_json},
                {"role": "user", "content": correction_prompt},
            ],
            response_format={"type": "json_object"},
            temperature=0.3,
            **{token_param: 4096},
        )

        retry_json = retry_response.choices[0].message.content or ""
        retry_parsed = _parse_response(retry_json)
        retry_usage = retry_response.usage

        retry_lineas = retry_parsed.get("lineas") or []
        retry_line_sum = sum(float(ln.get("importe_total") or 0) for ln in retry_lineas)
        retry_base = float(retry_parsed.get("base_imponible") or 0)
        retry_diff = abs(retry_line_sum - retry_base)

        logger.info(
            "Lines retry result: %d lines, sum=%.2f, base=%.2f, diff=%.2f (was %.2f)",
            len(retry_lineas), retry_line_sum, retry_base, retry_diff, diff,
        )

        if retry_diff < diff or len(retry_lineas) > len(lineas):
            reason = "more lines" if len(retry_lineas) > len(lineas) else f"diff {diff:.2f} → {retry_diff:.2f}"
            logger.info("Lines retry improved (%s), using corrected version.", reason)
            if usage and retry_usage:
                usage.prompt_tokens += retry_usage.prompt_tokens
                usage.completion_tokens += retry_usage.completion_tokens
            return retry_parsed, usage
        else:
            logger.info("Lines retry did not improve (diff %.2f → %.2f), keeping original.", diff, retry_diff)
            return parsed, usage

    except Exception as exc:
        logger.warning("Lines retry failed: %s — keeping original extraction.", exc)
        return parsed, usage


def _fix_lines_arithmetic(parsed: dict) -> None:
    """Post-process lines to fix missing/inconsistent importe_total.

    Rules applied IN-PLACE:
    1. If importe_total is empty but cant & precio exist → compute it.
    2. If cant=1, importe_total is set, and precio==importe → leave as-is
       (we can't know real cant/precio without re-reading the image).
    3. If cant & precio are set and importe_total differs from cant×precio
       by >1 cent → trust importe_total and try to derive cant or precio.
    """
    lineas = parsed.get("lineas")
    if not lineas:
        return

    fixed = 0
    for ln in lineas:
        cant = float(ln.get("cantidad") or 0)
        precio = float(ln.get("precio_unitario") or 0)
        imp = float(ln.get("importe_total") or 0)

        # Rule 1: fill missing importe_total
        if imp == 0 and cant > 0 and precio > 0:
            ln["importe_total"] = round(cant * precio, 2)
            fixed += 1
            continue

        # Rule 3: cant×precio doesn't match importe_total — trust importe
        if cant > 0 and precio > 0 and imp > 0:
            expected = round(cant * precio, 2)
            if abs(expected - imp) > 0.02:
                # Try to derive correct cantidad from importe/precio
                if precio > 0:
                    derived_cant = imp / precio
                    rounded_cant = round(derived_cant)
                    if rounded_cant >= 1 and abs(rounded_cant * precio - imp) < 0.02:
                        ln["cantidad"] = rounded_cant
                        fixed += 1

    if fixed:
        logger.info("Arithmetic fix: corrected %d line(s).", fixed)


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

    # Log and strip chain-of-thought reasoning field before validation
    razonamiento = data.pop("_razonamiento", None)
    if razonamiento:
        logger.info("Model reasoning: %s", str(razonamiento)[:600])

    # Normalize common field name variants the model may use
    for ln in data.get("lineas") or []:
        if "importe" in ln and "importe_total" not in ln:
            ln["importe_total"] = ln.pop("importe")

    # Validate through Pydantic — fills missing fields with defaults
    result = InvoiceResult.model_validate(data)
    dumped = result.model_dump()

    # ── Debug: log tax breakdown and line count ──
    desglose = dumped.get("desglose_impuestos") or []
    logger.info(
        "RAW EXTRACTION — base=%.2f iva_cuota=%.2f total=%.2f iva_pct=%s desglose_entries=%d lineas=%d",
        dumped.get("base_imponible") or 0,
        dumped.get("iva_cuota") or 0,
        dumped.get("total_factura") or 0,
        dumped.get("iva_porcentaje"),
        len(desglose),
        len(dumped.get("lineas") or []),
    )
    for i, d in enumerate(desglose):
        logger.info(
            "  desglose[%d]: base=%.2f tipo=%.2f%% cuota=%.2f",
            i, d.get("base_imponible") or 0, d.get("tipo_porcentaje") or 0, d.get("cuota") or 0,
        )

    return dumped
