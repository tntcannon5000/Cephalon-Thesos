from __future__ import annotations

import asyncio
import logging
import secrets
from datetime import UTC, datetime, timedelta

import pyotp
from fastapi import HTTPException, Request, Response, status

from veris_api.config import Settings, get_settings
from veris_api.db.identity import (
    IssuedSession,
    LoginMaterial,
    SessionIdentity,
    authenticate_session,
    consume_recovery_code,
    create_auth_session,
    get_login_material,
    update_password_hash,
)
from veris_api.security import (
    decrypt_mfa_secret,
    dummy_password_hash,
    keyed_digest,
    secure_equals,
    verify_password,
)

logger = logging.getLogger(__name__)
_password_semaphore = asyncio.Semaphore(4)


def session_cookie_name(settings: Settings | None = None) -> str:
    runtime = settings or get_settings()
    return "__Host-thesos_session" if runtime.session_cookie_secure else "thesos_session"


def csrf_cookie_name(settings: Settings | None = None) -> str:
    runtime = settings or get_settings()
    return "__Host-thesos_csrf" if runtime.session_cookie_secure else "thesos_csrf"


def device_cookie_name(settings: Settings | None = None) -> str:
    runtime = settings or get_settings()
    return "__Host-thesos_device" if runtime.session_cookie_secure else "thesos_device"


def set_auth_cookies(
    response: Response,
    issued: IssuedSession,
    *,
    settings: Settings | None = None,
) -> None:
    runtime = settings or get_settings()
    max_age = runtime.session_absolute_hours * 60 * 60
    response.set_cookie(
        session_cookie_name(runtime),
        issued.token,
        httponly=True,
        secure=runtime.session_cookie_secure,
        samesite="lax",
        path="/",
        max_age=max_age,
    )
    response.set_cookie(
        csrf_cookie_name(runtime),
        issued.csrf_token,
        httponly=False,
        secure=runtime.session_cookie_secure,
        samesite="lax",
        path="/",
        max_age=max_age,
    )


def clear_auth_cookies(response: Response, *, settings: Settings | None = None) -> None:
    runtime = settings or get_settings()
    for name in (session_cookie_name(runtime), csrf_cookie_name(runtime)):
        response.delete_cookie(
            name,
            secure=runtime.session_cookie_secure,
            httponly=name == session_cookie_name(runtime),
            samesite="lax",
            path="/",
        )


def ensure_device_cookie(
    request: Request,
    response: Response,
    *,
    settings: Settings | None = None,
) -> str:
    runtime = settings or get_settings()
    name = device_cookie_name(runtime)
    current = request.cookies.get(name) or getattr(request.state, "device_token", None)
    token = current or secrets.token_urlsafe(32)
    request.state.device_token = token
    if current is None:
        response.set_cookie(
            name,
            token,
            httponly=True,
            secure=runtime.session_cookie_secure,
            samesite="lax",
            path="/",
            max_age=60 * 60 * 24 * 365,
        )
    return token


async def optional_identity(request: Request) -> SessionIdentity | None:
    token = request.cookies.get(session_cookie_name())
    if not token:
        return None
    return await authenticate_session(token)


async def require_identity(request: Request) -> SessionIdentity:
    identity = await optional_identity(request)
    if identity is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"code": "authentication_required"},
        )
    return identity


def require_csrf(request: Request, identity: SessionIdentity) -> None:
    token = request.headers.get("x-csrf-token")
    cookie = request.cookies.get(csrf_cookie_name())
    if not token or not cookie or not secure_equals(token, cookie):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"code": "csrf_invalid"},
        )
    expected = keyed_digest(token, "csrf")
    if not secure_equals(expected, identity.csrf_digest):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"code": "csrf_invalid"},
        )


def require_admin(identity: SessionIdentity, *, enrolled: bool = True) -> None:
    if "admin" not in identity.roles:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
    if enrolled and not identity.mfa_enrolled:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"code": "admin_mfa_enrollment_required"},
        )


def require_recent_auth(identity: SessionIdentity, *, settings: Settings | None = None) -> None:
    runtime = settings or get_settings()
    if datetime.now(UTC) - identity.authenticated_at > timedelta(
        minutes=runtime.recent_auth_minutes
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"code": "recent_authentication_required"},
        )


async def verify_login(
    email: str,
    password: str,
    mfa_code: str | None,
) -> LoginMaterial | None:
    material = await get_login_material(email)
    verifier = material.password_hash or dummy_password_hash()
    async with _password_semaphore:
        verified, replacement = await asyncio.to_thread(verify_password, password, verifier)
    if (
        not verified
        or material.user_id is None
        or material.status != "active"
        or not material.password_hash
    ):
        return None

    if "admin" in material.roles and material.mfa and material.mfa.confirmed_at:
        if not mfa_code:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail={"code": "mfa_required"},
            )
        secret = decrypt_mfa_secret(material.mfa.encrypted_secret)
        valid_totp = pyotp.TOTP(secret).verify(mfa_code.replace(" ", ""), valid_window=1)
        valid_recovery = False
        if not valid_totp:
            recovery_digest = keyed_digest(mfa_code.casefold(), "mfa-recovery")
            valid_recovery = await consume_recovery_code(material.user_id, recovery_digest)
        if not valid_totp and not valid_recovery:
            return None
    if replacement:
        await update_password_hash(material.user_id, replacement)
    return material


async def issue_login_session(
    material: LoginMaterial,
    *,
    device_token: str | None,
    ip_signal: str,
) -> IssuedSession:
    if material.user_id is None:
        raise RuntimeError("Cannot issue a session without an account")
    return await create_auth_session(
        material.user_id,
        material.roles,
        device_token=device_token,
        ip_signal=ip_signal,
    )
