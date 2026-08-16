from __future__ import annotations

import asyncio
import logging
from contextlib import suppress

from dbos import DBOS, DBOSConfig, SetWorkflowID

from veris_api.agent import run_agent_workflow
from veris_api.config import get_settings

_launched = False
_tasks_by_run: dict[str, asyncio.Task[None]] = {}
logger = logging.getLogger(__name__)


def configure_runtime() -> None:
    settings = get_settings()
    config: DBOSConfig = {
        "name": "thesos",
        "application_version": "0.1.0",
        "system_database_url": settings.dbos_system_database_url,
    }
    DBOS(config=config)


def launch_runtime() -> None:
    global _launched
    if _launched:
        return
    configure_runtime()
    DBOS.launch()
    _launched = True
    logger.info("DBOS runtime launched")


async def submit_run(run_id: str) -> None:
    async def execute() -> None:
        with SetWorkflowID(run_id):
            await run_agent_workflow(run_id)

    task = asyncio.create_task(execute(), name=f"veris-run-{run_id}")
    _tasks_by_run[run_id] = task

    def finish(completed: asyncio.Task[None]) -> None:
        if _tasks_by_run.get(run_id) is completed:
            _tasks_by_run.pop(run_id, None)
        if completed.cancelled():
            logger.warning("Workflow task %s was cancelled", run_id)
            return
        error = completed.exception()
        if error is not None:
            logger.error(
                "Workflow task %s escaped with an error",
                run_id,
                exc_info=(type(error), error, error.__traceback__),
            )

    task.add_done_callback(finish)
    logger.info("Submitted workflow task %s", run_id)


async def cancel_run(run_id: str) -> None:
    task = _tasks_by_run.get(run_id)
    if task is not None and not task.done():
        task.cancel()

    try:
        DBOS.cancel_workflow(run_id)
    except Exception:
        logger.exception("DBOS cancellation failed for run %s", run_id)

    if task is not None:
        with suppress(asyncio.CancelledError):
            await task
        if _tasks_by_run.get(run_id) is task:
            _tasks_by_run.pop(run_id, None)
