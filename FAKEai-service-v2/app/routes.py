"""API routes — same contract as v1."""

import json
import logging
import os
import shutil
import tempfile

from fastapi import APIRouter, File, Form, HTTPException, UploadFile

from app.config import Settings
from app.pipeline.orchestrator import extract

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/ai", tags=["invoices"])

ALLOWED_EXTENSIONS = {".pdf", ".png", ".jpg", ".jpeg", ".tiff", ".tif"}

settings = Settings()


@router.post("/process")
async def process_invoice(
    file: UploadFile = File(...),
    mime_type: str = Form("application/pdf"),
    company_name: str = Form(""),
    company_tax_id: str = Form(""),
    company_tax_ids: str = Form(""),
):
    """Process an uploaded invoice and return structured data."""
    ext = os.path.splitext(file.filename or "")[1].lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(status_code=400, detail=f"Tipo de archivo no soportado: {ext}")

    # Parse company_tax_ids — accepts JSON array string or comma-separated
    tax_ids_list: list[str] = []
    if company_tax_ids:
        try:
            parsed = json.loads(company_tax_ids)
            if isinstance(parsed, list):
                tax_ids_list = [str(t).strip() for t in parsed if t]
        except json.JSONDecodeError:
            tax_ids_list = [t.strip() for t in company_tax_ids.split(",") if t.strip()]

    tmp_dir = tempfile.mkdtemp()
    tmp_path = os.path.join(tmp_dir, file.filename or f"upload{ext}")

    try:
        content = await file.read()
        max_bytes = settings.max_file_size_mb * 1024 * 1024
        if len(content) > max_bytes:
            raise HTTPException(
                status_code=400,
                detail=f"Archivo demasiado grande. Max: {settings.max_file_size_mb}MB",
            )

        with open(tmp_path, "wb") as f:
            f.write(content)

        result = await extract(
            file_path=tmp_path,
            mime_type=mime_type,
            company_name=company_name or None,
            company_tax_id=company_tax_id or None,
            company_tax_ids=tax_ids_list or None,
            settings=settings,
        )

        if not result.raw_text.strip() and not _has_content(result.data):
            raise HTTPException(
                status_code=422,
                detail="No se pudo extraer contenido útil del documento",
            )

        logger.info(
            "Processed %s — method=%s confidence=%.2f",
            file.filename, result.method, result.data.confianza,
        )
        return result.to_api_payload()

    except HTTPException:
        raise
    except Exception as exc:
        logger.error("Processing failed: %s", exc, exc_info=True)
        raise HTTPException(status_code=500, detail=f"Error procesando documento: {str(exc)}")
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)


@router.post("/extract")
async def extract_invoice(
    file: UploadFile = File(...),
    mime_type: str = Form("application/pdf"),
    company_name: str = Form(""),
    company_tax_id: str = Form(""),
    company_tax_ids: str = Form(""),
):
    """Alias for /process — same contract."""
    return await process_invoice(
        file=file, mime_type=mime_type,
        company_name=company_name, company_tax_id=company_tax_id,
        company_tax_ids=company_tax_ids,
    )


def _has_content(data) -> bool:
    return any([
        bool(data.numero_factura),
        bool(data.fecha),
        bool(data.proveedor),
        bool(data.cif_proveedor),
        bool(data.entities),
        (data.base_imponible or 0) > 0,
        (data.iva or 0) > 0,
        (data.total or 0) > 0,
        bool(data.lineas),
    ])
