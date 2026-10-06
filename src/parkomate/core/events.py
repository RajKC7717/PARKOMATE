"""A small, thread-safe, Qt-free publish/subscribe event bus.

Handlers run synchronously **on the publishing thread**. The UI subscribes through a bridge
that re-emits events as Qt signals (queued to the GUI thread), so publishers - workers,
the workflow, the records service - never need to know about Qt.

A failing handler is logged and never breaks the publisher or other handlers.
"""

from __future__ import annotations

import logging
import threading
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, TypeVar

from parkomate.core.enums import Stage
from parkomate.core.models import CheckOutcome, RejectInstruction

log = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class Event:
    """Base class of all events."""


@dataclass(frozen=True, slots=True)
class DeviceStarted(Event):
    device_row_id: int
    mac_address: str


@dataclass(frozen=True, slots=True)
class StageChanged(Event):
    device_row_id: int
    old: Stage
    new: Stage


@dataclass(frozen=True, slots=True)
class CheckRecorded(Event):
    device_row_id: int
    outcome: CheckOutcome


@dataclass(frozen=True, slots=True)
class DeviceCompleted(Event):
    device_row_id: int
    device_id: str | None


@dataclass(frozen=True, slots=True)
class DeviceRejected(Event):
    device_row_id: int
    instruction: RejectInstruction


@dataclass(frozen=True, slots=True)
class DeviceAbandoned(Event):
    device_row_id: int


@dataclass(frozen=True, slots=True)
class CountersChanged(Event):
    session_id: int


@dataclass(frozen=True, slots=True)
class SessionStarted(Event):
    session_id: int
    operator_id: int


@dataclass(frozen=True, slots=True)
class SessionEnded(Event):
    session_id: int


@dataclass(frozen=True, slots=True)
class AmbientMeasured(Event):
    session_id: int
    value_c: float


@dataclass(frozen=True, slots=True)
class SettingsReloaded(Event):
    changed_keys: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class StatusMessage(Event):
    """Free status line for the bottom bar (i18n key + params)."""

    key: str
    params: dict[str, Any] = field(default_factory=dict)
    at: datetime | None = None


E = TypeVar("E", bound=Event)
Handler = Callable[[Any], None]


class EventBus:
    """Publish/subscribe by event class. Subscribing to :class:`Event` receives everything."""

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._handlers: dict[type[Event], list[Handler]] = {}

    def subscribe(self, event_type: type[E], handler: Callable[[E], None]) -> Callable[[], None]:
        """Register ``handler`` for ``event_type`` (and its subclasses).

        Returns a function that unsubscribes the handler.
        """
        with self._lock:
            self._handlers.setdefault(event_type, []).append(handler)

        def unsubscribe() -> None:
            with self._lock:
                handlers = self._handlers.get(event_type, [])
                if handler in handlers:
                    handlers.remove(handler)

        return unsubscribe

    def publish(self, event: Event) -> None:
        with self._lock:
            targets = [
                handler
                for event_type, handlers in self._handlers.items()
                if isinstance(event, event_type)
                for handler in list(handlers)
            ]
        for handler in targets:
            try:
                handler(event)
            except Exception:
                log.exception("event handler %r failed for %s", handler, type(event).__name__)

    def clear(self) -> None:
        with self._lock:
            self._handlers.clear()
