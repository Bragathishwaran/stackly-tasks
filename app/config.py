"""Application configuration loaded from environment variables / .env file."""
from functools import lru_cache
from pathlib import Path
from typing import List

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

BASE_DIR = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    """Runtime settings. Values are read from the environment or a local .env."""

    model_config = SettingsConfigDict(
        env_file=BASE_DIR / ".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    PROJECT_NAME: str = "Doctor & Patient Management API"
    VERSION: str = "1.0.0"
    API_PREFIX: str = ""

    DATABASE_URL: str = "sqlite:///./doctor_patient.db"
    SQL_ECHO: bool = False

    SECRET_KEY: str = Field(..., min_length=16)
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30

    CORS_ORIGINS: List[str] = ["*"]

    @field_validator("CORS_ORIGINS", mode="before")
    @classmethod
    def _split_origins(cls, value: object) -> object:
        """Allow both JSON-ish lists and plain comma separated strings."""
        if isinstance(value, str) and not value.strip().startswith("["):
            return [origin.strip() for origin in value.split(",") if origin.strip()]
        return value


@lru_cache
def get_settings() -> Settings:
    """Cached settings accessor so .env is parsed once per process."""
    return Settings()


settings = get_settings()