import logging

from fastapi import APIRouter
from app.config import settings
from app.services.providers.registry import get_document_parser_provider

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/ai", tags=["health"])

@router.get("/health")
async def health_check():
    """Health check endpoint."""
    requested_provider = (settings.document_parser_force_provider or settings.document_parser_provider or "local").strip().lower()
    provider = get_document_parser_provider(requested_provider)
    provider_available = provider.is_available()
    fallback_provider = (settings.document_parser_fallback_provider or "local").strip().lower()
    fallback_available = get_document_parser_provider(fallback_provider).is_available() if settings.document_parser_fallback_enabled else False

    return {
        "status": "ok" if provider_available or fallback_available else "degraded",
        "service": "difactura-ai",
        "document_parser_provider": requested_provider,
        "document_parser_available": provider_available,
        "document_parser_fallback_enabled": settings.document_parser_fallback_enabled,
        "document_parser_fallback_provider": fallback_provider if settings.document_parser_fallback_enabled else "",
        "document_parser_fallback_available": fallback_available,
        "tesseract": "available" if fallback_available else "unavailable",
    }
