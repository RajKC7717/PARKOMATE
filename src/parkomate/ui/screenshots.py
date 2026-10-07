"""Render every screen to PNG (English + Marathi) for review without running the station.

    python -m parkomate.ui.screenshots [--out docs/screenshots] [--lang en mr]

Runs off-screen on the mock bench; nothing touches real hardware or the real data folder.
The :class:`StationDriver` is also used by the UI tests.
"""

from __future__ import annotations

import argparse
import os
import sys
import tempfile
import threading
import time
from collections.abc import Callable
from pathlib import Path
from typing import Any

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QCoreApplication, QEvent
from PySide6.QtWidgets import QApplication

from parkomate.app import AppContext, build_context
from parkomate.app_paths import AppPaths
from parkomate.config.manager import settings_to_toml, validate_settings
from parkomate.config.secrets import MemorySecretStore
from parkomate.core.enums import CheckCode, Stage
from parkomate.core.errors import SettingsError
from parkomate.core.interfaces import ProgressCallback
from parkomate.core.models import FlashResult
from parkomate.hardware.mocks import MockHardwareService, MockScenario
from parkomate.i18n import set_language
from parkomate.ui.main import create_application
from parkomate.ui.main_window import MainWindow
from parkomate.ui.viewmodels.station import LoginPhase, Page, StationController

ADMIN = ("ADM1", "Asha Patil", "secret-pass-1")
OPERATOR = ("OP12", "Omkar Jadhav", "operator-pass-1")


class GatedMock(MockHardwareService):
    """Mock whose flash can pause at a given percentage (for a genuine 'uploading' shot)."""

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self.gate_at: int | None = None
        self.gate = threading.Event()
        self.reached = threading.Event()

    def flash(self, progress_cb: ProgressCallback) -> FlashResult:
        gate_at = self.gate_at

        def progress(value: int) -> None:
            progress_cb(value)
            if gate_at is not None and value >= gate_at and not self.reached.is_set():
                self.reached.set()
                self.gate.wait(30)

        return super().flash(progress)


class StationDriver:
    """Builds an isolated station (temp data folder, mock bench) and drives it like an operator."""

    def __init__(
        self,
        *,
        scenario: MockScenario = MockScenario.ALL_PASS,
        settings: dict[str, Any] | None = None,
        data_dir: Path | None = None,
        size: tuple[int, int] = (1366, 768),
        delay_scale: float = 0.0,
    ) -> None:
        self.app = create_application()
        self.data_dir = data_dir or Path(tempfile.mkdtemp(prefix="parkomate-ui-"))
        paths = AppPaths(self.data_dir).ensure()
        if settings:
            paths.settings_file.write_text(
                settings_to_toml(validate_settings(settings)), encoding="utf-8"
            )
        self.hardware = GatedMock(scenario, delay_scale=delay_scale, seed=11)
        self.ctx: AppContext = build_context(
            paths,
            mock=True,
            secrets=MemorySecretStore(),
            hardware=self.hardware,
            configure_logging=False,
        )
        auth = self.ctx.auth
        admin = auth.create_first_admin(*ADMIN)
        from parkomate.core.enums import Role

        auth.create_operator(admin, OPERATOR[0], OPERATOR[1], OPERATOR[2], Role.OPERATOR)
        self.controller = StationController(self.ctx, ambient_result_ms=0)
        self.window = MainWindow(self.controller)
        self.window.resize(*size)
        self.window.show()

    # ------------------------------------------------------------------ waiting
    def process(self, ms: int = 30) -> None:
        end = time.monotonic() + ms / 1000
        while time.monotonic() < end:
            self.app.processEvents()
            time.sleep(0.005)
        self.app.processEvents()

    def wait(self, condition: Callable[[], bool], timeout: float = 15.0, what: str = "") -> None:
        end = time.monotonic() + timeout
        while time.monotonic() < end:
            self.app.processEvents()
            if condition():
                self.process(20)
                return
            time.sleep(0.005)
        c = self.controller
        raise TimeoutError(
            f"timed out waiting for {what or condition}: page={c.page} stage={c.stage} "
            f"error={c.error.error.code if c.error else None}"
        )

    def idle(self) -> None:
        self.wait(
            lambda: not self.controller.hw.busy and not self.controller.bg.busy, what="workers idle"
        )

    # ------------------------------------------------------------------ actions
    @property
    def c(self) -> StationController:
        return self.controller

    def start(self) -> None:
        self.c.start()
        self.wait(lambda: self.c.page is Page.LOGIN, what="login page")

    def login(self, code: str = ADMIN[0], password: str = ADMIN[2]) -> None:
        self.c.login(code, password)
        self.wait(
            lambda: self.c.page is Page.PRODUCTION or self.c.login_error is not None, what="login"
        )

    def ready_for_board(self) -> None:
        self.wait(
            lambda: (
                self.c.firmware is not None
                and self.c.programming.ports_loaded
                and not self.c.hw.busy
            ),
            what="firmware + ports",
        )

    def enter(self) -> None:
        self.window.shell.press_enter()
        self.process(20)

    def connect(self) -> None:
        self.ready_for_board()
        self.c.programming.connect_board()
        self.wait(
            lambda: (
                self.c.programming.whitelist_state.value in ("pass", "fail", "error")
                or self.c.reject is not None
            ),
            what="whitelist",
        )
        self.idle()

    def upload_until_done(self) -> None:
        vm = self.c.programming
        for _ in range(vm.max_attempts):
            if self.c.reject is not None or vm.upload_state.value == "pass":
                break
            vm.upload()
            self.idle()
        self.process(30)

    def through_programming(self) -> None:
        self.connect()
        self.upload_until_done()
        if self.c.programming.adjust_prompt:
            self.c.programming.answer_adjust(True)
        self.c.advance()
        self.wait(lambda: self.c.stage is Stage.TESTING, what="testing")

    def read_all_sensors(self, count: int | None = None) -> None:
        vm = self.c.testing
        self.wait(lambda: vm.comm_state.value != "working", what="comm test")
        total = vm.total_readings if count is None else count
        while len(vm.readings) < total:
            vm.read_sensor()
            self.idle()

    def mark_ok(self) -> None:
        vm = self.c.testing
        vm.mark(CheckCode.B2_SENSOR_OK, True)
        vm.mark(CheckCode.B2_INDICATOR_OK, True)
        self.wait(
            lambda: (
                vm.measure_state.value not in ("pending", "working") or self.c.reject is not None
            ),
            what="measurement",
        )
        self.idle()

    def through_testing(self) -> None:
        self.read_all_sensors()
        self.mark_ok()
        self.c.advance()
        self.wait(lambda: self.c.stage is Stage.LABELING, what="labeling")

    def through_labeling(self) -> None:
        vm = self.c.labeling
        self.wait(
            lambda: vm.identity_ok or self.c.error is not None or self.c.reject is not None,
            what="identity",
        )
        for code in vm.checklist:
            vm.toggle(code)
        self.c.advance()
        self.wait(lambda: self.c.stage is Stage.PACKAGING, what="packaging")

    def through_packaging(self) -> None:
        for code in self.c.packaging.checklist:
            self.c.packaging.toggle(code)
        self.c.advance()
        self.wait(
            lambda: self.c.stage is Stage.PROGRAMMING and self.c.device is None, what="next device"
        )

    def full_device(self) -> None:
        self.through_programming()
        self.through_testing()
        self.through_labeling()
        self.through_packaging()

    def shot(self, path: Path) -> None:
        self.process(60)
        path.parent.mkdir(parents=True, exist_ok=True)
        self.window.grab().save(str(path))

    def close(self) -> None:
        self.hardware.gate.set()
        self.controller.shutdown()
        self.window.hide()
        self.window.deleteLater()
        self.controller.deleteLater()
        # processEvents() never runs deferred deletes; without this every closed window
        # would keep listening to language changes.
        QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete.value)
        self.process(20)


# =========================================================================== screenshot run


def capture(out: Path, lang: str) -> list[Path]:
    shots: list[Path] = []

    def save(driver: StationDriver, name: str) -> None:
        path = out / f"{lang}_{name}.png"
        driver.shot(path)
        shots.append(path)

    def fresh(**kwargs: Any) -> StationDriver:
        driver = StationDriver(**kwargs)
        # Each operator's language is remembered; login switches to it.
        for operator in driver.ctx.auth.list_operators():
            driver.ctx.repos.operators.set_language(operator.id, lang)
        set_language(lang)
        return driver

    # --- login, lockout, ambient, programming states, reject, toast, drawer, end
    d = fresh(scenario=MockScenario.UPLOAD_FAILS_THEN_SUCCEEDS)
    d.start()
    set_language(lang)
    save(d, "01_login")
    for _ in range(5):
        d.c.login_phase = LoginPhase.FORM
        d.login(OPERATOR[0], "wrong-password")
    save(d, "02_login_locked")
    d.c.ambient_result_ms = 60_000
    d.c.login(ADMIN[0], ADMIN[2])
    d.wait(lambda: d.c.login_phase is LoginPhase.AMBIENT_DONE, what="ambient result")
    d.c.set_language(lang)
    save(d, "03_ambient")
    d.c._enter_production()
    d.ready_for_board()
    save(d, "04_programming_ready")
    d.connect()
    d.c.programming.upload()
    d.idle()
    save(d, "05_programming_failed_retry")
    d.hardware.gate_at = 52
    d.c.programming.upload()
    d.wait(
        lambda: d.hardware.reached.is_set() and d.c.programming.progress >= 52, what="gated flash"
    )
    d.process(250)
    save(d, "06_programming_uploading")
    d.hardware.gate.set()
    d.idle()
    d.hardware.gate_at = None
    save(d, "07_programming_adjust_prompt")
    d.c.programming.answer_adjust(True)
    d.c.advance()
    d.wait(lambda: d.c.stage is Stage.TESTING, what="testing")
    d.read_all_sensors(3)
    save(d, "08_testing_readings")
    d.read_all_sensors()
    d.mark_ok()
    save(d, "09_testing_measured")
    d.c.advance()
    d.wait(lambda: d.c.stage is Stage.LABELING, what="labeling")
    d.wait(lambda: d.c.labeling.identity_ok, what="identity")
    d.c.labeling.toggle(CheckCode.C1)
    d.c.labeling.toggle(CheckCode.C2)
    save(d, "10_labeling_match")
    d.c.labeling.toggle(CheckCode.C3)
    d.c.labeling.toggle(CheckCode.C4)
    d.c.advance()
    d.wait(lambda: d.c.stage is Stage.PACKAGING, what="packaging")
    d.c.packaging.toggle(CheckCode.D1)
    d.c.packaging.toggle(CheckCode.D2)
    save(d, "11_packaging")
    d.c.packaging.toggle(CheckCode.D3)
    d.c.packaging.toggle(CheckCode.D4)
    d.c.advance()
    d.wait(lambda: d.window.shell.toast.isVisible(), what="toast")
    save(d, "12_success_toast")
    d.hardware.set_scenario(MockScenario.V_C_OUT_OF_RANGE)
    d.through_programming()
    d.read_all_sensors()
    d.mark_ok()
    d.wait(lambda: d.c.reject is not None, what="reject")
    save(d, "13_reject_takeover")
    d.c.reject_confirmed()
    d.idle()
    d.window.shell.toast.hide()
    d.c.toggle_drawer(True)
    save(d, "14_session_drawer")
    d.c.toggle_drawer(False)
    d.c.request_end_session()
    save(d, "15_end_session_confirm")
    d.c.answer(True)
    d.wait(
        lambda: d.c.send_state is not None and d.c.send_state.value != "closing",
        what="session closed",
    )
    save(d, "16_session_summary")
    d.close()

    # --- labeling: ID write + confirm, manual entry
    d = fresh(scenario=MockScenario.ID_DIFFERS, settings={"camera": {"allow_manual_entry": True}})
    d.start()
    d.login()
    d.through_programming()
    d.through_testing()
    d.wait(lambda: d.c.labeling.identity_ok, what="identity written")
    d.c.labeling.toggle(CheckCode.C1)
    save(d, "17_labeling_id_written")
    d.c.labeling.reset()
    d.c.labeling.start_manual()
    d.c.labeling.submit_manual("PKM-000519", "PKM-000591")
    save(d, "18_labeling_manual_entry")
    d.close()

    # --- error banner: measurement timeout
    d = fresh(scenario=MockScenario.MEASUREMENT_TIMEOUT)
    d.start()
    d.login()
    d.through_programming()
    d.read_all_sensors()
    d.mark_ok()
    d.wait(lambda: d.c.error is not None, what="timeout banner")
    save(d, "19_error_measurement_timeout")
    d.close()

    # --- error banner: cable pulled mid-flash
    d = fresh(scenario=MockScenario.COM_DISCONNECT_MID_FLASH)
    d.start()
    d.login()
    d.connect()
    d.c.programming.upload()
    d.idle()
    save(d, "20_error_board_disconnected")
    d.close()

    # --- admin
    d = fresh()
    d.start()
    d.login()
    d.full_device()
    d.c.open_admin()
    d.wait(lambda: d.c.page is Page.ADMIN, what="admin")
    admin = d.window.admin
    for index, name in enumerate(
        [
            "21_admin_settings",
            "22_admin_operators",
            "23_admin_reports",
            "24_admin_counters",
            "25_admin_error_log",
        ]
    ):
        admin.tabs.setCurrentIndex(index)
        save(d, name)
    d.close()

    # --- invalid settings
    from parkomate.ui.views.pages import FatalView

    try:
        validate_settings({"limits": {"v_c_low": 3.4}, "email": {"password": "x"}})
    except SettingsError as exc:
        view = FatalView(exc, r"C:\ProgramData\Parkomate\settings.toml")
        view.resize(1366, 768)
        view.show()
        QApplication.processEvents()
        path = out / f"{lang}_26_invalid_settings.png"
        view.grab().save(str(path))
        shots.append(path)
        view.close()
    set_language("en")
    return shots


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Render every station screen to PNG")
    parser.add_argument("--out", type=Path, default=Path("docs/screenshots"))
    parser.add_argument("--lang", nargs="+", default=["en", "mr"])
    args = parser.parse_args(argv)
    os.environ["PARKOMATE_MOCK_DELAY"] = "0"
    create_application()
    written: list[Path] = []
    for lang in args.lang:
        written.extend(capture(args.out, lang))
    sys.stdout.write("\n".join(str(p) for p in written) + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
