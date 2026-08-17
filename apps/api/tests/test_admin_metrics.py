from __future__ import annotations

from datetime import UTC, datetime

from veris_api.db.admin import metrics_window


def test_fixed_metrics_window_aligns_and_fills_expected_buckets() -> None:
    window = metrics_window("hour", now=datetime(2026, 8, 17, 19, 37, 22, tzinfo=UTC))

    assert window.start == datetime(2026, 8, 17, 18, 40, tzinfo=UTC)
    assert window.end == datetime(2026, 8, 17, 19, 40, tzinfo=UTC)
    assert len(window.bucket_starts) == 12
    assert window.bucket_starts[-1] == datetime(2026, 8, 17, 19, 35, tzinfo=UTC)


def test_year_metrics_window_uses_calendar_months() -> None:
    window = metrics_window("year", now=datetime(2026, 8, 17, 19, 37, tzinfo=UTC))

    assert window.start == datetime(2025, 9, 1, tzinfo=UTC)
    assert window.end == datetime(2026, 9, 1, tzinfo=UTC)
    assert len(window.bucket_starts) == 12
    assert window.bucket_starts[-1] == datetime(2026, 8, 1, tzinfo=UTC)
