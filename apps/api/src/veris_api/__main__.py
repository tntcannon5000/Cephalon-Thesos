from __future__ import annotations

import uvicorn

from veris_api.config import get_settings
from veris_api.developer_logs import configure_console_logging, configure_developer_logging
from veris_api.event_loop import configure_platform_event_loop, uvicorn_loop_factory


def main() -> None:
    configure_platform_event_loop()
    settings = get_settings()
    configure_console_logging(settings.log_level)
    if settings.environment == "development":
        configure_developer_logging(settings.log_level)
    uvicorn.run(
        "veris_api.app:create_app",
        factory=True,
        host=settings.api_host,
        port=settings.api_port,
        reload=False,
        loop=uvicorn_loop_factory(),
        log_level=settings.log_level.lower(),
    )


if __name__ == "__main__":
    main()
