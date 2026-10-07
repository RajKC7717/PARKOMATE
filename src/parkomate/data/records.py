"""Production records API - the service the workflow and the UI call to persist production data.

It is stateful: it knows the open session (one per station) and validates every request
against the stored state, raising typed errors instead of writing inconsistent data, e.g.:

* no device can start without an open session, and only one device can be in progress;
* a check can only be recorded for an in-progress device and only for its own stage;
* a rejected device cannot be completed, a finished device cannot be rejected;
* "reduce failure count by 1" is allowed once per device, after a failure followed by a
  success.

Counters are never stored: they are computed from ``counter_events``.
"""

from __future__ import annotations

import logging
import re
import threading
from collections.abc import Mapping
from typing import Any

from parkomate.core.enums import (
    AmbientReason,
    CheckCode,
    CounterEvent,
    DeviceStatus,
    IdEntryMethod,
    Role,
    SessionEndReason,
    Stage,
)
from parkomate.core.errors import InputError, PermissionDeniedError, RecordStateError
from parkomate.core.events import (
    AmbientMeasured,
    CountersChanged,
    DeviceAbandoned,
    EventBus,
    SessionEnded,
    SessionStarted,
)
from parkomate.core.models import (
    AmbientReading,
    CheckResult,
    CounterEventRecord,
    Counters,
    Device,
    FirmwareInfo,
    Operator,
    Session,
    SessionSummary,
)
from parkomate.data import Repositories
from parkomate.i18n import tr_message

log = logging.getLogger(__name__)

RECORD_LANGUAGE = "en"
"""Language of the human-readable ``reject_reason`` stored with a device."""

_MAC_HEX = re.compile(r"^[0-9A-F]{12}$")


def normalise_mac(mac: str) -> str:
    """``24-6f-28-aa-bb-cc`` / ``246F28AABBCC`` -> ``24:6F:28:AA:BB:CC``."""
    compact = re.sub(r"[\s:\-.]", "", mac).upper()
    if not _MAC_HEX.match(compact):
        raise InputError(f"invalid MAC address {mac!r}", params={"value": mac})
    return ":".join(compact[i : i + 2] for i in range(0, 12, 2))


class ProductionRecords:
    def __init__(
        self, repos: Repositories, *, station_id: str, bus: EventBus | None = None
    ) -> None:
        self._repos = repos
        self._station_id = station_id
        self._bus = bus or EventBus()
        self._lock = threading.RLock()
        self._session_id: int | None = None
        self._operator: Operator | None = None

    # ------------------------------------------------------------------ properties
    @property
    def repos(self) -> Repositories:
        return self._repos

    @property
    def bus(self) -> EventBus:
        return self._bus

    @property
    def station_id(self) -> str:
        return self._station_id

    @station_id.setter
    def station_id(self, value: str) -> None:
        self._station_id = value

    @property
    def session(self) -> Session | None:
        with self._lock:
            if self._session_id is None:
                return None
            return self._repos.sessions.get(self._session_id)

    @property
    def operator(self) -> Operator | None:
        with self._lock:
            return self._operator

    def require_session(self) -> Session:
        session = self.session
        if session is None or not session.is_open:
            raise RecordStateError("no open session")
        return session

    def require_operator(self) -> Operator:
        with self._lock:
            if self._operator is None:
                raise RecordStateError("no operator logged in")
            return self._operator

    # ------------------------------------------------------------------ sessions
    def start_session(self, operator: Operator, *, language: str) -> Session:
        with self._lock:
            if self._session_id is not None:
                raise RecordStateError("a session is already open on this station")
            if not operator.is_active:
                raise RecordStateError(f"operator {operator.operator_code!r} is inactive")
            with self._repos.db.transaction():
                session = self._repos.sessions.create(operator.id, self._station_id, language)
                self._repos.audit.record(
                    operator.id,
                    "session.start",
                    {"session_id": session.id, "station_id": self._station_id},
                )
            self._session_id = session.id
            self._operator = operator
        self._bus.publish(SessionStarted(session.id, operator.id))
        return session

    def end_session(self, reason: SessionEndReason) -> Session:
        """Close the open session. An unfinished device is marked abandoned."""
        with self._lock:
            session = self.require_session()
            operator = self.require_operator()
            now = self._repos.clock.now()
            with self._repos.db.transaction():
                abandoned = self._repos.devices.abandon_in_session(session.id, now)
                self._repos.sessions.close(session.id, reason, now)
                self._repos.audit.record(
                    operator.id,
                    "session.end",
                    {"session_id": session.id, "reason": reason.value, "abandoned": abandoned},
                )
            self._session_id = None
            self._operator = None
            closed = self._repos.sessions.require(session.id)
        for device_row_id in abandoned:
            self._bus.publish(DeviceAbandoned(device_row_id))
        self._bus.publish(SessionEnded(session.id))
        return closed

    def set_session_firmware(self, firmware: FirmwareInfo) -> None:
        session = self.require_session()
        self._repos.sessions.set_firmware(
            session.id, firmware.name, firmware.version, firmware.sha256
        )

    def set_session_language(self, language: str) -> None:
        """Remember the operator's language choice (per operator, for the next login)."""
        operator = self.require_operator()
        self._repos.operators.set_language(operator.id, language)
        with self._lock:
            self._operator = self._repos.operators.require(operator.id)

    # ------------------------------------------------------------------ ambient
    def record_ambient(self, value_c: float, reason: AmbientReason) -> AmbientReading:
        session = self.require_session()
        if not -40.0 <= value_c <= 125.0:
            raise InputError(f"ambient temperature {value_c} °C out of sensor range")
        reading = self._repos.sessions.add_ambient(session.id, value_c, reason)
        self._bus.publish(AmbientMeasured(session.id, value_c))
        return reading

    def latest_ambient(self) -> AmbientReading | None:
        session = self.require_session()
        return self._repos.sessions.latest_ambient(session.id)

    # ------------------------------------------------------------------ devices
    def start_device(self, mac: str, *, firmware_version: str | None = None) -> int:
        """Register a new board on the bench. Returns the device row id."""
        normalised = normalise_mac(mac)
        with self._lock:
            session = self.require_session()
            active = self._repos.devices.active_for_session(session.id)
            if active is not None:
                raise RecordStateError(
                    f"device row {active.id} is still in progress; finish it first",
                    context={"device_row_id": active.id},
                )
            device = self._repos.devices.create(session.id, normalised, firmware_version)
        log.info("device %s started (row %d)", normalised, device.id)
        return device.id

    def get_device(self, device_row_id: int) -> Device:
        return self._repos.devices.require(device_row_id)

    def active_device(self) -> Device | None:
        session = self.session
        if session is None:
            return None
        return self._repos.devices.active_for_session(session.id)

    def list_session_devices(self, session_id: int | None = None) -> list[Device]:
        sid = session_id if session_id is not None else self.require_session().id
        return self._repos.devices.list_for_session(sid)

    def checks_for_device(self, device_row_id: int) -> list[CheckResult]:
        return self._repos.checks.list_for_device(device_row_id)

    def _require_in_progress(self, device_row_id: int) -> Device:
        device = self._repos.devices.require(device_row_id)
        session = self.require_session()
        if device.session_id != session.id:
            raise RecordStateError(
                f"device row {device_row_id} belongs to another session",
                context={"device_row_id": device_row_id},
            )
        if device.status is not DeviceStatus.IN_PROGRESS:
            raise RecordStateError(
                f"device row {device_row_id} is already {device.status.value}",
                context={"device_row_id": device_row_id, "status": device.status.value},
            )
        return device

    def record_check(
        self,
        device_row_id: int,
        stage: Stage,
        check_code: CheckCode,
        *,
        value: float | str | None = None,
        unit: str | None = None,
        limits: tuple[float | None, float | None] | None = None,
        passed: bool | None = None,
        operator_marked: bool = False,
        value_text: str | None = None,
    ) -> CheckResult:
        """Store one check result. Limits used for the decision are stored with it."""
        if check_code.stage is not stage:
            raise RecordStateError(
                f"{check_code.value} belongs to stage {check_code.stage.value}, not {stage.value}"
            )
        low, high = limits if limits is not None else (None, None)
        if low is not None and high is not None and low > high:
            raise InputError(f"limit_low {low} > limit_high {high} for {check_code.value}")
        value_num: float | None = None
        if isinstance(value, bool):
            raise InputError("pass booleans via 'passed', not 'value'")
        if isinstance(value, int | float):
            value_num = float(value)
        elif isinstance(value, str):
            value_text = value if value_text is None else f"{value} | {value_text}"
        with self._lock:
            self._require_in_progress(device_row_id)
            return self._repos.checks.add(
                device_row_id,
                stage,
                check_code,
                value_text=value_text,
                value_num=value_num,
                unit=unit if unit is not None else check_code.meta.unit,
                limit_low=low,
                limit_high=high,
                passed=passed,
                operator_marked=operator_marked,
            )

    def set_device_id(self, device_row_id: int, device_id: str, method: IdEntryMethod) -> None:
        device_id = device_id.strip()
        if not device_id:
            raise InputError("device ID must not be empty")
        with self._lock:
            self._require_in_progress(device_row_id)
            self._repos.devices.set_device_id(device_row_id, device_id, method)

    def set_device_firmware(self, device_row_id: int, version: str) -> None:
        with self._lock:
            self._require_in_progress(device_row_id)
            self._repos.devices.set_firmware_version(device_row_id, version)

    def complete_device(self, device_row_id: int) -> Device:
        with self._lock:
            self._require_in_progress(device_row_id)
            self._repos.devices.finish(
                device_row_id, DeviceStatus.COMPLETE, self._repos.clock.now()
            )
            device = self._repos.devices.require(device_row_id)
        self._publish_counters()
        return device

    def reject_device(
        self,
        device_row_id: int,
        stage: Stage,
        check_code: CheckCode,
        reason_key: str,
        reason_params: Mapping[str, Any] | None = None,
    ) -> Device:
        """Reject the device at ``stage`` because of ``check_code``.

        ``reason_key``/``reason_params`` are stored so reports can render the reason in
        any language; an English rendering is stored in ``reject_reason`` for direct reads.
        """
        if not stage.is_production:
            raise RecordStateError(f"cannot reject at stage {stage.value}")
        params = dict(reason_params or {})
        reason_text = tr_message(RECORD_LANGUAGE, reason_key, params)
        with self._lock:
            self._require_in_progress(device_row_id)
            self._repos.devices.reject(
                device_row_id,
                stage=stage,
                check_code=check_code,
                reason=reason_text,
                reason_key=reason_key,
                reason_params=params,
                finished_at=self._repos.clock.now(),
            )
            device = self._repos.devices.require(device_row_id)
        log.info(
            "device row %d rejected at %s (%s): %s",
            device_row_id,
            stage.value,
            check_code.value,
            reason_text,
        )
        self._publish_counters()
        return device

    def abandon_device(self, device_row_id: int) -> Device:
        with self._lock:
            self._require_in_progress(device_row_id)
            self._repos.devices.finish(
                device_row_id, DeviceStatus.ABANDONED, self._repos.clock.now()
            )
            device = self._repos.devices.require(device_row_id)
        self._bus.publish(DeviceAbandoned(device_row_id))
        return device

    # ------------------------------------------------------------------ counters
    def counter_event(
        self, event: CounterEvent, device_row_id: int | None = None
    ) -> CounterEventRecord:
        """Append a counter event for the session operator.

        ``upload_success``/``upload_failure`` also count a programming attempt on the
        device. ``failure_adjusted`` is checked with :meth:`can_adjust_failure`. ``reset``
        must go through :meth:`reset_counters` (admin only).
        """
        if event is CounterEvent.RESET:
            raise RecordStateError("use reset_counters() for resets (admin only)")
        if device_row_id is None:
            raise InputError(f"{event.value} needs a device")
        with self._lock:
            session = self.require_session()
            operator = self.require_operator()
            if event is CounterEvent.FAILURE_ADJUSTED:
                if not self.can_adjust_failure(device_row_id):
                    raise RecordStateError(
                        f"failure count cannot be adjusted for device row {device_row_id}",
                        context={"device_row_id": device_row_id},
                    )
                with self._repos.db.transaction():
                    record = self._repos.counters.add(session.id, event, operator.id, device_row_id)
                    self._repos.audit.record(
                        operator.id,
                        "counter.failure_adjusted",
                        {"session_id": session.id, "device_row_id": device_row_id},
                    )
            else:
                self._require_in_progress(device_row_id)
                with self._repos.db.transaction():
                    record = self._repos.counters.add(session.id, event, operator.id, device_row_id)
                    self._repos.devices.increment_programming_attempts(device_row_id)
        self._publish_counters()
        return record

    def adjust_failure(self, device_row_id: int) -> CounterEventRecord:
        """Operator accepted "Remove 1 failure from count for this device"."""
        return self.counter_event(CounterEvent.FAILURE_ADJUSTED, device_row_id)

    def can_adjust_failure(self, device_row_id: int) -> bool:
        """True when the device had an upload failure followed by a success and has not
        been adjusted yet (at most once per device)."""
        session = self.session
        device = self._repos.devices.get(device_row_id)
        if session is None or device is None or device.session_id != session.id:
            return False
        seen_failure = False
        recovered = False
        for record in self._repos.counters.list_for_device(device_row_id):
            if record.event is CounterEvent.FAILURE_ADJUSTED:
                return False
            if record.event is CounterEvent.UPLOAD_FAILURE:
                seen_failure = True
            elif record.event is CounterEvent.UPLOAD_SUCCESS and seen_failure:
                recovered = True
        return recovered

    def reset_counters(self, actor: Operator) -> CounterEventRecord:
        """Admin action: live counters restart from zero (history and summary are kept)."""
        if actor.role is not Role.ADMIN or not actor.is_active:
            raise PermissionDeniedError(
                f"operator {actor.operator_code!r} may not reset counters",
                context={"operator_id": actor.id},
            )
        with self._lock:
            session = self.require_session()
            with self._repos.db.transaction():
                record = self._repos.counters.add(session.id, CounterEvent.RESET, actor.id)
                self._repos.audit.record(actor.id, "counter.reset", {"session_id": session.id})
        self._publish_counters()
        return record

    def get_counters(self, session_id: int | None = None) -> Counters:
        """Live counters since the last reset of the session."""
        sid = session_id if session_id is not None else self.require_session().id
        reset = self._repos.counters.last_reset(sid)
        totals = self._repos.counters.totals(sid, after_id=reset.id if reset else 0)
        completed = rejected = 0
        for device in self._repos.devices.list_for_session(sid):
            if device.finished_at is None:
                continue
            if reset is not None and device.finished_at < reset.created_at:
                continue
            if device.status is DeviceStatus.COMPLETE:
                completed += 1
            elif device.status is DeviceStatus.REJECTED:
                rejected += 1
        return Counters(
            session_id=sid,
            upload_success=totals[CounterEvent.UPLOAD_SUCCESS],
            upload_failure=totals[CounterEvent.UPLOAD_FAILURE],
            failures_adjusted=totals[CounterEvent.FAILURE_ADJUSTED],
            completed=completed,
            rejected=rejected,
            since=reset.created_at if reset else None,
        )

    def _publish_counters(self) -> None:
        session = self.session
        if session is not None:
            self._bus.publish(CountersChanged(session.id))

    # ------------------------------------------------------------------ summary
    def current_session_summary(self) -> SessionSummary:
        return self.session_summary(self.require_session().id)

    def session_summary(self, session_id: int) -> SessionSummary:
        from parkomate.reports.summary import build_session_summary

        return build_session_summary(self._repos, session_id)
