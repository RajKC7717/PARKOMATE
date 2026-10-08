"""Record a real bench session and replay it later (tests, demos, bug reports).

* :class:`RecordingHardwareService` wraps any ``HardwareService`` and appends one JSON line
  per call: ``{"op", "args", "result"}`` or ``{"op", "args", "error": {code, message}}``;
  ``flash`` also stores the progress values. Firmware bytes are never part of a result.
* :class:`ReplayHardwareService` answers each call with the next recorded entry for that
  operation (errors are re-raised with their original code).

    python -m parkomate --mock   # normal development
    # on the bench: set PARKOMATE_RECORD=<file.jsonl> to record the real hardware
"""

from __future__ import annotations

import json
import logging
import threading
from collections import deque
from collections.abc import Callable, Iterable
from pathlib import Path
from typing import Any

from pydantic import BaseModel

from parkomate.core.errors import (
    CameraError,
    ErrorCode,
    HardwareError,
    MeasurementError,
    ParkomateError,
    ServerError,
)
from parkomate.core.interfaces import HardwareService, ProgressCallback
from parkomate.core.models import (
    FirmwareInfo,
    FlashResult,
    Measurement,
    PortInfo,
    PreviewFrame,
    SensorReading,
    WhitelistResult,
)

log = logging.getLogger(__name__)


def _model(cls: type[BaseModel]) -> Callable[[Any], Any]:
    return lambda raw: None if raw is None else cls.model_validate(raw)


DECODERS: dict[str, Callable[[Any], Any]] = {
    "list_ports": lambda raw: [PortInfo.model_validate(p) for p in raw],
    "connect": lambda raw: None,
    "disconnect": lambda raw: None,
    "is_connected": bool,
    "read_mac": str,
    "chip_name": str,
    "check_whitelist": _model(WhitelistResult),
    "fetch_firmware": _model(FirmwareInfo),
    "firmware_info": _model(FirmwareInfo),
    "flash": _model(FlashResult),
    "ping": bool,
    "read_sensor": _model(SensorReading),
    "get_device_id": str,
    "set_device_id": bool,
    "measure": _model(Measurement),
    "measure_ambient": float,
    "open_camera": lambda raw: None,
    "read_qr": lambda raw: None if raw is None else str(raw),
    "close_camera": lambda raw: None,
}
STICKY = frozenset({"chip_name", "firmware_info", "is_connected", "list_ports"})
"""Operations that keep answering their last recorded value once the recording runs out."""


def _encode(value: Any) -> Any:
    if isinstance(value, BaseModel):
        return value.model_dump(mode="json")
    if isinstance(value, list):
        return [_encode(v) for v in value]
    return value


def error_from(code: str, message: str) -> ParkomateError:
    error_code = ErrorCode(code)
    prefix = error_code.value.split("_")[0]
    cls: type[ParkomateError] = {
        "HW": HardwareError,
        "API": ServerError,
        "WHITELIST": ServerError,
        "FW": ServerError,
        "MEAS": MeasurementError,
        "CAM": CameraError,
        "QR": CameraError,
        "ID": HardwareError,
    }.get(prefix, ParkomateError)
    return cls(message, code=error_code)


class RecordingHardwareService:
    """Transparent wrapper that writes every call to a JSON-lines file."""

    def __init__(self, inner: HardwareService, path: Path) -> None:
        self._inner = inner
        self._path = path
        self._lock = threading.Lock()
        path.parent.mkdir(parents=True, exist_ok=True)

    def _write(self, entry: dict[str, Any]) -> None:
        with self._lock, self._path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(entry, ensure_ascii=False) + "\n")

    def _call(self, op: str, *args: Any, **extra: Any) -> Any:
        entry: dict[str, Any] = {"op": op, "args": [_encode(a) for a in args]}
        try:
            result = getattr(self._inner, op)(*args)
        except ParkomateError as exc:
            entry["error"] = {"code": exc.code.value, "message": exc.message}
            entry.update(extra)
            self._write(entry)
            raise
        entry["result"] = _encode(result)
        entry.update(extra)
        self._write(entry)
        return result

    def list_ports(self) -> list[PortInfo]:
        return self._call("list_ports")  # type: ignore[no-any-return]

    def connect(self, port: str) -> None:
        self._call("connect", port)

    def disconnect(self) -> None:
        self._call("disconnect")

    def is_connected(self) -> bool:
        return self._inner.is_connected()  # polled often: not recorded

    def read_mac(self) -> str:
        return self._call("read_mac")  # type: ignore[no-any-return]

    def chip_name(self) -> str:
        return self._call("chip_name")  # type: ignore[no-any-return]

    def check_whitelist(self, mac: str) -> WhitelistResult:
        return self._call("check_whitelist", mac)  # type: ignore[no-any-return]

    def fetch_firmware(self) -> FirmwareInfo:
        return self._call("fetch_firmware")  # type: ignore[no-any-return]

    def firmware_info(self) -> FirmwareInfo | None:
        return self._inner.firmware_info()

    def flash(self, progress_cb: ProgressCallback) -> FlashResult:
        ticks: list[int] = []

        def progress(value: int) -> None:
            ticks.append(value)
            progress_cb(value)

        entry: dict[str, Any] = {"op": "flash", "args": []}
        try:
            result = self._inner.flash(progress)
        except ParkomateError as exc:
            entry.update(error={"code": exc.code.value, "message": exc.message}, progress=ticks)
            self._write(entry)
            raise
        entry.update(result=_encode(result), progress=ticks)
        self._write(entry)
        return result

    def ping(self) -> bool:
        return self._call("ping")  # type: ignore[no-any-return]

    def read_sensor(self) -> SensorReading:
        return self._call("read_sensor")  # type: ignore[no-any-return]

    def get_device_id(self) -> str:
        return self._call("get_device_id")  # type: ignore[no-any-return]

    def set_device_id(self, device_id: str) -> bool:
        return self._call("set_device_id", device_id)  # type: ignore[no-any-return]

    def measure(self, timeout_s: float) -> Measurement:
        return self._call("measure", timeout_s)  # type: ignore[no-any-return]

    def measure_ambient(self) -> float:
        return self._call("measure_ambient")  # type: ignore[no-any-return]

    def open_camera(self) -> None:
        self._call("open_camera")

    def read_qr(self, timeout_s: float) -> str | None:
        return self._call("read_qr", timeout_s)  # type: ignore[no-any-return]

    def get_preview_frame(self) -> PreviewFrame | None:
        return self._inner.get_preview_frame()

    def close_camera(self) -> None:
        self._call("close_camera")

    def shutdown(self) -> None:
        self._inner.shutdown()


class ReplayHardwareService:
    """Answers calls from a recording (JSON lines), operation by operation."""

    def __init__(self, entries: Iterable[dict[str, Any]]) -> None:
        self._queues: dict[str, deque[dict[str, Any]]] = {}
        self._last: dict[str, dict[str, Any]] = {}
        self._lock = threading.Lock()
        self._connected = False
        for entry in entries:
            self._queues.setdefault(str(entry["op"]), deque()).append(entry)

    @classmethod
    def from_file(cls, path: Path) -> ReplayHardwareService:
        lines = path.read_text(encoding="utf-8").splitlines()
        return cls(json.loads(line) for line in lines if line.strip())

    def remaining(self) -> dict[str, int]:
        with self._lock:
            return {op: len(q) for op, q in self._queues.items() if q}

    def _next(self, op: str) -> dict[str, Any]:
        with self._lock:
            queue = self._queues.get(op)
            if queue:
                entry = queue.popleft()
                self._last[op] = entry
                return entry
            if op in STICKY and op in self._last:
                return self._last[op]
        raise HardwareError(f"replay has no more '{op}' entries", code=ErrorCode.HW_DEVICE_ERROR)

    def _answer(self, op: str) -> Any:
        entry = self._next(op)
        if "error" in entry:
            raise error_from(entry["error"]["code"], entry["error"].get("message", ""))
        return DECODERS[op](entry.get("result"))

    def list_ports(self) -> list[PortInfo]:
        return self._answer("list_ports")  # type: ignore[no-any-return]

    def connect(self, port: str) -> None:
        self._answer("connect")
        self._connected = True

    def disconnect(self) -> None:
        if self._queues.get("disconnect"):
            self._answer("disconnect")
        self._connected = False

    def is_connected(self) -> bool:
        return self._connected

    def read_mac(self) -> str:
        return self._answer("read_mac")  # type: ignore[no-any-return]

    def chip_name(self) -> str:
        try:
            return self._answer("chip_name")  # type: ignore[no-any-return]
        except HardwareError:
            return ""

    def check_whitelist(self, mac: str) -> WhitelistResult:
        return self._answer("check_whitelist")  # type: ignore[no-any-return]

    def fetch_firmware(self) -> FirmwareInfo:
        info: FirmwareInfo = self._answer("fetch_firmware")
        self._last["firmware_info"] = {"op": "firmware_info", "result": _encode(info)}
        return info

    def firmware_info(self) -> FirmwareInfo | None:
        entry = self._last.get("firmware_info")
        return None if entry is None else FirmwareInfo.model_validate(entry["result"])

    def flash(self, progress_cb: ProgressCallback) -> FlashResult:
        entry = self._next("flash")
        for value in entry.get("progress", []):
            progress_cb(int(value))
        if "error" in entry:
            self._connected = False
            raise error_from(entry["error"]["code"], entry["error"].get("message", ""))
        return FlashResult.model_validate(entry["result"])

    def ping(self) -> bool:
        return self._answer("ping")  # type: ignore[no-any-return]

    def read_sensor(self) -> SensorReading:
        return self._answer("read_sensor")  # type: ignore[no-any-return]

    def get_device_id(self) -> str:
        return self._answer("get_device_id")  # type: ignore[no-any-return]

    def set_device_id(self, device_id: str) -> bool:
        return self._answer("set_device_id")  # type: ignore[no-any-return]

    def measure(self, timeout_s: float) -> Measurement:
        return self._answer("measure")  # type: ignore[no-any-return]

    def measure_ambient(self) -> float:
        return self._answer("measure_ambient")  # type: ignore[no-any-return]

    def open_camera(self) -> None:
        self._answer("open_camera")

    def read_qr(self, timeout_s: float) -> str | None:
        return self._answer("read_qr")  # type: ignore[no-any-return]

    def get_preview_frame(self) -> PreviewFrame | None:
        return None

    def close_camera(self) -> None:
        if self._queues.get("close_camera"):
            self._answer("close_camera")

    def shutdown(self) -> None:
        return None
