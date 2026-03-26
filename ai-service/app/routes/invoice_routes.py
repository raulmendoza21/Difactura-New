"""Invoice processing routes."""

import logging
import os
import shutil
import tempfile

from fastapi import APIRouter, File, Form, HTTPException, UploadFile

from app.config import settings
from app.services.document_intelligence import document_intelligence_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/ai", tags=["invoices"])

ALLOWED_EXTENSIONS = {".pdf", ".png", ".jpg", ".jpeg", ".tiff", ".tif"}


def _has_extracted_content(data) -> bool:
    return any(
        [
            bool(data.numero_factura),
            bool(data.fecha),
            bool(data.proveedor),
            bool(data.cif_proveedor),
            data.base_imponible > 0,
            data.iva > 0,
            data.total > 0,
            bool(data.lineas),
        ]
    )


@router.post("/process")
async def process_invoice(
    file: UploadFile = File(...),
    mime_type: str = Form("application/pdf"),
    company_name: str = Form(""),
    company_tax_id: str = Form(""),
):
    """Process an uploaded invoice file and extract structured data."""
    ext = os.path.splitext(file.filename or "")[1].lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=f"Tipo de archivo no soportado: {ext}",
        )

    tmp_dir = tempfile.mkdtemp()
    tmp_path = os.path.join(tmp_dir, file.filename or f"upload{ext}")

    try:
        with open(tmp_path, "wb") as handle:
            content = await file.read()
            max_bytes = settings.max_file_size_mb * 1024 * 1024
            if len(content) > max_bytes:
                raise HTTPException(
                    status_code=400,
                    detail=f"Archivo demasiado grande. Max: {settings.max_file_size_mb}MB",
                )
            handle.write(content)

        result = await document_intelligence_service.extract(
            file_path=tmp_path,
            filename=file.filename or "",
            mime_type=mime_type,
            company_context={
                "name": company_name,
                "tax_id": company_tax_id,
            },
        )
        raw_text = result["raw_text"]
        data = result["data"]
        if not raw_text.strip() and not _has_extracted_content(data):
            raise HTTPException(
                status_code=422,
                detail="No se pudo extraer contenido util del documento",
            )

        logger.info(
            "Processing complete: %s, method=%s, provider=%s, confidence=%s",
            file.filename,
            result["method"],
            result["provider"],
            data.confianza,
        )

        return {
            "success": result["success"],
            **data.model_dump(),
            "document_input": result["document_input"],
            "field_confidence": result["field_confidence"],
            "normalized_document": result["normalized_document"].model_dump(),
            "coverage": result["coverage"].model_dump(),
            "raw_text": raw_text,
            "method": result["method"],
            "provider": result["provider"],
            "pages": result["pages"],
            "warnings": result["warnings"],
        }
    except HTTPException:
        raise
    except Exception as exc:
        logger.error("Processing failed: %s", exc, exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Error procesando documento: {str(exc)}",
        )
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)


@router.post("/extract")
async def extract_invoice(
    file: UploadFile = File(...),
    mime_type: str = Form("application/pdf"),
    company_name: str = Form(""),
    company_tax_id: str = Form(""),
):
    """Document-to-JSON endpoint with provider metadata."""
    return await process_invoice(
        file=file,
        mime_type=mime_type,
        company_name=company_name,
        company_tax_id=company_tax_id,
    )
