from __future__ import annotations

import asyncio
import json
import logging
import time
from collections.abc import AsyncGenerator, AsyncIterator
from contextlib import asynccontextmanager
from urllib.parse import urlparse

from fastapi import FastAPI, Header, HTTPException, Request, Response, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from sqlalchemy import text
from starlette.middleware.base import RequestResponseEndpoint
from starlette.middleware.trustedhost import TrustedHostMiddleware

from veris_api.auth import ensure_device_cookie, require_csrf, require_identity
from veris_api.config import get_settings
from veris_api.db.dispatch import worker_is_live
from veris_api.db.quota import ConcurrentRunLimitError, QuotaExceededError
from veris_api.db.repository import (
    ConversationTerminatedError,
    MessageNotFoundError,
    create_run,
    edit_message,
    events_after,
    get_run_for_user,
    request_run_cancellation,
)
from veris_api.db.session import dispose_engine, get_engine
from veris_api.developer_logs import configure_developer_logging, get_developer_log_buffer
from veris_api.routers.admin import router as admin_router
from veris_api.routers.auth import router as auth_router
from veris_api.routers.conversations import router as conversations_router
from veris_api.routers.me import router as me_router
from veris_api.schemas import (
    CreateRunRequest,
    CreateRunResponse,
    EditMessageRequest,
    EditMessageResponse,
    RunSnapshot,
)

TERMINAL_EVENTS = {"run.completed", "run.failed", "run.cancelled", "conversation.terminated"}
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncGenerator[None]:
    settings = get_settings()
    if settings.environment == "development":
        configure_developer_logging(settings.log_level)
        logger.info("Developer log stream is ready")
    yield
    await dispose_engine()


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(
        title="Thesos API",
        version="0.1.0",
        lifespan=lifespan,
        docs_url="/api/docs" if settings.environment == "development" else None,
        openapi_url="/api/openapi.json" if settings.environment == "development" else None,
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[settings.web_origin],
        allow_credentials=True,
        allow_methods=["GET", "POST", "PATCH", "DELETE"],
        allow_headers=["Content-Type", "Idempotency-Key", "X-CSRF-Token"],
    )
    configured_host = urlparse(settings.web_origin).hostname
    app.add_middleware(
        TrustedHostMiddleware,
        allowed_hosts=[
            host for host in (configured_host, "127.0.0.1", "localhost", "testserver") if host
        ],
    )
    app.include_router(auth_router)
    app.include_router(me_router)
    app.include_router(admin_router)
    app.include_router(conversations_router)

    @app.middleware("http")
    async def log_request(request: Request, call_next: RequestResponseEndpoint) -> Response:
        started_at = time.perf_counter()
        if request.method in {"POST", "PUT", "PATCH", "DELETE"}:
            origin = request.headers.get("origin")
            if (origin and origin != settings.web_origin) or (
                settings.environment == "production" and not origin
            ):
                return Response(status_code=status.HTTP_403_FORBIDDEN)
        try:
            response = await call_next(request)
        except Exception:
            logger.exception("%s %s failed", request.method, request.url.path)
            raise
        if not request.url.path.startswith("/api/v1/health"):
            elapsed_ms = (time.perf_counter() - started_at) * 1000
            logger.info(
                "%s %s -> %s in %.1fms",
                request.method,
                request.url.path,
                response.status_code,
                elapsed_ms,
            )
        ensure_device_cookie(request, response, settings=settings)
        return response

    @app.get("/api/v1/health/live")
    async def live() -> dict[str, str]:
        return {"status": "alive"}

    @app.get("/api/v1/health/ready")
    async def ready() -> dict[str, str]:
        async with get_engine().connect() as connection:
            await connection.execute(text("SELECT 1"))
        return {"status": "ready"}

    @app.get("/api/v1/health/worker")
    async def worker_health() -> dict[str, str]:
        if not await worker_is_live():
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail={"code": "worker_unavailable"},
            )
        return {"status": "ready"}

    @app.get("/api/v1/suggestions")
    async def suggestions(request: Request) -> dict[str, list[dict[str, str]]]:
        await require_identity(request)
        return {
            "suggestions": [
                {
                    "id": "incarnons",
                    "prompt": "Which Incarnon Genesis adapters are available this week?",
                    "meta": "Weekly rotation",
                },
                {
                    "id": "events",
                    "prompt": "What events and alerts are active right now?",
                    "meta": "Live state later",
                },
                {
                    "id": "archon",
                    "prompt": "Where does Archon Stretch drop?",
                    "meta": "Archive lookup",
                },
                {
                    "id": "build",
                    "prompt": "Build me a Steel Path setup for Gyre.",
                    "meta": "Build planning",
                },
            ]
        }

    if settings.environment == "development":

        @app.get("/api/v1/developer/logs")
        async def stream_developer_logs(
            request: Request,
            last_event_id: int = Header(default=0, alias="Last-Event-ID"),
        ) -> StreamingResponse:
            buffer = get_developer_log_buffer()

            async def log_stream() -> AsyncIterator[str]:
                sequence = last_event_id
                idle_ticks = 0
                while not await request.is_disconnected():
                    pending = buffer.after(sequence)
                    if pending:
                        idle_ticks = 0
                        for entry in pending:
                            sequence = entry.sequence
                            yield (f"id: {entry.sequence}\ndata: {json.dumps(entry.as_dict())}\n\n")
                    else:
                        idle_ticks += 1
                        if idle_ticks % 20 == 0:
                            yield "event: heartbeat\ndata: {}\n\n"
                        await asyncio.sleep(0.25)

            return StreamingResponse(
                log_stream(),
                media_type="text/event-stream",
                headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
            )

    @app.post(
        "/api/v1/runs", response_model=CreateRunResponse, status_code=status.HTTP_202_ACCEPTED
    )
    async def create_agent_run(
        body: CreateRunRequest,
        request: Request,
        response: Response,
        idempotency_key: str = Header(alias="Idempotency-Key", min_length=8, max_length=64),
    ) -> CreateRunResponse:
        identity = await require_identity(request)
        require_csrf(request, identity)
        try:
            created = await create_run(
                body,
                session_id=identity.session_id,
                idempotency_key=idempotency_key,
                user_id=identity.user_id,
                auth_session_id=identity.session_id,
            )
        except ConversationTerminatedError as error:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail={"code": "conversation_terminated"},
            ) from error
        except QuotaExceededError as error:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail={"code": "allowance_exhausted"},
            ) from error
        except ConcurrentRunLimitError as error:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail={"code": "concurrent_run_limit"},
            ) from error
        except MessageNotFoundError as error:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND) from error
        if created.created:
            logger.info(
                "Queued run %s for conversation %s",
                created.run_id,
                body.conversation_id,
            )
        return CreateRunResponse(
            run_id=created.run_id,
            event_url=f"/api/v1/runs/{created.run_id}/events",
            cancel_url=f"/api/v1/runs/{created.run_id}",
        )

    @app.get("/api/v1/runs/{run_id}", response_model=RunSnapshot)
    async def run_snapshot(
        run_id: str,
        request: Request,
    ) -> RunSnapshot:
        identity = await require_identity(request)
        run = await get_run_for_user(run_id, identity.user_id)
        if run is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
        return RunSnapshot(
            run_id=run.id,
            conversation_id=run.conversation_id,
            status=run.status,
            model=run.model,
            answer=run.answer_text,
            error_code=run.error_code,
            created_at=run.created_at,
            updated_at=run.updated_at,
        )

    @app.get("/api/v1/runs/{run_id}/events")
    async def stream_events(
        run_id: str,
        request: Request,
        last_event_id: int = Header(default=0, alias="Last-Event-ID"),
    ) -> StreamingResponse:
        identity = await require_identity(request)
        if await get_run_for_user(run_id, identity.user_id) is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)

        async def event_stream() -> AsyncIterator[str]:
            sequence = last_event_id
            idle_ticks = 0
            while not await request.is_disconnected():
                pending = await events_after(run_id, sequence)
                if pending:
                    idle_ticks = 0
                    for event in pending:
                        sequence = event.sequence
                        envelope = {
                            "event_id": event.sequence,
                            "run_id": event.run_id,
                            "type": event.event_type,
                            "created_at": event.created_at.isoformat(),
                            "payload": event.payload,
                        }
                        yield f"id: {event.sequence}\ndata: {json.dumps(envelope)}\n\n"
                        if event.event_type in TERMINAL_EVENTS:
                            return
                else:
                    idle_ticks += 1
                    if idle_ticks % 40 == 0:
                        yield ": heartbeat\n\n"
                    await asyncio.sleep(0.25)

        return StreamingResponse(
            event_stream(),
            media_type="text/event-stream",
            headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
        )

    @app.delete("/api/v1/runs/{run_id}", status_code=status.HTTP_204_NO_CONTENT)
    async def cancel_agent_run(
        run_id: str,
        request: Request,
    ) -> Response:
        identity = await require_identity(request)
        require_csrf(request, identity)
        if await get_run_for_user(run_id, identity.user_id) is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
        await request_run_cancellation(run_id)
        return Response(status_code=status.HTTP_204_NO_CONTENT)

    @app.patch(
        "/api/v1/conversations/{conversation_id}/messages/{message_id}",
        response_model=EditMessageResponse,
    )
    async def edit_conversation_message(
        conversation_id: str,
        message_id: str,
        _: EditMessageRequest,
        request: Request,
    ) -> EditMessageResponse:
        identity = await require_identity(request)
        require_csrf(request, identity)
        try:
            removed = await edit_message(
                conversation_id,
                message_id,
                session_id=identity.session_id,
                user_id=identity.user_id,
            )
        except MessageNotFoundError as error:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND) from error
        return EditMessageResponse(conversation_id=conversation_id, removed_message_ids=removed)

    return app
