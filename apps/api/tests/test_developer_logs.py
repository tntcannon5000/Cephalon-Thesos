import logging

from veris_api.developer_logs import DeveloperLogBuffer, DeveloperLogHandler


def test_developer_log_buffer_is_bounded_and_sequence_is_monotonic() -> None:
    buffer = DeveloperLogBuffer(max_entries=2)

    first = buffer.append(layer="backend", level="info", logger="test", message="first")
    second = buffer.append(layer="backend", level="warning", logger="test", message="second")
    third = buffer.append(layer="ai", level="error", logger="test", message="third")

    assert first.sequence < second.sequence < third.sequence
    assert [entry.message for entry in buffer.after(0)] == ["second", "third"]
    assert buffer.after(second.sequence) == [third]


def test_developer_log_handler_honours_explicit_ai_layer() -> None:
    buffer = DeveloperLogBuffer()
    handler = DeveloperLogHandler(buffer)
    record = logging.LogRecord(
        name="veris_api.agent",
        level=logging.INFO,
        pathname=__file__,
        lineno=1,
        msg="model dispatched",
        args=(),
        exc_info=None,
    )
    record.developer_layer = "ai"

    handler.emit(record)

    [entry] = buffer.after(0)
    assert entry.layer == "ai"
    assert entry.level == "info"
    assert entry.message == "model dispatched"
