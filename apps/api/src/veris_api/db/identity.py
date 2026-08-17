from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from uuid import uuid4

from sqlalchemy import delete, select, update

from veris_api.config import Settings, get_settings
from veris_api.db.models import (
    AccessAllowlist,
    AccessRequest,
    AdminMFA,
    AuthSession,
    EmailActionToken,
    PasswordCredential,
    UserAccount,
    UserDevice,
    UserPreference,
    UserRole,
)
from veris_api.db.session import get_session_factory
from veris_api.security import device_digest, keyed_digest, random_token


@dataclass(frozen=True)
class RegistrationResult:
    created: bool
    email: str | None = None
    token: str | None = None


@dataclass(frozen=True)
class LoginMaterial:
    user_id: str | None
    email: str | None
    status: str | None
    password_hash: str
    roles: frozenset[str]
    mfa: AdminMFA | None


@dataclass(frozen=True)
class IssuedSession:
    id: str
    token: str
    csrf_token: str


@dataclass(frozen=True)
class SessionIdentity:
    user_id: str
    email: str
    status: str
    session_id: str
    roles: frozenset[str]
    csrf_digest: str
    authenticated_at: datetime
    mfa_enrolled: bool


async def seed_allowlist(emails: list[str], *, admin_email: str | None = None) -> int:
    now = datetime.now(UTC)
    inserted = 0
    async with get_session_factory()() as session, session.begin():
        if admin_email:
            existing_admin_email = await session.scalar(
                select(UserAccount.email)
                .join(UserRole, UserRole.user_id == UserAccount.id)
                .where(UserRole.role == "admin")
                .limit(1)
            )
            pending_admin = await session.scalar(
                select(AccessAllowlist.email)
                .where(AccessAllowlist.role_on_registration == "admin")
                .limit(1)
            )
            if (existing_admin_email and existing_admin_email != admin_email) or (
                pending_admin and pending_admin != admin_email
            ):
                raise RuntimeError("An initial administrator has already been configured")
        for email in emails:
            entry = await session.scalar(
                select(AccessAllowlist).where(AccessAllowlist.email == email).with_for_update()
            )
            role = "admin" if email == admin_email else None
            if entry is None:
                session.add(
                    AccessAllowlist(
                        id=str(uuid4()),
                        email=email,
                        status="active",
                        role_on_registration=role,
                        created_at=now,
                        updated_at=now,
                    )
                )
                inserted += 1
            elif role and entry.role_on_registration is None and entry.claimed_by_user_id is None:
                entry.role_on_registration = role
                entry.updated_at = now
    return inserted


def _new_action_token(
    user_id: str,
    purpose: str,
    lifetime: timedelta,
    now: datetime,
    *,
    settings: Settings,
) -> tuple[EmailActionToken, str]:
    token = random_token()
    return (
        EmailActionToken(
            id=str(uuid4()),
            user_id=user_id,
            purpose=purpose,
            token_digest=keyed_digest(token, purpose, settings=settings),
            expires_at=now + lifetime,
            created_at=now,
        ),
        token,
    )


async def register_account(
    email: str,
    password_hash: str,
    terms_version: str,
    *,
    settings: Settings | None = None,
) -> RegistrationResult:
    runtime = settings or get_settings()
    now = datetime.now(UTC)
    async with get_session_factory()() as session, session.begin():
        allowlist = await session.scalar(
            select(AccessAllowlist).where(AccessAllowlist.email == email).with_for_update()
        )
        existing = await session.scalar(select(UserAccount.id).where(UserAccount.email == email))
        if (
            allowlist is None
            or allowlist.status != "active"
            or allowlist.claimed_by_user_id is not None
            or existing is not None
        ):
            return RegistrationResult(created=False)

        user_id = str(uuid4())
        account = UserAccount(
            id=user_id,
            email=email,
            status="pending_verification",
            terms_version=terms_version,
            terms_accepted_at=now,
            created_at=now,
            updated_at=now,
        )
        session.add(account)
        # These models intentionally have no ORM relationships; establish the
        # parent row before staging credentials, roles, preferences, and tokens.
        await session.flush()
        session.add(
            PasswordCredential(
                user_id=user_id,
                password_hash=password_hash,
                changed_at=now,
            )
        )
        session.add(UserPreference(user_id=user_id, updated_at=now))
        if allowlist.role_on_registration:
            session.add(
                UserRole(
                    user_id=user_id,
                    role=allowlist.role_on_registration,
                    granted_at=now,
                )
            )
        action, token = _new_action_token(
            user_id,
            "verify_email",
            timedelta(hours=24),
            now,
            settings=runtime,
        )
        session.add(action)
        allowlist.claimed_by_user_id = user_id
        allowlist.updated_at = now
        return RegistrationResult(created=True, email=email, token=token)


async def create_access_request(
    email: str,
    *,
    ip_signal: str,
    device_signal: str | None,
) -> None:
    now = datetime.now(UTC)
    async with get_session_factory()() as session, session.begin():
        pending = await session.scalar(
            select(AccessRequest.id).where(
                AccessRequest.email == email,
                AccessRequest.status == "pending",
            )
        )
        if pending:
            return
        session.add(
            AccessRequest(
                id=str(uuid4()),
                email=email,
                status="pending",
                ip_pseudonym=ip_signal,
                device_digest=device_signal,
                created_at=now,
            )
        )


async def issue_action_token_for_email(
    email: str,
    purpose: str,
    *,
    settings: Settings | None = None,
) -> tuple[str, str] | None:
    runtime = settings or get_settings()
    now = datetime.now(UTC)
    async with get_session_factory()() as session, session.begin():
        account = await session.scalar(
            select(UserAccount).where(UserAccount.email == email).with_for_update()
        )
        if account is None:
            return None
        if purpose == "verify_email" and account.status != "pending_verification":
            return None
        if purpose == "reset_password" and account.status not in {"active", "suspended"}:
            return None
        await session.execute(
            update(EmailActionToken)
            .where(
                EmailActionToken.user_id == account.id,
                EmailActionToken.purpose == purpose,
                EmailActionToken.consumed_at.is_(None),
            )
            .values(consumed_at=now)
        )
        lifetime = timedelta(hours=24) if purpose == "verify_email" else timedelta(minutes=30)
        action, token = _new_action_token(
            account.id,
            purpose,
            lifetime,
            now,
            settings=runtime,
        )
        session.add(action)
        return account.email, token


async def verify_email_token(token: str, *, settings: Settings | None = None) -> bool:
    runtime = settings or get_settings()
    now = datetime.now(UTC)
    digest = keyed_digest(token, "verify_email", settings=runtime)
    async with get_session_factory()() as session, session.begin():
        action = await session.scalar(
            select(EmailActionToken)
            .where(
                EmailActionToken.token_digest == digest,
                EmailActionToken.purpose == "verify_email",
            )
            .with_for_update()
        )
        if action is None or action.consumed_at is not None or action.expires_at <= now:
            return False
        account = await session.get(UserAccount, action.user_id, with_for_update=True)
        if account is None or account.status != "pending_verification":
            return False
        action.consumed_at = now
        account.status = "active"
        account.email_verified_at = now
        account.updated_at = now
        return True


async def get_login_material(email: str) -> LoginMaterial:
    async with get_session_factory()() as session:
        account = await session.scalar(select(UserAccount).where(UserAccount.email == email))
        if account is None:
            return LoginMaterial(None, None, None, "", frozenset(), None)
        credential = await session.get(PasswordCredential, account.id)
        roles = frozenset(
            await session.scalars(select(UserRole.role).where(UserRole.user_id == account.id))
        )
        mfa = await session.get(AdminMFA, account.id)
        return LoginMaterial(
            account.id,
            account.email,
            account.status,
            credential.password_hash if credential else "",
            roles,
            mfa,
        )


async def update_password_hash(user_id: str, password_hash: str) -> None:
    async with get_session_factory()() as session, session.begin():
        credential = await session.get(PasswordCredential, user_id, with_for_update=True)
        if credential:
            credential.password_hash = password_hash
            credential.changed_at = datetime.now(UTC)


async def create_auth_session(
    user_id: str,
    roles: frozenset[str],
    *,
    device_token: str | None,
    ip_signal: str,
    settings: Settings | None = None,
) -> IssuedSession:
    runtime = settings or get_settings()
    now = datetime.now(UTC)
    token = random_token()
    csrf_token = random_token(24)
    is_admin = "admin" in roles
    idle_delta = (
        timedelta(minutes=runtime.admin_session_idle_minutes)
        if is_admin
        else timedelta(hours=runtime.session_idle_hours)
    )
    absolute_delta = (
        timedelta(hours=runtime.admin_session_absolute_hours)
        if is_admin
        else timedelta(hours=runtime.session_absolute_hours)
    )
    session_id = str(uuid4())
    hashed_device = device_digest(device_token, settings=runtime) if device_token else None
    async with get_session_factory()() as session, session.begin():
        session.add(
            AuthSession(
                id=session_id,
                user_id=user_id,
                token_digest=keyed_digest(token, "session", settings=runtime),
                csrf_digest=keyed_digest(csrf_token, "csrf", settings=runtime),
                device_digest=hashed_device,
                ip_pseudonym=ip_signal,
                authenticated_at=now,
                created_at=now,
                last_seen_at=now,
                idle_expires_at=now + idle_delta,
                absolute_expires_at=now + absolute_delta,
            )
        )
        if hashed_device:
            existing_device = await session.scalar(
                select(UserDevice).where(
                    UserDevice.user_id == user_id,
                    UserDevice.device_digest == hashed_device,
                )
            )
            if existing_device:
                existing_device.last_seen_at = now
            else:
                session.add(
                    UserDevice(
                        id=str(uuid4()),
                        user_id=user_id,
                        device_digest=hashed_device,
                        first_seen_at=now,
                        last_seen_at=now,
                    )
                )
    return IssuedSession(session_id, token, csrf_token)


async def authenticate_session(
    token: str,
    *,
    settings: Settings | None = None,
) -> SessionIdentity | None:
    runtime = settings or get_settings()
    now = datetime.now(UTC)
    digest = keyed_digest(token, "session", settings=runtime)
    async with get_session_factory()() as session, session.begin():
        auth_session = await session.scalar(
            select(AuthSession).where(AuthSession.token_digest == digest).with_for_update()
        )
        if (
            auth_session is None
            or auth_session.revoked_at is not None
            or auth_session.idle_expires_at <= now
            or auth_session.absolute_expires_at <= now
        ):
            return None
        account = await session.get(UserAccount, auth_session.user_id)
        if account is None or account.status != "active":
            return None
        roles = frozenset(
            await session.scalars(select(UserRole.role).where(UserRole.user_id == account.id))
        )
        is_admin = "admin" in roles
        if (now - auth_session.last_seen_at) >= timedelta(minutes=5):
            idle_delta = (
                timedelta(minutes=runtime.admin_session_idle_minutes)
                if is_admin
                else timedelta(hours=runtime.session_idle_hours)
            )
            auth_session.last_seen_at = now
            auth_session.idle_expires_at = min(now + idle_delta, auth_session.absolute_expires_at)
        mfa = await session.get(AdminMFA, account.id) if is_admin else None
        return SessionIdentity(
            user_id=account.id,
            email=account.email,
            status=account.status,
            session_id=auth_session.id,
            roles=roles,
            csrf_digest=auth_session.csrf_digest,
            authenticated_at=auth_session.authenticated_at,
            mfa_enrolled=bool(mfa and mfa.confirmed_at),
        )


async def revoke_session(session_id: str, reason: str = "logout") -> None:
    now = datetime.now(UTC)
    async with get_session_factory()() as session, session.begin():
        await session.execute(
            update(AuthSession)
            .where(AuthSession.id == session_id, AuthSession.revoked_at.is_(None))
            .values(revoked_at=now, revoke_reason=reason)
        )


async def revoke_user_sessions(
    user_id: str,
    reason: str,
    *,
    except_session_id: str | None = None,
) -> None:
    conditions = [AuthSession.user_id == user_id, AuthSession.revoked_at.is_(None)]
    if except_session_id:
        conditions.append(AuthSession.id != except_session_id)
    async with get_session_factory()() as session, session.begin():
        await session.execute(
            update(AuthSession)
            .where(*conditions)
            .values(revoked_at=datetime.now(UTC), revoke_reason=reason)
        )


async def reset_password_with_token(
    token: str,
    password_hash: str,
    *,
    settings: Settings | None = None,
) -> bool:
    runtime = settings or get_settings()
    now = datetime.now(UTC)
    digest = keyed_digest(token, "reset_password", settings=runtime)
    async with get_session_factory()() as session, session.begin():
        action = await session.scalar(
            select(EmailActionToken)
            .where(
                EmailActionToken.token_digest == digest,
                EmailActionToken.purpose == "reset_password",
            )
            .with_for_update()
        )
        if action is None or action.consumed_at is not None or action.expires_at <= now:
            return False
        account = await session.get(UserAccount, action.user_id, with_for_update=True)
        credential = await session.get(PasswordCredential, action.user_id, with_for_update=True)
        if account is None or credential is None or account.status == "revoked":
            return False
        action.consumed_at = now
        credential.password_hash = password_hash
        credential.changed_at = now
        await session.execute(
            update(AuthSession)
            .where(AuthSession.user_id == account.id, AuthSession.revoked_at.is_(None))
            .values(revoked_at=now, revoke_reason="password_reset")
        )
        return True


async def get_preferences(user_id: str) -> UserPreference:
    async with get_session_factory()() as session, session.begin():
        preferences = await session.get(UserPreference, user_id)
        if preferences is None:
            preferences = UserPreference(user_id=user_id, updated_at=datetime.now(UTC))
            session.add(preferences)
            await session.flush()
        return preferences


async def update_preferences(
    user_id: str,
    *,
    display_name: str | None,
    theme_id: str | None,
    sidebar_width: int | None,
) -> UserPreference:
    async with get_session_factory()() as session, session.begin():
        preferences = await session.get(UserPreference, user_id, with_for_update=True)
        if preferences is None:
            preferences = UserPreference(user_id=user_id)
            session.add(preferences)
        preferences.display_name = display_name
        preferences.theme_id = theme_id
        preferences.sidebar_width = sidebar_width
        preferences.updated_at = datetime.now(UTC)
        await session.flush()
        return preferences


async def get_admin_mfa(user_id: str) -> AdminMFA | None:
    async with get_session_factory()() as session:
        return await session.get(AdminMFA, user_id)


async def set_admin_mfa_secret(user_id: str, encrypted_secret: str) -> None:
    async with get_session_factory()() as session, session.begin():
        current = await session.get(AdminMFA, user_id, with_for_update=True)
        if current and current.confirmed_at:
            raise RuntimeError("Administrator MFA is already enrolled")
        if current:
            current.encrypted_secret = encrypted_secret
        else:
            session.add(AdminMFA(user_id=user_id, encrypted_secret=encrypted_secret))


async def confirm_admin_mfa(user_id: str, recovery_hashes: list[str]) -> None:
    async with get_session_factory()() as session, session.begin():
        current = await session.get(AdminMFA, user_id, with_for_update=True)
        if current is None:
            raise RuntimeError("Administrator MFA setup has not started")
        current.recovery_code_hashes = recovery_hashes
        current.confirmed_at = datetime.now(UTC)


async def consume_recovery_code(user_id: str, code_digest: str) -> bool:
    async with get_session_factory()() as session, session.begin():
        current = await session.get(AdminMFA, user_id, with_for_update=True)
        if current is None or code_digest not in current.recovery_code_hashes:
            return False
        current.recovery_code_hashes = [
            value for value in current.recovery_code_hashes if value != code_digest
        ]
        return True


async def purge_expired_identity_data(now: datetime | None = None) -> None:
    cutoff = now or datetime.now(UTC)
    session_cutoff = cutoff - timedelta(days=30)
    async with get_session_factory()() as session, session.begin():
        await session.execute(delete(EmailActionToken).where(EmailActionToken.expires_at < cutoff))
        await session.execute(
            delete(AuthSession).where(
                AuthSession.absolute_expires_at < session_cutoff,
                AuthSession.revoked_at.is_not(None),
            )
        )
