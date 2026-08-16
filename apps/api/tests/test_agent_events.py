from __future__ import annotations

from collections.abc import AsyncIterator

import pytest
from pydantic_ai.messages import (
    AgentStreamEvent,
    PartDeltaEvent,
    PartEndEvent,
    PartStartEvent,
    ToolCallPart,
    ToolCallPartDelta,
)

from veris_api import agent_events


async def event_stream() -> AsyncIterator[AgentStreamEvent]:
    yield PartStartEvent(
        index=0,
        part=ToolCallPart(
            tool_name="final_result",
            args='{"action":"answer","answer":"First word second word third word ',
            tool_call_id="output-1",
        ),
    )
    yield PartDeltaEvent(
        index=0,
        delta=ToolCallPartDelta(args_delta='fourth word fifth word.'),
    )
    yield PartDeltaEvent(
        index=0,
        delta=ToolCallPartDelta(args_delta='","conversation_title":"Word Test"}'),
    )
    yield PartEndEvent(
        index=0,
        part=ToolCallPart(
            tool_name="final_result",
            args={
                "action": "answer",
                "answer": "First word second word third word fourth word fifth word.",
                "conversation_title": "Word Test",
            },
            tool_call_id="output-1",
        ),
    )


async def test_answer_snapshots_are_progressive_and_final(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    recorded: list[tuple[str, dict[str, object]]] = []

    async def record_event(
        run_id: str, event_type: str, payload: dict[str, object]
    ) -> int:
        assert run_id == "run-1"
        recorded.append((event_type, payload))
        return len(recorded)

    monkeypatch.setattr(agent_events, "add_event", record_event)

    await agent_events.persist_agent_events_for_run("run-1", event_stream())

    snapshots = [
        payload["text"]
        for event_type, payload in recorded
        if event_type == "answer.snapshot"
    ]
    assert snapshots == [
        "First word second word third word ",
        "First word second word third word fourth word fifth word.",
    ]
    assert [event_type for event_type, _ in recorded].count("answer.started") == 1
    assert recorded[0] == ("status.changed", {"kind": "composing", "label": "Composing"})


def test_partial_answer_decoder_preserves_escapes() -> None:
    arguments = '{"action":"answer","answer":"Line one\\nA \\"quoted\\" word and more'

    assert agent_events._partial_json_string_field(arguments) == (
        'Line one\nA "quoted" word and more'
    )
