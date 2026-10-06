"""Time source and ISO-8601 helpers.

All timestamps are timezone-aware. They are stored in UTC (``+00:00``) as ISO-8601 text and
converted to the station's local time only for display and reports.
"""

from __future__ import annotations

import threading
from datetime import UTC, datetime, timedelta
from typing import Protocol


class Clock(Protocol):
    def now(self) -> datetime:
        """Current time, timezone-aware (UTC)."""
        ...


class SystemClock:
    def now(self) -> datetime:
        return datetime.now(UTC)


class FakeClock:
    """Deterministic clock for tests. ``advance()`` moves time forward."""

    def __init__(self, start: datetime | None = None) -> None:
        self._now = start or datetime(2026, 1, 5, 8, 0, 0, tzinfo=UTC)
        if self._now.tzinfo is None:
            raise ValueError("FakeClock needs a timezone-aware start time")
        self._lock = threading.Lock()

    def now(self) -> datetime:
        with self._lock:
            return self._now

    def advance(self, seconds: float = 0.0, **kwargs: float) -> datetime:
        with self._lock:
            self._now = self._now + timedelta(seconds=seconds, **kwargs)
            return self._now

    def set(self, value: datetime) -> None:
        if value.tzinfo is None:
            raise ValueError("FakeClock needs timezone-aware datetimes")
        with self._lock:
            self._now = value


def to_iso(value: datetime) -> str:
    """Serialise an aware datetime as UTC ISO-8601 with microseconds."""
    if value.tzinfo is None:
        raise ValueError("naive datetimes are not allowed; attach a timezone")
    return value.astimezone(UTC).isoformat(timespec="microseconds")


def from_iso(value: str) -> datetime:
    """Parse an ISO-8601 string produced by :func:`to_iso` (or any aware ISO string)."""
    parsed = datetime.fromisoformat(value)
    if parsed.tzinfo is None:
        raise ValueError(f"timestamp without timezone: {value!r}")
    return parsed


def to_local(value: datetime) -> datetime:
    """Convert to the station's local timezone (for display/reports)."""
    return value.astimezone()


def local_iso(value: datetime | None) -> str:
    """Local-time ISO-8601 string with offset, seconds precision; empty for None."""
    if value is None:
        return ""
    return to_local(value).isoformat(timespec="seconds")
