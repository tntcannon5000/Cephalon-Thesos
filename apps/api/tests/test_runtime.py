from __future__ import annotations

import asyncio

import pytest

from veris_api import runtime


async def test_cancel_run_cancels_and_awaits_active_provider_task(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    provider_cancelled = asyncio.Event()
    dbos_calls: list[str] = []

    async def provider_request() -> None:
        try:
            await asyncio.Event().wait()
        finally:
            provider_cancelled.set()

    task = asyncio.create_task(provider_request())
    await asyncio.sleep(0)
    runtime._tasks_by_run["run-1"] = task
    monkeypatch.setattr(
        runtime.DBOS,
        "cancel_workflow",
        lambda run_id: dbos_calls.append(run_id),
    )

    await runtime.cancel_run("run-1")

    assert task.cancelled()
    assert provider_cancelled.is_set()
    assert dbos_calls == ["run-1"]
    assert "run-1" not in runtime._tasks_by_run
