from __future__ import annotations

from typing import Any

import pytest

from veris_api.config import Settings
from veris_api.turnstile import verify_turnstile


class FakeResponse:
    status_code = 200

    def __init__(self, payload: dict[str, Any]) -> None:
        self.payload = payload

    def json(self) -> dict[str, Any]:
        return self.payload


class FakeClient:
    def __init__(self, payload: dict[str, Any]) -> None:
        self.payload = payload

    async def __aenter__(self) -> FakeClient:
        return self

    async def __aexit__(self, *_: object) -> None:
        return None

    async def post(self, *_: object, **__: object) -> FakeResponse:
        return FakeResponse(self.payload)


@pytest.mark.parametrize(
    ("payload", "expected"),
    [
        (
            {
                "success": True,
                "hostname": "chat.cephalonthesos.com",
                "action": "access-request",
            },
            True,
        ),
        (
            {
                "success": True,
                "hostname": "cephalonthesos.com",
                "action": "access-request",
            },
            False,
        ),
        (
            {
                "success": True,
                "hostname": "chat.cephalonthesos.com",
                "action": "different-action",
            },
            False,
        ),
    ],
)
async def test_turnstile_binds_token_to_hostname_and_action(
    monkeypatch: pytest.MonkeyPatch,
    payload: dict[str, Any],
    expected: bool,
) -> None:
    settings = Settings.model_construct(
        environment="production",
        public_base_url="https://chat.cephalonthesos.com",
        turnstile_secret_key="secret",
    )
    monkeypatch.setattr(
        "veris_api.turnstile.httpx.AsyncClient",
        lambda **_: FakeClient(payload),
    )
    assert (
        await verify_turnstile(
            "token",
            "203.0.113.4",
            expected_action="access-request",
            settings=settings,
        )
        is expected
    )
