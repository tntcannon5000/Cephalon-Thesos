from __future__ import annotations

import os
from collections import defaultdict
from datetime import UTC, datetime
from uuid import uuid4

import httpx
import pyotp
import pytest
from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import create_async_engine

from veris_api.app import create_app
from veris_api.config import get_settings
from veris_api.db.identity import seed_allowlist
from veris_api.db.models import DailyServiceUsage, DailySignalUsage
from veris_api.db.session import dispose_engine
from veris_api.routers import auth as auth_routes

POSTGRES_URL = os.getenv("THESOS_INTEGRATION_DATABASE_URL")
pytestmark = pytest.mark.skipif(not POSTGRES_URL, reason="PostgreSQL integration URL not set")


async def _truncate_private_alpha_data() -> None:
    assert POSTGRES_URL is not None
    engine = create_async_engine(POSTGRES_URL)
    async with engine.begin() as connection:
        await connection.execute(
            text(
                "TRUNCATE access_allowlist, access_request, user_account, rate_limit_bucket, "
                "daily_service_usage, daily_signal_usage CASCADE"
            )
        )
    await engine.dispose()


async def test_private_alpha_registration_ownership_quota_and_admin_mfa(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    assert POSTGRES_URL is not None
    if get_settings().database_url != POSTGRES_URL:
        pytest.skip("Integration and application database URLs must match for this test")

    await _truncate_private_alpha_data()
    captured: dict[str, list[str]] = defaultdict(list)

    async def capture_email(_: str, purpose: str, token: str) -> None:
        captured[purpose].append(token)

    monkeypatch.setattr(auth_routes, "_send_without_disclosure", capture_email)
    admin_email = "alpha-admin@example.com"
    tester_email = "alpha-tester@example.com"
    password = "Archive passage phrase 2026!"
    await seed_allowlist([admin_email, tester_email], admin_email=admin_email)
    app = create_app()
    transport = httpx.ASGITransport(app=app)

    try:
        async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as public:
            config = await public.get("/api/v1/auth/config")
            assert config.status_code == 200
            terms_version = config.json()["terms_version"]

            for email in (admin_email, tester_email):
                response = await public.post(
                    "/api/v1/auth/register",
                    json={
                        "email": email,
                        "password": password,
                        "password_confirmation": password,
                        "accept_terms": True,
                        "terms_version": terms_version,
                    },
                )
                assert response.status_code == 200

            unapproved = await public.post(
                "/api/v1/auth/register",
                json={
                    "email": "not-approved@example.com",
                    "password": password,
                    "password_confirmation": password,
                    "accept_terms": True,
                    "terms_version": terms_version,
                },
            )
            assert unapproved.status_code == 200
            assert len(captured["verify_email"]) == 2

            for token in captured["verify_email"]:
                verified = await public.post(
                    "/api/v1/auth/verify-email",
                    json={"token": token},
                )
                assert verified.status_code == 200

        async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as tester:
            login = await tester.post(
                "/api/v1/auth/login",
                json={"email": tester_email, "password": password},
            )
            assert login.status_code == 200
            csrf = tester.cookies.get("thesos_csrf")
            assert csrf

            refused = await tester.patch(
                "/api/v1/me/preferences",
                json={"display_name": "Test Tenno"},
            )
            assert refused.status_code == 403
            updated = await tester.patch(
                "/api/v1/me/preferences",
                headers={"X-CSRF-Token": csrf},
                json={"display_name": "Test Tenno"},
            )
            assert updated.status_code == 200

            conversation_id = str(uuid4())
            message_id = str(uuid4())
            conversation = await tester.put(
                f"/api/v1/conversations/{conversation_id}",
                headers={"X-CSRF-Token": csrf},
                json={
                    "title": "Damage calculation",
                    "title_state": "pending",
                    "pinned": False,
                    "terminated": False,
                    "updated_at": datetime.now(UTC).isoformat(),
                    "messages": [
                        {
                            "id": message_id,
                            "role": "user",
                            "content": "How does multishot work?",
                            "state": "complete",
                            "created_at": datetime.now(UTC).isoformat(),
                        }
                    ],
                },
            )
            assert conversation.status_code == 200

            create_payload = {
                "message": "How does multishot work?",
                "conversation_id": conversation_id,
                "message_id": message_id,
                "history": [],
                "mode": "auto",
            }
            created = await tester.post(
                "/api/v1/runs",
                headers={"X-CSRF-Token": csrf, "Idempotency-Key": "alpha-idempotency"},
                json=create_payload,
            )
            retried = await tester.post(
                "/api/v1/runs",
                headers={"X-CSRF-Token": csrf, "Idempotency-Key": "alpha-idempotency"},
                json=create_payload,
            )
            assert created.status_code == retried.status_code == 202
            assert created.json()["run_id"] == retried.json()["run_id"]
            allowance = (await tester.get("/api/v1/me")).json()["allowance"]
            assert allowance["used"] == 1
            assert allowance["remaining"] == 9

            cancelled = await tester.delete(
                created.json()["cancel_url"],
                headers={"X-CSRF-Token": csrf},
            )
            assert cancelled.status_code == 204
            allowance = (await tester.get("/api/v1/me")).json()["allowance"]
            assert allowance["used"] == 0
            assert allowance["remaining"] == 10

        async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as admin:
            login = await admin.post(
                "/api/v1/auth/login",
                json={"email": admin_email, "password": password},
            )
            assert login.status_code == 200
            csrf = admin.cookies.get("thesos_csrf")
            assert csrf
            assert (await admin.get("/api/v1/admin/overview")).status_code == 403
            assert (
                await admin.delete(
                    f"/api/v1/conversations/{conversation_id}",
                    headers={"X-CSRF-Token": csrf},
                )
            ).status_code == 404

            setup = await admin.post(
                "/api/v1/admin/mfa/setup",
                headers={"X-CSRF-Token": csrf},
            )
            assert setup.status_code == 200
            secret = setup.json()["secret"]
            confirmed = await admin.post(
                "/api/v1/admin/mfa/confirm",
                headers={"X-CSRF-Token": csrf},
                json={"code": pyotp.TOTP(secret).now()},
            )
            assert confirmed.status_code == 200
            assert len(confirmed.json()["recovery_codes"]) == 10

            requires_mfa = await admin.post(
                "/api/v1/auth/login",
                json={"email": admin_email, "password": password},
            )
            assert requires_mfa.status_code == 401
            assert requires_mfa.json()["detail"]["code"] == "mfa_required"
            relogin = await admin.post(
                "/api/v1/auth/login",
                json={
                    "email": admin_email,
                    "password": password,
                    "mfa_code": pyotp.TOTP(secret).now(),
                },
            )
            assert relogin.status_code == 200
            assert (await admin.get("/api/v1/admin/overview")).status_code == 200

        engine = create_async_engine(POSTGRES_URL)
        async with engine.connect() as connection:
            service_units = await connection.scalar(
                select(func.coalesce(func.sum(DailyServiceUsage.reserved_or_charged_units), 0))
            )
            signal_units = await connection.scalar(
                select(func.coalesce(func.sum(DailySignalUsage.reserved_or_charged_units), 0))
            )
        await engine.dispose()
        assert int(service_units or 0) == 0
        assert int(signal_units or 0) == 0
    finally:
        await dispose_engine()
        await _truncate_private_alpha_data()
