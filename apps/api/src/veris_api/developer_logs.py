from __future__ import annotations

import logging
import threading
from collections import deque
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from itertools import count
from time import time_ns
from typing import Literal

DeveloperLayer = Literal["backend", "ai"]
DeveloperLevel = Literal["debug", "info", "warning", "error"]


@dataclass(frozen=True, slots=True)
class DeveloperLogEntry:
    sequence: int
    timestamp: str
    layer: DeveloperLayer
    level: DeveloperLevel
    logger: str
    message: str

    def as_dict(self) -> dict[str, int | str]:
        return asdict(self)


class DeveloperLogBuffer:
    def __init__(self, max_entries: int = 600) -> None:
        self._entries: deque[DeveloperLogEntry] = deque(maxlen=max_entries)
        # Microsecond epoch IDs remain ordered across process restarts and are safe in JavaScript.
        self._sequence = count(time_ns() // 1_000)
        self._lock = threading.Lock()

    def append(
        self,
        *,
        layer: DeveloperLayer,
        level: DeveloperLevel,
        logger: str,
        message: str,
    ) -> DeveloperLogEntry:
        with self._lock:
            entry = DeveloperLogEntry(
                sequence=next(self._sequence),
                timestamp=datetime.now(UTC).isoformat(),
                layer=layer,
                level=level,
                logger=logger,
                message=message,
            )
            self._entries.append(entry)
            return entry

    def after(self, sequence: int) -> list[DeveloperLogEntry]:
        with self._lock:
            return [entry for entry in self._entries if entry.sequence > sequence]


def _level_name(level: int) -> DeveloperLevel:
    if level >= logging.ERROR:
        return "error"
    if level >= logging.WARNING:
        return "warning"
    if level <= logging.DEBUG:
        return "debug"
    return "info"


def _layer_name(record: logging.LogRecord) -> DeveloperLayer:
    explicit_layer = getattr(record, "developer_layer", None)
    if explicit_layer == "ai":
        return "ai"
    if record.name.startswith(("pydantic_ai", "httpx", "httpcore")):
        return "ai"
    return "backend"


class DeveloperLogHandler(logging.Handler):
    def __init__(self, buffer: DeveloperLogBuffer) -> None:
        super().__init__()
        self._buffer = buffer

    def emit(self, record: logging.LogRecord) -> None:
        try:
            self._buffer.append(
                layer=_layer_name(record),
                level=_level_name(record.levelno),
                logger=record.name,
                message=self.format(record),
            )
        except Exception:
            self.handleError(record)


_developer_buffer = DeveloperLogBuffer()
_developer_handler = DeveloperLogHandler(_developer_buffer)
_configuration_lock = threading.Lock()


def get_developer_log_buffer() -> DeveloperLogBuffer:
    return _developer_buffer


def configure_console_logging(level: str = "INFO") -> None:
    numeric_level = getattr(logging, level.upper(), logging.INFO)
    logging.basicConfig(
        level=numeric_level,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )
    logging.getLogger("veris_api").setLevel(numeric_level)


def configure_developer_logging(level: str = "INFO") -> None:
    numeric_level = getattr(logging, level.upper(), logging.INFO)
    with _configuration_lock:
        _developer_handler.setLevel(numeric_level)
        root_logger = logging.getLogger()
        if _developer_handler not in root_logger.handlers:
            root_logger.addHandler(_developer_handler)

        logging.getLogger("veris_api").setLevel(numeric_level)
        for logger_name in ("uvicorn.error", "uvicorn.access"):
            logger = logging.getLogger(logger_name)
            if _developer_handler not in logger.handlers:
                logger.addHandler(_developer_handler)
