from __future__ import annotations

import logging

from app.config import settings
from app.models.document_provider import ProviderDocumentResult
from app.services.providers.registry import get_document_parser_provider

logger = logging.getLogger(__name__)


def resolve_primary_provider():
    configured_name = (settings.document_parser_force_provider or settings.document_parser_provider or "local").strip().lower()
    try:
        provider = get_document_parser_provider(configured_name)
        return configured_name, provider
    except Exception:
        if configured_name == "local":
            raise
        logger.exception("No se pudo resolver el proveedor documental configurado; se usara el local")
        return configured_name, get_document_parser_provider("local")


def resolve_fallback_provider(*, primary_provider: str):
    if not settings.document_parser_fallback_enabled:
        return None
    fallback_name = (settings.document_parser_fallback_provider or "local").strip().lower()
    if not fallback_name or fallback_name == primary_provider:
        return None
    return get_document_parser_provider(fallback_name)


def provider_trace(
    *,
    requested_provider: str,
    used_provider: str,
    fallback_applied: bool = False,
    fallback_reason: str = "",
    fallback_provider: str = "",
) -> dict[str, str | bool]:
    return {
        "requested_provider": requested_provider,
        "document_provider": used_provider,
        "fallback_provider": fallback_provider,
        "fallback_applied": fallback_applied,
        "fallback_reason": fallback_reason,
    }


def fallback_reason(exc: Exception) -> str:
    message = str(exc or "").lower()
    if "api key" in message or "configurada" in message:
        return "missing_credentials"
    if "timeout" in message:
        return "timeout"
    return "provider_error"


def extract_pdf_with_fallback(
    *,
    requested_provider: str,
    provider,
    file_path: str,
    include_page_images: bool,
) -> tuple[ProviderDocumentResult, dict[str, str | bool]]:
    try:
        return (
            provider.extract_pdf(file_path, include_page_images=include_page_images),
            provider_trace(
                requested_provider=requested_provider,
                used_provider=getattr(provider, "name", requested_provider),
            ),
        )
    except Exception as exc:
        fallback_provider_instance = resolve_fallback_provider(primary_provider=getattr(provider, "name", requested_provider))
        if fallback_provider_instance is None:
            raise
        logger.exception("El proveedor documental %s fallo con PDF; se usara el local", getattr(provider, "name", ""))
        return (
            fallback_provider_instance.extract_pdf(file_path, include_page_images=include_page_images),
            provider_trace(
                requested_provider=requested_provider,
                used_provider=getattr(fallback_provider_instance, "name", settings.document_parser_fallback_provider),
                fallback_applied=True,
                fallback_reason=fallback_reason(exc),
                fallback_provider=getattr(fallback_provider_instance, "name", settings.document_parser_fallback_provider),
            ),
        )


def extract_image_with_fallback(
    *,
    requested_provider: str,
    provider,
    file_path: str,
    mime_type: str,
    input_kind: str,
    include_page_images: bool,
) -> tuple[ProviderDocumentResult, dict[str, str | bool]]:
    try:
        return (
            provider.extract_image(
                file_path,
                mime_type=mime_type,
                input_kind=input_kind,
                include_page_images=include_page_images,
            ),
            provider_trace(
                requested_provider=requested_provider,
                used_provider=getattr(provider, "name", requested_provider),
            ),
        )
    except Exception as exc:
        fallback_provider_instance = resolve_fallback_provider(primary_provider=getattr(provider, "name", requested_provider))
        if fallback_provider_instance is None:
            raise
        logger.exception("El proveedor documental %s fallo con imagen; se usara el local", getattr(provider, "name", ""))
        return (
            fallback_provider_instance.extract_image(
                file_path,
                mime_type=mime_type,
                input_kind=input_kind,
                include_page_images=include_page_images,
            ),
            provider_trace(
                requested_provider=requested_provider,
                used_provider=getattr(fallback_provider_instance, "name", settings.document_parser_fallback_provider),
                fallback_applied=True,
                fallback_reason=fallback_reason(exc),
                fallback_provider=getattr(fallback_provider_instance, "name", settings.document_parser_fallback_provider),
            ),
        )
