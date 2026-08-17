from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from veris_api.db.models import RateLimitBucket
from veris_api.db.session import get_session_factory


class RateLimitExceededError(Exception):
    def __init__(self, retry_after: int) -> None:
        self.retry_after = retry_after
        super().__init__("Rate limit exceeded")


def _window(now: datetime, seconds: int) -> datetime:
    epoch = int(now.timestamp())
    return datetime.fromtimestamp(epoch - (epoch % seconds), tz=UTC)


async def consume_rate_limit(
    action: str,
    subject_digest: str,
    *,
    limit: int,
    window_seconds: int,
) -> int:
    now = datetime.now(UTC)
    window_start = _window(now, window_seconds)
    expires_at = window_start + timedelta(seconds=window_seconds)
    for attempt in range(2):
        try:
            async with get_session_factory()() as session, session.begin():
                bucket = await session.scalar(
                    select(RateLimitBucket)
                    .where(
                        RateLimitBucket.action == action,
                        RateLimitBucket.subject_digest == subject_digest,
                        RateLimitBucket.window_start == window_start,
                    )
                    .with_for_update()
                )
                if bucket is None:
                    bucket = RateLimitBucket(
                        id=str(uuid4()),
                        action=action,
                        subject_digest=subject_digest,
                        window_start=window_start,
                        count=1,
                        expires_at=expires_at,
                    )
                    session.add(bucket)
                else:
                    bucket.count += 1
                await session.flush()
                if bucket.count > limit:
                    raise RateLimitExceededError(max(1, round((expires_at - now).total_seconds())))
                return bucket.count
        except IntegrityError:
            if attempt:
                raise
    raise RuntimeError("Rate-limit bucket could not be updated")
