"""Run blocking work (hardware, hashing, reports, e-mail) off the GUI thread.

* :class:`TaskRunner` wraps a ``QThreadPool``. The hardware runner has exactly one thread,
  so hardware calls are serialised and never overlap.
* Results, errors and progress are delivered **on the GUI thread** through a QObject that
  lives there (queued signal connections), so callbacks may touch widgets.
* Any exception becomes a :class:`ParkomateError` (unexpected ones are logged with a
  traceback and wrapped as ``UNEXPECTED``); the UI thread never sees a raw exception.
"""

from __future__ import annotations

import itertools
import logging
import threading
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from PySide6.QtCore import QObject, QRunnable, QThreadPool, Signal, Slot

from parkomate.core.errors import ErrorCode, ParkomateError

log = logging.getLogger(__name__)

Progress = Callable[[int], None]
SuccessCallback = Callable[[Any], None]
ErrorCallback = Callable[[ParkomateError], None]
ProgressCallback = Callable[[int], None]


@dataclass(slots=True)
class _Callbacks:
    on_success: SuccessCallback | None
    on_error: ErrorCallback | None
    on_progress: ProgressCallback | None
    name: str


class _Bridge(QObject):
    done = Signal(int, object)
    failed = Signal(int, object)
    progress = Signal(int, int)


class _Job(QRunnable):
    def __init__(
        self, task_id: int, fn: Callable[[Progress], Any], bridge: _Bridge, name: str
    ) -> None:
        super().__init__()
        self.setAutoDelete(True)
        self._id = task_id
        self._fn = fn
        self._bridge = bridge
        self._name = name

    def run(self) -> None:
        try:
            result = self._fn(lambda value: self._bridge.progress.emit(self._id, int(value)))
        except ParkomateError as exc:
            log.info("task %s failed: %s %s", self._name, exc.code.value, exc.message)
            self._bridge.failed.emit(self._id, exc)
        except Exception as exc:
            log.exception("task %s crashed", self._name)
            wrapped = ParkomateError(
                f"{type(exc).__name__}: {exc}",
                code=ErrorCode.UNEXPECTED,
                context={"task": self._name},
            )
            self._bridge.failed.emit(self._id, wrapped)
        else:
            self._bridge.done.emit(self._id, result)


class TaskRunner(QObject):
    """Submit work; callbacks run on the GUI thread. ``busy_changed`` tracks activity."""

    busy_changed = Signal(bool)

    def __init__(self, max_threads: int = 1, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._pool = QThreadPool(self)
        self._pool.setMaxThreadCount(max_threads)
        self._bridge = _Bridge()
        self._bridge.done.connect(self._on_done)
        self._bridge.failed.connect(self._on_failed)
        self._bridge.progress.connect(self._on_progress)
        self._ids = itertools.count(1)
        self._lock = threading.Lock()
        self._pending: dict[int, _Callbacks] = {}

    @property
    def busy(self) -> bool:
        with self._lock:
            return bool(self._pending)

    def submit(
        self,
        fn: Callable[[], Any] | Callable[[Progress], Any],
        *,
        on_success: SuccessCallback | None = None,
        on_error: ErrorCallback | None = None,
        on_progress: ProgressCallback | None = None,
        name: str = "",
        with_progress: bool = False,
    ) -> int:
        """Queue ``fn``. With ``with_progress=True`` it receives a ``progress(int)`` function."""
        task_id = next(self._ids)
        call: Callable[[Progress], Any]
        if with_progress:
            call = fn  # type: ignore[assignment]
        else:
            plain = fn

            def call(_progress: Progress) -> Any:
                return plain()  # type: ignore[call-arg]

        with self._lock:
            was_busy = bool(self._pending)
            self._pending[task_id] = _Callbacks(on_success, on_error, on_progress, name)
        if not was_busy:
            self.busy_changed.emit(True)
        self._pool.start(_Job(task_id, call, self._bridge, name or getattr(fn, "__name__", "task")))
        return task_id

    def wait(self, timeout_ms: int = 30_000) -> bool:
        """Block until the pool is idle (shutdown / tests). Callbacks still need the event loop."""
        return self._pool.waitForDone(timeout_ms)

    def _finish(self, task_id: int) -> _Callbacks | None:
        with self._lock:
            callbacks = self._pending.pop(task_id, None)
            idle = not self._pending
        if idle:
            self.busy_changed.emit(False)
        return callbacks

    @Slot(int, object)
    def _on_done(self, task_id: int, result: object) -> None:
        callbacks = self._finish(task_id)
        if callbacks and callbacks.on_success:
            self._safe(callbacks.on_success, result, callbacks.name)

    @Slot(int, object)
    def _on_failed(self, task_id: int, error: object) -> None:
        callbacks = self._finish(task_id)
        if callbacks is None:
            return
        if callbacks.on_error:
            self._safe(callbacks.on_error, error, callbacks.name)
        else:
            log.warning("unhandled task error in %s: %r", callbacks.name, error)

    @Slot(int, int)
    def _on_progress(self, task_id: int, value: int) -> None:
        with self._lock:
            callbacks = self._pending.get(task_id)
        if callbacks and callbacks.on_progress:
            self._safe(callbacks.on_progress, value, callbacks.name)

    @staticmethod
    def _safe(callback: Callable[[Any], None], value: object, name: str) -> None:
        try:
            callback(value)
        except Exception:
            log.exception("callback of task %s failed", name)
