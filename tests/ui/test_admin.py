"""Admin area: role gating, settings editor, operators, reports/outbox, counters, error log."""

from __future__ import annotations

import logging
from email.message import EmailMessage

from PySide6.QtCore import QItemSelectionModel
from PySide6.QtWidgets import QDoubleSpinBox, QLineEdit, QTableWidget

from parkomate.core.enums import OutboxStatus, Role
from parkomate.core.errors import ErrorCode, ParkomateError
from parkomate.logging_setup import setup_logging
from parkomate.ui.screenshots import ADMIN, OPERATOR, StationDriver
from parkomate.ui.viewmodels.station import Page
from parkomate.ui.views.admin import settings_issue_text
from parkomate.ui.workers.runner import TaskRunner
from tests.ui.conftest import DriverFactory


def _open_admin(d: StationDriver) -> None:
    d.c.open_admin()
    d.wait(lambda: d.c.page is Page.ADMIN, what="admin page")


def _select_row(table: QTableWidget, row: int) -> None:
    index = table.model().index(row, 0)
    table.selectionModel().select(
        index,
        QItemSelectionModel.SelectionFlag.ClearAndSelect | QItemSelectionModel.SelectionFlag.Rows,
    )


def test_admin_is_role_gated(make_driver: DriverFactory) -> None:
    d = make_driver()
    d.start()
    d.login(OPERATOR[0], OPERATOR[2])
    assert not d.c.is_admin and not d.c.can_open_admin()
    d.c.open_admin()
    assert d.c.page is Page.PRODUCTION


def test_admin_blocked_while_device_in_progress(driver: StationDriver) -> None:
    d = driver
    d.connect()
    assert d.window.shell.top.admin_button.isVisible()
    assert not d.window.shell.top.admin_button.isEnabled()
    assert d.window.shell.top.admin_button.toolTip().startswith("Finish or reject")
    d.c.open_admin()
    assert d.c.page is Page.PRODUCTION


def test_settings_editor_validates_and_audits(driver: StationDriver) -> None:
    d = driver
    _open_admin(d)
    tab = d.window.admin.settings_tab
    assert tab.labels["limits.v_c_low"].text() == "Point C minimum (V)"
    low = tab.editors["limits.v_c_low"]
    assert isinstance(low, QDoubleSpinBox)
    low.setValue(3.5)  # above v_c_high (3.35) -> invalid
    tab.save_settings()
    error = tab.errors["limits.v_c_low"]
    assert not error.isHidden()
    assert error.text() == "v_c_low must be smaller than v_c_high"
    assert tab.editors["limits.v_c_low"].property("invalid") is True
    assert d.ctx.settings.limits.v_c_low == 3.25  # nothing saved
    low.setValue(3.26)
    station = tab.editors["station.station_id"]
    assert isinstance(station, QLineEdit)
    station.setText("BENCH-2")
    tab.save_settings()
    assert tab.result.text().startswith("✓  Saved - 2 change(s)")
    assert d.ctx.settings.limits.v_c_low == 3.26
    assert d.ctx.records.station_id == "BENCH-2"
    audit = d.ctx.repos.audit.list_entries(action="settings.update")[0]
    assert audit.details["changes"]["limits.v_c_low"] == [3.25, 3.26]
    tab.save_settings()
    assert tab.result.text() == "Nothing changed"


def test_email_settings_need_fields(driver: StationDriver) -> None:
    d = driver
    _open_admin(d)
    tab = d.window.admin.settings_tab
    tab.editors["email.enabled"].setChecked(True)  # type: ignore[union-attr]
    tab.save_settings()
    for key in ("email.host", "email.sender", "email.recipients"):
        assert tab.errors[key].text() == "Required when e-mail is switched on", key
    recipients = tab.editors["email.recipients"]
    assert isinstance(recipients, QLineEdit)
    recipients.setText("qa@parkomate.example, nope")
    tab.save_settings()
    assert tab.errors["email.recipients"].text() == "Invalid e-mail address: nope"


def test_store_secret_never_in_settings(driver: StationDriver) -> None:
    d = driver
    _open_admin(d)
    tab = d.window.admin.settings_tab
    tab.secret_name.setCurrentText("smtp_password")
    tab.secret_value.setText("hunter2")
    tab.secret_save.click()
    assert d.ctx.secrets.get("smtp_password") == "hunter2"
    assert tab.secret_value.text() == ""
    assert "hunter2" not in d.ctx.paths.settings_file.read_text(encoding="utf-8")
    entry = d.ctx.repos.audit.list_entries(action="secret.set")[0]
    assert entry.details == {"name": "smtp_password"}  # the value is never audited


def test_operators_tab(driver: StationDriver) -> None:
    d = driver
    _open_admin(d)
    tab = d.window.admin.operators_tab
    assert tab.table.rowCount() == 2
    tab.new_code.setText("OP99")
    tab.new_name.setText("Nita Kale")
    tab.new_pw.setText("pass-word-9")
    tab.new_pw2.setText("pass-word-0")
    tab.add_button.click()
    assert tab.result.text() == "The two passwords are different"
    tab.new_pw2.setText("pass-word-9")
    tab.add_button.click()
    assert tab.result.text() == "✓  Operator OP99 added"
    assert tab.table.rowCount() == 3 and tab.new_code.text() == ""
    created = d.ctx.repos.operators.get_by_code("OP99")
    assert created is not None and created.role is Role.OPERATOR
    row = next(r for r in range(3) if tab.table.item(r, 0).text() == "OP99")
    _select_row(tab.table, row)
    assert tab.toggle_active.text() == "Deactivate"
    tab.toggle_active.click()
    assert not d.ctx.repos.operators.require(created.id).is_active
    _select_row(tab.table, row)
    tab.toggle_role.click()
    assert d.ctx.repos.operators.require(created.id).role is Role.ADMIN
    _select_row(tab.table, row)
    tab.reset_pw.setText("brand-new-1")
    tab.reset_pw2.setText("brand-new-1")
    tab.reset_button.click()
    assert tab.result.text() == "✓  New password set for OP99"
    _select_row(tab.table, row)
    tab.unlock.click()
    assert tab.result.text() == "✓  Operator OP99 unlocked"
    # the last admin cannot demote themselves
    admin_row = next(r for r in range(3) if tab.table.item(r, 0).text() == ADMIN[0])
    d.ctx.auth.set_role(d.c.operator, created.id, Role.OPERATOR)  # type: ignore[arg-type]
    tab.refresh()
    _select_row(tab.table, admin_row)
    tab.toggle_role.click()
    assert tab.result.text().startswith("✕  Action not possible now")


def test_reports_and_outbox_tab(driver: StationDriver) -> None:
    d = driver
    d.full_device()
    _open_admin(d)
    tab = d.window.admin.reports_tab
    tab.refresh()
    assert tab.sessions.rowCount() == 1
    tab._export_selected("xlsx")
    assert tab.result.text() == "Select one or more sessions first"
    _select_row(tab.sessions, 0)
    tab.export_xlsx.click()
    d.idle()
    assert tab.result.text().startswith("✓  Written:") and ".xlsx" in tab.result.text()
    tab.export_range.click()
    d.idle()
    assert tab.result.text().startswith("✓  Written:")
    tab.device_search.setText("PKM-000519")
    tab.device_export.click()
    d.idle()
    assert "device_" in tab.result.text()
    tab.device_search.setText("nothing-like-this")
    tab.device_export.click()
    assert tab.result.text() == 'No device found for "nothing-like-this"'

    # outbox: a failed e-mail can be resent by the admin
    message = EmailMessage()
    message["Subject"] = "Report"
    message.set_content("x")
    item = d.ctx.outbox.enqueue(message, None)
    d.ctx.repos.outbox.mark_attempt_failed(
        item.id, "MAIL_FAILED: down", next_attempt_at=None, give_up=True
    )
    tab.refresh()
    assert tab.outbox.item(0, 3).text() == "Failed"
    tab._resend()
    assert tab.result.text() == "Select an e-mail first"
    _select_row(tab.outbox, 0)
    tab.resend.click()  # e-mail is switched off -> MAIL_NOT_CONFIGURED -> stays queued
    d.idle()
    assert tab.result.text() == "Not sent - it stays in the outbox and will be retried"
    assert d.ctx.repos.outbox.require(item.id).status is OutboxStatus.PENDING
    tab.send_now.click()
    d.idle()
    assert tab.result.text() == "E-mail is switched off in the settings"


def test_counters_tab_reset(driver: StationDriver) -> None:
    d = driver
    d.full_device()
    _open_admin(d)
    tab = d.window.admin.counters_tab
    d.window.admin.tabs.setCurrentWidget(tab)
    tab.refresh()
    assert "Completed 1" in tab.values.text()
    tab.reset.click()
    assert tab.confirm.isVisible()
    tab.confirm.no_button.click()
    assert d.c.counters is not None and d.c.counters.completed == 1
    tab.reset.click()
    tab.confirm.yes_button.click()
    d.process()
    assert d.c.counters.completed == 0
    assert tab.result.text() == "✓  Counters reset"
    d.window.admin.back.click()
    assert d.c.page is Page.PRODUCTION


def test_error_log_tab(driver: StationDriver) -> None:
    d = driver
    setup_logging(d.ctx.paths.logs_dir, console=False)
    try:
        log = logging.getLogger("parkomate.test")
        log.error("mail broke", extra={"error_code": "MAIL_FAILED", "context": {"n": 1}})
        log.error("db broke", extra={"error_code": "DB_ERROR"})
        for handler in logging.getLogger().handlers:
            handler.flush()
        _open_admin(d)
        tab = d.window.admin.errors_tab
        tab.refresh()
        assert tab.table.rowCount() == 2
        assert tab.table.item(0, 3).text() == "db broke"
        tab.filter.setCurrentIndex(tab.filter.findData("MAIL_FAILED"))
        assert tab.table.rowCount() == 1
        _select_row(tab.table, 0)
        assert '"n": 1' in tab.details.toPlainText()
    finally:
        root = logging.getLogger()
        for handler in list(root.handlers):
            if getattr(handler, "_parkomate_handler", False):
                root.removeHandler(handler)
                handler.close()


def test_admin_language_switch(driver: StationDriver) -> None:
    d = driver
    _open_admin(d)
    d.c.set_language("mr")
    d.process()
    admin = d.window.admin
    assert admin.tabs.tabText(0) == "सेटिंग्ज"
    assert admin.settings_tab.labels["limits.v_c_low"].text() == "पॉइंट C किमान (V)"
    d.c.set_language("en")


def test_settings_issue_text_fallback() -> None:
    from parkomate.config.manager import SettingsIssue

    issue = SettingsIssue("x.y", "something_new", {}, "raw detail")
    assert settings_issue_text(issue) == "Invalid value: raw detail"


def test_worker_wraps_unexpected_exceptions(qapp: object) -> None:
    runner = TaskRunner(1)
    errors: list[ParkomateError] = []
    results: list[object] = []
    busy: list[bool] = []
    runner.busy_changed.connect(busy.append)

    def crash() -> None:
        raise ZeroDivisionError("boom")

    runner.submit(crash, on_error=errors.append, name="crash")
    runner.submit(lambda: 42, on_success=results.append)
    runner.submit(lambda: (_ for _ in ()).throw(ParkomateError("typed")))  # no handler: logged
    from PySide6.QtCore import QCoreApplication

    for _ in range(200):
        QCoreApplication.processEvents()
        if errors and results and not runner.busy:
            break
        runner.wait(10)
    assert errors[0].code is ErrorCode.UNEXPECTED and "ZeroDivisionError" in errors[0].message
    assert results == [42]
    assert busy[0] is True and busy[-1] is False
