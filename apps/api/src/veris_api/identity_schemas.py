from __future__ import annotations

from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, Field, field_validator, model_validator

from veris_api.security import normalize_email


class EmailRequest(BaseModel):
    email: str = Field(min_length=3, max_length=320)

    @field_validator("email")
    @classmethod
    def validate_email(cls, value: str) -> str:
        return normalize_email(value)


class RegisterRequest(EmailRequest):
    password: str = Field(min_length=1, max_length=256)
    password_confirmation: str = Field(min_length=1, max_length=256)
    accept_terms: bool
    terms_version: str = Field(min_length=1, max_length=64)

    @model_validator(mode="after")
    def passwords_match(self) -> RegisterRequest:
        if self.password != self.password_confirmation:
            raise ValueError("Passwords do not match")
        if not self.accept_terms:
            raise ValueError("Terms must be accepted")
        return self


class LoginRequest(EmailRequest):
    password: str = Field(min_length=1, max_length=256)
    mfa_code: str | None = Field(default=None, min_length=6, max_length=32)


class TokenRequest(BaseModel):
    token: str = Field(min_length=32, max_length=256)


class ResetPasswordRequest(TokenRequest):
    password: str = Field(min_length=1, max_length=256)
    password_confirmation: str = Field(min_length=1, max_length=256)

    @model_validator(mode="after")
    def passwords_match(self) -> ResetPasswordRequest:
        if self.password != self.password_confirmation:
            raise ValueError("Passwords do not match")
        return self


class ChangePasswordRequest(BaseModel):
    current_password: str = Field(min_length=1, max_length=256)
    password: str = Field(min_length=1, max_length=256)
    password_confirmation: str = Field(min_length=1, max_length=256)

    @model_validator(mode="after")
    def passwords_match(self) -> ChangePasswordRequest:
        if self.password != self.password_confirmation:
            raise ValueError("Passwords do not match")
        return self


class GenericAuthResponse(BaseModel):
    accepted: bool = True
    message: str


class PublicAuthConfig(BaseModel):
    terms_version: str
    turnstile_site_key: str | None = None


class AllowanceResponse(BaseModel):
    day: date
    limit: int
    used: int
    remaining: int
    reset_at: datetime


class PreferenceResponse(BaseModel):
    display_name: str | None = None
    theme_id: str | None = None
    sidebar_width: int | None = None


class PreferenceUpdate(BaseModel):
    display_name: str | None = Field(default=None, max_length=32)
    theme_id: str | None = Field(default=None, max_length=48)
    sidebar_width: int | None = Field(default=None, ge=220, le=420)


class MeResponse(BaseModel):
    id: str
    email: str
    status: str
    roles: list[str]
    admin_mfa_enrolled: bool
    terms_version: str
    allowance: AllowanceResponse
    preferences: PreferenceResponse


class AccessRequestCreate(EmailRequest):
    turnstile_token: str | None = Field(default=None, max_length=2048)


class QuotaRequestCreate(BaseModel):
    requested_units: int = Field(default=10, ge=1, le=100)
    reason: str = Field(min_length=10, max_length=500)


class QuotaRequestResponse(BaseModel):
    id: str
    requested_units: int
    reason: str
    status: str
    created_at: datetime


class MFAConfirmRequest(BaseModel):
    code: str = Field(min_length=6, max_length=8)


class MFASetupResponse(BaseModel):
    secret: str
    provisioning_uri: str


class MFAConfirmResponse(BaseModel):
    recovery_codes: list[str]


class AllowlistCreate(EmailRequest):
    role: Literal["admin"] | None = None


class UserStatusUpdate(BaseModel):
    status: Literal["active", "suspended", "revoked"]


class QuotaGrantCreate(BaseModel):
    user_id: str = Field(min_length=36, max_length=36)
    units: int = Field(ge=1, le=1000)
    valid_on: date
    reason: str | None = Field(default=None, max_length=240)


class ResolveRequest(BaseModel):
    resolution: Literal["approved", "denied"]
    grant_units: int | None = Field(default=None, ge=1, le=1000)


class AdminOverviewResponse(BaseModel):
    users: int
    active_users: int
    pending_access_requests: int
    pending_quota_requests: int
    runs_today: int
    tokens_today: int
    estimated_cost_usd_today: str
    active_runs: int
    live_workers: int


AdminMetricsPeriod = Literal["15m", "hour", "day", "week", "month", "year"]


class AdminMetricPoint(BaseModel):
    started_at: datetime
    attempts: int
    runs: int
    request_tokens: int
    response_tokens: int
    total_tokens: int
    estimated_cost_usd: str


class AdminUserUsage(BaseModel):
    user_id: str
    email: str
    runs: int
    total_tokens: int
    estimated_cost_usd: str


class AdminModelUsage(BaseModel):
    provider: str
    model: str
    attempts: int
    total_tokens: int
    estimated_cost_usd: str
    average_latency_ms: int | None


class AdminMetricsResponse(BaseModel):
    period: AdminMetricsPeriod
    starts_at: datetime
    ends_at: datetime
    attempts: int
    runs: int
    request_tokens: int
    response_tokens: int
    total_tokens: int
    estimated_cost_usd: str
    points: list[AdminMetricPoint]
    users: list[AdminUserUsage]
    models: list[AdminModelUsage]


class AdminUserResponse(BaseModel):
    id: str
    email: str
    status: str
    roles: list[str]
    daily_run_limit: int | None
    runs_today: int
    created_at: datetime


class AdminAccessRequestResponse(BaseModel):
    id: str
    email: str
    status: str
    created_at: datetime


class AdminQuotaRequestResponse(BaseModel):
    id: str
    user_id: str
    email: str
    requested_units: int
    reason: str
    status: str
    created_at: datetime


class AdminAuditResponse(BaseModel):
    id: int
    actor_user_id: str | None
    action: str
    subject_type: str
    subject_id: str | None
    metadata: dict[str, object]
    created_at: datetime
