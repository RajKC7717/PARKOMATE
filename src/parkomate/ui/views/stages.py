"""The four stage screens. Same layout everywhere: left = steps/checks, right = live data."""

from __future__ import annotations

from datetime import datetime

from PySide6.QtCore import QRectF, Qt, QTimer
from PySide6.QtGui import QColor, QImage, QPainter, QPaintEvent, QPen
from PySide6.QtWidgets import (
    QComboBox,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QProgressBar,
    QVBoxLayout,
    QWidget,
)

from parkomate.core.enums import CheckCode, IdentityStatus, IdEntryMethod, Stage
from parkomate.core.models import CheckOutcome
from parkomate.i18n import t
from parkomate.ui.components.icons import Icon
from parkomate.ui.components.widgets import (
    BigButton,
    CheckRow,
    CounterBadge,
    StatusPill,
    TrLabel,
    scroll_card,
    set_prop,
)
from parkomate.ui.qt_i18n import language_notifier
from parkomate.ui.theme.fonts import font
from parkomate.ui.theme.tokens import COLORS, SIZES
from parkomate.ui.viewmodels.base import StageViewModel
from parkomate.ui.viewmodels.labeling import ChecklistMixin, LabelingViewModel, PackagingViewModel
from parkomate.ui.viewmodels.programming import ProgrammingViewModel, StepState
from parkomate.ui.viewmodels.station import StationController
from parkomate.ui.viewmodels.testing import TestingViewModel

_PILL = {
    StepState.PENDING: "pending",
    StepState.WORKING: "working",
    StepState.PASS: "pass",
    StepState.FAIL: "fail",
    StepState.ERROR: "warn",
}

CHECK_ICONS = {
    CheckCode.C1: "pcb",
    CheckCode.C2: "screw",
    CheckCode.C3: "sticker",
    CheckCode.C4: "qr",
    CheckCode.D1: "sensor",
    CheckCode.D2: "indicator",
    CheckCode.D3: "connector",
    CheckCode.D4: "screw",
}


def local_time(value: datetime) -> str:
    return value.astimezone().strftime("%H:%M:%S")


class StepRow(QFrame):
    """Numbered step with a title, a status pill and a body."""

    def __init__(self, number: str, title_key: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setProperty("tone", "pending")
        outer = QVBoxLayout(self)
        outer.setContentsMargins(SIZES.space_s + 4, 6, SIZES.space_s + 4, 6)
        outer.setSpacing(2)
        header = QHBoxLayout()
        self.number = QLabel(number)
        self.number.setFont(font(SIZES.font_h2, bold=True))
        self.number.setFixedWidth(36)
        self.title = TrLabel(title_key, role="h2")
        self.pill = StatusPill()
        header.addWidget(self.number)
        header.addWidget(self.title, 1)
        header.addWidget(self.pill)
        outer.addLayout(header)
        self.body = QVBoxLayout()
        self.body.setContentsMargins(42, 0, 0, 0)
        self.body.setSpacing(SIZES.space_xs)
        outer.addLayout(self.body)

    def set_state(self, state: StepState, key: str | None = None) -> None:
        pill = _PILL[state]
        self.pill.set_state(pill, key)
        set_prop(self, "tone", {"working": "info"}.get(pill, pill))


class StageView(QWidget):
    vm: StageViewModel

    def __init__(
        self, controller: StationController, vm: StageViewModel, ratio: tuple[int, int] = (5, 6)
    ) -> None:
        super().__init__()
        self.c = controller
        self.vm = vm
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(SIZES.space_m)
        self.left, self.left_layout = scroll_card()
        self.right, self.right_layout = scroll_card()
        layout.addWidget(self.left, ratio[0])
        layout.addWidget(self.right, ratio[1])
        vm.changed.connect(self.update_view)
        language_notifier().changed.connect(self.update_view)

    def update_view(self, *_args: object) -> None:
        raise NotImplementedError


class RejectChooser(QFrame):
    """'Which item failed?' - inline, never a dialog."""

    def __init__(self, vm: ChecklistMixin, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.vm = vm
        self.setProperty("tone", "fail")
        self._layout = QVBoxLayout(self)
        self._layout.setContentsMargins(SIZES.space_m, SIZES.space_m, SIZES.space_m, SIZES.space_m)
        self._layout.addWidget(TrLabel("reject.choose_item", role="h2"))
        self._grid = QGridLayout()
        self._layout.addLayout(self._grid)
        self.cancel = BigButton("action.cancel", hint_key="key.esc")
        self.cancel.clicked.connect(vm.cancel_reject)
        self._layout.addWidget(self.cancel, 0, Qt.AlignmentFlag.AlignRight)
        self._buttons: dict[CheckCode, BigButton] = {}
        self.setVisible(False)

    def update_view(self) -> None:
        codes = self.vm.reject_codes()
        if list(self._buttons) != codes:
            for button in self._buttons.values():
                button.deleteLater()
            self._buttons = {}
            for index, code in enumerate(codes):
                button = BigButton(code.label_key, variant="danger")
                button.clicked.connect(lambda _c=False, code=code: self.vm.reject_for(code))
                self._grid.addWidget(button, index // 2, index % 2)
                self._buttons[code] = button
        self.setVisible(self.vm.choosing_reject)


# =========================================================================== Programming


class ProgrammingView(StageView):
    vm: ProgrammingViewModel

    def __init__(self, controller: StationController) -> None:
        super().__init__(controller, controller.programming)
        left = self.left_layout
        self.step_connect = StepRow("1", "prog.step.connect")
        self.port_combo = QComboBox()
        self.port_combo.setMinimumWidth(320)
        self.port_combo.activated.connect(self._port_chosen)
        self.chip = QLabel()
        self.chip.setProperty("role", "muted")
        self.step_connect.body.addWidget(self.port_combo)
        self.step_connect.body.addWidget(self.chip)
        self.step_whitelist = StepRow("2", "prog.step.authorised")
        self.mac = QLabel()
        self.mac.setFont(font(SIZES.font_h2, bold=True))
        self.whitelist_text = QLabel()
        self.whitelist_text.setWordWrap(True)
        self.step_whitelist.body.addWidget(self.mac)
        self.step_whitelist.body.addWidget(self.whitelist_text)
        self.step_firmware = StepRow("3", "prog.step.firmware")
        self.firmware_text = QLabel()
        self.firmware_text.setWordWrap(True)
        self.step_firmware.body.addWidget(self.firmware_text)
        self.step_upload = StepRow("4", "prog.step.upload")
        self.progress = QProgressBar()
        self.progress.setRange(0, 100)
        self.progress.setFormat("%p %")
        self.upload_info = QLabel()
        self.step_upload.body.addWidget(self.progress)
        self.step_upload.body.addWidget(self.upload_info)
        for step in (self.step_connect, self.step_whitelist, self.step_firmware, self.step_upload):
            left.addWidget(step)
        left.addStretch(1)

        right = self.right_layout
        right.addWidget(TrLabel("prog.result_title", role="h2"))
        self.result_pill = StatusPill(size="large")
        right.addWidget(self.result_pill, 0, Qt.AlignmentFlag.AlignLeft)
        self.result_text = QLabel()
        self.result_text.setWordWrap(True)
        self.result_text.setFont(font(SIZES.font_h2))
        right.addWidget(self.result_text)
        self.adjust = QFrame()
        self.adjust.setProperty("tone", "info")
        adjust_layout = QVBoxLayout(self.adjust)
        adjust_layout.setContentsMargins(SIZES.space_m, SIZES.space_m, SIZES.space_m, SIZES.space_m)
        adjust_layout.addWidget(TrLabel("prog.adjust.question", role="h2"))
        adjust_layout.addWidget(TrLabel("prog.adjust.help", role="muted"))
        buttons = QHBoxLayout()
        self.adjust_yes = BigButton("action.adjust_yes", variant="primary")
        self.adjust_no = BigButton("action.adjust_no")
        self.adjust_yes.clicked.connect(lambda: self.vm.answer_adjust(True))
        self.adjust_no.clicked.connect(lambda: self.vm.answer_adjust(False))
        buttons.addWidget(self.adjust_yes)
        buttons.addWidget(self.adjust_no)
        buttons.addStretch(1)
        adjust_layout.addLayout(buttons)
        right.addWidget(self.adjust)
        right.addStretch(1)
        counters = QFrame()
        counters.setProperty("tone", "pending")
        grid = QGridLayout(counters)
        grid.setContentsMargins(SIZES.space_m, SIZES.space_m, SIZES.space_m, SIZES.space_m)
        grid.addWidget(TrLabel("prog.counters_title", role="h2"), 0, 0, 1, 2)
        self.c_ok = CounterBadge("counter.uploads_ok", "check")
        self.c_fail = CounterBadge("counter.uploads_fail", "cross")
        self.c_adjusted = CounterBadge("counter.failures_adjusted", "info")
        grid.addWidget(self.c_ok, 1, 0)
        grid.addWidget(self.c_fail, 1, 1)
        grid.addWidget(self.c_adjusted, 2, 0)
        self.reset_counters = BigButton("action.reset_counters", variant="danger")
        self.reset_counters.clicked.connect(controller.reset_counters)
        grid.addWidget(self.reset_counters, 2, 1)
        right.addWidget(counters)
        controller.counters_changed.connect(self.update_view)
        controller.session_changed.connect(self.update_view)
        self.update_view()

    def _port_chosen(self, index: int) -> None:
        self.vm.select_port(self.port_combo.itemData(index))

    def update_view(self, *_args: object) -> None:
        vm = self.vm
        # 1 - connect
        self.port_combo.blockSignals(True)
        self.port_combo.clear()
        self.port_combo.addItem(t("prog.choose_port"), None)
        for port in vm.ports:
            label = f"{port.name}  -  {port.description}"
            if port.vid_pid:
                label = f"{label}  ({port.vid_pid})"
            self.port_combo.addItem(label, port.name)
        index = self.port_combo.findData(vm.selected_port) if vm.selected_port else 0
        self.port_combo.setCurrentIndex(max(0, index))
        self.port_combo.setEnabled(not vm.device_started and not vm.ports_loading)
        self.port_combo.setAccessibleName(t("prog.step.connect"))
        self.port_combo.blockSignals(False)
        self.chip.setText(t("prog.chip", chip=vm.chip) if vm.chip else "")
        self.step_connect.set_state(vm.connect_state)
        # 2 - whitelist
        self.mac.setText(t("prog.mac", mac=vm.mac) if vm.mac else t("prog.mac_unknown"))
        self.whitelist_text.setText(
            {
                StepState.PENDING: "",
                StepState.WORKING: t("prog.whitelist.checking"),
                StepState.PASS: t("prog.whitelist.allowed"),
                StepState.FAIL: t("prog.whitelist.denied"),
                StepState.ERROR: t("prog.whitelist.error"),
            }[vm.whitelist_state]
        )
        self.step_whitelist.set_state(vm.whitelist_state)
        # 3 - firmware
        firmware = self.c.firmware
        if self.c.firmware_loading:
            self.firmware_text.setText(t("prog.firmware.loading"))
            self.step_firmware.set_state(StepState.WORKING)
        elif self.c.firmware_error is not None:
            self.firmware_text.setText(t("prog.firmware.error"))
            self.step_firmware.set_state(StepState.ERROR)
        elif firmware is not None:
            text = t("prog.firmware.info", name=firmware.name, version=firmware.version)
            if firmware.hash_verified:
                text = f"{text}\n{t('prog.firmware.hash_ok')}"
            self.firmware_text.setText(text)
            self.step_firmware.set_state(StepState.PASS)
        else:
            self.firmware_text.setText("")
            self.step_firmware.set_state(StepState.PENDING)
        # 4 - upload
        self.progress.setValue(vm.progress)
        self.progress.setAccessibleName(t("prog.step.upload"))
        info = []
        if vm.upload_state is not StepState.PENDING or vm.elapsed_s:
            info.append(t("prog.elapsed", s=f"{vm.elapsed_s:.1f}"))
        if vm.attempts or vm.upload_state is StepState.WORKING:
            shown = vm.attempts + (1 if vm.upload_state is StepState.WORKING else 0)
            info.append(t("prog.attempt", n=max(1, shown), total=vm.max_attempts))
        self.upload_info.setText("   ·   ".join(info))
        self.step_upload.set_state(vm.upload_state)
        # result panel
        state = vm.upload_state
        if state is StepState.PASS:
            self.result_pill.set_state("pass")
            self.result_text.setText(t("prog.result.pass"))
        elif state in (StepState.FAIL, StepState.ERROR) and vm.attempts:
            self.result_pill.set_state("fail")
            outcome = vm.last_outcome
            reason = t(outcome.reason_key) if outcome and outcome.reason_key else ""
            self.result_text.setText(
                t("prog.result.fail", reason=reason, n=vm.attempts, total=vm.max_attempts)
            )
        elif state is StepState.WORKING:
            self.result_pill.set_state("working", "status.word.uploading")
            self.result_text.setText(t("prog.result.uploading", pct=vm.progress))
        else:
            self.result_pill.set_state("pending")
            self.result_text.setText(t("prog.result.waiting"))
        self.adjust.setVisible(vm.adjust_prompt)
        counters = self.c.counters
        if counters is not None:
            self.c_ok.set_value(str(counters.upload_success))
            self.c_fail.set_value(str(counters.net_upload_failure))
            self.c_adjusted.set_value(str(counters.failures_adjusted))
        self.reset_counters.setVisible(self.c.is_admin)


# =========================================================================== Testing


class DecisionRow(QFrame):
    """'Sensor readings: [✓ Success] [✕ Failure]' with one line of guidance."""

    def __init__(
        self, code: CheckCode, title_key: str, help_key: str, vm: TestingViewModel
    ) -> None:
        super().__init__()
        self.code = code
        self.vm = vm
        self.setProperty("tone", "pending")
        layout = QHBoxLayout(self)
        layout.setContentsMargins(SIZES.space_m, SIZES.space_s, SIZES.space_m, SIZES.space_s)
        text = QVBoxLayout()
        text.addWidget(TrLabel(title_key, role="h2"))
        text.addWidget(TrLabel(help_key, role="muted"))
        layout.addLayout(text, 1)
        self.success = BigButton("action.mark_success", variant="pass")
        self.failure = BigButton("action.mark_failure", variant="danger")
        for button in (self.success, self.failure):
            button.setCheckable(True)
            layout.addWidget(button)
        self.success.clicked.connect(lambda: self.vm.mark(code, True))
        self.failure.clicked.connect(lambda: self.vm.mark(code, False))

    def update_view(self, enabled: bool) -> None:
        value = self.vm.marks[self.code]
        self.success.setChecked(value is True)
        self.failure.setChecked(value is False)
        self.success.setEnabled(enabled and value is None)
        self.failure.setEnabled(enabled and value is None)
        set_prop(self, "tone", "pending" if value is None else ("pass" if value else "fail"))


class TestingView(StageView):
    vm: TestingViewModel

    ROWS = (CheckCode.B3_V_A, CheckCode.B3_V_B, CheckCode.B3_V_C, CheckCode.B3_T_REG)

    def __init__(self, controller: StationController) -> None:
        super().__init__(controller, controller.testing, ratio=(6, 5))
        left = self.left_layout
        self.step_comm = StepRow("B1", "test.step.comm")
        self.comm_text = QLabel()
        self.step_comm.body.addWidget(self.comm_text)
        left.addWidget(self.step_comm)
        self.step_sensor = StepRow("B2", "test.step.sensor")
        self.reading_title = QLabel()
        self.reading_title.setFont(font(SIZES.font_h2, bold=True))
        self.readings = QLabel()
        self.readings.setFont(font(SIZES.font_h2))
        self.step_sensor.body.addWidget(self.reading_title)
        self.step_sensor.body.addWidget(self.readings)
        left.addWidget(self.step_sensor)
        self.sensor_row = DecisionRow(
            CheckCode.B2_SENSOR_OK, "test.mark.sensor", "test.mark.sensor_help", self.vm
        )
        self.indicator_row = DecisionRow(
            CheckCode.B2_INDICATOR_OK, "test.mark.indicator", "test.mark.indicator_help", self.vm
        )
        left.addWidget(self.sensor_row)
        left.addWidget(self.indicator_row)
        left.addStretch(1)

        right = self.right_layout
        self.step_elec = StepRow("B3", "test.step.electrical")
        right.addWidget(self.step_elec)
        grid = QGridLayout()
        grid.setHorizontalSpacing(SIZES.space_m)
        grid.setVerticalSpacing(SIZES.space_s)
        for col, key in enumerate(
            ("test.col.check", "test.col.measured", "test.col.allowed", "test.col.result")
        ):
            header = TrLabel(key, role="small")
            header.setFont(font(SIZES.font_small, bold=True))
            grid.addWidget(header, 0, col)
        self.cells: dict[CheckCode, tuple[TrLabel, QLabel, QLabel, StatusPill]] = {}
        for row, code in enumerate(self.ROWS, start=1):
            name = TrLabel(code.label_key)
            name.setWordWrap(True)
            name.setFont(font(SIZES.font_base))
            measured = QLabel("-")
            measured.setFont(font(SIZES.font_h2, bold=True))
            allowed = QLabel()
            allowed.setWordWrap(True)
            allowed.setFont(font(SIZES.font_small))
            pill = StatusPill()
            grid.addWidget(name, row, 0)
            grid.addWidget(measured, row, 1)
            grid.addWidget(allowed, row, 2)
            grid.addWidget(pill, row, 3)
            self.cells[code] = (name, measured, allowed, pill)
        right.addLayout(grid)
        self.waiting = QLabel()
        self.waiting.setFont(font(SIZES.font_h2, bold=True))
        self.waiting.setWordWrap(True)
        right.addWidget(self.waiting)
        right.addStretch(1)
        ambient = QHBoxLayout()
        ambient.addWidget(Icon("thermo", 32, COLORS.text_muted))
        self.ambient = QLabel()
        self.ambient.setFont(font(SIZES.font_h2, bold=True))
        ambient.addWidget(self.ambient, 1)
        self.remeasure = BigButton("action.remeasure_ambient", hint_key="key.f9")
        self.remeasure.clicked.connect(controller.remeasure_ambient)
        ambient.addWidget(self.remeasure)
        right.addLayout(ambient)
        self.update_view()

    def _allowed_text(self, code: CheckCode) -> str:
        limits = self.c.settings.limits
        decimals = limits.decimals
        if code is CheckCode.B3_T_REG:
            ambient = self.c.ambient_c
            if ambient is None:
                return t("test.allowed_temp_unknown", margin=f"{limits.temp_margin_c:g}")
            return t(
                "test.allowed_temp",
                limit=f"{ambient + limits.temp_margin_c:.1f}",
                margin=f"{limits.temp_margin_c:g}",
            )
        point = code.value[-1].lower()
        low, high = limits.voltage_range(point)
        return t(
            "test.allowed_range", low=f"{low:.{decimals}f}", high=f"{high:.{decimals}f}", unit="V"
        )

    def update_view(self, *_args: object) -> None:
        vm = self.vm
        self.step_comm.set_state(vm.comm_state)
        self.comm_text.setText(
            {
                StepState.PENDING: "",
                StepState.WORKING: t("test.comm.working"),
                StepState.PASS: t("test.comm.ok"),
                StepState.FAIL: t("test.comm.fail"),
                StepState.ERROR: t("test.comm.error"),
            }[vm.comm_state]
        )
        total = vm.total_readings
        count = len(vm.readings)
        sensor_state = (
            StepState.PASS
            if vm.readings_done and vm.marks_ok
            else StepState.WORKING
            if count or vm.reading_busy
            else StepState.PENDING
        )
        if any(v is False for v in vm.marks.values()):
            sensor_state = StepState.FAIL
        self.step_sensor.set_state(sensor_state)
        self.reading_title.setText(t("test.reading_progress", n=count, total=total))
        values = [f"{reading.value:g}" for reading in vm.readings]
        values += ["-"] * (total - count)
        unit = vm.readings[0].unit if vm.readings else ""
        self.readings.setText(f"{'  ·  '.join(values)}  {unit}")
        if vm.readings:
            self.readings.setToolTip(local_time(vm.readings[-1].read_at))
        comm_ok = vm.comm_state is StepState.PASS
        self.sensor_row.update_view(comm_ok and vm.readings_done)
        self.indicator_row.update_view(comm_ok)
        # B3
        results: dict[CheckCode, CheckOutcome] = {o.check_code: o for o in vm.results}
        for code, (_name, measured, allowed, pill) in self.cells.items():
            allowed.setText(self._allowed_text(code))
            outcome = results.get(code)
            if outcome is None or outcome.value_num is None:
                measured.setText("-")
                pill.set_state("working" if vm.measure_state is StepState.WORKING else "pending")
            else:
                unit = "°C" if code is CheckCode.B3_T_REG else "V"
                measured.setText(f"{outcome.value_num:g} {unit}")
                pill.set_state("pass" if outcome.passed else "fail")
                if outcome.passed is None:
                    pill.set_state("pending")
        elec_state = vm.measure_state
        self.step_elec.set_state(elec_state)
        if vm.measure_state is StepState.WORKING:
            self.waiting.setText(t("test.waiting", s=vm.seconds_left))
        elif vm.measure_state is StepState.ERROR:
            self.waiting.setText(t("test.measure_error"))
        else:
            self.waiting.setText("")
        self.ambient.setText(
            t("test.ambient", value=f"{self.c.ambient_c:.1f}")
            if self.c.ambient_c is not None
            else t("drawer.ambient_unknown")
        )


# =========================================================================== Labeling


class CameraPreview(QWidget):
    """Live camera frames, or an animated placeholder with a framing guide (mock)."""

    def __init__(self, controller: StationController, vm: LabelingViewModel) -> None:
        super().__init__()
        self.c = controller
        self.vm = vm
        self.setMinimumSize(420, 240)
        self._image: QImage | None = None
        self._phase = 0
        self._timer = QTimer(self)
        self._timer.setInterval(66)  # ~15 fps
        self._timer.timeout.connect(self._poll)
        self.setAccessibleName(t("camera.preview"))

    def set_active(self, active: bool) -> None:
        if active and not self._timer.isActive():
            self._timer.start()
        elif not active:
            self._timer.stop()
            self.update()

    def _poll(self) -> None:
        frame = self.c.ctx.hardware.get_preview_frame()
        if frame is not None:
            self._image = QImage(
                frame.rgb, frame.width, frame.height, frame.width * 3, QImage.Format.Format_RGB888
            ).copy()
        self._phase = (self._phase + 1) % 60
        self.update()

    def paintEvent(self, _event: QPaintEvent) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        rect = QRectF(self.rect())
        painter.fillRect(rect, QColor(COLORS.text))
        if self._image is not None:
            painter.drawImage(rect, self._image)
        guide = rect.adjusted(
            rect.width() * 0.28, rect.height() * 0.12, -rect.width() * 0.28, -rect.height() * 0.12
        )
        pen = QPen(QColor(COLORS.surface), 4)
        painter.setPen(pen)
        arm = min(guide.width(), guide.height()) * 0.2
        for x, y, dx, dy in (
            (guide.left(), guide.top(), 1, 1),
            (guide.right(), guide.top(), -1, 1),
            (guide.left(), guide.bottom(), 1, -1),
            (guide.right(), guide.bottom(), -1, -1),
        ):
            painter.drawLine(int(x), int(y), int(x + dx * arm), int(y))
            painter.drawLine(int(x), int(y), int(x), int(y + dy * arm))
        scanning = self.vm.camera_state is StepState.WORKING
        if scanning:
            y = guide.top() + guide.height() * (self._phase / 60)
            painter.setPen(QPen(QColor(COLORS.focus), 3))
            painter.drawLine(int(guide.left() + 8), int(y), int(guide.right() - 8), int(y))
        painter.setPen(QColor(COLORS.surface))
        painter.setFont(font(SIZES.font_small, bold=True))
        if self._image is None:
            text = t("camera.scanning") if scanning else t("camera.simulated")
            if not self.c.ctx.using_mocks:
                text = t("camera.scanning") if scanning else t("camera.idle")
            painter.drawText(
                rect.adjusted(8, 8, -8, -8),
                int(Qt.AlignmentFlag.AlignBottom | Qt.AlignmentFlag.AlignHCenter),
                text,
            )
        painter.end()


class ChecklistView(StageView):
    vm: ChecklistMixin

    def _build_checklist(self, title_key: str) -> None:
        self.left_layout.addWidget(TrLabel(title_key, role="h2"))
        self.rows: dict[CheckCode, CheckRow] = {}
        for index, code in enumerate(self.vm.checklist, start=1):
            row = CheckRow(code.label_key, CHECK_ICONS.get(code, "list"), f"key.f{index}")
            row.clicked.connect(lambda _c=False, code=code: self._clicked(code))
            self.rows[code] = row
            self.left_layout.addWidget(row)
        self.left_layout.addStretch(1)

    def _clicked(self, code: CheckCode) -> None:
        self.vm.toggle(code)
        self.update_view()

    def _render_checklist(self) -> None:
        enabled = self.c.device_in_progress
        for code, row in self.rows.items():
            row.setChecked(bool(self.vm.ticks.get(code)))
            row.setEnabled(enabled)


class LabelingView(ChecklistView):
    vm: LabelingViewModel

    def __init__(self, controller: StationController) -> None:
        super().__init__(controller, controller.labeling)
        self._build_checklist("label.checklist_title")
        right = self.right_layout
        right.addWidget(TrLabel("label.qr_title", role="h2"))
        self.preview = CameraPreview(controller, self.vm)
        right.addWidget(self.preview, 1)
        decoded = QHBoxLayout()
        decoded.addWidget(TrLabel("label.decoded", role="muted"))
        self.decoded = QLabel("-")
        self.decoded.setFont(font(SIZES.font_value_large, bold=True))
        self.decoded.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        decoded.addWidget(self.decoded, 1)
        self.manual_flag = TrLabel("label.manual_flag", role="small")
        decoded.addWidget(self.manual_flag)
        right.addLayout(decoded)

        self.manual = QFrame()
        self.manual.setProperty("tone", "info")
        manual_layout = QGridLayout(self.manual)
        manual_layout.setContentsMargins(SIZES.space_m, SIZES.space_m, SIZES.space_m, SIZES.space_m)
        manual_layout.addWidget(TrLabel("manual.title", role="h2"), 0, 0, 1, 2)
        self.manual_first = QLineEdit()
        self.manual_second = QLineEdit()
        for field in (self.manual_first, self.manual_second):
            field.setProperty("enter_submits", True)
            field.returnPressed.connect(self._submit_manual)
        manual_layout.addWidget(self.manual_first, 1, 0)
        manual_layout.addWidget(self.manual_second, 1, 1)
        self.manual_error = QLabel()
        self.manual_error.setProperty("status", "fail")
        manual_layout.addWidget(self.manual_error, 2, 0, 1, 2)
        self.manual_ok = BigButton("action.confirm_id", variant="primary")
        self.manual_cancel = BigButton("action.cancel")
        self.manual_ok.clicked.connect(self._submit_manual)
        self.manual_cancel.clicked.connect(self.vm.cancel_manual)
        manual_layout.addWidget(self.manual_cancel, 3, 0)
        manual_layout.addWidget(self.manual_ok, 3, 1)
        right.addWidget(self.manual)

        self.identity = QFrame()
        self.identity.setProperty("tone", "pending")
        identity_layout = QGridLayout(self.identity)
        identity_layout.setContentsMargins(
            SIZES.space_m, SIZES.space_m, SIZES.space_m, SIZES.space_m
        )
        identity_layout.addWidget(TrLabel("label.identity_title", role="h2"), 0, 0, 1, 2)
        identity_layout.addWidget(TrLabel("label.board_id", role="muted"), 1, 0)
        identity_layout.addWidget(TrLabel("label.qr_id", role="muted"), 2, 0)
        self.board_value = QLabel("-")
        self.board_value.setFont(font(SIZES.font_h2, bold=True))
        self.qr_value = QLabel("-")
        self.qr_value.setFont(font(SIZES.font_h2, bold=True))
        identity_layout.addWidget(self.board_value, 1, 1)
        identity_layout.addWidget(self.qr_value, 2, 1)
        self.identity_pill = StatusPill()
        identity_layout.addWidget(self.identity_pill, 1, 2, 2, 1)
        right.addWidget(self.identity)
        self.chooser = RejectChooser(self.vm)
        right.addWidget(self.chooser)
        controller.stage_changed.connect(self._stage_changed)
        self.update_view()

    def _stage_changed(self) -> None:
        self.preview.set_active(self.c.stage is Stage.LABELING and self.c.reject is None)

    def _submit_manual(self) -> None:
        self.vm.submit_manual(self.manual_first.text(), self.manual_second.text())

    def update_view(self, *_args: object) -> None:
        vm = self.vm
        self._render_checklist()
        self.preview.set_active(self.c.stage is Stage.LABELING and self.c.reject is None)
        self.preview.update()
        self.decoded.setText(vm.qr_id or "-")
        self.manual_flag.setVisible(vm.qr_id is not None and vm.method is IdEntryMethod.MANUAL)
        was_hidden = not self.manual.isVisible()
        self.manual.setVisible(vm.manual_mode)
        if vm.manual_mode and was_hidden:
            self.manual_first.clear()
            self.manual_second.clear()
            self.manual_first.setFocus()
        self.manual_first.setPlaceholderText(t("manual.first"))
        self.manual_second.setPlaceholderText(t("manual.second"))
        self.manual_first.setAccessibleName(t("manual.first"))
        self.manual_second.setAccessibleName(t("manual.second"))
        self.manual_error.setText(t(vm.manual_error_key) if vm.manual_error_key else "")
        self.board_value.setText(vm.board_id if vm.board_id else "-")
        self.qr_value.setText(vm.qr_id or "-")
        identity = vm.identity
        if identity is None:
            if vm.identity_state is StepState.WORKING:
                self.identity_pill.set_state("working", "label.reading_board")
            elif vm.identity_state is StepState.ERROR:
                self.identity_pill.set_state("warn", "identity.failed")
            else:
                self.identity_pill.set_state("pending")
        elif identity is IdentityStatus.WRITE_REQUIRED:
            pill = "warn" if vm.identity_state is StepState.ERROR else "working"
            self.identity_pill.set_state(pill, identity.label_key)
        elif identity is IdentityStatus.FAILED:
            self.identity_pill.set_state("fail", identity.label_key)
        else:
            self.identity_pill.set_state("pass", identity.label_key)
        set_prop(
            self.identity,
            "tone",
            {"pass": "pass", "fail": "fail", "working": "info"}.get(
                self.identity_pill.state(), "pending"
            ),
        )
        self.chooser.update_view()


class PackagingView(ChecklistView):
    vm: PackagingViewModel

    def __init__(self, controller: StationController) -> None:
        super().__init__(controller, controller.packaging)
        self._build_checklist("pack.checklist_title")
        right = self.right_layout
        right.addWidget(TrLabel("pack.device_title", role="h2"))
        self.device = QLabel("-")
        self.device.setFont(font(SIZES.font_value_large, bold=True))
        right.addWidget(self.device)
        self.mac = QLabel()
        self.mac.setProperty("role", "muted")
        right.addWidget(self.mac)
        self.passed = QLabel()
        self.passed.setFont(font(SIZES.font_h2, bold=True))
        self.passed.setProperty("status", "pass")
        right.addWidget(self.passed)
        right.addStretch(1)
        self.chooser = RejectChooser(self.vm)
        right.addWidget(self.chooser)
        controller.device_changed.connect(self.update_view)
        self.update_view()

    def update_view(self, *_args: object) -> None:
        self._render_checklist()
        state = self.c.device
        self.device.setText((state.device_id or state.mac_address) if state else "-")
        self.mac.setText(t("prog.mac", mac=state.mac_address) if state else "")
        stages = [Stage.PROGRAMMING, Stage.TESTING, Stage.LABELING]
        self.passed.setText("\n".join(f"✓  {t(stage.label_key)}" for stage in stages))
        self.chooser.update_view()
