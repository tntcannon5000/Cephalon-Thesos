from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic import AliasChoices, Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from veris_api.model_policy import (
    DEFAULT_OPENROUTER_FALLBACK_MODELS,
    DEFAULT_OPENROUTER_MODEL,
    validate_model_route,
)

REPO_ROOT = Path(__file__).resolve().parents[4]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=REPO_ROOT / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    environment: str = Field(
        default="development",
        validation_alias=AliasChoices("THESOS_ENV", "VERIS_ENV"),
    )
    log_level: str = Field(
        default="INFO",
        validation_alias=AliasChoices("THESOS_LOG_LEVEL", "VERIS_LOG_LEVEL"),
    )
    api_host: str = Field(
        default="127.0.0.1",
        validation_alias=AliasChoices("THESOS_API_HOST", "VERIS_API_HOST"),
    )
    api_port: int = Field(
        default=8000,
        validation_alias=AliasChoices("THESOS_API_PORT", "VERIS_API_PORT"),
    )
    web_origin: str = Field(
        default="http://127.0.0.1:5173",
        validation_alias=AliasChoices("THESOS_WEB_ORIGIN", "VERIS_WEB_ORIGIN"),
    )

    database_url: str = "sqlite+aiosqlite:///./data/veris.db"
    dbos_system_database_url: str = "sqlite:///./data/dbos.sqlite"

    openrouter_api_key: str = ""
    openrouter_model: str = DEFAULT_OPENROUTER_MODEL
    openrouter_fallback_models: tuple[str, ...] = DEFAULT_OPENROUTER_FALLBACK_MODELS
    openrouter_allow_paid_models: bool = False
    openrouter_app_url: str = "http://127.0.0.1:5173"
    openrouter_app_title: str = "Thesos Local Alpha"

    @model_validator(mode="after")
    def validate_openrouter_route(self) -> Settings:
        validate_model_route(
            self.openrouter_model,
            self.openrouter_fallback_models,
            allow_paid=self.openrouter_allow_paid_models,
        )
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()
