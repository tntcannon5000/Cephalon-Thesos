from __future__ import annotations

import json
import re
from collections.abc import AsyncIterable
from typing import Any, cast

from pydantic_ai import FunctionToolCallEvent, FunctionToolResultEvent
from pydantic_ai.messages import (
    AgentStreamEvent,
    PartDeltaEvent,
    PartEndEvent,
    PartStartEvent,
    ThinkingPart,
    ThinkingPartDelta,
    ToolCallPart,
    ToolCallPartDelta,
)
from pydantic_ai.tools import RunContext
from pydantic_core import from_json

from veris_api.db.repository import add_event

OUTPUT_TOOL_NAME = "final_result"
SNAPSHOT_MIN_CHARS = 24
ANSWER_FIELD = re.compile(r'"answer"\s*:\s*"')

TOOL_ACTIVITY_LABELS = {
    "archive_search": "Searching archives",
    "warframe_market_search": "Checking market",
    "build_calculator": "Calculating build",
}


def _tool_label(tool_name: str) -> str:
    return TOOL_ACTIVITY_LABELS.get(tool_name, "Using tool")


def _output_payload(part: ToolCallPart | None) -> dict[str, Any] | None:
    if part is None:
        return None
    if isinstance(part.args, dict):
        return part.args
    if not isinstance(part.args, str):
        return None
    try:
        parsed = from_json(part.args, allow_partial=True)
    except ValueError:
        return None
    return cast(dict[str, Any], parsed) if isinstance(parsed, dict) else None


def _partial_json_string_field(arguments: str) -> str:
    """Decode the streamed answer string without treating it as authoritative output."""
    match = ANSWER_FIELD.search(arguments)
    if match is None:
        return ""

    encoded = arguments[match.end() :]
    escaped = False
    closing_quote: int | None = None
    for index, character in enumerate(encoded):
        if escaped:
            escaped = False
        elif character == "\\":
            escaped = True
        elif character == '"':
            closing_quote = index
            break
    if closing_quote is not None:
        encoded = encoded[:closing_quote]

    # A network chunk can end in the middle of an escape or a unicode code point.
    # Trim only that incomplete suffix and let the standard JSON decoder handle escapes.
    for trim in range(0, min(6, len(encoded)) + 1):
        candidate = encoded if trim == 0 else encoded[:-trim]
        try:
            decoded = json.loads(f'"{candidate}"')
        except json.JSONDecodeError:
            continue
        return decoded if isinstance(decoded, str) else ""
    return ""


def _streamed_answer(part: ToolCallPart | None) -> tuple[str | None, str]:
    payload = _output_payload(part)
    action = payload.get("action") if payload else None
    answer = payload.get("answer") if payload else None
    if answer is None and part is not None and isinstance(part.args, str):
        answer = _partial_json_string_field(part.args)
    return (action if isinstance(action, str) else None, str(answer or ""))


def _revealable_words(answer: str) -> str:
    boundary = max(answer.rfind(" "), answer.rfind("\n"), answer.rfind("\t"))
    return answer[: boundary + 1] if boundary >= 0 else ""


async def persist_agent_events_for_run(
    run_id: str,
    events: AsyncIterable[AgentStreamEvent],
) -> None:
    output_part: ToolCallPart | None = None
    answer_started = False
    last_snapshot = ""
    # mark_working emits the initial Thinking state before the model request begins.
    last_activity: tuple[str, str, str | None] | None = ("thinking", "Thinking", None)

    async def set_activity(kind: str, label: str, tool_name: str | None = None) -> None:
        nonlocal last_activity
        activity = (kind, label, tool_name)
        if activity == last_activity:
            return
        last_activity = activity
        payload: dict[str, Any] = {"kind": kind, "label": label}
        if tool_name:
            payload["tool"] = tool_name
        await add_event(run_id, "status.changed", payload)

    async def emit_snapshot(answer: str, *, final: bool = False) -> None:
        nonlocal answer_started, last_snapshot
        snapshot = answer if final else _revealable_words(answer)
        if not snapshot or snapshot == last_snapshot:
            return
        if not final and len(snapshot) - len(last_snapshot) < SNAPSHOT_MIN_CHARS:
            return
        if not answer_started:
            answer_started = True
            await add_event(run_id, "answer.started", {})
        last_snapshot = snapshot
        await add_event(run_id, "answer.snapshot", {"text": snapshot})

    async for event in events:
        if isinstance(event, PartStartEvent):
            if isinstance(event.part, ThinkingPart):
                await set_activity("thinking", "Thinking")
            elif isinstance(event.part, ToolCallPart) and event.part.tool_name == OUTPUT_TOOL_NAME:
                output_part = event.part
                await set_activity("composing", "Composing")
                action, answer = _streamed_answer(output_part)
                if action in {"answer", "urgent_safety"}:
                    await emit_snapshot(answer)
        elif isinstance(event, PartDeltaEvent):
            if isinstance(event.delta, ThinkingPartDelta):
                await set_activity("thinking", "Thinking")
            elif isinstance(event.delta, ToolCallPartDelta) and output_part is not None:
                updated = event.delta.apply(output_part)
                if isinstance(updated, ToolCallPart):
                    output_part = updated
                    action, answer = _streamed_answer(output_part)
                    if action in {"answer", "urgent_safety"}:
                        await emit_snapshot(answer)
        elif (
            isinstance(event, PartEndEvent)
            and isinstance(event.part, ToolCallPart)
            and event.part.tool_name == OUTPUT_TOOL_NAME
        ):
            output_part = event.part
            action, answer = _streamed_answer(output_part)
            if action in {"answer", "urgent_safety"}:
                await emit_snapshot(answer, final=True)
        elif isinstance(event, FunctionToolCallEvent):
            label = _tool_label(event.part.tool_name)
            await add_event(
                run_id,
                "tool.activity",
                {"phase": "started", "tool": event.part.tool_name, "label": label},
            )
            await set_activity("tool", label, event.part.tool_name)
        elif isinstance(event, FunctionToolResultEvent):
            await add_event(
                run_id,
                "tool.activity",
                {"phase": "completed", "tool": event.part.tool_name, "label": "Reviewing"},
            )
            await set_activity("thinking", "Reviewing", event.part.tool_name)


async def persist_agent_events(
    context: RunContext[None],
    events: AsyncIterable[AgentStreamEvent],
) -> None:
    if context.run_id is None:
        raise RuntimeError("Agent event stream has no run ID")
    await persist_agent_events_for_run(context.run_id, events)
