from __future__ import annotations

from datetime import UTC, datetime

from veris_api.db.models import AuditEvent
from veris_api.db.session import get_session_factory


async def record_audit_event(
    action: str,
    subject_type: str,
    *,
    actor_user_id: str | None = None,
    subject_id: str | None = None,
    metadata: dict[str, object] | None = None,
    ip_pseudonym: str | None = None,
) -> None:
    async with get_session_factory()() as session, session.begin():
        session.add(
            AuditEvent(
                actor_user_id=actor_user_id,
                action=action,
                subject_type=subject_type,
                subject_id=subject_id,
                metadata_json=metadata or {},
                ip_pseudonym=ip_pseudonym,
                created_at=datetime.now(UTC),
            )
        )
