import logging

from fastapi import APIRouter
from app.services.ocr_service import ocr_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/ai", tags=["health"])

# Cache Tesseract availability at module level (won't change at runtime)
_tesseract_available: bool | None = None


@router.get("/health")
async def health_check():
    """Health check endpoint."""
    global _tesseract_available
    if _tesseract_available is None:
        _tesseract_available = ocr_service.is_available()
        logger.info("Tesseract availability cached: %s", _tesseract_available)

    return {
        "status": "ok" if _tesseract_available else "degraded",
        "service": "difactura-ai",
        "tesseract": "available" if _tesseract_available else "unavailable",
    }
