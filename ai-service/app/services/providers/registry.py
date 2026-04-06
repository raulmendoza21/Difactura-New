from __future__ import annotations

from app.config import settings
from app.services.providers.base import DocumentParserProvider
from app.services.providers.local_document_parser_provider import local_document_parser_provider
from app.services.providers.mistral_document_parser_provider import mistral_document_parser_provider


def get_document_parser_provider(name: str | None = None) -> DocumentParserProvider:
    provider_name = (name or settings.document_parser_provider or "local").strip().lower()
    if provider_name in {"local", "local_bundle"}:
        return local_document_parser_provider
    if provider_name == "mistral":
        return mistral_document_parser_provider
    raise ValueError(f"Proveedor documental no soportado: {provider_name}")
