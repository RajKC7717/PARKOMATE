"""STUB WorkflowService - a simple reference implementation so the UI can be built and demoed.

    >>> THIS IS A STUB. Piyush replaces it with the real state machine in the full build. <<<

It already enforces the essentials of the specification:

* stage order PROGRAMMING -> TESTING -> LABELING -> PACKAGING -> COMPLETE, any -> REJECTED;
* gates: A = whitelist allowed + upload success; B = comm OK + N readings + sensor OK +
  indicator OK + V_A/V_B/V_C in limits + (T_reg - ambient) <= margin; C = C1-C4 ticked +
  QR read + identity reconciled; D = D1-D4 ticked;
* limits from settings, inclusive, values rounded half-up to ``limits.decimals``;
* only programming is retriable (up to ``programming.max_retries`` attempts); every other
  failure rejects the device immediately;
* every result is persisted through :class:`~parkomate.data.records.ProductionRecords` and
  published on the event bus.
"""

from __future__ import annotations

import logging
import re
import threading
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime
from decimal import ROUND_HALF_UP, Decimal
from typing import Any

from parkomate.config.settings import Settings
from parkomate.core.enums import (
    LABELING_CHECKLIST,
    PACKAGING_CHECKLIST,
    CheckCode,
    CheckKind,
    CounterEvent,
    DeviceStatus,
    IdentityStatus,
    IdEntryMethod,
    Stage,
)
from parkomate.core.errors import InputError, RecordStateError
from parkomate.core.events import (
    CheckRecorded,
    DeviceCompleted,
    DeviceRejected,
    DeviceStarted,
    EventBus,
    StageChanged,
)
from parkomate.core.interfaces import CheckValue
from parkomate.core.models import (
    CheckOutcome,
    DeviceState,
    IdentityOutcome,
    Measurement,
    RejectInstruction,
)
from parkomate.data.records import ProductionRecords

log = logging.getLogger(__name__)

_NEXT_STAGE: dict[Stage, Stage] = {
    Stage.PROGRAMMING: Stage.TESTING,
    Stage.TESTING: Stage.LABELING,
    Stage.LABELING: Stage.PACKAGING,
    Stage.PACKAGING: Stage.COMPLETE,
}
_ORDER: tuple[Stage, ...] = (
    Stage.PROGRAMMING,
    Stage.TESTING,
    Stage.LABELING,
    Stage.PACKAGING,
    Stage.COMPLETE,
)
_CHECKLISTS = frozenset(LABELING_CHECKLIST + PACKAGING_CHECKLIST)


def quantize(value: float, decimals: int) -> Decimal:
    """Round half-up on the *decimal* representation (3.245 -> 3.25 at 2 decimals)."""
    return Decimal(repr(value)).quantize(Decimal(1).scaleb(-decimals), rounding=ROUND_HALF_UP)


def within(value: float, low: float, high: float, decimals: int) -> bool:
    """Inclusive limit check after rounding all three numbers to ``decimals``."""
    rounded = quantize(value, decimals)
    return quantize(low, decimals) <= rounded <= quantize(high, decimals)


@dataclass(slots=True)
class _Active:
    device_row_id: int
    mac_address: str
    started_at: datetime
    stage: Stage = Stage.PROGRAMMING
    status: DeviceStatus = DeviceStatus.IN_PROGRESS
    upload_attempts: int = 0
    upload_failures: int = 0
    readings: list[float] = field(default_factory=list)
    marks: dict[CheckCode, bool] = field(default_factory=dict)
    outcomes: dict[CheckCode, CheckOutcome] = field(default_factory=dict)
    qr_id: str | None = None
    device_id: str | None = None
    identity: IdentityStatus | None = None
    reject: RejectInstruction | None = None


class StubWorkflowService:
    """STUB implementation of :class:`parkomate.core.interfaces.WorkflowService`."""

    def __init__(
        self,
        records: ProductionRecords,
        settings: Callable[[], Settings],
        bus: EventBus | None = None,
    ) -> None:
        self._records = records
        self._settings = settings
        self._bus = bus or records.bus
        self._lock = threading.RLock()
        self._active: _Active | None = None

    # ================================================================== lifecycle
    def start_device(self, mac: str) -> DeviceState:
        with self._lock:
            if self._active is not None and self._active.status is DeviceStatus.IN_PROGRESS:
                raise RecordStateError("a device is already on the bench")
            row_id = self._records.start_device(mac)
            device = self._records.get_device(row_id)
            self._active = _Active(row_id, device.mac_address, device.started_at)
            snapshot = self._snapshot()
        self._bus.publish(DeviceStarted(row_id, device.mac_address))
        assert snapshot is not None
        return snapshot

    def current_device(self) -> DeviceState | None:
        with self._lock:
            return self._snapshot()

    def current_stage(self) -> Stage:
        with self._lock:
            return self._active.stage if self._active else Stage.PROGRAMMING

    def abandon_device(self) -> None:
        with self._lock:
            active = self._active
            if active is None or active.status is not DeviceStatus.IN_PROGRESS:
                self._active = None
                return
            self._records.abandon_device(active.device_row_id)
            self._active = None

    def clear_finished(self) -> None:
        with self._lock:
            if self._active is not None and self._active.status is DeviceStatus.IN_PROGRESS:
                raise RecordStateError("the device on the bench is not finished")
            self._active = None

    # ================================================================== gates
    def required_checks(self, stage: Stage) -> list[CheckCode]:
        count = self._settings().limits.sensor_reading_count
        if stage is Stage.PROGRAMMING:
            return [CheckCode.A_WHITELIST, CheckCode.A_UPLOAD]
        if stage is Stage.TESTING:
            return [
                CheckCode.B1_COMM,
                *(CheckCode.reading(i) for i in range(1, count + 1)),
                CheckCode.B2_SENSOR_OK,
                CheckCode.B2_INDICATOR_OK,
                CheckCode.B3_V_A,
                CheckCode.B3_V_B,
                CheckCode.B3_V_C,
                CheckCode.B3_T_REG,
            ]
        if stage is Stage.LABELING:
            return [*LABELING_CHECKLIST, CheckCode.C_QR_READ, CheckCode.C_ID_SYNC]
        if stage is Stage.PACKAGING:
            return list(PACKAGING_CHECKLIST)
        return []

    def _satisfied(self, active: _Active, code: CheckCode) -> bool:
        if code in _CHECKLISTS:
            return active.marks.get(code) is True
        outcome = active.outcomes.get(code)
        if outcome is None:
            return False
        if code.meta.kind is CheckKind.INFO:
            return True
        return outcome.passed is True

    def missing_checks(self) -> list[CheckCode]:
        with self._lock:
            active = self._active
            if active is None or active.status is not DeviceStatus.IN_PROGRESS:
                return []
            return [c for c in self.required_checks(active.stage) if not self._satisfied(active, c)]

    def is_stage_complete(self, stage: Stage) -> bool:
        with self._lock:
            active = self._active
            if active is None or stage not in _ORDER:
                return False
            if active.status is DeviceStatus.REJECTED:
                return False
            current = _ORDER.index(active.stage)
            target = _ORDER.index(stage)
            if target < current:
                return True
            if target > current:
                return False
            return all(self._satisfied(active, c) for c in self.required_checks(stage))

    def can_submit(self) -> bool:
        with self._lock:
            active = self._active
            return (
                active is not None
                and active.status is DeviceStatus.IN_PROGRESS
                and not self.missing_checks()
            )

    # ================================================================== checks
    def submit_check(
        self, check_code: CheckCode, value: CheckValue = None, *, text: str | None = None
    ) -> CheckOutcome:
        with self._lock:
            active = self._require_active()
            if check_code.stage is not active.stage:
                raise RecordStateError(
                    f"{check_code.value} cannot be submitted during {active.stage.value}"
                )
            if check_code in (
                CheckCode.B3_V_A,
                CheckCode.B3_V_B,
                CheckCode.B3_V_C,
                CheckCode.B3_T_REG,
                CheckCode.B3_T_AMB,
            ):
                raise RecordStateError("electrical checks go through evaluate_measurement()")
            if check_code is CheckCode.C_ID_SYNC:
                raise RecordStateError("identity goes through reconcile_identity()")
            if check_code in _CHECKLISTS:
                return self._tick(active, check_code, _as_bool(value, check_code))
            if check_code is CheckCode.A_WHITELIST:
                return self._whitelist(active, _as_bool(value, check_code), text)
            if check_code is CheckCode.A_UPLOAD:
                return self._upload(active, _as_bool(value, check_code), text)
            if check_code is CheckCode.B1_COMM:
                return self._simple_auto(
                    active, check_code, _as_bool(value, check_code), "reject.reason.comm_failed"
                )
            if check_code.reading_index is not None:
                return self._reading(active, check_code, value)
            if check_code in (CheckCode.B2_SENSOR_OK, CheckCode.B2_INDICATOR_OK):
                return self._operator_mark(active, check_code, _as_bool(value, check_code))
            if check_code is CheckCode.C_QR_READ:
                return self._qr_read(active, value)
        raise RecordStateError(f"unsupported check {check_code.value}")  # pragma: no cover

    def _tick(self, active: _Active, code: CheckCode, ticked: bool) -> CheckOutcome:
        active.marks[code] = ticked
        return CheckOutcome(check_code=code, stage=code.stage, passed=ticked)

    def _whitelist(self, active: _Active, allowed: bool, text: str | None) -> CheckOutcome:
        outcome = self._record(
            active,
            CheckCode.A_WHITELIST,
            passed=allowed,
            value_text=active.mac_address if not text else f"{active.mac_address} | {text}",
        )
        if not allowed:
            return self._fail(
                active, outcome, "reject.reason.whitelist_denied", {"mac": active.mac_address}
            )
        return outcome

    def _upload(self, active: _Active, success: bool, text: str | None) -> CheckOutcome:
        whitelist = active.outcomes.get(CheckCode.A_WHITELIST)
        if whitelist is None or whitelist.passed is not True:
            raise RecordStateError("whitelist must pass before uploading")
        if self._satisfied(active, CheckCode.A_UPLOAD):
            raise RecordStateError("firmware already uploaded")
        max_attempts = self._settings().programming.max_retries
        if active.upload_attempts >= max_attempts:
            raise RecordStateError("no upload attempts left")
        active.upload_attempts += 1
        event = CounterEvent.UPLOAD_SUCCESS if success else CounterEvent.UPLOAD_FAILURE
        self._records.counter_event(event, active.device_row_id)
        if success and text:
            self._records.set_device_firmware(active.device_row_id, text)
        if not success:
            active.upload_failures += 1
        retry = not success and active.upload_attempts < max_attempts
        outcome = self._record(
            active,
            CheckCode.A_UPLOAD,
            passed=success,
            value_text=text,
            attempt=active.upload_attempts,
            max_attempts=max_attempts,
            retry_allowed=retry,
            reason_key=None if success else "reject.reason.upload_failed",
        )
        if not success and not retry:
            return self._fail(
                active,
                outcome,
                "reject.reason.upload_failed_max",
                {"attempts": active.upload_attempts},
            )
        return outcome

    def _simple_auto(
        self, active: _Active, code: CheckCode, passed: bool, reason_key: str
    ) -> CheckOutcome:
        outcome = self._record(active, code, passed=passed)
        if not passed:
            return self._fail(active, outcome, reason_key, {})
        return outcome

    def _reading(self, active: _Active, code: CheckCode, value: CheckValue) -> CheckOutcome:
        if not self._satisfied(active, CheckCode.B1_COMM):
            raise RecordStateError("communication test must pass before sensor readings")
        if isinstance(value, bool) or not isinstance(value, int | float):
            raise InputError(f"{code.value} needs a numeric reading")
        index = code.reading_index
        total = self._settings().limits.sensor_reading_count
        expected = len(active.readings) + 1
        if index != expected or expected > total:
            raise RecordStateError(f"expected reading {expected} of {total}, got {index}")
        active.readings.append(float(value))
        return self._record(active, code, passed=None, value_num=float(value))

    def _operator_mark(self, active: _Active, code: CheckCode, ok: bool) -> CheckOutcome:
        total = self._settings().limits.sensor_reading_count
        if code is CheckCode.B2_SENSOR_OK and len(active.readings) < total:
            raise RecordStateError(f"take all {total} sensor readings first")
        if not self._satisfied(active, CheckCode.B1_COMM):
            raise RecordStateError("communication test must pass first")
        active.marks[code] = ok
        outcome = self._record(active, code, passed=ok, operator_marked=True)
        if not ok:
            return self._fail(
                active, outcome, "reject.reason.operator_marked_fail", {"check_key": code.label_key}
            )
        return outcome

    def _qr_read(self, active: _Active, value: CheckValue) -> CheckOutcome:
        if not isinstance(value, str) or not value.strip():
            raise InputError("C_QR_READ needs the decoded ID text")
        qr = value.strip()
        pattern = self._settings().camera.id_pattern
        if not re.fullmatch(pattern, qr):
            # A badly formatted label is not a device fault: record it and let them rescan.
            return self._record(
                active,
                CheckCode.C_QR_READ,
                passed=False,
                value_text=qr,
                retry_allowed=True,
                reason_key="identity.qr_bad_format",
                reason_params={"value": qr},
            )
        active.qr_id = qr
        active.identity = None
        return self._record(active, CheckCode.C_QR_READ, passed=True, value_text=qr)

    # ================================================================== stage flow
    def submit_and_next(self) -> Stage:
        with self._lock:
            active = self._require_active()
            missing = self.missing_checks()
            if missing:
                raise RecordStateError(
                    "stage gate not satisfied",
                    context={"missing": [c.value for c in missing]},
                )
            old = active.stage
            if old in (Stage.LABELING, Stage.PACKAGING):
                checklist = LABELING_CHECKLIST if old is Stage.LABELING else PACKAGING_CHECKLIST
                for code in checklist:
                    self._record(active, code, passed=True, operator_marked=True, publish=False)
            new = _NEXT_STAGE[old]
            active.stage = new
            if new is Stage.COMPLETE:
                self._records.complete_device(active.device_row_id)
                active.status = DeviceStatus.COMPLETE
            device_id = active.device_id
        self._bus.publish(StageChanged(active.device_row_id, old, new))
        if new is Stage.COMPLETE:
            self._bus.publish(DeviceCompleted(active.device_row_id, device_id))
        log.info("device row %d: %s -> %s", active.device_row_id, old.value, new.value)
        return new

    def reject(
        self,
        check_code: CheckCode,
        reason_key: str = "reject.reason.manual",
        **reason_params: object,
    ) -> RejectInstruction:
        with self._lock:
            active = self._require_active()
            if check_code.stage is not active.stage:
                raise RecordStateError(
                    f"cannot reject for {check_code.value} during {active.stage.value}"
                )
            last = active.outcomes.get(check_code)
            if last is None or last.passed is not False:
                self._record(active, check_code, passed=False, operator_marked=True, publish=False)
            params: dict[str, Any] = {"check_key": check_code.label_key, **reason_params}
            return self._do_reject(active, check_code, reason_key, params)

    def can_retry_programming(self) -> bool:
        with self._lock:
            active = self._active
            if active is None or active.status is not DeviceStatus.IN_PROGRESS:
                return False
            if active.stage is not Stage.PROGRAMMING:
                return False
            last = active.outcomes.get(CheckCode.A_UPLOAD)
            return (
                last is not None
                and last.passed is False
                and active.upload_attempts < self._settings().programming.max_retries
            )

    # ================================================================== testing
    def evaluate_measurement(self, measurement: Measurement) -> list[CheckOutcome]:
        with self._lock:
            active = self._require_active()
            if active.stage is not Stage.TESTING:
                raise RecordStateError("measurement outside the testing stage")
            total = self._settings().limits.sensor_reading_count
            if not (
                self._satisfied(active, CheckCode.B1_COMM)
                and len(active.readings) >= total
                and active.marks.get(CheckCode.B2_SENSOR_OK) is True
                and active.marks.get(CheckCode.B2_INDICATOR_OK) is True
            ):
                raise RecordStateError("finish B1 and B2 before measuring")
            limits = self._settings().limits
            decimals = limits.decimals
            outcomes: list[CheckOutcome] = []
            first_fail: tuple[CheckOutcome, str, dict[str, Any]] | None = None

            for point, code in (
                ("a", CheckCode.B3_V_A),
                ("b", CheckCode.B3_V_B),
                ("c", CheckCode.B3_V_C),
            ):
                low, high = limits.voltage_range(point)
                raw = getattr(measurement, f"v_{point}")
                if raw is None:
                    outcome = self._record(
                        active,
                        code,
                        passed=False,
                        limits=(low, high),
                        reason_key="reject.reason.value_missing",
                        reason_params={"check_key": code.label_key},
                    )
                    params: dict[str, Any] = {"check_key": code.label_key}
                    reason = "reject.reason.value_missing"
                else:
                    value = float(quantize(raw, decimals))
                    passed = within(raw, low, high, decimals)
                    params = {
                        "check_key": code.label_key,
                        "value": f"{value:.{decimals}f}",
                        "unit": "V",
                        "low": f"{low:.{decimals}f}",
                        "high": f"{high:.{decimals}f}",
                    }
                    reason = "reject.reason.out_of_range"
                    outcome = self._record(
                        active,
                        code,
                        passed=passed,
                        value_num=value,
                        limits=(low, high),
                        reason_key=None if passed else reason,
                        reason_params=params,
                    )
                outcomes.append(outcome)
                if outcome.passed is False and first_fail is None:
                    first_fail = (outcome, reason, params)

            ambient_reading = self._records.latest_ambient()
            ambient = ambient_reading.value_c if ambient_reading else None
            margin = limits.temp_margin_c
            t_reg = measurement.t_reg_c
            code = CheckCode.B3_T_REG
            if t_reg is None or ambient is None:
                reason = (
                    "reject.reason.value_missing"
                    if t_reg is None
                    else "reject.reason.ambient_missing"
                )
                params = {"check_key": code.label_key}
                outcome = self._record(
                    active,
                    code,
                    passed=False,
                    value_num=None if t_reg is None else float(quantize(t_reg, decimals)),
                    reason_key=reason,
                    reason_params=params,
                )
            else:
                rise = float(quantize(t_reg - ambient, decimals))
                limit = float(quantize(ambient + margin, decimals))
                passed = quantize(t_reg - ambient, decimals) <= quantize(margin, decimals)
                value = float(quantize(t_reg, decimals))
                reason = "reject.reason.temp_too_high"
                params = {
                    "check_key": code.label_key,
                    "value": f"{value:.{decimals}f}",
                    "ambient": f"{ambient:.1f}",
                    "margin": f"{margin:g}",
                    "limit": f"{limit:.{decimals}f}",
                    "rise": f"{rise:.{decimals}f}",
                }
                outcome = self._record(
                    active,
                    code,
                    passed=passed,
                    value_num=value,
                    limits=(None, limit),
                    value_text=f"rise {rise:.{decimals}f} °C over ambient {ambient:.1f} °C",
                    reason_key=None if passed else reason,
                    reason_params=params,
                )
            outcomes.append(outcome)
            if outcome.passed is False and first_fail is None:
                first_fail = (outcome, reason, params)

            if measurement.t_amb_c is not None:
                self._record(
                    active,
                    CheckCode.B3_T_AMB,
                    passed=None,
                    value_num=float(quantize(measurement.t_amb_c, decimals)),
                )

            if first_fail is not None:
                failed_outcome, reason, params = first_fail
                rejected = self._fail(active, failed_outcome, reason, params)
                outcomes = [rejected if o is failed_outcome else o for o in outcomes]
            return outcomes

    # ================================================================== labeling
    def reconcile_identity(
        self,
        qr_id: str,
        device_id: str | None,
        *,
        after_write: bool = False,
        method: IdEntryMethod = IdEntryMethod.CAMERA,
    ) -> IdentityOutcome:
        with self._lock:
            active = self._require_active()
            if active.stage is not Stage.LABELING:
                raise RecordStateError("identity is reconciled in the labeling stage")
            qr = qr_id.strip()
            if active.qr_id is None or qr != active.qr_id:
                raise RecordStateError("read the QR code first")
            current = (device_id or "").strip()
            if not after_write:
                if current == qr:
                    self._records.set_device_id(active.device_row_id, qr, method)
                    active.device_id = qr
                    active.identity = IdentityStatus.MATCH
                    self._record(active, CheckCode.C_ID_SYNC, passed=True, value_text=f"match {qr}")
                    return IdentityOutcome(status=IdentityStatus.MATCH, qr_id=qr, device_id=current)
                active.identity = IdentityStatus.WRITE_REQUIRED
                return IdentityOutcome(
                    status=IdentityStatus.WRITE_REQUIRED, qr_id=qr, device_id=current or None
                )
            if active.identity is not IdentityStatus.WRITE_REQUIRED:
                raise RecordStateError("no ID write was requested")
            if current == qr:
                self._records.set_device_id(active.device_row_id, qr, method)
                active.device_id = qr
                active.identity = IdentityStatus.CONFIRMED
                self._record(active, CheckCode.C_ID_SYNC, passed=True, value_text=f"written {qr}")
                return IdentityOutcome(status=IdentityStatus.CONFIRMED, qr_id=qr, device_id=current)
            active.identity = IdentityStatus.FAILED
            params = {"qr": qr, "device": current or "-"}
            outcome = self._record(
                active,
                CheckCode.C_ID_SYNC,
                passed=False,
                value_text=f"qr {qr} / device {current or '-'}",
                reason_key="reject.reason.id_sync_failed",
                reason_params=params,
            )
            rejected = self._fail(active, outcome, "reject.reason.id_sync_failed", params)
            return IdentityOutcome(
                status=IdentityStatus.FAILED,
                qr_id=qr,
                device_id=current or None,
                reject=rejected.reject,
            )

    # ================================================================== internals
    def _require_active(self) -> _Active:
        active = self._active
        if active is None:
            raise RecordStateError("no device on the bench")
        if active.status is not DeviceStatus.IN_PROGRESS:
            raise RecordStateError(f"device is already {active.status.value}")
        return active

    def _record(
        self,
        active: _Active,
        code: CheckCode,
        *,
        passed: bool | None,
        value_num: float | None = None,
        value_text: str | None = None,
        limits: tuple[float | None, float | None] | None = None,
        operator_marked: bool = False,
        attempt: int = 1,
        max_attempts: int = 1,
        retry_allowed: bool = False,
        reason_key: str | None = None,
        reason_params: dict[str, Any] | None = None,
        publish: bool = True,
    ) -> CheckOutcome:
        self._records.record_check(
            active.device_row_id,
            code.stage,
            code,
            value=value_num,
            value_text=value_text,
            limits=limits,
            passed=passed,
            operator_marked=operator_marked,
        )
        low, high = limits if limits is not None else (None, None)
        outcome = CheckOutcome(
            check_code=code,
            stage=code.stage,
            passed=passed,
            value_num=value_num,
            value_text=value_text,
            unit=code.meta.unit,
            limit_low=low,
            limit_high=high,
            reason_key=reason_key,
            reason_params=dict(reason_params or {}),
            retry_allowed=retry_allowed,
            attempt=attempt,
            max_attempts=max_attempts,
        )
        active.outcomes[code] = outcome
        if publish:
            self._bus.publish(CheckRecorded(active.device_row_id, outcome))
        return outcome

    def _fail(
        self, active: _Active, outcome: CheckOutcome, reason_key: str, params: dict[str, Any]
    ) -> CheckOutcome:
        full = {"check_key": outcome.check_code.label_key, **params}
        instruction = self._do_reject(active, outcome.check_code, reason_key, full)
        rejected = outcome.model_copy(
            update={"reject": instruction, "reason_key": reason_key, "reason_params": full}
        )
        active.outcomes[outcome.check_code] = rejected
        return rejected

    def _do_reject(
        self, active: _Active, code: CheckCode, reason_key: str, params: dict[str, Any]
    ) -> RejectInstruction:
        stage = active.stage
        self._records.reject_device(active.device_row_id, stage, code, reason_key, params)
        instruction = RejectInstruction(
            device_row_id=active.device_row_id,
            stage=stage,
            check_code=code,
            reason_key=reason_key,
            reason_params=params,
        )
        active.status = DeviceStatus.REJECTED
        active.stage = Stage.REJECTED
        active.reject = instruction
        self._bus.publish(StageChanged(active.device_row_id, stage, Stage.REJECTED))
        self._bus.publish(DeviceRejected(active.device_row_id, instruction))
        return instruction

    def _snapshot(self) -> DeviceState | None:
        active = self._active
        if active is None:
            return None
        return DeviceState(
            device_row_id=active.device_row_id,
            mac_address=active.mac_address,
            device_id=active.device_id,
            qr_id=active.qr_id,
            stage=active.stage,
            status=active.status,
            started_at=active.started_at,
            upload_attempts=active.upload_attempts,
            upload_failures=active.upload_failures,
            readings=list(active.readings),
            marks=dict(active.marks),
            outcomes=dict(active.outcomes),
            identity=active.identity,
            reject=active.reject,
        )


def _as_bool(value: CheckValue, code: CheckCode) -> bool:
    if not isinstance(value, bool):
        raise InputError(f"{code.value} needs True/False, got {value!r}")
    return value
