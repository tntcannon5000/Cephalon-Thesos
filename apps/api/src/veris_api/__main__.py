from __future__ import annotations

import uvicorn

from veris_api.config import get_settings
from veris_api.developer_logs import configure_developer_logging
from veris_api.runtime import launch_runtime


def main() -> None:
    settings = get_settings()
    if settings.environment == "development":
        configure_developer_logging(settings.log_level)
    launch_runtime()
    uvicorn.run(
        "veris_api.app:create_app",
        factory=True,
        host=settings.api_host,
        port=settings.api_port,
        reload=False,
        log_level=settings.log_level.lower(),
    )


if __name__ == "__main__":
    main()
