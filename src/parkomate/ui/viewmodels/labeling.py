"""Stage C - Labeling (checklist, QR scan, device identity) and Stage D - Packaging."""

from __future__ import annotations

import re
from collections.abc import Callable
from typing import TYPE_CHECKING

from parkomate.core.enums import (
    LABELING_CHECKLIST,
    PACKAGING_CHECKLIST,
    CheckCode,
    IdentityStatus,
    IdEntryMethod,
    Stage,
)
from parkomate.core.errors import CameraError, ErrorCode, ParkomateError
from parkomate.core.models import IdentityOutcome
from parkomate.ui.viewmodels.base import (
    Action,
    ConfirmState,
    StageViewModel,
    StatusLine,
    missing_reason,
)
from parkomate.ui.viewmodels.programming import StepState

if TYPE_CHECKING:
    from parkomate.ui.viewmodels.station import StationController


class ChecklistMixin(StageViewModel):
    """F1-F4 tick the four checklist rows; 'Reject device' asks which item failed."""

    checklist: tuple[CheckCode, ...] = ()

    def reset_checklist(self) -> None:
        self.ticks: dict[CheckCode, bool] = dict.fromkeys(self.checklist, False)
        self.choosing_reject = False

    def toggle(self, code: CheckCode) -> None:
        if code not in self.ticks or not self.c.device_in_progress:
            return
        value = not self.ticks[code]
        if self.guard(lambda: self.c.ctx.workflow.submit_check(code, value)) is not None:
            self.ticks[code] = value
        self.notify()

    def function_key(self, number: int) -> bool:
        if 1 <= number <= len(self.checklist):
            self.toggle(self.checklist[number - 1])
            return True
        return False

    @property
    def missing_ticks(self) -> list[CheckCode]:
        return [code for code in self.checklist if not self.ticks.get(code)]

    def start_reject(self) -> None:
        self.choosing_reject = True
        self.notify()

    def cancel_reject(self) -> None:
        self.choosing_reject = False
        self.notify()

    def reject_codes(self) -> list[CheckCode]:
        return list(self.checklist)

    def reject_for(self, code: CheckCode) -> None:
        """Operator chose the failing item: confirm inline, then reject."""
        self.choosing_reject = False
        self.notify()
        reason = "reject.reason.item_missing" if code in self.checklist else "reject.reason.manual"
        self.c.ask(
            ConfirmState(
                "confirm.reject_for",
                lambda: self.guard(lambda: self.c.ctx.workflow.reject(code, reason)),
                yes_key="action.reject_device",
                params={"check_key": code.label_key},
            )
        )


class LabelingViewModel(ChecklistMixin):
    stage = Stage.LABELING
    checklist = LABELING_CHECKLIST

    def __init__(self, controller: StationController) -> None:
        super().__init__(controller)
        self.reset()

    def reset(self) -> None:
        self.reset_checklist()
        self.camera_state = StepState.PENDING
        self.qr_id: str | None = None
        self.method = IdEntryMethod.CAMERA
        self.identity_state = StepState.PENDING
        self.identity: IdentityStatus | None = None
        self.board_id: str | None = None
        self.manual_mode = False
        self.manual_error_key: str | None = None
        self.camera_open = False

    @property
    def manual_allowed(self) -> bool:
        return bool(self.c.settings.camera.allow_manual_entry)

    @property
    def identity_ok(self) -> bool:
        return self.identity in (IdentityStatus.MATCH, IdentityStatus.CONFIRMED)

    def enter(self) -> None:
        if self.qr_id is None and self.camera_state is StepState.PENDING:
            self.scan()  # automatic on entering Labeling
        self.notify()

    def leave(self) -> None:
        if self.camera_open:
            self.camera_open = False
            self.c.hw.submit(
                self.c.ctx.hardware.close_camera, name="close_camera", on_error=lambda _e: None
            )

    # ------------------------------------------------------------------ QR
    def scan(self) -> None:
        if self.camera_state is StepState.WORKING or self.identity_ok:
            return
        self.c.clear_error()
        self.camera_state = StepState.WORKING
        self.manual_mode = False
        self.notify()
        hardware = self.c.ctx.hardware
        timeout = float(self.c.settings.timeouts.qr_scan_s)

        def job() -> str | None:
            hardware.open_camera()
            return hardware.read_qr(timeout)

        self.c.hw.submit(job, on_success=self._scanned, on_error=self._scan_error, name="scan")

    def _scanned(self, code: str | None) -> None:
        self.camera_open = True
        if code is None:
            self._scan_error(CameraError("no readable QR code", code=ErrorCode.QR_UNREADABLE))
            return
        self._accept_id(code, IdEntryMethod.CAMERA)

    def _scan_error(self, error: ParkomateError) -> None:
        self.camera_state = StepState.ERROR
        self.c.show_error(error, retry=self.scan, retry_key="action.scan_again")
        self.notify()

    def start_manual(self) -> None:
        if self.manual_allowed and not self.identity_ok:
            self.manual_mode = True
            self.manual_error_key = None
            self.notify()

    def cancel_manual(self) -> None:
        self.manual_mode = False
        self.manual_error_key = None
        self.notify()

    def submit_manual(self, first: str, second: str) -> None:
        """Typed ID, entered twice. Flagged as 'manual' in the records."""
        first, second = first.strip(), second.strip()
        if not first or first != second:
            self.manual_error_key = "manual.mismatch"
        elif not re.fullmatch(self.c.settings.camera.id_pattern, first):
            self.manual_error_key = "manual.bad_format"
        else:
            self.manual_error_key = None
            self.manual_mode = False
            self._accept_id(first, IdEntryMethod.MANUAL)
            return
        self.notify()

    def _accept_id(self, code: str, method: IdEntryMethod) -> None:
        outcome = self.guard(lambda: self.c.ctx.workflow.submit_check(CheckCode.C_QR_READ, code))
        if outcome is None:
            self.camera_state = StepState.ERROR
            self.notify()
            return
        if outcome.passed is not True:
            self.camera_state = StepState.ERROR
            self.c.show_error(
                ParkomateError(
                    "bad QR format", code=ErrorCode.QR_BAD_FORMAT, params={"value": code}
                ),
                retry=self.scan,
                retry_key="action.scan_again",
            )
            self.notify()
            return
        self.qr_id = code
        self.method = method
        self.camera_state = StepState.PASS
        self.c.device_updated()
        self.notify()
        self.check_identity()

    # ------------------------------------------------------------------ identity
    def check_identity(self) -> None:
        if self.qr_id is None:
            return
        self.c.clear_error()
        self.identity_state = StepState.WORKING
        self.identity = None
        self.notify()
        self.c.hw.submit(
            self.c.ctx.hardware.get_device_id,
            on_success=self._board_id_read,
            on_error=self._identity_error(self.check_identity),
            name="get_device_id",
        )

    def _board_id_read(self, board_id: str) -> None:
        qr = self.qr_id
        if qr is None:
            return
        self.board_id = board_id
        outcome = self.guard(
            lambda: self.c.ctx.workflow.reconcile_identity(qr, board_id, method=self.method)
        )
        self._apply_identity(outcome)
        if outcome is not None and outcome.status is IdentityStatus.WRITE_REQUIRED:
            self.write_identity()

    def write_identity(self) -> None:
        qr = self.qr_id
        if qr is None:
            return
        self.c.clear_error()
        self.identity_state = StepState.WORKING
        self.identity = IdentityStatus.WRITE_REQUIRED
        self.notify()
        hardware = self.c.ctx.hardware

        def job() -> str | None:
            if not hardware.set_device_id(qr):
                return None
            return hardware.get_device_id()

        self.c.hw.submit(
            job,
            on_success=self._written,
            on_error=self._identity_error(self.write_identity),
            name="set_device_id",
        )

    def _written(self, readback: str | None) -> None:
        qr = self.qr_id
        if qr is None:
            return
        self.board_id = readback
        outcome = self.guard(
            lambda: self.c.ctx.workflow.reconcile_identity(
                qr, readback, after_write=True, method=self.method
            )
        )
        self._apply_identity(outcome)

    def _apply_identity(self, outcome: IdentityOutcome | None) -> None:
        if outcome is None:
            self.identity_state = StepState.ERROR
        else:
            self.identity = outcome.status
            self.identity_state = {
                IdentityStatus.MATCH: StepState.PASS,
                IdentityStatus.CONFIRMED: StepState.PASS,
                IdentityStatus.WRITE_REQUIRED: StepState.WORKING,
                IdentityStatus.FAILED: StepState.FAIL,
            }[outcome.status]
        self.c.device_updated()
        self.notify()

    def _identity_error(self, retry: Callable[[], None]) -> Callable[[ParkomateError], None]:
        def handle(error: ParkomateError) -> None:
            self.identity_state = StepState.ERROR
            self.c.show_error(error, retry=retry)
            self.notify()

        return handle

    def reject_codes(self) -> list[CheckCode]:
        return [*self.checklist, CheckCode.C_QR_READ, CheckCode.C_ID_SYNC]

    # ------------------------------------------------------------------ bottom bar
    def primary(self) -> Action:
        enter = "key.enter"
        if self.camera_state is StepState.WORKING:
            return Action(
                "action.submit_next",
                enabled=False,
                reason_key="gate.scanning",
                hint_key=enter,
                name="next",
            )
        if self.qr_id is None:
            return Action("action.scan_again", self.scan, hint_key=enter, name="scan")
        if self.identity_state is StepState.WORKING:
            return Action(
                "action.submit_next",
                enabled=False,
                reason_key="gate.configuring_device",
                hint_key=enter,
                name="next",
            )
        if self.identity_state is StepState.ERROR:
            retry = (
                self.write_identity
                if self.identity is IdentityStatus.WRITE_REQUIRED
                else self.check_identity
            )
            return Action("action.try_again", retry, hint_key=enter, name="identity_retry")
        missing = self.missing_ticks
        if missing:
            key, params = missing_reason(len(missing), len(self.checklist))
            return Action(
                "action.submit_next",
                enabled=False,
                reason_key=key,
                reason_params=params,
                hint_key=enter,
                name="next",
            )
        return Action(
            "action.submit_next",
            self.c.advance,
            enabled=self.identity_ok,
            hint_key=enter,
            name="next",
        )

    def secondary(self) -> list[Action]:
        actions: list[Action] = []
        if self.manual_allowed and not self.identity_ok and not self.manual_mode:
            actions.append(
                Action("action.type_id", self.start_manual, variant="secondary", name="manual")
            )
        if self.c.device_in_progress and self.identity_state is not StepState.WORKING:
            actions.append(
                Action("action.reject_device", self.start_reject, variant="danger", name="reject")
            )
        return actions

    def status(self) -> StatusLine | None:
        if self.camera_state is StepState.WORKING:
            return StatusLine("status.label.scanning", tone="pending")
        if self.identity is IdentityStatus.WRITE_REQUIRED:
            return StatusLine("identity.write_required", tone="pending")
        if self.identity_ok and self.missing_ticks:
            return StatusLine("status.label.identity_ok", tone="pass")
        if self.identity_ok:
            return StatusLine("status.all_checks_done", tone="pass")
        return None


class PackagingViewModel(ChecklistMixin):
    stage = Stage.PACKAGING
    checklist = PACKAGING_CHECKLIST

    def __init__(self, controller: StationController) -> None:
        super().__init__(controller)
        self.reset()

    def reset(self) -> None:
        self.reset_checklist()

    def primary(self) -> Action:
        missing = self.missing_ticks
        if missing:
            key, params = missing_reason(len(missing), len(self.checklist))
            return Action(
                "action.complete_device",
                enabled=False,
                reason_key=key,
                reason_params=params,
                hint_key="key.enter",
                name="complete",
            )
        return Action(
            "action.complete_device", self.c.advance, hint_key="key.enter", name="complete"
        )

    def secondary(self) -> list[Action]:
        if not self.c.device_in_progress:
            return []
        return [Action("action.reject_device", self.start_reject, variant="danger", name="reject")]

    def status(self) -> StatusLine | None:
        if self.missing_ticks:
            return StatusLine("status.pack.checklist", tone="info")
        return StatusLine("status.pack.ready", tone="pass")
