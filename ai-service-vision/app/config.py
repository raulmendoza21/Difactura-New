import os
from pathlib import Path

from pydantic import ConfigDict, Field
from pydantic_settings import BaseSettings

_ROOT = Path(__file__).resolve().parents[1]


class Settings(BaseSettings):
    model_config = ConfigDict(
        env_file=os.getenv("AI_VISION_ENV_FILE", str(_ROOT / ".env")),
        extra="ignore",
        populate_by_name=True,
    )

    openai_api_key: str = Field(default="", alias="OPENAI_API_KEY")
    openai_base_url: str = Field(default="https://api.openai.com/v1", alias="OPENAI_BASE_URL")
    openai_model: str = Field(default="gpt-4.1", alias="OPENAI_MODEL")
    timeout_seconds: int = Field(default=120, alias="OPENAI_TIMEOUT_SECONDS")
    max_file_size_mb: int = Field(default=50, alias="MAX_FILE_SIZE_MB")
    max_pages: int = Field(default=8, alias="MAX_PAGES")
    image_dpi: int = Field(default=300, alias="IMAGE_DPI")
