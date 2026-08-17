from __future__ import annotations

import secrets

import pyotp
from fastapi import APIRouter, HTTPException, Request, Response, status

from veris_api.auth import (
    clear_auth_cookies,
    require_admin,
    require_csrf,
    require_identity,
    require_recent_auth,
)
from veris_api.db import admin
from veris_api.db.audit import record_audit_event
from veris_api.db.identity import (
    confirm_admin_mfa,
    get_admin_mfa,
    revoke_user_sessions,
    set_admin_mfa_secret,
)
from veris_api.identity_schemas import (
    AdminAccessRequestResponse,
    AdminAuditResponse,
    AdminMetricsPeriod,
    AdminMetricsResponse,
    AdminOverviewResponse,
    AdminQuotaRequestResponse,
    AdminUserResponse,
    AllowlistCreate,
    GenericAuthResponse,
    MFAConfirmRequest,
    MFAConfirmResponse,
    MFASetupResponse,
    QuotaGrantCreate,
    ResolveRequest,
    UserStatusUpdate,
)
from veris_api.security import decrypt_mfa_secret, encrypt_mfa_secret, ip_pseudonym, keyed_digest

router = APIRouter(prefix="/api/v1/admin")


async def _admin_identity(request: Request, *, mutation: bool = False):
    identity = await require_identity(request)
    require_admin(identity, enrolled=False)
    if mutation:
        require_csrf(request, identity)
        require_recent_auth(identity)
    return identity


@router.post("/mfa/setup", response_model=MFASetupResponse)
async def setup_mfa(request: Request) -> MFASetupResponse:
    identity = await require_identity(request)
    require_admin(identity, enrolled=False)
    require_csrf(request, identity)
    require_recent_auth(identity)
    current = await get_admin_mfa(identity.user_id)
    if current and current.confirmed_at:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"code": "mfa_already_enrolled"},
        )
    secret = pyotp.random_base32()
    await set_admin_mfa_secret(identity.user_id, encrypt_mfa_secret(secret))
    return MFASetupResponse(
        secret=secret,
        provisioning_uri=pyotp.TOTP(secret).provisioning_uri(
            name=identity.email,
            issuer_name="Thesos",
        ),
    )


@router.post("/mfa/confirm", response_model=MFAConfirmResponse)
async def confirm_mfa(
    body: MFAConfirmRequest,
    request: Request,
    response: Response,
) -> MFAConfirmResponse:
    identity = await require_identity(request)
    require_admin(identity, enrolled=False)
    require_csrf(request, identity)
    require_recent_auth(identity)
    current = await get_admin_mfa(identity.user_id)
    if current is None or current.confirmed_at:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"code": "mfa_setup_required"},
        )
    secret = decrypt_mfa_secret(current.encrypted_secret)
    if not pyotp.TOTP(secret).verify(body.code, valid_window=1):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"code": "mfa_code_invalid"},
        )
    alphabet = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"
    recovery_codes = [
        "".join(secrets.choice(alphabet) for _ in range(4))
        + "-"
        + "".join(secrets.choice(alphabet) for _ in range(4))
        for _ in range(10)
    ]
    recovery_hashes = [keyed_digest(code.casefold(), "mfa-recovery") for code in recovery_codes]
    await confirm_admin_mfa(identity.user_id, recovery_hashes)
    await revoke_user_sessions(identity.user_id, "mfa_enrolled")
    clear_auth_cookies(response)
    await record_audit_event(
        "admin.mfa_enrolled",
        "user",
        actor_user_id=identity.user_id,
        subject_id=identity.user_id,
        ip_pseudonym=ip_pseudonym(request),
    )
    return MFAConfirmResponse(recovery_codes=recovery_codes)


@router.get("/overview", response_model=AdminOverviewResponse)
async def get_overview(request: Request) -> AdminOverviewResponse:
    await _admin_identity(request)
    return AdminOverviewResponse.model_validate(await admin.overview())


@router.get("/metrics", response_model=AdminMetricsResponse)
async def get_metrics(
    request: Request,
    period: AdminMetricsPeriod = "day",
) -> AdminMetricsResponse:
    await _admin_identity(request)
    return AdminMetricsResponse.model_validate(await admin.usage_metrics(period))


@router.get("/users", response_model=list[AdminUserResponse])
async def get_users(request: Request) -> list[AdminUserResponse]:
    await _admin_identity(request)
    return [AdminUserResponse.model_validate(item) for item in await admin.list_users()]


@router.post("/allowlist", response_model=GenericAuthResponse)
async def add_allowlist(body: AllowlistCreate, request: Request) -> GenericAuthResponse:
    identity = await _admin_identity(request, mutation=True)
    entry = await admin.add_allowlist_entry(
        body.email,
        role=body.role,
        actor_user_id=identity.user_id,
    )
    await record_audit_event(
        "admin.allowlist_added",
        "allowlist",
        actor_user_id=identity.user_id,
        subject_id=entry.id,
        metadata={"role": body.role or "user"},
        ip_pseudonym=ip_pseudonym(request),
    )
    if body.role == "admin":
        return GenericAuthResponse(
            message=(
                "The address is eligible for registration and will receive administrator access."
            )
        )
    return GenericAuthResponse(message="The address is now eligible for registration.")


@router.get("/access-requests", response_model=list[AdminAccessRequestResponse])
async def get_access_requests(request: Request) -> list[AdminAccessRequestResponse]:
    await _admin_identity(request)
    return [
        AdminAccessRequestResponse(
            id=item.id,
            email=item.email,
            status=item.status,
            created_at=item.created_at,
        )
        for item in await admin.list_access_requests()
    ]


@router.post("/access-requests/{request_id}/resolve", response_model=GenericAuthResponse)
async def resolve_access(
    request_id: str,
    body: ResolveRequest,
    request: Request,
) -> GenericAuthResponse:
    identity = await _admin_identity(request, mutation=True)
    resolved = await admin.resolve_access_request(
        request_id,
        body.resolution,
        actor_user_id=identity.user_id,
    )
    if resolved is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
    await record_audit_event(
        "admin.access_request_resolved",
        "access_request",
        actor_user_id=identity.user_id,
        subject_id=request_id,
        metadata={"resolution": body.resolution},
        ip_pseudonym=ip_pseudonym(request),
    )
    return GenericAuthResponse(message="The access request has been resolved.")


@router.patch("/users/{user_id}/status", response_model=GenericAuthResponse)
async def set_user_status(
    user_id: str,
    body: UserStatusUpdate,
    request: Request,
) -> GenericAuthResponse:
    identity = await _admin_identity(request, mutation=True)
    if not await admin.update_user_status(
        user_id,
        body.status,
        actor_user_id=identity.user_id,
    ):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
    await record_audit_event(
        "admin.user_status_changed",
        "user",
        actor_user_id=identity.user_id,
        subject_id=user_id,
        metadata={"status": body.status},
        ip_pseudonym=ip_pseudonym(request),
    )
    return GenericAuthResponse(message="The account status has been updated.")


@router.post("/quota-grants", response_model=GenericAuthResponse)
async def grant_quota(body: QuotaGrantCreate, request: Request) -> GenericAuthResponse:
    identity = await _admin_identity(request, mutation=True)
    try:
        grant = await admin.create_grant(
            body.user_id,
            body.units,
            body.valid_on,
            body.reason,
            actor_user_id=identity.user_id,
        )
    except ValueError as error:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND) from error
    await record_audit_event(
        "admin.quota_granted",
        "quota_grant",
        actor_user_id=identity.user_id,
        subject_id=grant.id,
        metadata={"units": grant.units, "valid_on": grant.valid_on.isoformat()},
        ip_pseudonym=ip_pseudonym(request),
    )
    return GenericAuthResponse(message="The allowance grant has been recorded.")


@router.get("/quota-requests", response_model=list[AdminQuotaRequestResponse])
async def get_quota_requests(request: Request) -> list[AdminQuotaRequestResponse]:
    await _admin_identity(request)
    return [
        AdminQuotaRequestResponse.model_validate(item) for item in await admin.list_quota_requests()
    ]


@router.post("/quota-requests/{request_id}/resolve", response_model=GenericAuthResponse)
async def resolve_quota(
    request_id: str,
    body: ResolveRequest,
    request: Request,
) -> GenericAuthResponse:
    identity = await _admin_identity(request, mutation=True)
    resolved = await admin.resolve_quota_request(
        request_id,
        body.resolution,
        body.grant_units,
        actor_user_id=identity.user_id,
    )
    if resolved is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
    await record_audit_event(
        "admin.quota_request_resolved",
        "quota_request",
        actor_user_id=identity.user_id,
        subject_id=request_id,
        metadata={"resolution": body.resolution, "units": body.grant_units},
        ip_pseudonym=ip_pseudonym(request),
    )
    return GenericAuthResponse(message="The quota request has been resolved.")


@router.get("/users/{user_id}/sessions")
async def get_sessions(user_id: str, request: Request) -> list[dict[str, object]]:
    await _admin_identity(request)
    return await admin.list_user_sessions(user_id)


@router.delete("/sessions/{session_id}", response_model=GenericAuthResponse)
async def revoke_session(session_id: str, request: Request) -> GenericAuthResponse:
    identity = await _admin_identity(request, mutation=True)
    if not await admin.revoke_managed_session(session_id, identity.user_id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
    await record_audit_event(
        "admin.session_revoked",
        "auth_session",
        actor_user_id=identity.user_id,
        subject_id=session_id,
        ip_pseudonym=ip_pseudonym(request),
    )
    return GenericAuthResponse(message="The session has been revoked.")


@router.get("/failures")
async def get_failures(request: Request) -> list[dict[str, object]]:
    await _admin_identity(request)
    return await admin.recent_failures()


@router.get("/audit", response_model=list[AdminAuditResponse])
async def get_audit(request: Request) -> list[AdminAuditResponse]:
    await _admin_identity(request)
    return [
        AdminAuditResponse(
            id=item.id,
            actor_user_id=item.actor_user_id,
            action=item.action,
            subject_type=item.subject_type,
            subject_id=item.subject_id,
            metadata=item.metadata_json,
            created_at=item.created_at,
        )
        for item in await admin.list_audit_events()
    ]
