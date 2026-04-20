"""API routes — /ai/process emitting the same contract as the v2 engine."""

from __future__ import annotations

import logging
import os
import re
import shutil
import tempfile
import unicodedata

from fastapi import APIRouter, File, Form, HTTPException, UploadFile

from app.config import Settings
from app.vision_engine import extract_invoice

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/ai", tags=["invoices"])

ALLOWED_EXTENSIONS = {".pdf", ".png", ".jpg", ".jpeg", ".tiff", ".tif", ".webp"}

_settings = Settings()

# ── Confidence scoring weights ──────────────────────────────────────────────
# Fields and their weights for the global confidence calculation.
# Critical fields weigh more; optional fields weigh less.
_FIELD_WEIGHTS = {
    "numero_factura": 1.5,
    "fecha": 1.5,
    "proveedor": 1.2,
    "cif_proveedor": 1.3,
    "cliente": 0.8,
    "cif_cliente": 0.8,
    "base_imponible": 1.5,
    "iva": 1.0,
    "iva_porcentaje": 0.7,
    "total": 1.8,
    "lineas": 1.0,
}


def _compute_field_confidence(data: dict, lineas: list, vision_result: dict) -> dict[str, float]:
    """Compute realistic per-field confidence based on presence, coherence, and inference."""
    fc: dict[str, float] = {}

    # Base: 0.92 if field present and looks reasonable, 0.0 if absent
    fc["numero_factura"] = 0.92 if data.get("numero_factura") else 0.0
    fc["fecha"] = 0.92 if data.get("fecha_emision") else 0.0
    fc["proveedor"] = 0.92 if data.get("emisor_nombre") else 0.0
    fc["cif_proveedor"] = _nif_confidence(data.get("emisor_nif"))
    fc["cliente"] = 0.92 if data.get("receptor_nombre") else 0.0
    fc["cif_cliente"] = _nif_confidence(data.get("receptor_nif"))
    fc["base_imponible"] = 0.92 if data.get("base_imponible") is not None else 0.0
    fc["iva_porcentaje"] = 0.90 if data.get("iva_porcentaje") is not None else 0.0
    fc["iva"] = 0.92 if data.get("iva_cuota") is not None else 0.0
    fc["total"] = 0.92 if data.get("total_factura") is not None else 0.0
    fc["lineas"] = 0.90 if data.get("lineas") else 0.0

    # ── Coherence checks: penalize if arithmetic doesn't add up ──
    base = _to_float(data.get("base_imponible"))
    iva = _to_float(data.get("iva_cuota"))
    total = _to_float(data.get("total_factura"))
    retencion = _to_float(data.get("retencion_importe"))
    recargo = _to_float(data.get("recargo_importe"))

    if total > 0:
        expected = base + iva + recargo - retencion
        diff = abs(expected - total)
        if diff > 0.10:
            # Totals don't match — reduce confidence on amounts
            penalty = min(0.30, diff / total) if total > 0 else 0.15
            fc["total"] = max(0.50, fc["total"] - penalty)
            fc["base_imponible"] = max(0.50, fc["base_imponible"] - penalty * 0.7)
            fc["iva"] = max(0.50, fc["iva"] - penalty * 0.7)

    # Line items coherence
    if lineas and base > 0:
        line_sum = sum(_to_float(ln.get("importe_total")) for ln in (data.get("lineas") or []))
        line_diff = abs(line_sum - base)
        if line_diff > max(base * 0.05, 2.0):
            fc["lineas"] = max(0.55, fc["lineas"] - 0.20)

    # If retries were needed (indicated by higher token usage), slightly reduce confidence
    usage = vision_result.get("usage", {})
    prompt_tokens = usage.get("prompt_tokens", 0) if isinstance(usage, dict) else 0
    if prompt_tokens > 8000:  # indicates retry calls happened
        for key in fc:
            if fc[key] > 0:
                fc[key] = max(0.50, fc[key] - 0.05)

    return fc


def _nif_confidence(nif_value) -> float:
    """Score NIF/CIF field: higher if format looks valid."""
    if not nif_value:
        return 0.0
    clean = re.sub(r"[\s\-]", "", str(nif_value)).upper()
    # Spanish NIF/CIF pattern: letter + 7 digits + letter/digit OR 8 digits + letter
    if re.match(r"^[A-Z]\d{7}[A-Z0-9]$", clean) or re.match(r"^\d{8}[A-Z]$", clean):
        return 0.94
    return 0.70  # present but unusual format


def _compute_global_confidence(field_confidence: dict[str, float]) -> float:
    """Weighted average of per-field confidences. Returns 0-1 ratio."""
    total_weight = 0.0
    weighted_sum = 0.0
    for field, weight in _FIELD_WEIGHTS.items():
        value = field_confidence.get(field, 0.0)
        # Only count fields that could have a value (don't penalize optional absent fields)
        if value > 0 or field in ("numero_factura", "fecha", "total", "base_imponible"):
            weighted_sum += value * weight
            total_weight += weight
    if total_weight == 0:
        return 0.0
    raw = weighted_sum / total_weight
    # Clamp to a realistic range — never output > 0.97 or exact round numbers
    return round(min(0.97, raw), 4)


def _clean_tax_id(value: str) -> str:
    return re.sub(r"[\s\-]", "", str(value or "")).upper()


def _to_float(value) -> float:
    try:
        return float(value) if value is not None else 0.0
    except (TypeError, ValueError):
        return 0.0


def _normalize_for_side(name: str) -> str:
    """Normalise a company name for loose comparison (accents, suffixes, punctuation)."""
    if not name:
        return ""
    n = unicodedata.normalize("NFD", str(name).upper())
    n = "".join(c for c in n if unicodedata.category(c) != "Mn")  # strip diacritics
    n = re.sub(r"\bS\.?L\.?U?\.?\b|\bS\.?A\.?U?\.?\b|\bS\.?C\.?\b|\bC\.?B\.?\b", "", n)
    n = re.sub(r'[.,;:\'"()\-]', " ", n)
    n = re.sub(r"\s+", " ", n).strip()
    return n


def _determine_operation_side(data: dict, company_tax_id: str, company_name: str = "") -> str:
    """Determine compra/venta from who is emisor vs receptor.

    Cross-checks extracted names against the company name to catch cases where
    the model accidentally places the company NIF in the wrong party field.
    """
    if not company_tax_id:
        return "unknown"
    cid = _clean_tax_id(company_tax_id)
    emisor_nif = _clean_tax_id(data.get("emisor_nif") or "")
    receptor_nif = _clean_tax_id(data.get("receptor_nif") or "")

    nif_emisor = bool(emisor_nif and emisor_nif == cid)
    nif_receptor = bool(receptor_nif and receptor_nif == cid)

    # Name-based cross-check: resolve conflicts when NIF is mis-assigned by the model
    if company_name and (nif_emisor or nif_receptor):
        cname = _normalize_for_side(company_name)
        ename = _normalize_for_side(data.get("emisor_nombre") or "")
        rname = _normalize_for_side(data.get("receptor_nombre") or "")
        name_in_emisor = bool(cname and ename and (cname in ename or ename in cname))
        name_in_receptor = bool(cname and rname and (cname in rname or rname in cname))

        # NIF says emisor but name says receptor → model swapped NIFs → it's a compra
        if nif_emisor and name_in_receptor and not name_in_emisor:
            logger.debug(
                "NIF/name conflict: NIF %s found in emisor_nif but company name "
                "matches receptor_nombre — treating as compra",
                cid,
            )
            return "compra"
        # NIF says receptor but name says emisor → model swapped NIFs → it's a venta
        if nif_receptor and name_in_emisor and not name_in_receptor:
            logger.debug(
                "NIF/name conflict: NIF %s found in receptor_nif but company name "
                "matches emisor_nombre — treating as venta",
                cid,
            )
            return "venta"

    if nif_emisor:
        return "venta"
    if nif_receptor:
        return "compra"
    return "unknown"


def _build_v2_response(vision_result: dict, company_tax_id: str, company_name: str = "") -> dict:
    """Map vision engine output → v2 engine contract so the backend adapter needs 0 changes."""
    data = vision_result["data"]
    operation_side = _determine_operation_side(data, company_tax_id, company_name)

    # Line items — map vision schema → v2 schema
    lineas = [
        {
            "descripcion": ln.get("descripcion") or "",
            "cantidad": _to_float(ln.get("cantidad")),
            "precio_unitario": _to_float(ln.get("precio_unitario")),
            "importe": _to_float(ln.get("importe_total")),
        }
        for ln in (data.get("lineas") or [])
    ]

    # Per-field confidence — realistic scoring based on presence, format, and coherence
    field_confidence = _compute_field_confidence(data, lineas, vision_result)
    global_confidence = _compute_global_confidence(field_confidence)

    # Detect inferred/missing fields for frontend indicators
    inferred_fields: list[str] = []
    missing_fields: list[str] = []
    for field_name, conf in field_confidence.items():
        if conf == 0.0:
            missing_fields.append(field_name)
        elif conf < 0.80:
            inferred_fields.append(field_name)

    # Tax breakdown → v2 format
    desglose = data.get("desglose_impuestos") or []
    tax_breakdown = [
        {
            "tax_regime": data.get("regimen_fiscal") or "",
            "rate": _to_float(t.get("tipo_porcentaje")),
            "taxable_base": _to_float(t.get("base_imponible")),
            "tax_amount": _to_float(t.get("cuota")),
        }
        for t in desglose
        if _to_float(t.get("tipo_porcentaje")) is not None
    ]

    # When there are multiple desglose entries, compute correct totals by summing
    if len(tax_breakdown) > 1:
        _base_sum = sum((t["taxable_base"] or 0) for t in tax_breakdown)
        _tax_sum = sum((t["tax_amount"] or 0) for t in tax_breakdown)
    else:
        _base_sum = _to_float(data.get("base_imponible"))
        _tax_sum = _to_float(data.get("iva_cuota"))

    # Withholdings
    retencion_importe = _to_float(data.get("retencion_importe"))
    withholdings = (
        [
            {
                "withholding_type": "IRPF",
                "rate": _to_float(data.get("retencion_porcentaje")),
                "taxable_base": _to_float(data.get("base_imponible")),
                "amount": retencion_importe,
            }
        ]
        if retencion_importe > 0
        else []
    )

    tipo = data.get("tipo_factura", "factura")
    is_rectificativa = "rectificativ" in tipo.lower()

    normalized_document = {
        "document_meta": {
            "extraction_provider": vision_result.get("model", "openai_vision"),
            "extraction_method": "vision",
            "extraction_confidence": global_confidence,
            "pages": vision_result.get("pages", 1),
            "elapsed_seconds": vision_result.get("elapsed_seconds"),
            "usage": vision_result.get("usage"),
            "warnings": (
                [f"missing:{f}" for f in missing_fields]
                + [f"inferred:{f}" for f in inferred_fields]
            ),
        },
        "classification": {
            "document_type": tipo,
            "invoice_side": "emitida" if operation_side == "venta" else "recibida" if operation_side == "compra" else "desconocida",
            "operation_kind": operation_side if operation_side != "unknown" else "desconocida",
            "is_rectificative": is_rectificativa,
            "is_simplified": "simplificad" in tipo.lower() or "ticket" in tipo.lower(),
        },
        "identity": {
            "invoice_number": data.get("numero_factura") or "",
            "issue_date": data.get("fecha_emision") or "",
            "rectified_invoice_number": data.get("numero_factura_rectificada") or "",
            "serie": data.get("serie") or "",
        },
        "issuer": {
            "name": data.get("emisor_nombre") or "",
            "legal_name": data.get("emisor_nombre") or "",
            "tax_id": data.get("emisor_nif") or "",
            "address": data.get("emisor_direccion") or "",
            "postal_code": data.get("emisor_cp") or "",
            "city": data.get("emisor_ciudad") or "",
            "country": data.get("emisor_pais") or "",
        },
        "recipient": {
            "name": data.get("receptor_nombre") or "",
            "legal_name": data.get("receptor_nombre") or "",
            "tax_id": data.get("receptor_nif") or "",
            "address": data.get("receptor_direccion") or "",
            "postal_code": data.get("receptor_cp") or "",
            "city": data.get("receptor_ciudad") or "",
            "country": data.get("receptor_pais") or "",
        },
        "totals": {
            "subtotal": _base_sum,
            "tax_total": _tax_sum,
            "withholding_total": retencion_importe,
            "total": _to_float(data.get("total_factura")),
            "amount_due": _to_float(data.get("total_factura")),
        },
        "tax_breakdown": tax_breakdown,
        "withholdings": withholdings,
        "line_items": lineas,
        "payment_info": {
            "forma_pago": data.get("forma_pago") or "",
            "condiciones_pago": data.get("condiciones_pago") or "",
            "cuenta_bancaria": data.get("cuenta_bancaria") or "",
            "moneda": data.get("moneda") or "EUR",
            "fecha_vencimiento": data.get("fecha_vencimiento") or "",
        },
        "observaciones": data.get("observaciones") or "",
        "_fromEngine": True,
    }

    return {
        "success": True,
        # ── v2 flat fields (used by backend adapter & persistence) ──────────
        "numero_factura": data.get("numero_factura") or "",
        "rectified_invoice_number": data.get("numero_factura_rectificada") or "",
        "fecha": data.get("fecha_emision") or "",
        "tipo_factura": tipo,
        "proveedor": data.get("emisor_nombre") or "",
        "cif_proveedor": data.get("emisor_nif") or "",
        "cliente": data.get("receptor_nombre") or "",
        "cif_cliente": data.get("receptor_nif") or "",
        "base_imponible": _base_sum,
        "iva_porcentaje": _to_float(data.get("iva_porcentaje")) if len(tax_breakdown) <= 1 else None,
        "iva": _tax_sum,
        "retencion_porcentaje": _to_float(data.get("retencion_porcentaje")),
        "retencion": retencion_importe,
        "total": _to_float(data.get("total_factura")),
        "tax_regime": data.get("regimen_fiscal") or "",
        "operation_side": operation_side,
        "document_type": tipo,
        "confianza": global_confidence,
        "lineas": lineas,
        # ── extra meta ──────────────────────────────────────────────────────
        "field_confidence": field_confidence,
        "inferred_fields": inferred_fields,
        "missing_fields": missing_fields,
        "normalized_document": normalized_document,
        "method": "vision",
        "provider": vision_result.get("model", "openai_vision"),
        "pages": vision_result.get("pages", 1),
        "warnings": (
            [f"missing:{f}" for f in missing_fields]
            + [f"inferred:{f}" for f in inferred_fields]
        ),
    }


@router.post("/process")
async def process_invoice(
    file: UploadFile = File(...),
    mime_type: str = Form("application/pdf"),
    company_name: str = Form(""),
    company_tax_id: str = Form(""),
    company_tax_ids: str = Form(""),  # accepted but not needed — we use emisor/receptor NIFs
):
    """Extract invoice data from an uploaded PDF or image using OpenAI Vision."""
    ext = os.path.splitext(file.filename or "")[1].lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(status_code=400, detail=f"Tipo de archivo no soportado: {ext}")

    if not _settings.openai_api_key:
        raise HTTPException(
            status_code=503,
            detail="Motor visual no configurado: falta OPENAI_API_KEY",
        )

    content = await file.read()
    max_bytes = _settings.max_file_size_mb * 1024 * 1024
    if len(content) > max_bytes:
        raise HTTPException(
            status_code=400,
            detail=f"Archivo demasiado grande. Máximo: {_settings.max_file_size_mb} MB",
        )

    tmp_dir = tempfile.mkdtemp()
    tmp_path = os.path.join(tmp_dir, file.filename or f"upload{ext}")

    try:
        with open(tmp_path, "wb") as f:
            f.write(content)

        company_context = None
        if company_name or company_tax_id:
            company_context = {"name": company_name, "tax_id": company_tax_id}

        vision_result = await extract_invoice(
            file_path=tmp_path,
            settings=_settings,
            company_context=company_context,
        )

        response = _build_v2_response(vision_result, company_tax_id, company_name=company_name)

        logger.info(
            "Processed %s — model=%s pages=%d elapsed=%.2fs side=%s",
            file.filename,
            vision_result["model"],
            vision_result["pages"],
            vision_result["elapsed_seconds"],
            response["operation_side"],
        )
        return response

    except ValueError as exc:
        logger.error("Extraction failed for %s: %s", file.filename, exc)
        raise HTTPException(status_code=500, detail=str(exc))
    except Exception as exc:
        logger.exception("Unexpected error processing %s", file.filename)
        raise HTTPException(status_code=500, detail=f"Error interno: {exc}")
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)
