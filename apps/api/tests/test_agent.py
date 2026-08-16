from __future__ import annotations

import inspect

import pytest
from pydantic_ai import ModelRetry

from veris_api import agent as agent_module
from veris_api.agent import require_complete_answer
from veris_api.schemas import TurnResult


def test_complete_answer_is_accepted() -> None:
    result = TurnResult(action="answer", answer="A complete archive response.")

    assert require_complete_answer(result) is result


def test_cut_off_answer_is_retried() -> None:
    result = TurnResult(action="answer", answer="An unfinished archive response that")

    with pytest.raises(ModelRetry):
        require_complete_answer(result)


def test_restricted_action_does_not_require_answer_text() -> None:
    result = TurnResult(action="archive_unavailable")

    assert require_complete_answer(result) is result


async def test_title_event_precedes_completed_event(monkeypatch: pytest.MonkeyPatch) -> None:
    events: list[tuple[str, dict[str, object]]] = []

    async def record_event(
        run_id: str, event_type: str, payload: dict[str, object]
    ) -> None:
        assert run_id == "run-1"
        events.append((event_type, payload))

    async def ignore_call(*args: object, **kwargs: object) -> None:
        del args, kwargs

    monkeypatch.setattr(agent_module, "add_event", record_event)
    monkeypatch.setattr(agent_module, "set_message_safety", ignore_call)
    monkeypatch.setattr(agent_module, "set_run_status", ignore_call)

    persist_turn_result = inspect.unwrap(agent_module.persist_turn_result)
    await persist_turn_result(
        "run-1",
        "message-1",
        TurnResult(
            action="answer",
            answer="Void Relics contain Prime rewards.",
            conversation_title="Void Relic Rewards",
        ),
    )

    event_types = [event_type for event_type, _ in events]
    assert event_types[-2:] == ["conversation.titled", "run.completed"]
    assert events[-2][1] == {"title": "Void Relic Rewards"}
