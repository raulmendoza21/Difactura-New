from __future__ import annotations

import importlib


def create_client(*, api_key: str, base_url: str):
    try:
        mistral_module = importlib.import_module("mistralai")
    except ImportError as exc:
        try:
            mistral_module = importlib.import_module("mistralai.client")
        except ImportError:
            raise RuntimeError(
                "Dependencia mistralai no disponible. Anadela al entorno para usar el proveedor Mistral."
            ) from exc

    client_cls = getattr(mistral_module, "Mistral", None)
    if client_cls is None:
        try:
            legacy_module = importlib.import_module("mistralai.client")
        except ImportError:
            legacy_module = None
        client_cls = getattr(legacy_module, "Mistral", None) if legacy_module else None
    if client_cls is None:
        raise RuntimeError("No se pudo cargar el cliente Mistral desde la libreria mistralai")

    try:
        return client_cls(
            api_key=api_key,
            server_url=base_url,
        )
    except TypeError:
        return client_cls(api_key=api_key)
