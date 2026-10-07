"""Contracts between the three owners. See CONTRACTS.md for the prose version.

* :class:`HardwareService` - implemented by **Aditya** (``parkomate.hardware``).
  Today: ``parkomate.hardware.mocks.MockHardwareService``.
* :class:`WorkflowService` - implemented by **Piyush** (``parkomate.workflow``).
  Today: ``parkomate.workflow.stub.StubWorkflowService``.

The UI and the data layer depend only on these Protocols, never on the implementations.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Protocol, runtime_checkable

from parkomate.core.enums import CheckCode, IdEntryMethod, Stage
from parkomate.core.models import (
    CheckOutcome,
    DeviceState,
    FirmwareInfo,
    FlashResult,
    IdentityOutcome,
    Measurement,
    PortInfo,
    PreviewFrame,
    RejectInstruction,
    SensorReading,
    WhitelistResult,
)

ProgressCallback = Callable[[int], None]
"""Receives flashing progress 0..100. Called from the worker thread running ``flash``."""

CheckValue = float | str | bool | None


@runtime_checkable
class HardwareService(Protocol):
    """Everything that touches the bench: serial port, ESP32, server API, measurement device,
    camera.

    Threading: every method except :meth:`get_preview_frame` may block and **must be called
    from a worker thread**, never from the UI thread. Implementations must be safe to call
    from any one worker at a time (the UI serialises hardware calls).

    Errors: every failure raises a :class:`parkomate.core.errors.ParkomateError` subclass
    (``HardwareError``, ``ServerError``, ``MeasurementError``, ``CameraError``) with a
    specific :class:`~parkomate.core.errors.ErrorCode`. Never a bare exception.

    Firmware: the BIN is kept in RAM only (``bytearray``) and zeroed by :meth:`shutdown`.
    It is never written to disk, a temp file, a log or a report.
    """

    # -- serial port --------------------------------------------------------------------
    def list_ports(self) -> list[PortInfo]:
        """Serial ports, known ESP32 USB-UART bridges first (``is_esp_candidate``)."""
        ...

    def connect(self, port: str) -> None:
        """Open ``port``. Raises ``HW_NO_PORT`` / ``HW_PORT_BUSY``."""
        ...

    def disconnect(self) -> None:
        """Close the port. Safe to call when not connected. The next ``connect`` is treated
        as a new board."""
        ...

    def is_connected(self) -> bool: ...

    # -- device identity ----------------------------------------------------------------
    def read_mac(self) -> str:
        """MAC of the connected ESP32 as ``AA:BB:CC:DD:EE:FF`` (upper case)."""
        ...

    def chip_name(self) -> str:
        """Chip description for the UI, e.g. ``ESP32-D0WD-V3`` (empty if unknown)."""
        ...

    # -- server -------------------------------------------------------------------------
    def check_whitelist(self, mac: str) -> WhitelistResult:
        """Ask the server whether ``mac`` may be programmed. ``allowed=False`` is a normal
        result (not an exception); network problems raise ``API_*`` errors."""
        ...

    def fetch_firmware(self) -> FirmwareInfo:
        """Download the firmware into RAM, verify its SHA-256 and return its metadata."""
        ...

    def firmware_info(self) -> FirmwareInfo | None:
        """Metadata of the firmware currently held in RAM, if any."""
        ...

    # -- programming --------------------------------------------------------------------
    def flash(self, progress_cb: ProgressCallback) -> FlashResult:
        """Write the in-RAM firmware to the connected board and verify it.

        A failed flash that the board survived returns ``FlashResult(success=False, ...)``.
        Losing the port mid-flash raises ``HardwareError(HW_COM_DISCONNECTED)``.
        """
        ...

    # -- device link (firmware running) -------------------------------------------------
    def ping(self) -> bool:
        """Communication test. ``False`` = device did not answer correctly."""
        ...

    def read_sensor(self) -> SensorReading: ...

    def get_device_id(self) -> str:
        """ID stored in the device ("" if none)."""
        ...

    def set_device_id(self, device_id: str) -> bool:
        """Write ``device_id`` into the device. ``True`` = device acknowledged."""
        ...

    # -- measurement device -------------------------------------------------------------
    def measure(self, timeout_s: float) -> Measurement:
        """Open a listening window and return the first valid packet.

        Raises ``MeasurementError(MEAS_TIMEOUT)`` / ``MeasurementError(MEAS_BAD_DATA)``.
        """
        ...

    def measure_ambient(self) -> float:
        """Ambient temperature in °C."""
        ...

    # -- camera -------------------------------------------------------------------------
    def open_camera(self) -> None: ...

    def read_qr(self, timeout_s: float) -> str | None:
        """Decode one QR code. ``None`` when nothing readable was seen within the timeout."""
        ...

    def get_preview_frame(self) -> PreviewFrame | None:
        """Latest camera frame for the preview, or ``None``. Must return immediately (it is
        polled from the UI thread at ~15 fps)."""
        ...

    def close_camera(self) -> None: ...

    # -- lifecycle ----------------------------------------------------------------------
    def shutdown(self) -> None:
        """Release every resource and zero the firmware buffer."""
        ...


@runtime_checkable
class WorkflowService(Protocol):
    """The workflow brain: stage order, stage gates, limit checks, reject/retry/complete.

    The UI performs hardware I/O (in workers) and hands the *results* to this service; the
    service decides pass/fail, records every result through the production records API and
    publishes events (``StageChanged``, ``CheckRecorded``, ``DeviceCompleted``,
    ``DeviceRejected``, ``CountersChanged``) on the shared :class:`~parkomate.core.events.EventBus`.

    A failure that is final (not retriable) **rejects the device inside the call** and the
    returned outcome carries ``reject``; the UI then shows the reject takeover.

    Methods are fast (database writes only) and may be called from the UI thread.
    """

    # -- device lifecycle ---------------------------------------------------------------
    def start_device(self, mac: str) -> DeviceState:
        """Begin a new device at PROGRAMMING. Raises ``INVALID_STATE`` if one is active."""
        ...

    def current_device(self) -> DeviceState | None:
        """Snapshot of the active device, ``None`` when the bench is idle."""
        ...

    def current_stage(self) -> Stage:
        """Stage of the active device; ``PROGRAMMING`` when idle."""
        ...

    def abandon_device(self) -> None:
        """Mark the active device abandoned (session ending with a device on the bench)."""
        ...

    def clear_finished(self) -> None:
        """Forget a completed/rejected device so the bench is idle for the next one."""
        ...

    # -- checks -------------------------------------------------------------------------
    def required_checks(self, stage: Stage) -> list[CheckCode]: ...

    def missing_checks(self) -> list[CheckCode]:
        """Required checks of the current stage that have not passed yet (gate message)."""
        ...

    def is_stage_complete(self, stage: Stage) -> bool: ...

    def submit_check(
        self, check_code: CheckCode, value: CheckValue = None, *, text: str | None = None
    ) -> CheckOutcome:
        """Submit one result for the current stage.

        ``value`` is: ``bool`` for automatic/operator-marked checks (whitelist allowed,
        upload success, ping ok, sensor/indicator OK, checklist ticked), ``float`` for
        readings, ``str`` for text values (e.g. the decoded QR). ``text`` is optional extra
        detail stored with the result (e.g. an error code or the firmware version).
        """
        ...

    def can_submit(self) -> bool:
        """True when the current stage gate is satisfied."""
        ...

    def submit_and_next(self) -> Stage:
        """Close the current stage and advance. Returns the new stage (``COMPLETE`` after
        packaging). Raises ``INVALID_STATE`` when the gate is not satisfied."""
        ...

    def reject(
        self,
        check_code: CheckCode,
        reason_key: str = "reject.reason.manual",
        **reason_params: object,
    ) -> RejectInstruction:
        """Operator-initiated reject at the current stage for ``check_code``."""
        ...

    # -- programming --------------------------------------------------------------------
    def can_retry_programming(self) -> bool: ...

    # -- testing ------------------------------------------------------------------------
    def evaluate_measurement(self, measurement: Measurement) -> list[CheckOutcome]:
        """Check V_A, V_B, V_C and regulator temperature against the configured limits."""
        ...

    # -- labeling -----------------------------------------------------------------------
    def reconcile_identity(
        self,
        qr_id: str,
        device_id: str | None,
        *,
        after_write: bool = False,
        method: IdEntryMethod = IdEntryMethod.CAMERA,
    ) -> IdentityOutcome:
        """Compare QR ID and device ID.

        First call (``after_write=False``): equal -> ``MATCH``; different ->
        ``WRITE_REQUIRED`` (caller writes the QR ID with ``HardwareService.set_device_id`` and
        reads it back). Second call (``after_write=True``) with the read-back ID: equal ->
        ``CONFIRMED``; different -> ``FAILED`` and the device is rejected.
        """
        ...
