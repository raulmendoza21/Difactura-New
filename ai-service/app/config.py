from pydantic import ConfigDict
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    model_config = ConfigDict(env_file=".env")

    tesseract_path: str = "/usr/bin/tesseract"
    ocr_language: str = "spa"
    confidence_threshold: float = 0.7
    max_file_size_mb: int = 50
    paddle_ocr_enabled: bool = True
    paddle_text_det_limit_side_len: int = 2500
    document_parser_provider: str = "local"
    document_parser_force_provider: str = ""
    document_parser_fallback_enabled: bool = True
    document_parser_fallback_provider: str = "local"
    mistral_api_key: str = ""
    mistral_base_url: str = "https://api.mistral.ai"
    mistral_ocr_model: str = "mistral-ocr-latest"
    mistral_file_visibility: str = "workspace"
    mistral_extract_header: bool = True
    mistral_extract_footer: bool = True
    mistral_table_format: str = "markdown"
    doc_ai_enabled: bool = False
    doc_ai_provider: str = "heuristic"
    doc_ai_base_url: str = ""
    doc_ai_api_key: str = ""
    doc_ai_model: str = ""
    doc_ai_timeout_seconds: int = 300
    doc_ai_max_pages: int = 4
    doc_ai_keep_alive: str = "1h"
    doc_ai_selective_enabled: bool = True
    doc_ai_fallback_confidence_threshold: float = 0.82
    doc_ai_fallback_missing_required_threshold: int = 2
    doc_ai_fallback_warning_threshold: int = 2
    allowed_mime_types: list[str] = [
        "application/pdf",
        "image/png",
        "image/jpeg",
        "image/tiff",
    ]


settings = Settings()
