"""Operator flow through the real UI on the mock bench."""

from __future__ import annotations

import itertools
import time

import pytest
from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QAbstractButton, QLabel, QWidget

from parkomate.core.enums import CheckCode, DeviceStatus, SessionEndReason, Stage
from parkomate.core.errors import ErrorCode
from parkomate.hardware.mocks import MockScenario
from parkomate.i18n import load_catalogue
from parkomate.ui.screenshots import ADMIN, OPERATOR, StationDriver
from parkomate.ui.viewmodels.station import LoginPhase, Page, SendState
from tests.ui.conftest import DriverFactory


def primary(d: StationDriver) -> str:
    action = d.window.shell.bottom.primary_action()
    assert action is not None
    return action.name


def primary_enabled(d: StationDriver) -> bool:
    return d.window.shell.bottom.primary.isEnabled()


def reason_text(d: StationDriver) -> str:
    return d.window.shell.bottom.reason.text()


# ------------------------------------------------------------------ login


def test_login_success(make_driver: DriverFactory) -> None:
    d = make_driver()
    d.start()
    assert d.window.stack.currentWidget() is d.window.login
    view = d.window.login
    view.code.setText(OPERATOR[0])
    view.password.setText(OPERATOR[2])
    view.login_button.click()
    d.wait(lambda: d.c.page is Page.PRODUCTION, what="production")
    assert d.window.stack.currentWidget() is d.window.shell
    assert d.c.operator is not None and d.c.operator.operator_code == "OP12"
    assert d.c.ambient_c is not None  # measured right after login
    assert not d.window.shell.top.admin_button.isVisible()  # operators have no admin area


def test_login_wrong_password(make_driver: DriverFactory) -> None:
    d = make_driver()
    d.start()
    d.login(OPERATOR[0], "nope")
    view = d.window.login
    assert d.c.page is Page.LOGIN
    assert view.error.isVisible()
    assert view.error.title.text() == "Login failed"
    assert view.password.text() == ""  # cleared for the next try
    assert d.c.login_phase is LoginPhase.FORM


def test_login_lockout_shows_minutes(make_driver: DriverFactory) -> None:
    d = make_driver()
    d.start()
    for _ in range(5):
        d.login(OPERATOR[0], "nope")
    assert d.c.login_error is not None and d.c.login_error.code is ErrorCode.AUTH_LOCKED
    view = d.window.login
    assert view.error.title.text() == "Account locked"
    assert "5 more minute(s)" in view.error.body.text()
    d.login(OPERATOR[0], OPERATOR[2])  # right password still refused while locked
    assert d.c.page is Page.LOGIN and d.c.login_error.code is ErrorCode.AUTH_LOCKED


# ------------------------------------------------------------------ gates per stage


def test_programming_gate(driver: StationDriver) -> None:
    d = driver
    assert d.c.programming.selected_port == "COM4"  # the only ESP32 bridge: auto-selected
    assert primary(d) == "connect" and primary_enabled(d)
    d.enter()  # Enter = primary action
    d.wait(lambda: d.c.programming.whitelist_state.value == "pass", what="whitelist")
    d.idle()
    assert primary(d) == "upload" and primary_enabled(d)
    d.enter()
    d.idle()
    assert d.c.programming.upload_state.value == "pass"
    assert primary(d) == "next" and primary_enabled(d)
    assert not d.c.programming.adjust_prompt  # no failure -> no adjust question
    d.enter()
    d.wait(lambda: d.c.stage is Stage.TESTING, what="testing")


def test_testing_gate(driver: StationDriver) -> None:
    d = driver
    d.through_programming()
    d.wait(lambda: d.c.testing.comm_state.value == "pass", what="auto comm test")
    assert primary(d) == "read"
    d.read_all_sensors()
    assert primary(d) == "measure" and not primary_enabled(d)
    assert reason_text(d) == "Mark the sensor readings and the indicator light"
    # buttons for sensor readings are enabled once 5 readings exist
    view = d.window.shell.views[Stage.TESTING]
    assert view.sensor_row.success.isEnabled()
    d.mark_ok()  # measurement starts automatically
    assert d.c.testing.measure_state.value == "pass"
    assert primary(d) == "next" and primary_enabled(d)


def test_labeling_and_packaging_gates(driver: StationDriver) -> None:
    d = driver
    d.through_programming()
    d.through_testing()
    vm = d.c.labeling
    d.wait(lambda: vm.identity_ok, what="auto scan + identity")
    assert primary(d) == "next" and not primary_enabled(d)
    assert reason_text(d) == "Tick all 4 checks to continue"
    d.c.function_key(1)  # F1
    d.c.function_key(2)
    d.process()
    assert reason_text(d) == "Tick 2 more check(s) to continue"
    view = d.window.shell.views[Stage.LABELING]
    view.rows[CheckCode.C3].click()  # whole row is clickable
    d.c.function_key(4)
    d.process()
    assert primary_enabled(d)
    d.enter()
    d.wait(lambda: d.c.stage is Stage.PACKAGING, what="packaging")
    assert primary(d) == "complete" and not primary_enabled(d)
    for n in (1, 2, 3):
        d.c.function_key(n)
    d.c.function_key(3)  # untick D3 again
    d.process()
    assert not primary_enabled(d)
    d.c.function_key(3)
    d.c.function_key(4)
    d.process()
    assert primary_enabled(d)


# ------------------------------------------------------------------ outcomes


def test_reject_takeover_text_and_return(make_driver: DriverFactory) -> None:
    d = make_driver(MockScenario.V_C_OUT_OF_RANGE)
    d.start()
    d.login()
    d.through_programming()
    d.read_all_sensors()
    d.mark_ok()
    d.wait(lambda: d.window.shell.takeover.isVisible(), what="takeover")
    takeover = d.window.shell.takeover
    assert takeover.headline.text() == "REJECT"
    assert takeover.place.text() == "Place device in the TESTING reject box (B)"
    assert takeover.box.text() == "B"
    assert takeover.reason.text() == "Point C voltage 3.21 V - allowed 3.25-3.35 V"
    assert d.window.shell.bottom.primary_action() is None  # nothing else to do
    d.window.shell.c.escape()  # Esc never dismisses a reject
    assert takeover.isVisible()
    takeover.button.click()  # "Device placed in box"
    d.wait(lambda: d.c.stage is Stage.PROGRAMMING and d.c.device is None, what="reset")
    assert not takeover.isVisible()
    assert d.c.counters is not None and d.c.counters.rejected == 1


def test_success_returns_to_programming(driver: StationDriver) -> None:
    d = driver
    d.full_device()
    toast = d.window.shell.toast
    assert toast.isVisible() and toast.label.text() == "Device PKM-000519 complete"
    assert d.c.stage is Stage.PROGRAMMING and d.c.device is None
    assert d.c.programming.connect_state.value == "pending"  # clean screen for next board
    assert d.c.counters is not None and d.c.counters.completed == 1
    d.full_device()  # the next board goes through the same way
    assert d.c.counters.completed == 2


def test_adjust_prompt_only_after_fail_then_success(make_driver: DriverFactory) -> None:
    d = make_driver(MockScenario.UPLOAD_FAILS_THEN_SUCCEEDS)
    d.start()
    d.login()
    d.connect()
    view = d.window.shell.views[Stage.PROGRAMMING]
    d.c.programming.upload()
    d.idle()
    assert d.c.programming.upload_state.value == "fail"
    assert not view.adjust.isVisible()  # failure alone: no prompt
    assert primary(d) == "retry"
    assert d.window.shell.bottom.primary.text().startswith("Retry upload (2 of 3)")
    d.enter()
    d.idle()
    assert view.adjust.isVisible()
    view.adjust_yes.click()
    d.process()
    assert not view.adjust.isVisible()
    assert d.c.counters is not None and d.c.counters.failures_adjusted == 1
    assert d.c.counters.net_upload_failure == 0
    assert not d.ctx.records.can_adjust_failure(d.c.device.device_row_id)  # once only


def test_no_prompt_when_first_upload_succeeds(driver: StationDriver) -> None:
    driver.connect()
    driver.upload_until_done()
    assert not driver.c.programming.adjust_prompt


def test_end_session_summary_and_logout(driver: StationDriver) -> None:
    d = driver
    d.full_device()
    d.c.toggle_drawer(True)
    assert d.window.shell.drawer.isVisible()
    assert d.window.shell.drawer.devices.count() == 1
    d.window.shell.drawer.end_button.click()
    assert d.window.shell.bottom.confirm.isVisible()  # inline, not an OS dialog
    d.c.escape()  # Esc cancels, never ends the session
    assert d.c.page is Page.PRODUCTION and d.c.confirm is None
    d.c.request_end_session()
    d.window.shell.press_enter()  # Enter confirms
    d.wait(lambda: d.c.send_state not in (None, SendState.CLOSING), what="closed")
    assert d.c.page is Page.SESSION_END
    view = d.window.session_end
    assert view._values["end.complete"].text() == "1"
    assert d.c.send_state is SendState.DISABLED  # e-mail off by default: saved locally
    assert "Report saved on this PC" in view.send_text.text()
    view.logout.click()
    d.wait(lambda: d.c.page is Page.LOGIN, what="login")


def test_end_session_with_device_abandons_it(driver: StationDriver) -> None:
    d = driver
    d.connect()
    row = d.c.device.device_row_id  # type: ignore[union-attr]
    d.c.request_end_session()
    assert d.c.confirm is not None and d.c.confirm.message_key == "confirm.end_session_device"
    d.c.answer(True)
    d.wait(lambda: d.c.send_state not in (None, SendState.CLOSING), what="closed")
    assert d.ctx.repos.devices.require(row).status is DeviceStatus.ABANDONED


def test_crash_recovery_notice(make_driver: DriverFactory) -> None:
    d = make_driver()
    # A previous run crashed with a board on the bench.
    admin = d.ctx.repos.operators.get_by_code(ADMIN[0])
    assert admin is not None
    d.ctx.records.start_session(admin, language="en")
    d.ctx.records.start_device("24:6F:28:00:00:01")
    d.ctx.records._session_id = None  # the process "died": nothing closed the session
    d.ctx.records._operator = None
    d.start()
    notice = d.window.login.notice
    assert notice.isVisible()
    assert notice.title.text() == "Last device was not finished - it has been marked abandoned"
    sessions = d.ctx.repos.sessions.list_sessions()
    assert sessions[0].end_reason is SessionEndReason.CRASH_RECOVERED


# ------------------------------------------------------------------ errors with fix steps


def test_measurement_timeout_banner_and_retry(make_driver: DriverFactory) -> None:
    d = make_driver(MockScenario.MEASUREMENT_TIMEOUT)
    d.start()
    d.login()
    d.through_programming()
    d.read_all_sensors()
    d.mark_ok()
    banner = d.window.shell.banner
    assert banner.isVisible() and banner.title.text() == "No measurement received"
    assert banner.steps.text().startswith("1.  Check that the measuring device")
    assert banner.retry_button.text() == "Measure again"
    assert not banner.details.isVisible()
    banner.details_link.click()
    assert banner.details.isVisible() and "MEAS_TIMEOUT" in banner.details.text()
    banner.retry_button.click()
    d.wait(lambda: d.c.testing.measure_state.value == "pass", what="second measurement")
    assert not banner.isVisible()


def test_cable_pulled_mid_flash(make_driver: DriverFactory) -> None:
    d = make_driver(MockScenario.COM_DISCONNECT_MID_FLASH)
    d.start()
    d.login()
    d.connect()
    d.c.programming.upload()
    d.idle()
    banner = d.window.shell.banner
    assert banner.title.text() == "Board not connected"
    assert d.c.programming.attempts == 1  # the interrupted flash counts as a failed attempt
    banner.retry_button.click()  # "Retry upload" reconnects and flashes again
    d.idle()
    assert d.c.programming.upload_state.value == "pass"


def test_manual_id_entry(make_driver: DriverFactory) -> None:
    d = make_driver(MockScenario.QR_UNREADABLE, settings={"camera": {"allow_manual_entry": True}})
    d.start()
    d.login()
    d.through_programming()
    d.read_all_sensors()
    d.mark_ok()
    d.c.advance()
    d.wait(lambda: d.c.error is not None, what="QR unreadable banner")
    assert d.c.error is not None and d.c.error.error.code is ErrorCode.QR_UNREADABLE
    names = [b.objectName() for b in d.window.shell.bottom.secondary_buttons() if b.isVisible()]
    assert "secondary_manual" in names
    vm = d.c.labeling
    vm.start_manual()
    view = d.window.shell.views[Stage.LABELING]
    assert view.manual.isVisible()
    view.manual_first.setText("PKM-000777")
    view.manual_second.setText("PKM-000778")
    view.manual_ok.click()
    assert view.manual_error.text() == "The two entries are different - type them again"
    view.manual_second.setText("PKM-000777")
    view.manual_second.setFocus()
    d.window.shell.press_enter()  # Enter in the field submits it
    d.wait(lambda: vm.identity_ok, what="manual identity")
    device = d.ctx.repos.devices.require(d.c.device.device_row_id)  # type: ignore[union-attr]
    assert device.device_id == "PKM-000777" and device.id_entry_method.value == "manual"


# ------------------------------------------------------------------ every mock scenario


@pytest.mark.parametrize(
    ("scenario", "outcome"),
    [
        (MockScenario.ALL_PASS, "complete"),
        (MockScenario.UPLOAD_FAILS_THEN_SUCCEEDS, "complete"),
        (MockScenario.ID_DIFFERS, "complete"),
        (MockScenario.QR_UNREADABLE, "complete"),
        (MockScenario.MEASUREMENT_TIMEOUT, "complete"),
        (MockScenario.COM_DISCONNECT_MID_FLASH, "complete"),
        (MockScenario.WHITELIST_DENIED, "reject_A"),
        (MockScenario.UPLOAD_ALWAYS_FAILS, "reject_A"),
        (MockScenario.COMM_FAIL, "reject_B"),
        (MockScenario.V_C_OUT_OF_RANGE, "reject_B"),
        (MockScenario.TEMP_TOO_HIGH, "reject_B"),
        (MockScenario.ID_WRITE_FAILS, "reject_C"),
        (MockScenario.CAMERA_MISSING, "camera_error"),
    ],
)
def test_every_scenario_end_to_end(
    make_driver: DriverFactory, scenario: MockScenario, outcome: str
) -> None:
    d = make_driver(scenario)
    d.start()
    d.login()
    d.ready_for_board()

    def retry_errors() -> None:
        if d.c.error is not None and d.c.error.retry is not None:
            d.c.retry_error()
            d.idle()

    d.connect()
    for _ in range(4):
        if d.c.reject or d.c.programming.upload_state.value == "pass":
            break
        d.c.programming.upload()
        d.idle()
        retry_errors()
    if d.c.reject is None:
        d.c.advance()
        d.wait(lambda: d.c.stage is Stage.TESTING or d.c.reject is not None, what="testing")
    if d.c.reject is None:
        d.wait(
            lambda: d.c.testing.comm_state.value != "working" or d.c.reject is not None, what="comm"
        )
        d.process(50)
    if d.c.reject is None:
        d.read_all_sensors()
        d.mark_ok()
        retry_errors()
        d.idle()
    if d.c.reject is None:
        d.c.advance()
        d.wait(
            lambda: d.c.labeling.identity_ok or d.c.reject is not None or d.c.error is not None,
            what="identity",
        )
        if outcome == "camera_error":
            assert d.c.error is not None and d.c.error.error.code is ErrorCode.CAM_NOT_FOUND
            return
        retry_errors()
        d.wait(lambda: d.c.labeling.identity_ok or d.c.reject is not None, what="identity 2")
    if d.c.reject is None:
        for n in (1, 2, 3, 4):
            d.c.function_key(n)
        d.c.advance()
        d.wait(lambda: d.c.stage is Stage.PACKAGING, what="packaging")
        for n in (1, 2, 3, 4):
            d.c.function_key(n)
        d.c.advance()
        d.wait(lambda: d.c.device is None, what="complete")
        assert outcome == "complete"
        assert d.c.counters is not None and d.c.counters.completed == 1
        return
    instruction = d.c.reject
    assert outcome == f"reject_{instruction.box_letter}", instruction
    d.wait(lambda: d.window.shell.takeover.isVisible(), what="takeover")


# ------------------------------------------------------------------ language & a11y


def _visible_texts(root: QWidget) -> list[str]:
    texts = []
    for widget in root.findChildren(QWidget):
        if not widget.isVisible():
            continue
        if isinstance(widget, QLabel | QAbstractButton) and widget.text().strip():
            texts.append(widget.text().strip())
    return texts


def test_language_switch_rerenders_everything(driver: StationDriver) -> None:
    d = driver
    d.connect()
    english_only = {
        text
        for key, text in load_catalogue("en").items()
        if load_catalogue("mr").get(key) != text and not key.startswith(("cli.", "key."))
    }
    before = _visible_texts(d.window)
    assert any(text in english_only for text in before)
    d.window.shell.top.language.button("mr").click()
    d.process(50)
    after = _visible_texts(d.window)
    leftovers = [text for text in after if text in english_only]
    assert leftovers == []
    assert d.window.shell.top.stepper.label_for(Stage.PROGRAMMING).text().endswith("प्रोग्रामिंग")
    assert d.window.shell.bottom.primary.text().startswith("फर्मवेअर अपलोड करा")
    # remembered per operator
    assert d.ctx.repos.operators.get_by_code(ADMIN[0]).language == "mr"  # type: ignore[union-attr]
    d.window.shell.top.language.button("en").click()
    d.process(50)
    assert d.window.shell.bottom.primary.text().startswith("Upload firmware")


def test_accessibility_basics(driver: StationDriver) -> None:
    d = driver
    bottom = d.window.shell.bottom
    assert bottom.primary.accessibleName() == "Connect board"
    assert bottom.primary.minimumHeight() >= 56
    stepper = d.window.shell.top.stepper
    assert "Programming" in stepper.accessibleName()
    d.through_programming()
    d.through_testing()
    view = d.window.shell.views[Stage.LABELING]
    for row in view.rows.values():
        assert row.accessibleName()
        assert row.minimumHeight() >= 56
        assert row.focusPolicy().name == "StrongFocus"
    # Tab order on the login page: operator ID -> password -> show -> log in
    login = d.window.login
    chain = []
    widget = login.code
    while len(chain) < 4:
        chain.append(widget)
        widget = widget.nextInFocusChain()
        while not (widget.focusPolicy().value & 0x1):  # skip widgets without Tab focus
            widget = widget.nextInFocusChain()
    assert chain == [login.code, login.password, login.show_password, login.login_button]
    # Disabled primary explains itself (tooltip + text + accessible description)
    assert not bottom.primary.isEnabled()
    assert bottom.primary.toolTip() == "Tick all 4 checks to continue"
    assert bottom.primary.accessibleDescription() == bottom.primary.toolTip()


@pytest.mark.slow
def test_ui_never_freezes_during_hardware_calls(make_driver: DriverFactory) -> None:
    d = make_driver(delay_scale=1.0)  # real mock delays: a flash takes ~1.5 s
    d.start()
    d.login()
    d.ready_for_board()
    d.connect()
    ticks: list[float] = []
    timer = QTimer()
    timer.setInterval(50)
    timer.timeout.connect(lambda: ticks.append(time.monotonic()))
    timer.start()
    started = time.monotonic()
    d.c.programming.upload()
    assert d.c.programming.upload_state.value == "working"  # returned immediately
    assert time.monotonic() - started < 0.2
    d.wait(lambda: d.c.programming.upload_state.value == "pass", timeout=20, what="flash")
    timer.stop()
    duration = time.monotonic() - started
    assert duration > 1.0
    assert len(ticks) >= duration / 0.05 * 0.6  # the event loop kept running
    gaps = [b - a for a, b in itertools.pairwise(ticks)]
    assert max(gaps) < 0.4
    assert d.c.programming.progress == 100
