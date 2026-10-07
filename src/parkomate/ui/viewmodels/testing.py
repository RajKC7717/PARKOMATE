"""Stage B - Testing: communication, sensor readings + operator marks, electrical measurement."""

from __future__ import annotations

from typing import TYPE_CHECKING

from PySide6.QtCore import QTimer

from parkomate.core.enums import CheckCode, Stage
from parkomate.core.errors import ParkomateError
from parkomate.core.models import CheckOutcome, Measurement, SensorReading
from parkomate.ui.viewmodels.base import Action, ConfirmState, StageViewModel, StatusLine
from parkomate.ui.viewmodels.programming import StepState

if TYPE_CHECKING:
    from parkomate.ui.viewmodels.station import StationController

MARK_CODES = (CheckCode.B2_SENSOR_OK, CheckCode.B2_INDICATOR_OK)


class TestingViewModel(StageViewModel):
    stage = Stage.TESTING

    def __init__(self, controller: StationController) -> None:
        super().__init__(controller)
        self._countdown = QTimer(self)
        self._countdown.setInterval(1000)
        self._countdown.timeout.connect(self._count_down)
        controller.ambient_changed.connect(self.notify)
        self.reset()

    def reset(self) -> None:
        self._countdown.stop()
        self.comm_state = StepState.PENDING
        self.readings: list[SensorReading] = []
        self.reading_busy = False
        self.marks: dict[CheckCode, bool | None] = dict.fromkeys(MARK_CODES)
        self.measure_state = StepState.PENDING
        self.results: list[CheckOutcome] = []
        self.seconds_left = 0

    @property
    def total_readings(self) -> int:
        return int(self.c.settings.limits.sensor_reading_count)

    @property
    def readings_done(self) -> bool:
        return len(self.readings) >= self.total_readings

    @property
    def marks_ok(self) -> bool:
        return all(self.marks[code] is True for code in MARK_CODES)

    def enter(self) -> None:
        if self.comm_state is StepState.PENDING:
            self.test_comm()  # automatic on entering Testing
        self.notify()

    # ------------------------------------------------------------------ B1
    def test_comm(self) -> None:
        if self.comm_state is StepState.WORKING:
            return
        self.c.clear_error()
        self.comm_state = StepState.WORKING
        self.notify()
        self.c.hw.submit(
            self.c.ctx.hardware.ping,
            on_success=self._pinged,
            on_error=self._ping_error,
            name="ping",
        )

    def _pinged(self, ok: bool) -> None:
        outcome = self.guard(lambda: self.c.ctx.workflow.submit_check(CheckCode.B1_COMM, bool(ok)))
        if outcome is None:
            self.comm_state = StepState.ERROR
        else:
            self.comm_state = StepState.PASS if outcome.passed else StepState.FAIL
        self.c.device_updated()
        self.notify()

    def _ping_error(self, error: ParkomateError) -> None:
        self.comm_state = StepState.ERROR
        self.c.show_error(error, retry=self.test_comm, retry_key="action.test_again")
        self.notify()

    # ------------------------------------------------------------------ B2
    def read_sensor(self) -> None:
        if self.reading_busy or self.readings_done or self.comm_state is not StepState.PASS:
            return
        self.c.clear_error()
        self.reading_busy = True
        self.notify()
        self.c.hw.submit(
            self.c.ctx.hardware.read_sensor,
            on_success=self._sensor_read,
            on_error=self._sensor_error,
            name="read_sensor",
        )

    def _sensor_read(self, reading: SensorReading) -> None:
        self.reading_busy = False
        code = CheckCode.reading(len(self.readings) + 1)
        outcome = self.guard(lambda: self.c.ctx.workflow.submit_check(code, reading.value))
        if outcome is not None:
            self.readings.append(reading)
        self.c.device_updated()
        self.notify()

    def _sensor_error(self, error: ParkomateError) -> None:
        self.reading_busy = False
        self.c.show_error(error, retry=self.read_sensor)
        self.notify()

    def mark(self, code: CheckCode, ok: bool) -> None:
        """Operator marks Sensor readings / Indicator light as Success or Failure."""
        if code not in MARK_CODES or self.marks[code] is not None:
            return
        if code is CheckCode.B2_SENSOR_OK and not self.readings_done:
            return
        if self.comm_state is not StepState.PASS:
            return
        if ok:
            self._submit_mark(code, True)
            return
        self.c.ask(
            ConfirmState(
                "confirm.mark_failed",
                lambda: self._submit_mark(code, False),
                yes_key="action.yes_failed",
                params={"check_key": code.label_key},
            )
        )

    def _submit_mark(self, code: CheckCode, ok: bool) -> None:
        outcome = self.guard(lambda: self.c.ctx.workflow.submit_check(code, ok))
        if outcome is not None:
            self.marks[code] = ok
        self.c.device_updated()
        self.notify()
        if self.marks_ok and self.readings_done and self.measure_state is StepState.PENDING:
            self.measure()  # automatic once B2 is complete

    # ------------------------------------------------------------------ B3
    def measure(self) -> None:
        if self.measure_state is StepState.WORKING or not (self.readings_done and self.marks_ok):
            return
        self.c.clear_error()
        timeout = float(self.c.settings.timeouts.measurement_s)
        self.measure_state = StepState.WORKING
        self.results = []
        self.seconds_left = round(timeout)
        self._countdown.start()
        self.notify()
        self.c.hw.submit(
            lambda: self.c.ctx.hardware.measure(timeout),
            on_success=self._measured,
            on_error=self._measure_error,
            name="measure",
        )

    def _count_down(self) -> None:
        self.seconds_left = max(0, self.seconds_left - 1)
        self.notify()

    def _measured(self, measurement: Measurement) -> None:
        self._countdown.stop()
        outcomes = self.guard(lambda: self.c.ctx.workflow.evaluate_measurement(measurement))
        if outcomes is None:
            self.measure_state = StepState.ERROR
        else:
            self.results = list(outcomes)
            failed = any(o.passed is False for o in self.results)
            self.measure_state = StepState.FAIL if failed else StepState.PASS
        self.c.device_updated()
        self.notify()

    def _measure_error(self, error: ParkomateError) -> None:
        self._countdown.stop()
        self.measure_state = StepState.ERROR
        self.c.show_error(error, retry=self.measure, retry_key="action.measure_again")
        self.notify()

    # ------------------------------------------------------------------ reject
    def reject_device(self) -> None:
        missing = self.c.ctx.workflow.missing_checks()
        code = missing[0] if missing else CheckCode.B1_COMM
        self.c.ask(
            ConfirmState(
                "confirm.reject_device",
                lambda: self.guard(lambda: self.c.ctx.workflow.reject(code)),
                yes_key="action.reject_device",
            )
        )

    # ------------------------------------------------------------------ bottom bar
    def primary(self) -> Action:
        enter = "key.enter"
        if self.comm_state is StepState.WORKING:
            return Action(
                "action.read_sensor_n",
                enabled=False,
                reason_key="gate.testing_comm",
                params={"n": 1, "total": self.total_readings},
                hint_key=enter,
                name="read",
            )
        if self.comm_state is not StepState.PASS:
            return Action("action.test_again", self.test_comm, hint_key=enter, name="test_comm")
        if not self.readings_done:
            n = len(self.readings) + 1
            return Action(
                "action.read_sensor_n",
                self.read_sensor,
                params={"n": n, "total": self.total_readings},
                enabled=not self.reading_busy,
                reason_key="gate.reading_sensor" if self.reading_busy else None,
                hint_key=enter,
                name="read",
            )
        if not self.marks_ok:
            return Action(
                "action.measure",
                enabled=False,
                reason_key="gate.mark_sensor_indicator",
                hint_key=enter,
                name="measure",
            )
        if self.measure_state is StepState.WORKING:
            return Action(
                "action.measure",
                enabled=False,
                reason_key="gate.waiting_measurement",
                reason_params={"s": self.seconds_left},
                hint_key=enter,
                name="measure",
            )
        if self.measure_state is StepState.PASS:
            return Action("action.submit_next", self.c.advance, hint_key=enter, name="next")
        return Action("action.measure", self.measure, hint_key=enter, name="measure")

    def secondary(self) -> list[Action]:
        actions: list[Action] = []
        if self.comm_state is StepState.PASS and not self.readings:
            actions.append(
                Action("action.test_again", self.test_comm, variant="secondary", name="test_again")
            )
        if self.c.device_in_progress and self.measure_state is not StepState.WORKING:
            actions.append(
                Action("action.reject_device", self.reject_device, variant="danger", name="reject")
            )
        return actions

    def status(self) -> StatusLine | None:
        missing = self.c.ctx.workflow.missing_checks()
        if not missing:
            return StatusLine("status.all_checks_done", tone="pass")
        if self.measure_state is StepState.WORKING:
            return StatusLine("status.test.waiting", {"s": self.seconds_left}, tone="pending")
        items: list[str | tuple[str, dict[str, int]]] = []
        if any(code.reading_index is not None for code in missing):
            items.append(
                ("status.item.readings", {"n": len(self.readings), "total": self.total_readings})
            )
        items.extend(code.label_key for code in missing if code.reading_index is None)
        return StatusLine(
            "status.still_needed",
            {"items_keys": items[:2], "more": max(0, len(items) - 2)},
            tone="warn",
        )
