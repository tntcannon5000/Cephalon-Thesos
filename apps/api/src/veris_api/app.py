from __future__ import annotations

import asyncio
import json
import logging
import secrets
import time
from collections.abc import AsyncGenerator, AsyncIterator
from contextlib import asynccontextmanager

from fastapi import Cookie, FastAPI, Header, HTTPException, Request, Response, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from sqlalchemy import text
from starlette.middleware.base import RequestResponseEndpoint

from veris_api.config import get_settings
from veris_api.db.repository import (
    ConversationTerminatedError,
    MessageNotFoundError,
    create_run,
    edit_message,
    events_after,
    get_run_for_session,
    mark_run_cancelled,
)
from veris_api.db.session import dispose_engine, get_engine
from veris_api.developer_logs import configure_developer_logging, get_developer_log_buffer
from veris_api.runtime import cancel_run, submit_run
from veris_api.schemas import (
    CreateRunRequest,
    CreateRunResponse,
    EditMessageRequest,
    EditMessageResponse,
    RunSnapshot,
)

TERMINAL_EVENTS = {"run.completed", "run.failed", "run.cancelled", "conversation.terminated"}
SESSION_COOKIE = "veris_session"
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
        openapi_url="/api/openapi.json",
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[settings.web_origin],
        allow_credentials=True,
        allow_methods=["GET", "POST", "PATCH", "DELETE"],
        allow_headers=["Content-Type", "Idempotency-Key"],
    )

    @app.middleware("http")
    async def log_request(request: Request, call_next: RequestResponseEndpoint) -> Response:
        started_at = time.perf_counter()
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
        return response

    @app.get("/api/v1/health/live")
    async def live() -> dict[str, str]:
        return {"status": "alive"}

    @app.get("/api/v1/health/ready")
    async def ready() -> dict[str, str]:
        async with get_engine().connect() as connection:
            await connection.execute(text("SELECT 1"))
        return {"status": "ready"}

    @app.get("/api/v1/suggestions")
    async def suggestions() -> dict[str, list[dict[str, str]]]:
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
                            yield (
                                f"id: {entry.sequence}\n"
                                f"data: {json.dumps(entry.as_dict())}\n\n"
                            )
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
        response: Response,
        idempotency_key: str = Header(alias="Idempotency-Key", min_length=8, max_length=64),
        veris_session: str | None = Cookie(default=None),
    ) -> CreateRunResponse:
        session_id = veris_session or secrets.token_urlsafe(32)
        try:
            created = await create_run(
                body,
                session_id=session_id,
                idempotency_key=idempotency_key,
            )
        except ConversationTerminatedError as error:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail={"code": "conversation_terminated"},
            ) from error

        if veris_session is None:
            response.set_cookie(
                SESSION_COOKIE,
                session_id,
                httponly=True,
                secure=False,
                samesite="lax",
                max_age=60 * 60 * 24 * 30,
            )
        if created.created:
            logger.info(
                "Accepted run %s for conversation %s",
                created.run_id,
                body.conversation_id,
            )
            await submit_run(created.run_id)
        return CreateRunResponse(
            run_id=created.run_id,
            event_url=f"/api/v1/runs/{created.run_id}/events",
            cancel_url=f"/api/v1/runs/{created.run_id}",
        )

    @app.get("/api/v1/runs/{run_id}", response_model=RunSnapshot)
    async def run_snapshot(
        run_id: str,
        veris_session: str | None = Cookie(default=None),
    ) -> RunSnapshot:
        if veris_session is None:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED)
        run = await get_run_for_session(run_id, veris_session)
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
        veris_session: str | None = Cookie(default=None),
        last_event_id: int = Header(default=0, alias="Last-Event-ID"),
    ) -> StreamingResponse:
        if veris_session is None or await get_run_for_session(run_id, veris_session) is None:
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
        veris_session: str | None = Cookie(default=None),
    ) -> Response:
        if veris_session is None or await get_run_for_session(run_id, veris_session) is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
        await cancel_run(run_id)
        await mark_run_cancelled(run_id)
        return Response(status_code=status.HTTP_204_NO_CONTENT)

    @app.patch(
        "/api/v1/conversations/{conversation_id}/messages/{message_id}",
        response_model=EditMessageResponse,
    )
    async def edit_conversation_message(
        conversation_id: str,
        message_id: str,
        _: EditMessageRequest,
        veris_session: str | None = Cookie(default=None),
    ) -> EditMessageResponse:
        if veris_session is None:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED)
        try:
            removed = await edit_message(
                conversation_id,
                message_id,
                session_id=veris_session,
            )
        except MessageNotFoundError as error:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND) from error
        return EditMessageResponse(conversation_id=conversation_id, removed_message_ids=removed)

    return app
