"""Admin area (role-gated): settings, operators, reports + e-mail outbox, counters, error log."""

from __future__ import annotations

import json
from collections.abc import Sequence
from datetime import UTC, date, datetime, time, timedelta
from typing import Any, Literal, cast, get_args, get_origin

from pydantic import BaseModel
from PySide6.QtCore import QDate, Qt, QUrl
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (
    QAbstractItemView,
    QCheckBox,
    QComboBox,
    QDateEdit,
    QDoubleSpinBox,
    QFormLayout,
    QFrame,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QPlainTextEdit,
    QScrollArea,
    QSpinBox,
    QTableWidget,
    QTableWidgetItem,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from parkomate.config.settings import Settings
from parkomate.core.enums import Role
from parkomate.core.errors import ErrorCode, ParkomateError, SettingsError
from parkomate.core.models import Operator
from parkomate.i18n import t, translator
from parkomate.logging_setup import read_error_log
from parkomate.ui.components.widgets import BigButton, InlineConfirm, TrLabel, card, set_prop
from parkomate.ui.qt_i18n import error_cause, error_title, language_notifier
from parkomate.ui.theme.fonts import font
from parkomate.ui.theme.tokens import SIZES
from parkomate.ui.viewmodels.station import StationController

Editor = QCheckBox | QSpinBox | QDoubleSpinBox | QComboBox | QLineEdit


def settings_issue_text(issue: Any) -> str:
    """Translated text for a ``SettingsIssue`` (falls back to the English detail)."""
    key = f"settings.err.{issue.type}"
    if translator().has(key, "en"):
        params = {k: v for k, v in issue.ctx.items() if not isinstance(v, list | dict)}
        return t(key, **params)
    return t("settings.err.generic", detail=issue.message)


def _table(headers: Sequence[str]) -> QTableWidget:
    table = QTableWidget(0, len(headers))
    table.setHorizontalHeaderLabels(list(headers))
    table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
    table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
    table.verticalHeader().setVisible(False)
    table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
    table.horizontalHeader().setStretchLastSection(True)
    return table


def _set_headers(table: QTableWidget, keys: Sequence[str]) -> None:
    table.setHorizontalHeaderLabels([t(k) for k in keys])


def _fill(table: QTableWidget, rows: list[list[str]], data: list[Any] | None = None) -> None:
    table.setRowCount(len(rows))
    for r, row in enumerate(rows):
        for c, value in enumerate(row):
            item = QTableWidgetItem(value)
            if c == 0 and data is not None:
                item.setData(Qt.ItemDataRole.UserRole, data[r])
            table.setItem(r, c, item)


def _selected_data(table: QTableWidget) -> list[Any]:
    rows = sorted({index.row() for index in table.selectionModel().selectedRows()})
    values = []
    for row in rows:
        item = table.item(row, 0)
        if item is not None:
            values.append(item.data(Qt.ItemDataRole.UserRole))
    return values


def _local(value: datetime | None) -> str:
    return "" if value is None else value.astimezone().strftime("%Y-%m-%d %H:%M")


class ResultLine(QLabel):
    """One-line outcome message with tone (pass / fail / info)."""

    def __init__(self) -> None:
        super().__init__()
        self.setWordWrap(True)
        self.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        self.setFont(font(SIZES.font_base, bold=True))

    def ok(self, text: str) -> None:
        set_prop(self, "status", "pass")
        self.setText(f"✓  {text}")

    def fail(self, error: ParkomateError) -> None:
        set_prop(self, "status", "fail")
        self.setText(f"✕  {error_title(error)} - {error_cause(error)}")

    def info(self, text: str) -> None:
        set_prop(self, "status", "info")
        self.setText(text)


# =========================================================================== settings


class SettingsTab(QWidget):
    def __init__(self, controller: StationController) -> None:
        super().__init__()
        self.c = controller
        layout = QVBoxLayout(self)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        inner = QWidget()
        self.form_layout = QVBoxLayout(inner)
        self.form_layout.setSpacing(SIZES.space_l)
        scroll.setWidget(inner)
        layout.addWidget(scroll, 1)
        self.editors: dict[str, Editor] = {}
        self.errors: dict[str, QLabel] = {}
        self.labels: dict[str, QLabel] = {}
        self.groups: dict[str, QGroupBox] = {}
        self._build()
        self._build_secrets()
        buttons = QHBoxLayout()
        self.result = ResultLine()
        buttons.addWidget(self.result, 1)
        self.reload = BigButton("action.reload_settings")
        self.reload.clicked.connect(self.load)
        self.save = BigButton("action.save_settings", variant="primary")
        self.save.clicked.connect(self.save_settings)
        buttons.addWidget(self.reload)
        buttons.addWidget(self.save)
        layout.addLayout(buttons)
        language_notifier().changed.connect(self.retranslate)
        self.retranslate()
        self.load()

    # ---------------------------------------------------------------- build
    def _build(self) -> None:
        general = self._group("general")
        self._add_field(general, "retention_days", Settings.model_fields["retention_days"])
        for section, info in Settings.model_fields.items():
            model = info.annotation
            if not (isinstance(model, type) and issubclass(model, BaseModel)):
                continue
            form = self._group(section)
            for key, field_info in model.model_fields.items():
                self._add_field(form, f"{section}.{key}", field_info)

    def _group(self, section: str) -> QFormLayout:
        box = QGroupBox()
        box.setFont(font(SIZES.font_h2, bold=True))
        form = QFormLayout(box)
        form.setLabelAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        form.setHorizontalSpacing(SIZES.space_l)
        form.setVerticalSpacing(SIZES.space_s)
        self.groups[section] = box
        self.form_layout.addWidget(box)
        return form

    def _add_field(self, form: QFormLayout, dotted: str, info: Any) -> None:
        editor = self._editor_for(info)
        editor.setFont(font(SIZES.font_base))
        label = QLabel()
        label.setFont(font(SIZES.font_base))
        label.setWordWrap(True)
        error = QLabel()
        error.setProperty("status", "fail")
        error.setWordWrap(True)
        error.setVisible(False)
        column = QVBoxLayout()
        column.setSpacing(2)
        column.addWidget(editor)
        column.addWidget(error)
        form.addRow(label, column)
        self.editors[dotted] = editor
        self.errors[dotted] = error
        self.labels[dotted] = label

    @staticmethod
    def _bounds(info: Any) -> tuple[float | None, float | None]:
        low = high = None
        for meta in info.metadata:
            for attr in ("ge", "gt"):
                if getattr(meta, attr, None) is not None:
                    low = getattr(meta, attr)
            for attr in ("le", "lt"):
                if getattr(meta, attr, None) is not None:
                    high = getattr(meta, attr)
        return low, high

    def _editor_for(self, info: Any) -> Editor:
        annotation = info.annotation
        low, high = self._bounds(info)
        if annotation is bool:
            return QCheckBox()
        if annotation is int:
            spin = QSpinBox()
            spin.setRange(
                int(low if low is not None else -1_000_000),
                int(high if high is not None else 1_000_000_000),
            )
            return spin
        if annotation is float:
            dspin = QDoubleSpinBox()
            dspin.setDecimals(3)
            dspin.setSingleStep(0.01)
            dspin.setRange(
                float(low if low is not None else -1_000_000.0),
                float(high if high is not None else 1_000_000.0),
            )
            return dspin
        if get_origin(annotation) is Literal:
            combo = QComboBox()
            for option in get_args(annotation):
                combo.addItem(str(option), option)
            return combo
        return QLineEdit()

    def _build_secrets(self) -> None:
        box = QGroupBox()
        box.setFont(font(SIZES.font_h2, bold=True))
        self.groups["secrets"] = box
        grid = QGridLayout(box)
        self.secret_help = QLabel()
        self.secret_help.setWordWrap(True)
        self.secret_help.setFont(font(SIZES.font_base))
        grid.addWidget(self.secret_help, 0, 0, 1, 3)
        self.secret_name = QComboBox()
        self.secret_value = QLineEdit()
        self.secret_value.setEchoMode(QLineEdit.EchoMode.Password)
        self.secret_save = BigButton("action.store_secret")
        self.secret_save.clicked.connect(self._store_secret)
        grid.addWidget(self.secret_name, 1, 0)
        grid.addWidget(self.secret_value, 1, 1)
        grid.addWidget(self.secret_save, 1, 2)
        self.secret_state = QLabel()
        self.secret_state.setFont(font(SIZES.font_base))
        grid.addWidget(self.secret_state, 2, 0, 1, 3)
        self.form_layout.addWidget(box)

    # ---------------------------------------------------------------- data
    def load(self) -> None:
        values = self.c.settings.model_dump(mode="json")
        for dotted, editor in self.editors.items():
            value: Any = values
            for part in dotted.split("."):
                value = value[part]
            self._set_value(editor, value)
        self._clear_errors()
        self._refresh_secrets()

    @staticmethod
    def _set_value(editor: Editor, value: Any) -> None:
        if isinstance(editor, QCheckBox):
            editor.setChecked(bool(value))
        elif isinstance(editor, QSpinBox):
            editor.setValue(int(value))
        elif isinstance(editor, QDoubleSpinBox):
            editor.setValue(float(value))
        elif isinstance(editor, QComboBox):
            editor.setCurrentIndex(max(0, editor.findData(value)))
        elif isinstance(value, list):
            editor.setText(", ".join(str(v) for v in value))
        else:
            editor.setText(str(value))

    def collect(self) -> dict[str, Any]:
        data: dict[str, Any] = {}
        for dotted, editor in self.editors.items():
            if isinstance(editor, QCheckBox):
                value: Any = editor.isChecked()
            elif isinstance(editor, QSpinBox | QDoubleSpinBox):
                value = editor.value()
            elif isinstance(editor, QComboBox):
                value = editor.currentData()
            else:
                value = editor.text().strip()
                if dotted == "email.recipients":
                    value = [part.strip() for part in value.split(",") if part.strip()]
            target = data
            parts = dotted.split(".")
            for part in parts[:-1]:
                target = target.setdefault(part, {})
            target[parts[-1]] = value
        return data

    def _clear_errors(self) -> None:
        for dotted, label in self.errors.items():
            label.setVisible(False)
            set_prop(self.editors[dotted], "invalid", False)

    def save_settings(self) -> None:
        operator = self.c.operator
        if operator is None:
            return
        self._clear_errors()
        try:
            changes = self.c.ctx.settings_manager.save(self.collect(), operator)
        except SettingsError as exc:
            self._show_issues(exc)
            self.result.fail(exc)
            return
        except ParkomateError as exc:
            self.result.fail(exc)
            return
        if changes:
            self.result.ok(t("settings.saved", n=len(changes)))
        else:
            self.result.info(t("settings.no_changes"))
        self.load()

    def _show_issues(self, exc: SettingsError) -> None:
        first: QWidget | None = None
        for issue in exc.issues:
            keys = issue.ctx.get("keys") if isinstance(issue.ctx.get("keys"), list) else [issue.key]
            for key in keys:
                label = self.errors.get(key)
                if label is None:
                    continue
                label.setText(settings_issue_text(issue))
                label.setVisible(True)
                set_prop(self.editors[key], "invalid", True)
                first = first or self.editors[key]
        if first is not None:
            first.setFocus()

    def _secret_names(self) -> list[str]:
        settings = self.c.settings
        return [
            settings.email.password_ref,
            settings.email.oauth_token_ref,
            settings.server.api_token_ref,
        ]

    def _refresh_secrets(self) -> None:
        current = self.secret_name.currentText()
        self.secret_name.clear()
        names = self._secret_names()
        self.secret_name.addItems(names)
        if current in names:
            self.secret_name.setCurrentText(current)
        states = []
        for name in names:
            stored = self.c.ctx.secrets.get(name) is not None
            states.append(
                t(
                    "settings.secret_state",
                    name=name,
                    state=t("settings.secret_stored" if stored else "settings.secret_missing"),
                )
            )
        self.secret_state.setText("\n".join(states))

    def _store_secret(self) -> None:
        operator = self.c.operator
        value = self.secret_value.text()
        name = self.secret_name.currentText()
        if operator is None or not operator.is_admin or not value or not name:
            return
        try:
            self.c.ctx.secrets.set(name, value)
        except Exception:  # keyring backends raise their own types
            self.result.fail(
                ParkomateError(
                    "keyring write failed", code=ErrorCode.SECRET_MISSING, params={"name": name}
                )
            )
            return
        self.c.ctx.repos.audit.record(operator.id, "secret.set", {"name": name})
        self.secret_value.clear()
        self.result.ok(t("settings.secret_saved", name=name))
        self._refresh_secrets()

    def retranslate(self, *_args: object) -> None:
        for section, box in self.groups.items():
            box.setTitle(t(f"settings.section.{section}"))
        for dotted, label in self.labels.items():
            text = t(f"settings.f.{dotted}")
            label.setText(text)
            self.editors[dotted].setAccessibleName(text)
        self.secret_help.setText(t("settings.secrets_help"))
        self.secret_value.setPlaceholderText(t("settings.secret_value"))
        self.secret_value.setAccessibleName(t("settings.secret_value"))
        self._refresh_secrets()


# =========================================================================== operators


class OperatorsTab(QWidget):
    COLUMNS = (
        "admin.op.code",
        "admin.op.name",
        "admin.op.role",
        "admin.op.active",
        "admin.op.locked",
    )

    def __init__(self, controller: StationController) -> None:
        super().__init__()
        self.c = controller
        layout = QHBoxLayout(self)
        layout.setSpacing(SIZES.space_l)
        left = QVBoxLayout()
        self.table = _table(self.COLUMNS)
        self.table.itemSelectionChanged.connect(self._selection_changed)
        left.addWidget(self.table, 1)
        actions = QHBoxLayout()
        self.toggle_active = BigButton("action.deactivate")
        self.toggle_active.clicked.connect(self._toggle_active)
        self.unlock = BigButton("action.unlock")
        self.unlock.clicked.connect(self._unlock)
        self.toggle_role = BigButton("action.make_admin")
        self.toggle_role.clicked.connect(self._toggle_role)
        for button in (self.toggle_active, self.unlock, self.toggle_role):
            actions.addWidget(button)
        left.addLayout(actions)
        reset_row = QHBoxLayout()
        self.reset_pw = QLineEdit()
        self.reset_pw.setEchoMode(QLineEdit.EchoMode.Password)
        self.reset_pw2 = QLineEdit()
        self.reset_pw2.setEchoMode(QLineEdit.EchoMode.Password)
        self.reset_button = BigButton("action.reset_password")
        self.reset_button.clicked.connect(self._reset_password)
        reset_row.addWidget(self.reset_pw)
        reset_row.addWidget(self.reset_pw2)
        reset_row.addWidget(self.reset_button)
        left.addLayout(reset_row)
        self.result = ResultLine()
        left.addWidget(self.result)
        layout.addLayout(left, 3)

        add_card, add = card()
        add.addWidget(TrLabel("admin.op.add_title", role="h2"))
        self.new_code = QLineEdit()
        self.new_name = QLineEdit()
        self.new_role = QComboBox()
        self.new_pw = QLineEdit()
        self.new_pw.setEchoMode(QLineEdit.EchoMode.Password)
        self.new_pw2 = QLineEdit()
        self.new_pw2.setEchoMode(QLineEdit.EchoMode.Password)
        for widget in (self.new_code, self.new_name, self.new_role, self.new_pw, self.new_pw2):
            add.addWidget(widget)
        self.add_button = BigButton("action.add_operator", variant="primary")
        self.add_button.clicked.connect(self._add)
        add.addWidget(self.add_button)
        add.addStretch(1)
        layout.addWidget(add_card, 2)
        language_notifier().changed.connect(self.retranslate)
        self.retranslate()

    def refresh(self) -> None:
        operators = self.c.ctx.auth.list_operators()
        rows = []
        for op in operators:
            locked = op.locked_until is not None and op.locked_until > self.c.ctx.repos.clock.now()
            rows.append(
                [
                    op.operator_code,
                    op.full_name,
                    t(op.role.label_key),
                    t("common.yes" if op.is_active else "common.no"),
                    t("common.yes" if locked else "common.no"),
                ]
            )
        _fill(self.table, rows, [op.id for op in operators])
        self._selection_changed()

    def _selected(self) -> Operator | None:
        ids = _selected_data(self.table)
        return self.c.ctx.repos.operators.get(ids[0]) if ids else None

    def _selection_changed(self) -> None:
        selected = self._selected()
        for button in (self.toggle_active, self.unlock, self.toggle_role, self.reset_button):
            button.setEnabled(selected is not None)
        if selected is not None:
            self.toggle_active.set_text_key(
                "action.deactivate" if selected.is_active else "action.activate"
            )
            self.toggle_role.set_text_key(
                "action.make_operator" if selected.is_admin else "action.make_admin"
            )

    def _run(self, fn: Any, ok_key: str, **params: Any) -> None:
        actor = self.c.operator
        if actor is None:
            return
        try:
            fn(actor)
        except ParkomateError as exc:
            self.result.fail(exc)
            return
        self.result.ok(t(ok_key, **params))
        self.refresh()

    def _toggle_active(self) -> None:
        op = self._selected()
        if op is not None:
            self._run(
                lambda a: self.c.ctx.auth.set_active(a, op.id, not op.is_active),
                "admin.op.updated",
                code=op.operator_code,
            )

    def _unlock(self) -> None:
        op = self._selected()
        if op is not None:
            self._run(
                lambda a: self.c.ctx.auth.unlock(a, op.id),
                "admin.op.unlocked",
                code=op.operator_code,
            )

    def _toggle_role(self) -> None:
        op = self._selected()
        if op is not None:
            role = Role.OPERATOR if op.is_admin else Role.ADMIN
            self._run(
                lambda a: self.c.ctx.auth.set_role(a, op.id, role),
                "admin.op.updated",
                code=op.operator_code,
            )

    def _reset_password(self) -> None:
        op = self._selected()
        if op is None:
            return
        if self.reset_pw.text() != self.reset_pw2.text():
            self.result.info(t("admin.op.passwords_differ"))
            return
        password = self.reset_pw.text()
        self._run(
            lambda a: self.c.ctx.auth.reset_password(a, op.id, password),
            "admin.op.password_reset",
            code=op.operator_code,
        )
        self.reset_pw.clear()
        self.reset_pw2.clear()

    def _add(self) -> None:
        if self.new_pw.text() != self.new_pw2.text():
            self.result.info(t("admin.op.passwords_differ"))
            return
        code, name = self.new_code.text(), self.new_name.text()
        role = self.new_role.currentData()
        password = self.new_pw.text()
        self._run(
            lambda a: self.c.ctx.auth.create_operator(a, code, name, password, role),
            "admin.op.created",
            code=code.strip(),
        )
        if self.result.property("status") == "pass":
            for field in (self.new_code, self.new_name, self.new_pw, self.new_pw2):
                field.clear()

    def retranslate(self, *_args: object) -> None:
        _set_headers(self.table, self.COLUMNS)
        self.table.setAccessibleName(t("admin.tab.operators"))
        placeholders = [
            (self.new_code, "admin.op.code"),
            (self.new_name, "admin.op.name"),
            (self.new_pw, "admin.op.password"),
            (self.new_pw2, "admin.op.password_again"),
            (self.reset_pw, "admin.op.new_password"),
            (self.reset_pw2, "admin.op.password_again"),
        ]
        for field, key in placeholders:
            field.setPlaceholderText(t(key))
            field.setAccessibleName(t(key))
        current = self.new_role.currentData()
        self.new_role.clear()
        for role in (Role.OPERATOR, Role.ADMIN):
            self.new_role.addItem(t(role.label_key), role)
        self.new_role.setCurrentIndex(max(0, self.new_role.findData(current)))
        self.new_role.setAccessibleName(t("admin.op.role"))


# =========================================================================== reports


class ReportsTab(QWidget):
    SESSION_COLUMNS = (
        "admin.rep.session",
        "admin.rep.operator",
        "admin.rep.started",
        "admin.rep.ended",
        "admin.rep.devices",
    )
    OUTBOX_COLUMNS = (
        "admin.out.id",
        "admin.out.created",
        "admin.out.subject",
        "admin.out.status",
        "admin.out.attempts",
        "admin.out.error",
    )

    def __init__(self, controller: StationController) -> None:
        super().__init__()
        self.c = controller
        layout = QVBoxLayout(self)
        top = QHBoxLayout()
        sessions_box = QVBoxLayout()
        self.sessions_title = TrLabel("admin.rep.sessions_title", role="h2")
        sessions_box.addWidget(self.sessions_title)
        self.sessions = _table(self.SESSION_COLUMNS)
        sessions_box.addWidget(self.sessions, 1)
        buttons = QHBoxLayout()
        self.export_xlsx = BigButton("action.export_excel", variant="primary")
        self.export_csv = BigButton("action.export_csv")
        self.export_xlsx.clicked.connect(lambda: self._export_selected("xlsx"))
        self.export_csv.clicked.connect(lambda: self._export_selected("csv"))
        buttons.addWidget(self.export_xlsx)
        buttons.addWidget(self.export_csv)
        sessions_box.addLayout(buttons)
        range_row = QHBoxLayout()
        self.date_from = QDateEdit()
        self.date_to = QDateEdit()
        for edit in (self.date_from, self.date_to):
            edit.setCalendarPopup(True)
            edit.setDisplayFormat("yyyy-MM-dd")
        today = QDate.currentDate()
        self.date_from.setDate(today.addDays(-7))
        self.date_to.setDate(today)
        self.range_format = QComboBox()
        self.export_range = BigButton("action.export_range")
        self.export_range.clicked.connect(self._export_range)
        range_row.addWidget(self.date_from)
        range_row.addWidget(self.date_to)
        range_row.addWidget(self.range_format)
        range_row.addWidget(self.export_range)
        sessions_box.addLayout(range_row)
        device_row = QHBoxLayout()
        self.device_search = QLineEdit()
        self.device_export = BigButton("action.export_device")
        self.device_export.clicked.connect(self._export_device)
        device_row.addWidget(self.device_search, 1)
        device_row.addWidget(self.device_export)
        sessions_box.addLayout(device_row)
        top.addLayout(sessions_box, 1)
        layout.addLayout(top, 1)

        layout.addWidget(TrLabel("admin.out.title", role="h2"))
        self.outbox = _table(self.OUTBOX_COLUMNS)
        layout.addWidget(self.outbox, 1)
        outbox_buttons = QHBoxLayout()
        self.result = ResultLine()
        outbox_buttons.addWidget(self.result, 1)
        self.open_folder = BigButton("action.open_reports_folder")
        self.open_folder.clicked.connect(self._open_folder)
        self.resend = BigButton("action.resend")
        self.resend.clicked.connect(self._resend)
        self.send_now = BigButton("action.send_pending")
        self.send_now.clicked.connect(self._send_now)
        for button in (self.open_folder, self.resend, self.send_now):
            outbox_buttons.addWidget(button)
        layout.addLayout(outbox_buttons)
        language_notifier().changed.connect(self.retranslate)
        self.retranslate()

    def refresh(self) -> None:
        repos = self.c.ctx.repos
        sessions = repos.sessions.list_sessions(limit=200)
        rows = []
        for session in sessions:
            operator = repos.operators.get(session.operator_id)
            count = len(repos.devices.list_for_session(session.id))
            rows.append(
                [
                    str(session.id),
                    operator.operator_code if operator else "",
                    _local(session.started_at),
                    _local(session.ended_at),
                    str(count),
                ]
            )
        _fill(self.sessions, rows, [s.id for s in sessions])
        items = self.c.ctx.outbox.list_items()
        _fill(
            self.outbox,
            [
                [
                    str(i.id),
                    _local(i.created_at),
                    i.subject,
                    t(i.status.label_key),
                    str(i.attempts),
                    i.last_error or "",
                ]
                for i in items
            ],
            [i.id for i in items],
        )

    def _done(self, paths: list[Any]) -> None:
        self.result.ok(t("admin.rep.written", files=", ".join(str(p) for p in paths)))

    def _export_selected(self, fmt: str) -> None:
        ids = sorted(_selected_data(self.sessions))
        if not ids:
            self.result.info(t("admin.rep.select_session"))
            return
        exporter = self.c.ctx.exporter
        self.result.info(t("admin.rep.working"))
        self.c.bg.submit(
            lambda: exporter.export_sessions(ids, fmt=fmt),  # type: ignore[arg-type]
            on_success=self._done,
            on_error=self.result.fail,
            name="export",
        )

    def _export_range(self) -> None:
        start_day = cast(date, self.date_from.date().toPython())
        end_day = cast(date, self.date_to.date().toPython())
        start = datetime.combine(start_day, time.min).astimezone()
        end = datetime.combine(end_day + timedelta(days=1), time.min).astimezone()
        fmt = self.range_format.currentData()
        exporter = self.c.ctx.exporter
        self.result.info(t("admin.rep.working"))
        self.c.bg.submit(
            lambda: exporter.export_range(start.astimezone(UTC), end.astimezone(UTC), fmt=fmt),
            on_success=self._done,
            on_error=self.result.fail,
            name="export_range",
        )

    def _export_device(self) -> None:
        text = self.device_search.text().strip()
        matches = self.c.ctx.repos.devices.search(text) if text else []
        if not matches:
            self.result.info(t("admin.rep.no_device", text=text))
            return
        exporter = self.c.ctx.exporter
        row_id = matches[0].id
        self.c.bg.submit(
            lambda: [exporter.export_device(row_id)],
            on_success=self._done,
            on_error=self.result.fail,
            name="export_device",
        )

    def _open_folder(self) -> None:
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(self.c.ctx.exporter.reports_dir)))

    def _resend(self) -> None:
        ids = _selected_data(self.outbox)
        operator = self.c.operator
        if not ids or operator is None:
            self.result.info(t("admin.out.select_item"))
            return
        outbox = self.c.ctx.outbox
        item_id = ids[0]

        def done(sent: object) -> None:
            if sent:
                self.result.ok(t("admin.out.sent"))
            else:
                self.result.info(t("admin.out.not_sent"))
            self.refresh()

        self.c.bg.submit(
            lambda: outbox.resend(operator, item_id),
            on_success=done,
            on_error=self.result.fail,
            name="resend",
        )

    def _send_now(self) -> None:
        def done(report: Any) -> None:
            if report.skipped:
                self.result.info(t("admin.out.disabled"))
            else:
                self.result.info(t("admin.out.result", sent=report.sent, failed=report.failed))
            self.refresh()

        self.c.bg.submit(
            self.c.ctx.station.send_pending,
            on_success=done,
            on_error=self.result.fail,
            name="send_pending",
        )

    def retranslate(self, *_args: object) -> None:
        _set_headers(self.sessions, self.SESSION_COLUMNS)
        _set_headers(self.outbox, self.OUTBOX_COLUMNS)
        self.sessions.setAccessibleName(t("admin.rep.sessions_title"))
        self.outbox.setAccessibleName(t("admin.out.title"))
        self.device_search.setPlaceholderText(t("admin.rep.device_search"))
        self.device_search.setAccessibleName(t("admin.rep.device_search"))
        self.date_from.setAccessibleName(t("admin.rep.from"))
        self.date_to.setAccessibleName(t("admin.rep.to"))
        current = self.range_format.currentData() or "xlsx"
        self.range_format.clear()
        for fmt in ("xlsx", "csv", "both"):
            self.range_format.addItem(t(f"admin.rep.format_{fmt}"), fmt)
        self.range_format.setCurrentIndex(max(0, self.range_format.findData(current)))
        self.range_format.setAccessibleName(t("admin.rep.format"))


# =========================================================================== counters


class CountersTab(QWidget):
    def __init__(self, controller: StationController) -> None:
        super().__init__()
        self.c = controller
        layout = QVBoxLayout(self)
        layout.addWidget(TrLabel("admin.cnt.title", role="h2"))
        self.values = QLabel()
        self.values.setFont(font(SIZES.font_h2, bold=True))
        self.values.setWordWrap(True)
        layout.addWidget(self.values)
        layout.addWidget(TrLabel("admin.cnt.help", role="muted"))
        self.confirm = InlineConfirm()
        self.confirm.setVisible(False)
        self.confirm.answered.connect(self._answered)
        layout.addWidget(self.confirm)
        self.reset = BigButton("action.reset_counters", variant="danger")
        self.reset.clicked.connect(self._ask)
        layout.addWidget(self.reset, 0, Qt.AlignmentFlag.AlignLeft)
        self.result = ResultLine()
        layout.addWidget(self.result)
        layout.addStretch(1)
        controller.counters_changed.connect(self.refresh)
        language_notifier().changed.connect(self.refresh)

    def refresh(self, *_args: object) -> None:
        counters = self.c.counters
        if counters is None:
            self.values.setText(t("admin.cnt.no_session"))
            self.reset.setEnabled(False)
            return
        self.reset.setEnabled(True)
        since = _local(counters.since) if counters.since else t("admin.cnt.since_start")
        self.values.setText(
            t(
                "admin.cnt.values",
                ok=counters.upload_success,
                fail=counters.upload_failure,
                adjusted=counters.failures_adjusted,
                done=counters.completed,
                rejected=counters.rejected,
                since=since,
            )
        )

    def _ask(self) -> None:
        self.confirm.show_confirm(
            t("confirm.reset_counters"), "action.reset_counters", "action.cancel", True
        )

    def _answered(self, yes: bool) -> None:
        self.confirm.setVisible(False)
        operator = self.c.operator
        if not yes or operator is None:
            return
        try:
            self.c.ctx.records.reset_counters(operator)
        except ParkomateError as exc:
            self.result.fail(exc)
            return
        self.result.ok(t("admin.cnt.reset_done"))
        self.c.refresh_counters()


# =========================================================================== error log


class ErrorLogTab(QWidget):
    COLUMNS = ("admin.log.time", "admin.log.level", "admin.log.code", "admin.log.message")

    def __init__(self, controller: StationController) -> None:
        super().__init__()
        self.c = controller
        self._entries: list[dict[str, Any]] = []
        layout = QVBoxLayout(self)
        row = QHBoxLayout()
        self.filter = QComboBox()
        self.filter.currentIndexChanged.connect(lambda _i: self.refresh())
        self.refresh_button = BigButton("action.refresh")
        self.refresh_button.clicked.connect(self.refresh)
        row.addWidget(self.filter, 1)
        row.addWidget(self.refresh_button)
        layout.addLayout(row)
        self.table = _table(self.COLUMNS)
        self.table.itemSelectionChanged.connect(self._show_details)
        layout.addWidget(self.table, 2)
        self.details = QPlainTextEdit()
        self.details.setReadOnly(True)
        layout.addWidget(self.details, 1)
        language_notifier().changed.connect(self.retranslate)
        self.retranslate()

    def refresh(self) -> None:
        code = self.filter.currentData()
        self._entries = read_error_log(self.c.ctx.paths.logs_dir, limit=200, error_code=code)
        rows = [
            [
                str(e.get("time", "")),
                str(e.get("level", "")),
                str(e.get("error_code") or ""),
                str(e.get("message", "")),
            ]
            for e in self._entries
        ]
        _fill(self.table, rows, list(range(len(rows))))
        self.details.setPlainText("" if rows else t("admin.log.empty"))

    def _show_details(self) -> None:
        selected = _selected_data(self.table)
        if selected:
            entry = self._entries[int(selected[0])]
            self.details.setPlainText(json.dumps(entry, ensure_ascii=False, indent=2))

    def retranslate(self, *_args: object) -> None:
        _set_headers(self.table, self.COLUMNS)
        self.table.setAccessibleName(t("admin.tab.errors"))
        self.details.setAccessibleName(t("admin.log.details"))
        current = self.filter.currentData()
        self.filter.blockSignals(True)
        self.filter.clear()
        self.filter.addItem(t("admin.log.all_codes"), None)
        for code in ErrorCode:
            self.filter.addItem(code.value, code.value)
        self.filter.setCurrentIndex(max(0, self.filter.findData(current)))
        self.filter.setAccessibleName(t("admin.log.filter"))
        self.filter.blockSignals(False)


# =========================================================================== shell


class AdminView(QWidget):
    TABS = (
        "admin.tab.settings",
        "admin.tab.operators",
        "admin.tab.reports",
        "admin.tab.counters",
        "admin.tab.errors",
    )

    def __init__(self, controller: StationController) -> None:
        super().__init__()
        self.c = controller
        self.setObjectName("Page")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(SIZES.space_l, SIZES.space_m, SIZES.space_l, SIZES.space_m)
        header = QHBoxLayout()
        header.addWidget(TrLabel("admin.title", role="h1"), 1)
        self.back = BigButton("action.back_to_production", variant="primary", hint_key="key.esc")
        self.back.clicked.connect(controller.close_admin)
        header.addWidget(self.back)
        layout.addLayout(header)
        frame = QFrame()
        frame.setProperty("card", True)
        frame_layout = QVBoxLayout(frame)
        self.tabs = QTabWidget()
        self.settings_tab = SettingsTab(controller)
        self.operators_tab = OperatorsTab(controller)
        self.reports_tab = ReportsTab(controller)
        self.counters_tab = CountersTab(controller)
        self.errors_tab = ErrorLogTab(controller)
        for tab in (
            self.settings_tab,
            self.operators_tab,
            self.reports_tab,
            self.counters_tab,
            self.errors_tab,
        ):
            self.tabs.addTab(tab, "")
        frame_layout.addWidget(self.tabs)
        layout.addWidget(frame, 1)
        language_notifier().changed.connect(self.retranslate)
        self.retranslate()

    def refresh(self) -> None:
        self.settings_tab.load()
        self.operators_tab.refresh()
        self.reports_tab.refresh()
        self.counters_tab.refresh()
        self.errors_tab.refresh()

    def retranslate(self, *_args: object) -> None:
        for index, key in enumerate(self.TABS):
            self.tabs.setTabText(index, t(key))
