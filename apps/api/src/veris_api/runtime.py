from __future__ import annotations

import asyncio
import logging
from contextlib import suppress
from time import monotonic

from dbos import DBOS, DBOSConfig, SetWorkflowID

from veris_api.agent import run_agent_workflow
from veris_api.config import get_settings
from veris_api.db.dispatch import (
    cancellation_requested,
    claim_next_run,
    heartbeat_worker,
    release_run_for_retry,
    renew_run_lease,
)
from veris_api.db.repository import mark_run_cancelled
from veris_api.db.retention import (
    purge_expired_runs,
    purge_expired_security_data,
    purge_stale_workers,
)

_launched = False
_tasks_by_run: dict[str, asyncio.Task[None]] = {}
logger = logging.getLogger(__name__)


def configure_runtime(worker_id: str) -> None:
    settings = get_settings()
    config: DBOSConfig = {
        "name": "thesos",
        "application_version": "0.2.0",
        "system_database_url": settings.dbos_system_database_url,
        "executor_id": worker_id,
        "sys_db_pool_size": settings.dbos_database_pool_size,
        "sys_db_polling_concurrency": settings.worker_concurrency,
        "max_executor_threads": settings.worker_concurrency * 2,
        "run_admin_server": False,
        "use_listen_notify": True,
    }
    DBOS(config=config)


def launch_runtime(worker_id: str) -> None:
    global _launched
    if _launched:
        return
    configure_runtime(worker_id)
    DBOS.launch()
    _launched = True
    logger.info("DBOS runtime launched for worker %s", worker_id)


async def execute_claimed_run(run_id: str, worker_id: str) -> None:
    if await cancellation_requested(run_id):
        await mark_run_cancelled(run_id)
        return

    async def execute() -> None:
        with SetWorkflowID(run_id):
            await run_agent_workflow(run_id)

    task = asyncio.create_task(execute(), name=f"thesos-workflow-{run_id}")
    _tasks_by_run[run_id] = task
    lease_renewed_at = monotonic()
    settings = get_settings()
    try:
        while not task.done():
            if await cancellation_requested(run_id):
                await cancel_run(run_id)
                await mark_run_cancelled(run_id)
                return
            if monotonic() - lease_renewed_at >= settings.worker_lease_seconds / 3:
                if not await renew_run_lease(run_id, worker_id):
                    await cancel_run(run_id)
                    return
                lease_renewed_at = monotonic()
            await asyncio.sleep(settings.worker_poll_seconds)
        await task
    except asyncio.CancelledError:
        await cancel_run(run_id)
        raise
    except Exception:
        logger.exception("Claimed workflow %s failed outside its agent boundary", run_id)
        await release_run_for_retry(run_id, worker_id, "worker_execution_failed")
    finally:
        if _tasks_by_run.get(run_id) is task:
            _tasks_by_run.pop(run_id, None)


async def cancel_run(run_id: str) -> None:
    task = _tasks_by_run.get(run_id)
    if task is not None and task is not asyncio.current_task() and not task.done():
        task.cancel()

    try:
        DBOS.cancel_workflow(run_id)
    except Exception:
        logger.exception("DBOS cancellation failed for run %s", run_id)

    if task is not None and task is not asyncio.current_task():
        with suppress(asyncio.CancelledError):
            await task
        if _tasks_by_run.get(run_id) is task:
            _tasks_by_run.pop(run_id, None)


async def run_worker_loop(worker_id: str, stop_event: asyncio.Event) -> None:
    settings = get_settings()
    active: dict[str, asyncio.Task[None]] = {}
    next_retention_at = 0.0
    await heartbeat_worker(worker_id, 0)
    logger.info(
        "Agent worker %s ready with concurrency=%s",
        worker_id,
        settings.worker_concurrency,
    )

    while not stop_event.is_set():
        completed = [run_id for run_id, task in active.items() if task.done()]
        for run_id in completed:
            task = active.pop(run_id)
            with suppress(asyncio.CancelledError):
                error = task.exception()
                if error is not None:
                    logger.error(
                        "Worker task %s escaped",
                        run_id,
                        exc_info=(type(error), error, error.__traceback__),
                    )

        while len(active) < settings.worker_concurrency:
            claimed = await claim_next_run(worker_id)
            if claimed is None:
                break
            active[claimed.run_id] = asyncio.create_task(
                execute_claimed_run(claimed.run_id, worker_id),
                name=f"thesos-claimed-{claimed.run_id}",
            )
            logger.info(
                "Worker %s claimed run %s attempt=%s",
                worker_id,
                claimed.run_id,
                claimed.dispatch_attempt,
            )

        await heartbeat_worker(worker_id, len(active))
        now = monotonic()
        if now >= next_retention_at:
            purged_ids = await purge_expired_runs()
            await purge_expired_security_data()
            await purge_stale_workers()
            for run_id in purged_ids:
                with suppress(Exception):
                    await DBOS.delete_workflow_async(run_id)
            if purged_ids:
                logger.info("Purged %s expired runs", len(purged_ids))
            next_retention_at = now + settings.retention_poll_seconds
        with suppress(TimeoutError):
            await asyncio.wait_for(stop_event.wait(), timeout=settings.worker_poll_seconds)

    await heartbeat_worker(worker_id, len(active), status="stopping")
    if active:
        await asyncio.gather(*active.values(), return_exceptions=True)
