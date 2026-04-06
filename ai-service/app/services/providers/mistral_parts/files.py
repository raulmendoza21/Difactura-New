from __future__ import annotations

from pathlib import Path


def upload_file(client, path: Path, *, visibility: str):
    with open(path, "rb") as handle:
        payload = {
            "file_name": path.name,
            "content": handle,
        }
        try:
            return client.files.upload(
                file=payload,
                purpose="ocr",
                visibility=visibility,
            )
        except TypeError:
            return client.files.upload(
                file=payload,
                purpose="ocr",
            )


def extract_file_id(upload_response) -> str:
    file_id = getattr(upload_response, "id", "") or upload_response.get("id", "")
    if not file_id:
        raise RuntimeError("Mistral no devolvio file_id al subir el documento")
    return str(file_id)


def delete_file_quietly(client, file_id: str, logger) -> None:
    try:
        client.files.delete(file_id=file_id)
    except Exception as exc:
        logger.warning("No se pudo borrar el archivo temporal de Mistral %s: %s", file_id, exc)
