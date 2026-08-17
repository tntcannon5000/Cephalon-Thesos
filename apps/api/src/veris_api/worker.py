from __future__ import annotations

import asyncio
import logging
import os
import signal
import socket
from contextlib import suppress
from uuid import uuid4

from dbos import DBOS

from veris_api.config import get_settings
from veris_api.db.session import dispose_engine
from veris_api.developer_logs import configure_console_logging, configure_developer_logging
from veris_api.event_loop import configure_platform_event_loop
from veris_api.runtime import launch_runtime, run_worker_loop

logger = logging.getLogger(__name__)


async def worker_main() -> None:
    settings = get_settings()
    configure_console_logging(settings.log_level)
    if settings.environment == "development":
        configure_developer_logging(settings.log_level)
    worker_id = os.getenv(
        "THESOS_WORKER_ID",
        f"{socket.gethostname()}-{os.getpid()}-{uuid4().hex[:8]}",
    )
    stop_event = asyncio.Event()
    loop = asyncio.get_running_loop()
    for signal_name in (signal.SIGINT, signal.SIGTERM):
        with suppress(NotImplementedError):
            loop.add_signal_handler(signal_name, stop_event.set)

    launch_runtime(worker_id)
    try:
        await run_worker_loop(worker_id, stop_event)
    finally:
        logger.info("Agent worker %s shutting down", worker_id)
        DBOS.destroy(workflow_completion_timeout_sec=30)
        await dispose_engine()


def main() -> None:
    configure_platform_event_loop()
    asyncio.run(worker_main())


if __name__ == "__main__":
    main()
