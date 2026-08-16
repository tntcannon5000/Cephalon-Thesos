from __future__ import annotations

import asyncio
import logging

from dbos import DBOS, DBOSConfig, SetWorkflowID

from veris_api.agent import run_agent_workflow
from veris_api.config import get_settings

_launched = False
_tasks: set[asyncio.Task[None]] = set()
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
    _tasks.add(task)

    def finish(completed: asyncio.Task[None]) -> None:
        _tasks.discard(completed)
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


def cancel_run(run_id: str) -> None:
    DBOS.cancel_workflow(run_id)
