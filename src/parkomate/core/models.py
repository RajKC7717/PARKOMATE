"""Pydantic data models shared across layers.

Three groups:

* **Records** - rows the data layer stores (Operator, Session, Device, CheckResult, ...).
* **Hardware DTOs** - what :class:`~parkomate.core.interfaces.HardwareService` returns.
* **Workflow DTOs** - what :class:`~parkomate.core.interfaces.WorkflowService` returns.

All models are immutable (``frozen=True``); create changed copies with ``model_copy``.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from parkomate.core.enums import (
    AmbientReason,
    CheckCode,
    CounterEvent,
    DeviceStatus,
    IdentityStatus,
    IdEntryMethod,
    OutboxStatus,
    Role,
    SessionEndReason,
    Stage,
)
from parkomate.core.errors import ErrorCode


class _Frozen(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


# --------------------------------------------------------------------------- records


class Operator(_Frozen):
    """A person who can log in. The password hash is deliberately not part of this model."""

    id: int
    operator_code: str
    full_name: str
    role: Role
    is_active: bool
    failed_attempts: int = 0
    locked_until: datetime | None = None
    language: str | None = None
    created_at: datetime

    @property
    def is_admin(self) -> bool:
        return self.role is Role.ADMIN


class Session(_Frozen):
    id: int
    operator_id: int
    station_id: str
    started_at: datetime
    ended_at: datetime | None = None
    end_reason: SessionEndReason | None = None
    firmware_name: str | None = None
    firmware_version: str | None = None
    firmware_sha256: str | None = None
    ambient_c_initial: float | None = None
    language: str

    @property
    def is_open(self) -> bool:
        return self.ended_at is None


class AmbientReading(_Frozen):
    id: int
    session_id: int
    value_c: float
    measured_at: datetime
    reason: AmbientReason


class Device(_Frozen):
    """One physical board going through the line (``devices`` row).

    ``id`` is the *device row id*; ``device_id`` is the QR identity assigned in stage C.
    """

    id: int
    session_id: int
    device_id: str | None = None
    mac_address: str
    firmware_version: str | None = None
    started_at: datetime
    finished_at: datetime | None = None
    status: DeviceStatus
    reject_stage: Stage | None = None
    reject_check_code: CheckCode | None = None
    reject_reason: str | None = None
    reject_reason_key: str | None = None
    reject_reason_params: dict[str, Any] = Field(default_factory=dict)
    programming_attempts: int = 0
    id_entry_method: IdEntryMethod | None = None


class CheckResult(_Frozen):
    id: int
    device_row_id: int
    stage: Stage
    check_code: CheckCode
    value_text: str | None = None
    value_num: float | None = None
    unit: str | None = None
    limit_low: float | None = None
    limit_high: float | None = None
    passed: bool | None = None
    operator_marked: bool = False
    created_at: datetime


class CounterEventRecord(_Frozen):
    id: int
    session_id: int
    device_row_id: int | None = None
    event: CounterEvent
    operator_id: int
    created_at: datetime


class Counters(_Frozen):
    """Live counters, computed from ``counter_events`` and ``devices`` since the last reset."""

    session_id: int
    upload_success: int = 0
    upload_failure: int = 0
    failures_adjusted: int = 0
    completed: int = 0
    rejected: int = 0
    since: datetime | None = None  # time of the last reset, None = whole session

    @property
    def net_upload_failure(self) -> int:
        """Failures shown to the operator: raw failures minus adjustments."""
        return max(0, self.upload_failure - self.failures_adjusted)


class OutboxItem(_Frozen):
    id: int
    session_id: int | None = None
    status: OutboxStatus
    attempts: int = 0
    last_error: str | None = None
    payload_path: str | None = None
    subject: str = ""
    created_at: datetime
    sent_at: datetime | None = None
    next_attempt_at: datetime | None = None


class AuditEntry(_Frozen):
    id: int
    operator_id: int | None = None
    action: str
    details: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime


class SessionSummary(_Frozen):
    """Totals for one session, used by the summary card, the e-mail and the reports."""

    session: Session
    operator_code: str
    operator_name: str
    ambient_readings: list[AmbientReading] = Field(default_factory=list)
    total_devices: int = 0
    complete: int = 0
    rejected_by_stage: dict[Stage, int] = Field(default_factory=dict)
    abandoned: int = 0
    in_progress: int = 0
    upload_success: int = 0
    upload_failure: int = 0
    failures_adjusted: int = 0
    counter_resets: int = 0
    first_pass_complete: int = 0
    """Completed devices that never had an upload failure (numerator of first-pass yield)."""

    @property
    def rejected_total(self) -> int:
        return sum(self.rejected_by_stage.values())

    @property
    def net_upload_failure(self) -> int:
        return max(0, self.upload_failure - self.failures_adjusted)

    @property
    def first_pass_yield(self) -> float | None:
        """First-pass yield in percent.

        ``devices completed without any upload failure / devices that finished
        (complete + rejected)``. Abandoned and in-progress devices are excluded because they
        never reached a pass/fail verdict. ``None`` when no device finished.
        """
        finished = self.complete + self.rejected_total
        if finished == 0:
            return None
        return round(100.0 * self.first_pass_complete / finished, 1)


# --------------------------------------------------------------------------- hardware DTOs


class PortInfo(_Frozen):
    name: str  # "COM3" / "/dev/ttyUSB0"
    description: str = ""
    vid: int | None = None
    pid: int | None = None
    serial_number: str | None = None
    is_esp_candidate: bool = False
    """True when the USB VID:PID belongs to a known ESP32 USB-UART bridge."""

    @property
    def vid_pid(self) -> str:
        if self.vid is None or self.pid is None:
            return ""
        return f"{self.vid:04X}:{self.pid:04X}"


class WhitelistResult(_Frozen):
    mac_address: str
    allowed: bool
    reason: str | None = None
    checked_at: datetime


class FirmwareInfo(_Frozen):
    """Metadata of the firmware held in RAM. The bytes never leave the hardware service."""

    name: str
    version: str
    sha256: str
    size: int
    hash_verified: bool = False


class FlashResult(_Frozen):
    success: bool
    error_code: ErrorCode | None = None
    message: str = ""
    duration_s: float = 0.0
    bytes_written: int = 0


class SensorReading(_Frozen):
    value: float
    unit: str = ""
    raw: str | None = None
    read_at: datetime


class Measurement(_Frozen):
    """One JSON packet from the measurement device."""

    station: str | None = None
    seq: int | None = None
    v_a: float | None
    v_b: float | None
    v_c: float | None
    t_reg_c: float | None
    t_amb_c: float | None = None
    received_at: datetime


@dataclass(frozen=True, slots=True)
class PreviewFrame:
    """A camera frame for the UI preview: packed RGB888, ``width * height * 3`` bytes."""

    width: int
    height: int
    rgb: bytes


# --------------------------------------------------------------------------- workflow DTOs


class RejectInstruction(_Frozen):
    """Everything the UI needs for the red reject takeover.

    The UI renders ``t("reject.place_in_box", stage=t(stage.label_key), box=box_letter)``
    and ``t(reason_key, **reason_params)``.
    """

    device_row_id: int
    stage: Stage
    check_code: CheckCode
    reason_key: str
    reason_params: dict[str, Any] = Field(default_factory=dict)
    message_key: str = "reject.place_in_box"

    @property
    def box_letter(self) -> str:
        return self.stage.letter


class CheckOutcome(_Frozen):
    """Result of submitting/evaluating one check."""

    check_code: CheckCode
    stage: Stage
    passed: bool | None
    value_num: float | None = None
    value_text: str | None = None
    unit: str | None = None
    limit_low: float | None = None
    limit_high: float | None = None
    reason_key: str | None = None
    reason_params: dict[str, Any] = Field(default_factory=dict)
    retry_allowed: bool = False
    attempt: int = 1
    max_attempts: int = 1
    reject: RejectInstruction | None = None


class IdentityOutcome(_Frozen):
    status: IdentityStatus
    qr_id: str
    device_id: str | None
    reject: RejectInstruction | None = None


class DeviceState(_Frozen):
    """Snapshot of the device currently on the bench, as the workflow sees it."""

    device_row_id: int
    mac_address: str
    device_id: str | None = None
    qr_id: str | None = None
    stage: Stage
    status: DeviceStatus
    started_at: datetime
    upload_attempts: int = 0
    upload_failures: int = 0
    readings: list[float] = Field(default_factory=list)
    marks: dict[CheckCode, bool] = Field(default_factory=dict)
    outcomes: dict[CheckCode, CheckOutcome] = Field(default_factory=dict)
    identity: IdentityStatus | None = None
    reject: RejectInstruction | None = None

    @property
    def display_id(self) -> str:
        """Best human identifier: QR/device ID when known, else MAC."""
        return self.device_id or self.qr_id or self.mac_address
