from __future__ import annotations

import asyncio
import logging

from fastapi import APIRouter, HTTPException, Request, Response, status

from veris_api.auth import (
    clear_auth_cookies,
    ensure_device_cookie,
    issue_login_session,
    require_csrf,
    require_identity,
    set_auth_cookies,
    verify_login,
)
from veris_api.config import get_settings
from veris_api.db.audit import record_audit_event
from veris_api.db.identity import (
    create_access_request,
    get_login_material,
    issue_action_token_for_email,
    register_account,
    reset_password_with_token,
    revoke_session,
    revoke_user_sessions,
    update_password_hash,
    verify_email_token,
)
from veris_api.db.rate_limits import RateLimitExceededError, consume_rate_limit
from veris_api.email_delivery import EmailDeliveryError, send_action_email
from veris_api.identity_schemas import (
    AccessRequestCreate,
    ChangePasswordRequest,
    EmailRequest,
    GenericAuthResponse,
    LoginRequest,
    PublicAuthConfig,
    RegisterRequest,
    ResetPasswordRequest,
    TokenRequest,
)
from veris_api.security import (
    PasswordPolicyError,
    client_ip,
    device_digest,
    hash_password,
    ip_pseudonym,
    verify_password,
)
from veris_api.turnstile import verify_turnstile

router = APIRouter(prefix="/api/v1")
logger = logging.getLogger(__name__)

GENERIC_REGISTRATION = GenericAuthResponse(
    message="If this address is eligible, a verification message will arrive shortly."
)
GENERIC_EMAIL = GenericAuthResponse(
    message="If an eligible account matches, an email will arrive shortly."
)


@router.get("/auth/config", response_model=PublicAuthConfig)
async def public_auth_config() -> PublicAuthConfig:
    settings = get_settings()
    return PublicAuthConfig(
        terms_version=settings.terms_version,
        turnstile_site_key=settings.turnstile_site_key or None,
    )


def _rate_limit_response(error: RateLimitExceededError) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_429_TOO_MANY_REQUESTS,
        detail={"code": "rate_limited", "retry_after": error.retry_after},
        headers={"Retry-After": str(error.retry_after)},
    )


async def _send_without_disclosure(email: str, purpose: str, token: str) -> None:
    try:
        await send_action_email(email, purpose, token)
    except EmailDeliveryError:
        logger.exception("Transactional email delivery failed for purpose=%s", purpose)


async def _validated_password_hash(password: str) -> str:
    try:
        return await asyncio.to_thread(hash_password, password)
    except PasswordPolicyError as error:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"code": "password_policy", "message": str(error)},
        ) from error


@router.post("/auth/register", response_model=GenericAuthResponse)
async def register(
    body: RegisterRequest, request: Request, response: Response
) -> GenericAuthResponse:
    settings = get_settings()
    signal = ip_pseudonym(request, settings=settings)
    try:
        await consume_rate_limit("register", signal, limit=5, window_seconds=3600)
    except RateLimitExceededError as error:
        raise _rate_limit_response(error) from error
    if body.terms_version != settings.terms_version:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"code": "terms_version_changed", "terms_version": settings.terms_version},
        )
    password_hash = await _validated_password_hash(body.password)
    result = await register_account(body.email, password_hash, body.terms_version)
    ensure_device_cookie(request, response, settings=settings)
    if result.created and result.email and result.token:
        await _send_without_disclosure(result.email, "verify_email", result.token)
        await record_audit_event(
            "account.registered",
            "user",
            subject_id=None,
            ip_pseudonym=signal,
        )
    return GENERIC_REGISTRATION


@router.post("/auth/verify-email", response_model=GenericAuthResponse)
async def verify_email(body: TokenRequest) -> GenericAuthResponse:
    if not await verify_email_token(body.token):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"code": "invalid_or_expired_token"},
        )
    return GenericAuthResponse(message="Your email is verified. You may now log in.")


@router.post("/auth/resend-verification", response_model=GenericAuthResponse)
async def resend_verification(body: EmailRequest, request: Request) -> GenericAuthResponse:
    signal = ip_pseudonym(request)
    try:
        await consume_rate_limit("email_action", signal, limit=5, window_seconds=3600)
    except RateLimitExceededError as error:
        raise _rate_limit_response(error) from error
    issued = await issue_action_token_for_email(body.email, "verify_email")
    if issued:
        await _send_without_disclosure(issued[0], "verify_email", issued[1])
    return GENERIC_EMAIL


@router.post("/auth/password/forgot", response_model=GenericAuthResponse)
async def forgot_password(body: EmailRequest, request: Request) -> GenericAuthResponse:
    signal = ip_pseudonym(request)
    try:
        await consume_rate_limit("email_action", signal, limit=5, window_seconds=3600)
    except RateLimitExceededError as error:
        raise _rate_limit_response(error) from error
    issued = await issue_action_token_for_email(body.email, "reset_password")
    if issued:
        await _send_without_disclosure(issued[0], "reset_password", issued[1])
    return GENERIC_EMAIL


@router.post("/auth/password/reset", response_model=GenericAuthResponse)
async def reset_password(body: ResetPasswordRequest) -> GenericAuthResponse:
    password_hash = await _validated_password_hash(body.password)
    if not await reset_password_with_token(body.token, password_hash):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"code": "invalid_or_expired_token"},
        )
    return GenericAuthResponse(message="Your password has been replaced. Please log in again.")


@router.post("/auth/login", response_model=GenericAuthResponse)
async def login(body: LoginRequest, request: Request, response: Response) -> GenericAuthResponse:
    settings = get_settings()
    signal = ip_pseudonym(request, settings=settings)
    device_token = ensure_device_cookie(request, response, settings=settings)
    try:
        await consume_rate_limit("login_ip", signal, limit=10, window_seconds=900)
        await consume_rate_limit(
            "login_device",
            device_digest(device_token, settings=settings),
            limit=15,
            window_seconds=900,
        )
    except RateLimitExceededError as error:
        raise _rate_limit_response(error) from error
    material = await verify_login(body.email, body.password, body.mfa_code)
    if material is None:
        await record_audit_event(
            "auth.login_failed",
            "authentication",
            ip_pseudonym=signal,
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"code": "invalid_credentials"},
        )
    issued = await issue_login_session(
        material,
        device_token=device_token,
        ip_signal=signal,
    )
    set_auth_cookies(response, issued, settings=settings)
    await record_audit_event(
        "auth.login_succeeded",
        "user",
        actor_user_id=material.user_id,
        subject_id=material.user_id,
        ip_pseudonym=signal,
    )
    return GenericAuthResponse(message="Access granted.")


@router.post("/auth/logout", response_model=GenericAuthResponse)
async def logout(request: Request, response: Response) -> GenericAuthResponse:
    identity = await require_identity(request)
    require_csrf(request, identity)
    await revoke_session(identity.session_id)
    clear_auth_cookies(response)
    return GenericAuthResponse(message="You have been logged out.")


@router.post("/auth/password/change", response_model=GenericAuthResponse)
async def change_password(body: ChangePasswordRequest, request: Request) -> GenericAuthResponse:
    identity = await require_identity(request)
    require_csrf(request, identity)
    material = await get_login_material(identity.email)
    verified, _ = await asyncio.to_thread(
        verify_password,
        body.current_password,
        material.password_hash,
    )
    if not verified:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"code": "invalid_credentials"},
        )
    replacement = await _validated_password_hash(body.password)
    await update_password_hash(identity.user_id, replacement)
    await revoke_user_sessions(
        identity.user_id,
        "password_changed",
        except_session_id=identity.session_id,
    )
    return GenericAuthResponse(message="Your password has been changed.")


@router.post("/access-requests", response_model=GenericAuthResponse)
async def request_access(
    body: AccessRequestCreate,
    request: Request,
    response: Response,
) -> GenericAuthResponse:
    settings = get_settings()
    raw_ip = client_ip(request, settings=settings)
    signal = ip_pseudonym(request, settings=settings)
    device_token = ensure_device_cookie(request, response, settings=settings)
    try:
        await consume_rate_limit("access_request", signal, limit=3, window_seconds=86_400)
    except RateLimitExceededError as error:
        raise _rate_limit_response(error) from error
    if not await verify_turnstile(
        body.turnstile_token,
        raw_ip,
        expected_action="access-request",
        settings=settings,
    ):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"code": "challenge_required"},
        )
    await create_access_request(
        body.email,
        ip_signal=signal,
        device_signal=device_digest(device_token, settings=settings),
    )
    return GenericAuthResponse(
        message="Your request has been recorded. Access remains subject to approval."
    )
