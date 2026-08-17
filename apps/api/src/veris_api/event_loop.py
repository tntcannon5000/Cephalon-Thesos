from __future__ import annotations

import asyncio
import sys
from typing import Any, cast


def configure_platform_event_loop() -> None:
    if sys.platform != "win32":
        return
    policy_type = cast(Any, asyncio).WindowsSelectorEventLoopPolicy
    asyncio.set_event_loop_policy(policy_type())


def uvicorn_loop_factory() -> Any:
    if sys.platform == "win32":
        return asyncio.SelectorEventLoop
    return "auto"
