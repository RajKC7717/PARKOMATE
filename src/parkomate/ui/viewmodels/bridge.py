"""Re-emit core events as Qt signals, always delivered on the GUI thread (queued)."""

from __future__ import annotations

from PySide6.QtCore import QObject, Qt, Signal

from parkomate.core.events import (
    CountersChanged,
    DeviceCompleted,
    DeviceRejected,
    Event,
    EventBus,
    SettingsReloaded,
)


class EventBridge(QObject):
    counters_changed = Signal(int)
    device_rejected = Signal(object)  # RejectInstruction
    device_completed = Signal(int, object)  # device_row_id, device_id
    settings_reloaded = Signal(object)  # tuple of changed keys
    any_event = Signal(object)

    _incoming = Signal(object)

    def __init__(self, bus: EventBus, parent: QObject | None = None) -> None:
        super().__init__(parent)
        # Queued: handlers never run inside the publisher's call stack, and events published
        # from worker threads arrive on the GUI thread.
        self._incoming.connect(self._dispatch, Qt.ConnectionType.QueuedConnection)
        self._unsubscribe = bus.subscribe(Event, self._incoming.emit)

    def close(self) -> None:
        self._unsubscribe()

    def _dispatch(self, event: object) -> None:
        if isinstance(event, CountersChanged):
            self.counters_changed.emit(event.session_id)
        elif isinstance(event, DeviceRejected):
            self.device_rejected.emit(event.instruction)
        elif isinstance(event, DeviceCompleted):
            self.device_completed.emit(event.device_row_id, event.device_id)
        elif isinstance(event, SettingsReloaded):
            self.settings_reloaded.emit(event.changed_keys)
        self.any_event.emit(event)
