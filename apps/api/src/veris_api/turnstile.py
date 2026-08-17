from __future__ import annotations

from urllib.parse import urlsplit

import httpx

from veris_api.config import Settings, get_settings


async def verify_turnstile(
    token: str | None,
    remote_ip: str,
    *,
    expected_action: str,
    settings: Settings | None = None,
) -> bool:
    runtime = settings or get_settings()
    if runtime.environment != "production" and not runtime.turnstile_secret_key:
        return True
    if not token:
        return False
    async with httpx.AsyncClient(timeout=8) as client:
        response = await client.post(
            "https://challenges.cloudflare.com/turnstile/v0/siteverify",
            data={
                "secret": runtime.turnstile_secret_key,
                "response": token,
                "remoteip": remote_ip,
            },
        )
    if response.status_code != 200:
        return False
    payload = response.json()
    expected_hostname = urlsplit(runtime.public_base_url).hostname
    return (
        isinstance(payload, dict)
        and payload.get("success") is True
        and bool(expected_hostname)
        and payload.get("hostname") == expected_hostname
        and payload.get("action") == expected_action
    )
