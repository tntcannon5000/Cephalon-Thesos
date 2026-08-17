from __future__ import annotations

import pytest
from pydantic import ValidationError

from veris_api.config import Settings


def test_production_rejects_sqlite() -> None:
    with pytest.raises(ValidationError, match="require PostgreSQL"):
        Settings(
            THESOS_ENV="production",
            THESOS_WEB_ORIGIN="https://cephalonthesos.com",
            SESSION_COOKIE_SECURE=True,
            DATABASE_URL="sqlite+aiosqlite:///unsafe.db",
            DBOS_SYSTEM_DATABASE_URL="sqlite:///unsafe-dbos.db",
            OPENROUTER_API_KEY="configured",
        )


def test_production_rejects_insecure_origin() -> None:
    with pytest.raises(ValidationError, match="must use HTTPS"):
        Settings(
            THESOS_ENV="production",
            THESOS_WEB_ORIGIN="http://cephalonthesos.com",
            SESSION_COOKIE_SECURE=True,
            DATABASE_URL="postgresql+psycopg://user:secret@db/thesos",
            DBOS_SYSTEM_DATABASE_URL="postgresql://user:secret@db/thesos",
            OPENROUTER_API_KEY="configured",
        )


def test_production_accepts_complete_private_alpha_configuration() -> None:
    settings = Settings(
        THESOS_ENV="production",
        THESOS_WEB_ORIGIN="https://cephalonthesos.com",
        SESSION_COOKIE_SECURE=True,
        DATABASE_URL="postgresql+psycopg://user:secret@db/thesos",
        DBOS_SYSTEM_DATABASE_URL="postgresql://user:secret@db/thesos",
        SESSION_DIGEST_KEY="session-secret-that-is-independent-and-long",
        IP_HMAC_KEY="ip-secret-that-is-also-independent-and-long",
        ADMIN_MFA_ENCRYPTION_KEY="mfa-secret-that-is-independent-and-long",
        TRUSTED_PROXY_CIDRS=("172.16.0.0/12",),
        EMAIL_DELIVERY="resend",
        RESEND_API_KEY="configured",
        TURNSTILE_SITE_KEY="configured",
        TURNSTILE_SECRET_KEY="configured",
        OPENROUTER_API_KEY="configured",
    )

    assert settings.environment == "production"
    assert settings.base_daily_run_limit == 10
