from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import AliasChoices, Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy.engine import make_url

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

    environment: Literal["development", "test", "production"] = Field(
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

    database_url: str = "postgresql+psycopg://thesos:thesos-local-only@127.0.0.1:5432/thesos"
    dbos_system_database_url: str = "postgresql://thesos:thesos-local-only@127.0.0.1:5432/thesos"

    session_cookie_secure: bool = False
    session_digest_key: str = "thesos-development-session-key"
    ip_hmac_key: str = "thesos-development-ip-key"
    admin_mfa_encryption_key: str = "thesos-development-mfa-key"
    trusted_proxy_cidrs: tuple[str, ...] = ("127.0.0.1/32", "::1/128")
    terms_version: str = "2026-08-17-private-alpha"
    public_base_url: str = "http://127.0.0.1:5173"
    session_idle_hours: int = Field(default=24 * 7, ge=1, le=24 * 30)
    session_absolute_hours: int = Field(default=24 * 30, ge=1, le=24 * 90)
    admin_session_idle_minutes: int = Field(default=30, ge=5, le=240)
    admin_session_absolute_hours: int = Field(default=8, ge=1, le=24)
    recent_auth_minutes: int = Field(default=15, ge=5, le=60)
    base_daily_run_limit: int = Field(default=10, ge=1, le=1000)
    device_daily_run_limit: int = Field(default=10, ge=1, le=1000)
    ip_daily_run_limit: int = Field(default=10, ge=1, le=1000)
    global_daily_run_limit: int = Field(default=100, ge=1, le=100_000)
    max_user_concurrent_runs: int = Field(default=2, ge=1, le=10)
    email_delivery: Literal["file", "resend"] = "file"
    email_from: str = "Thesos <archives@localhost>"
    resend_api_key: str = ""
    development_mail_directory: Path = REPO_ROOT / "var" / "dev-mail"
    turnstile_secret_key: str = ""
    turnstile_site_key: str = ""
    database_pool_size: int = Field(default=5, ge=1, le=20)
    database_max_overflow: int = Field(default=5, ge=0, le=20)
    dbos_database_pool_size: int = Field(default=5, ge=2, le=20)
    worker_concurrency: int = Field(default=2, ge=1, le=16)
    worker_poll_seconds: float = Field(default=0.5, ge=0.1, le=10)
    worker_lease_seconds: int = Field(default=60, ge=15, le=600)
    worker_max_dispatch_attempts: int = Field(default=3, ge=1, le=10)
    run_retention_days: int = Field(default=30, ge=1, le=365)
    retention_poll_seconds: int = Field(default=3600, ge=60, le=86_400)

    openrouter_api_key: str = ""
    openrouter_model: str = DEFAULT_OPENROUTER_MODEL
    openrouter_fallback_models: tuple[str, ...] = DEFAULT_OPENROUTER_FALLBACK_MODELS
    openrouter_allow_paid_models: bool = False
    openrouter_app_url: str = "http://127.0.0.1:5173"
    openrouter_app_title: str = "Thesos Local Alpha"

    @model_validator(mode="after")
    def validate_runtime(self) -> Settings:
        validate_model_route(
            self.openrouter_model,
            self.openrouter_fallback_models,
            allow_paid=self.openrouter_allow_paid_models,
        )
        database_backend = make_url(self.database_url).get_backend_name()
        dbos_backend = make_url(self.dbos_system_database_url).get_backend_name()
        if self.environment != "test" and (
            database_backend != "postgresql" or dbos_backend != "postgresql"
        ):
            raise ValueError("Development and production runtimes require PostgreSQL")
        if self.environment == "production":
            if not self.web_origin.startswith("https://"):
                raise ValueError("Production THESOS_WEB_ORIGIN must use HTTPS")
            if not self.session_cookie_secure:
                raise ValueError("Production session cookies must be secure")
            if not self.openrouter_api_key:
                raise ValueError("Production OPENROUTER_API_KEY is required")
            required_secrets = {
                "THESOS_SESSION_DIGEST_KEY": self.session_digest_key,
                "THESOS_IP_HMAC_KEY": self.ip_hmac_key,
                "THESOS_ADMIN_MFA_ENCRYPTION_KEY": self.admin_mfa_encryption_key,
            }
            for name, value in required_secrets.items():
                if len(value) < 32 or "development" in value:
                    raise ValueError(f"Production {name} must be an independent strong secret")
            if self.email_delivery != "resend" or not self.resend_api_key:
                raise ValueError("Production transactional email requires Resend configuration")
            if not self.turnstile_secret_key or not self.turnstile_site_key:
                raise ValueError("Production Turnstile configuration is required")
            if not self.trusted_proxy_cidrs:
                raise ValueError("Production trusted proxy CIDRs are required")
            if "local-only" in self.database_url or "local-only" in self.dbos_system_database_url:
                raise ValueError("Production database credentials cannot use local defaults")
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()
