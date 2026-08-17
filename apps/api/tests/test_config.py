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
