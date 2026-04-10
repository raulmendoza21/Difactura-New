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

CONFIDENCE = 0.95  # vision models are highly accurate on clear documents


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

    # Per-field confidence — all high since vision model read them directly
    field_confidence: dict[str, float] = {
        "numero_factura": CONFIDENCE if data.get("numero_factura") else 0.0,
        "fecha": CONFIDENCE if data.get("fecha_emision") else 0.0,
        "proveedor": CONFIDENCE if data.get("emisor_nombre") else 0.0,
        "cif_proveedor": CONFIDENCE if data.get("emisor_nif") else 0.0,
        "cliente": CONFIDENCE if data.get("receptor_nombre") else 0.0,
        "cif_cliente": CONFIDENCE if data.get("receptor_nif") else 0.0,
        "base_imponible": CONFIDENCE if data.get("base_imponible") is not None else 0.0,
        "iva_porcentaje": CONFIDENCE if data.get("iva_porcentaje") is not None else 0.0,
        "iva": CONFIDENCE if data.get("iva_cuota") is not None else 0.0,
        "total": CONFIDENCE if data.get("total_factura") is not None else 0.0,
        "lineas": CONFIDENCE if data.get("lineas") else 0.0,
    }

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
            "extraction_confidence": CONFIDENCE,
            "pages": vision_result.get("pages", 1),
            "elapsed_seconds": vision_result.get("elapsed_seconds"),
            "usage": vision_result.get("usage"),
            "warnings": [],
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
        "confianza": CONFIDENCE,
        "lineas": lineas,
        # ── extra meta ──────────────────────────────────────────────────────
        "field_confidence": field_confidence,
        "normalized_document": normalized_document,
        "method": "vision",
        "provider": vision_result.get("model", "openai_vision"),
        "pages": vision_result.get("pages", 1),
        "warnings": [],
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
        raise HTTPException(status_code=422, detail=str(exc))
    except Exception as exc:
        logger.exception("Unexpected error processing %s", file.filename)
        raise HTTPException(status_code=500, detail=f"Error interno: {exc}")
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)
