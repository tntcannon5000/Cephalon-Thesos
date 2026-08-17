from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request, status

from veris_api.auth import require_csrf, require_identity
from veris_api.config import get_settings
from veris_api.db.identity import get_preferences, update_preferences
from veris_api.db.quota import allowance_for_user, create_quota_request
from veris_api.identity_schemas import (
    AllowanceResponse,
    MeResponse,
    PreferenceResponse,
    PreferenceUpdate,
    QuotaRequestCreate,
    QuotaRequestResponse,
)

router = APIRouter(prefix="/api/v1")


async def me_response(request: Request) -> MeResponse:
    identity = await require_identity(request)
    allowance = await allowance_for_user(identity.user_id)
    preferences = await get_preferences(identity.user_id)
    return MeResponse(
        id=identity.user_id,
        email=identity.email,
        status=identity.status,
        roles=sorted(identity.roles),
        admin_mfa_enrolled=identity.mfa_enrolled,
        terms_version=get_settings().terms_version,
        allowance=AllowanceResponse(
            day=allowance.day,
            limit=allowance.limit,
            used=allowance.used,
            remaining=allowance.remaining,
            reset_at=allowance.reset_at,
        ),
        preferences=PreferenceResponse(
            display_name=preferences.display_name,
            theme_id=preferences.theme_id,
            sidebar_width=preferences.sidebar_width,
        ),
    )


@router.get("/me", response_model=MeResponse)
async def get_me(request: Request) -> MeResponse:
    return await me_response(request)


@router.patch("/me/preferences", response_model=PreferenceResponse)
async def patch_preferences(body: PreferenceUpdate, request: Request) -> PreferenceResponse:
    identity = await require_identity(request)
    require_csrf(request, identity)
    current = await get_preferences(identity.user_id)
    preferences = await update_preferences(
        identity.user_id,
        display_name=(
            body.display_name if "display_name" in body.model_fields_set else current.display_name
        ),
        theme_id=body.theme_id if "theme_id" in body.model_fields_set else current.theme_id,
        sidebar_width=(
            body.sidebar_width
            if "sidebar_width" in body.model_fields_set
            else current.sidebar_width
        ),
    )
    return PreferenceResponse(
        display_name=preferences.display_name,
        theme_id=preferences.theme_id,
        sidebar_width=preferences.sidebar_width,
    )


@router.post(
    "/quota-requests",
    response_model=QuotaRequestResponse,
    status_code=status.HTTP_201_CREATED,
)
async def request_quota(body: QuotaRequestCreate, request: Request) -> QuotaRequestResponse:
    identity = await require_identity(request)
    require_csrf(request, identity)
    try:
        created = await create_quota_request(
            identity.user_id,
            body.requested_units,
            body.reason,
        )
    except ValueError as error:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"code": "quota_request_pending"},
        ) from error
    return QuotaRequestResponse(
        id=created.id,
        requested_units=created.requested_units,
        reason=created.reason,
        status=created.status,
        created_at=created.created_at,
    )
