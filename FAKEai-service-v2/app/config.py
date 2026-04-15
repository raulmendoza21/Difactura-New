import os
from pathlib import Path

from pydantic import ConfigDict, Field
from pydantic_settings import BaseSettings

_ROOT = Path(__file__).resolve().parents[1]


class Settings(BaseSettings):
    model_config = ConfigDict(
        env_file=os.getenv("AI_SERVICE_ENV_FILE", str(_ROOT / ".env")),
        extra="ignore",
        populate_by_name=True,
    )

    tesseract_path: str = "/usr/bin/tesseract"
    ocr_language: str = "spa"
    max_file_size_mb: int = 50
    paddle_ocr_enabled: bool = True

    # Mistral OCR (primary OCR provider)
    mistral_api_key: str = ""
    mistral_base_url: str = "https://api.mistral.ai"
    mistral_ocr_model: str = "mistral-ocr-latest"

    # AI layer — accepts both AI_* and DOC_AI_* env vars
    ai_enabled: bool = Field(default=False, alias="DOC_AI_ENABLED")
    ai_provider: str = Field(default="openai_compatible", alias="DOC_AI_PROVIDER")
    ai_base_url: str = Field(default="", alias="DOC_AI_BASE_URL")
    ai_api_key: str = Field(default="", alias="DOC_AI_API_KEY")
    ai_model: str = Field(default="", alias="DOC_AI_MODEL")
    ai_timeout_seconds: int = Field(default=120, alias="DOC_AI_TIMEOUT_SECONDS")
    ai_confidence_threshold: float = Field(default=0.5, alias="DOC_AI_FALLBACK_CONFIDENCE_THRESHOLD")


settings = Settings()
