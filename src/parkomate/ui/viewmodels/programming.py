"""Stage A - Programming: connect board, whitelist, firmware, upload (with retry)."""

from __future__ import annotations

from enum import StrEnum
from typing import TYPE_CHECKING, Any

from PySide6.QtCore import QElapsedTimer, QTimer

from parkomate.core.enums import CheckCode, Stage
from parkomate.core.errors import HardwareError, ParkomateError
from parkomate.core.models import CheckOutcome, FlashResult, PortInfo, WhitelistResult
from parkomate.ui.viewmodels.base import Action, ConfirmState, StageViewModel, StatusLine

if TYPE_CHECKING:
    from parkomate.ui.viewmodels.station import StationController


class StepState(StrEnum):
    PENDING = "pending"
    WORKING = "working"
    PASS = "pass"
    FAIL = "fail"
    ERROR = "error"


class FlashInterruptedError(HardwareError):
    """``flash()`` raised (e.g. cable pulled): counts as a failed upload attempt."""

    def __init__(self, original: ParkomateError) -> None:
        super().__init__(
            original.message, code=original.code, params=original.params, context=original.context
        )
        self.original = original


class ProgrammingViewModel(StageViewModel):
    stage = Stage.PROGRAMMING

    def __init__(self, controller: StationController) -> None:
        super().__init__(controller)
        self._elapsed = QElapsedTimer()
        self._ticker = QTimer(self)
        self._ticker.setInterval(200)
        self._ticker.timeout.connect(self._tick)
        controller.firmware_changed.connect(self.notify)
        self.ports: list[PortInfo] = []
        self.ports_loaded = False
        self.reset()

    # ------------------------------------------------------------------ state
    def reset(self) -> None:
        self._ticker.stop()
        self.ports_loading = False
        self.selected_port: str | None = None
        self.connect_state = StepState.PENDING
        self.mac: str | None = None
        self.chip = ""
        self.whitelist_state = StepState.PENDING
        self.upload_state = StepState.PENDING
        self.progress = 0
        self.elapsed_s = 0.0
        self.attempts = 0
        self.last_outcome: CheckOutcome | None = None
        self.adjust_prompt = False
        self.adjust_done = False
        if self.ports:
            self._auto_select()

    @property
    def max_attempts(self) -> int:
        return int(self.c.settings.programming.max_retries)

    @property
    def device_started(self) -> bool:
        return self.mac is not None

    @property
    def firmware_ready(self) -> bool:
        return self.c.firmware is not None and not self.c.firmware_loading

    def enter(self) -> None:
        if not self.ports_loaded and not self.ports_loading:
            self.refresh_ports()
        self.notify()

    # ------------------------------------------------------------------ ports
    def refresh_ports(self) -> None:
        if self.ports_loading or self.device_started:
            return
        self.ports_loading = True
        self.notify()
        self.c.hw.submit(
            self.c.ctx.hardware.list_ports,
            on_success=self._ports_listed,
            on_error=self._ports_failed,
            name="list_ports",
        )

    def _ports_listed(self, ports: list[PortInfo]) -> None:
        self.ports_loading = False
        self.ports_loaded = True
        self.ports = list(ports)
        self._auto_select()
        self.notify()

    def _ports_failed(self, error: ParkomateError) -> None:
        self.ports_loading = False
        self.c.show_error(error, retry=self.refresh_ports, retry_key="action.refresh_ports")
        self.notify()

    def _auto_select(self) -> None:
        """Auto-select when exactly one ESP32 bridge is connected."""
        names = {p.name for p in self.ports}
        if self.selected_port in names:
            return
        candidates = [p for p in self.ports if p.is_esp_candidate]
        self.selected_port = candidates[0].name if len(candidates) == 1 else None

    def select_port(self, name: str | None) -> None:
        if self.device_started:
            return
        self.selected_port = name
        self.notify()

    # ------------------------------------------------------------------ connect
    def connect_board(self) -> None:
        port = self.selected_port
        if port is None or self.connect_state is StepState.WORKING or self.device_started:
            return
        self.c.clear_error()
        self.connect_state = StepState.WORKING
        self.notify()
        hardware = self.c.ctx.hardware

        def job() -> tuple[str, str]:
            hardware.connect(port)
            return hardware.read_mac(), hardware.chip_name()

        self.c.hw.submit(
            job, on_success=self._connected, on_error=self._connect_failed, name="connect"
        )

    def _connected(self, result: tuple[str, str]) -> None:
        mac, chip = result
        state = self.guard(lambda: self.c.ctx.workflow.start_device(mac))
        if state is None:
            self.connect_state = StepState.ERROR
            self.notify()
            return
        self.mac = state.mac_address
        self.chip = chip
        self.connect_state = StepState.PASS
        self.c.device_updated()
        self.notify()
        self.check_whitelist()

    def _connect_failed(self, error: ParkomateError) -> None:
        self.connect_state = StepState.ERROR
        self.c.show_error(error, retry=self.connect_board)
        self.notify()

    # ------------------------------------------------------------------ whitelist
    def check_whitelist(self) -> None:
        mac = self.mac
        if mac is None:
            return
        self.whitelist_state = StepState.WORKING
        self.notify()
        self.c.hw.submit(
            lambda: self.c.ctx.hardware.check_whitelist(mac),
            on_success=self._whitelisted,
            on_error=self._whitelist_failed,
            name="whitelist",
        )

    def _whitelisted(self, result: WhitelistResult) -> None:
        outcome = self.guard(
            lambda: self.c.ctx.workflow.submit_check(
                CheckCode.A_WHITELIST, result.allowed, text=result.reason
            )
        )
        if outcome is None:
            self.whitelist_state = StepState.ERROR
        else:
            self.whitelist_state = StepState.PASS if outcome.passed else StepState.FAIL
        self.c.device_updated()
        self.notify()

    def _whitelist_failed(self, error: ParkomateError) -> None:
        self.whitelist_state = StepState.ERROR
        self.c.show_error(error, retry=self.check_whitelist)
        self.notify()

    # ------------------------------------------------------------------ upload
    def can_upload(self) -> bool:
        return (
            self.whitelist_state is StepState.PASS
            and self.firmware_ready
            and self.upload_state not in (StepState.WORKING, StepState.PASS)
            and self.attempts < self.max_attempts
            and self.c.reject is None
        )

    def upload(self) -> None:
        if not self.can_upload() or self.selected_port is None:
            return
        self.c.clear_error()
        self.upload_state = StepState.WORKING
        self.progress = 0
        self.elapsed_s = 0.0
        self._elapsed.start()
        self._ticker.start()
        self.notify()
        hardware = self.c.ctx.hardware
        port = self.selected_port

        def job(progress: Any) -> FlashResult:
            if not hardware.is_connected():
                hardware.connect(port)  # re-plugged after a disconnect: not an attempt yet
            try:
                return hardware.flash(progress)
            except ParkomateError as exc:
                raise FlashInterruptedError(exc) from exc

        self.c.hw.submit(
            job,
            with_progress=True,
            on_success=self._flashed,
            on_error=self._flash_error,
            on_progress=self._progress,
            name="flash",
        )

    def _progress(self, value: int) -> None:
        self.progress = max(self.progress, min(100, value))
        self.notify()

    def _tick(self) -> None:
        self.elapsed_s = self._elapsed.elapsed() / 1000.0
        self.notify()

    def _stop_timer(self) -> None:
        self._ticker.stop()
        if self._elapsed.isValid():
            self.elapsed_s = self._elapsed.elapsed() / 1000.0

    def _flashed(self, result: FlashResult) -> None:
        self._stop_timer()
        if result.success:
            self.progress = 100
        firmware = self.c.firmware
        text = (
            (firmware.version if firmware else None)
            if result.success
            else (result.error_code.value if result.error_code else result.message)
        )
        self._record_upload(result.success, text)

    def _flash_error(self, error: ParkomateError) -> None:
        self._stop_timer()
        if isinstance(error, FlashInterruptedError):
            outcome = self._record_upload(False, error.code.value)
            if outcome is not None and outcome.reject is None:
                self.c.show_error(
                    error.original, retry=self.upload, retry_key="action.retry_upload"
                )
            return
        self.upload_state = StepState.ERROR if self.attempts == 0 else StepState.FAIL
        self.c.show_error(error, retry=self.upload, retry_key="action.retry_upload")
        self.notify()

    def _record_upload(self, success: bool, text: str | None) -> CheckOutcome | None:
        outcome: CheckOutcome | None = self.guard(
            lambda: self.c.ctx.workflow.submit_check(CheckCode.A_UPLOAD, success, text=text)
        )
        if outcome is None:
            self.upload_state = StepState.ERROR
            self.notify()
            return None
        self.last_outcome = outcome
        self.attempts = outcome.attempt
        self.upload_state = StepState.PASS if outcome.passed else StepState.FAIL
        if outcome.passed and not self.adjust_done:
            state = self.c.device
            if state is not None and self.c.ctx.records.can_adjust_failure(state.device_row_id):
                self.adjust_prompt = True
        self.c.device_updated()
        self.notify()
        return outcome

    def answer_adjust(self, yes: bool) -> None:
        """'Remove 1 failure from count for this device?' - asked once per device."""
        if not self.adjust_prompt:
            return
        state = self.c.device
        if yes and state is not None:
            self.guard(lambda: self.c.ctx.records.adjust_failure(state.device_row_id))
        self.adjust_prompt = False
        self.adjust_done = True
        self.notify()

    # ------------------------------------------------------------------ reject
    def reject_device(self) -> None:
        code = (
            CheckCode.A_UPLOAD if self.whitelist_state is StepState.PASS else CheckCode.A_WHITELIST
        )
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
        if not self.device_started:
            if self.connect_state is StepState.WORKING:
                return Action(
                    "action.connect_board",
                    enabled=False,
                    reason_key="gate.connecting",
                    hint_key=enter,
                    name="connect",
                )
            if self.selected_port is None:
                reason = "gate.select_port" if self.ports else "gate.plug_board"
                return Action(
                    "action.connect_board",
                    enabled=False,
                    reason_key=reason,
                    hint_key=enter,
                    name="connect",
                )
            return Action(
                "action.connect_board", self.connect_board, hint_key=enter, name="connect"
            )
        if self.whitelist_state in (StepState.PENDING, StepState.WORKING):
            return Action(
                "action.upload_firmware",
                enabled=False,
                reason_key="gate.checking_whitelist",
                hint_key=enter,
                name="upload",
            )
        if self.whitelist_state is StepState.ERROR:
            return Action(
                "action.try_again", self.check_whitelist, hint_key=enter, name="whitelist_retry"
            )
        if self.upload_state is StepState.PASS:
            return Action("action.submit_next", self.c.advance, hint_key=enter, name="next")
        if self.upload_state is StepState.WORKING:
            return Action(
                "action.upload_firmware",
                enabled=False,
                reason_key="gate.uploading",
                hint_key=enter,
                name="upload",
            )
        if not self.firmware_ready:
            if self.c.firmware_error is not None:
                return Action(
                    "action.load_firmware",
                    self.c.load_firmware,
                    hint_key=enter,
                    name="load_firmware",
                )
            return Action(
                "action.upload_firmware",
                enabled=False,
                reason_key="gate.firmware_loading",
                hint_key=enter,
                name="upload",
            )
        if self.attempts > 0:
            return Action(
                "action.retry_upload_n",
                self.upload,
                params={"n": self.attempts + 1, "total": self.max_attempts},
                enabled=self.can_upload(),
                hint_key=enter,
                name="retry",
            )
        return Action(
            "action.upload_firmware",
            self.upload,
            enabled=self.can_upload(),
            hint_key=enter,
            name="upload",
        )

    def secondary(self) -> list[Action]:
        actions: list[Action] = []
        if not self.device_started:
            actions.append(
                Action(
                    "action.refresh_ports",
                    self.refresh_ports,
                    enabled=not self.ports_loading,
                    hint_key="key.f5",
                    variant="secondary",
                    name="refresh",
                )
            )
        elif self.c.device_in_progress and self.upload_state is not StepState.WORKING:
            failed = self.upload_state in (StepState.FAIL, StepState.ERROR) or (
                self.whitelist_state is StepState.ERROR
            )
            if failed:
                actions.append(
                    Action(
                        "action.reject_device", self.reject_device, variant="danger", name="reject"
                    )
                )
        return actions

    def status(self) -> StatusLine | None:
        if not self.device_started:
            if self.ports_loading:
                return StatusLine("status.prog.looking_for_ports", tone="pending")
            if not self.ports:
                return StatusLine("status.prog.no_ports", tone="warn")
            if self.selected_port is None:
                return StatusLine("status.prog.choose_port", tone="warn")
            return StatusLine("status.prog.ready_to_connect", {"port": self.selected_port})
        if self.upload_state is StepState.WORKING:
            return StatusLine("status.prog.uploading", {"pct": self.progress}, tone="pending")
        if self.upload_state is StepState.PASS:
            return StatusLine("status.prog.upload_ok", tone="pass")
        if self.upload_state is StepState.FAIL:
            return StatusLine(
                "status.prog.upload_failed",
                {"n": self.attempts, "total": self.max_attempts},
                tone="fail",
            )
        if self.whitelist_state is StepState.PASS and self.firmware_ready:
            return StatusLine("status.prog.ready_to_upload", tone="info")
        return None

    def function_key(self, number: int) -> bool:
        if number == 5:
            self.refresh_ports()
            return True
        return False
