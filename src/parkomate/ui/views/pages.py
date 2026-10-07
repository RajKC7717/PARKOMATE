"""Login, starting, session-end and fatal-error pages."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QVBoxLayout,
    QWidget,
)

from parkomate import __version__
from parkomate.core.enums import PRODUCTION_STAGES
from parkomate.core.errors import ErrorCode, ParkomateError, SettingsError
from parkomate.i18n import t
from parkomate.ui.components.icons import Icon
from parkomate.ui.components.widgets import (
    BigButton,
    LanguageSwitch,
    StatusPill,
    TrLabel,
    card,
)
from parkomate.ui.qt_i18n import error_cause, error_steps, error_title, language_notifier
from parkomate.ui.theme.fonts import font
from parkomate.ui.theme.tokens import COLORS, SIZES
from parkomate.ui.viewmodels.station import LoginPhase, SendState, StationController


def _centered(widget: QWidget, width: int) -> QWidget:
    page = QWidget()
    page.setObjectName("Page")
    outer = QVBoxLayout(page)
    outer.addStretch(1)
    row = QHBoxLayout()
    row.addStretch(1)
    widget.setFixedWidth(width)
    row.addWidget(widget)
    row.addStretch(1)
    outer.addLayout(row)
    outer.addStretch(1)
    return page


class MessageBox(QFrame):
    """Inline error/info box: title + cause + steps."""

    def __init__(self, status: str = "fail") -> None:
        super().__init__()
        self.setProperty("tone", status)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(SIZES.space_m, SIZES.space_m, SIZES.space_m, SIZES.space_m)
        self.icon = Icon("warn", 36, COLORS.fail_fg if status == "fail" else COLORS.info_fg)
        layout.addWidget(self.icon, 0, Qt.AlignmentFlag.AlignTop)
        text = QVBoxLayout()
        self.title = QLabel()
        self.title.setFont(font(SIZES.font_h2, bold=True))
        self.title.setWordWrap(True)
        self.body = QLabel()
        self.body.setWordWrap(True)
        text.addWidget(self.title)
        text.addWidget(self.body)
        layout.addLayout(text, 1)
        self.setVisible(False)

    def show_error(self, error: ParkomateError) -> None:
        self.title.setText(error_title(error))
        steps = error_steps(error)
        lines = [error_cause(error), *(f"{i}.  {s}" for i, s in enumerate(steps, start=1))]
        self.body.setText("\n".join(lines))
        self.setAccessibleName(f"{self.title.text()}. {self.body.text()}")
        self.setVisible(True)

    def show_text(self, title: str, body: str) -> None:
        self.title.setText(title)
        self.body.setText(body)
        self.body.setVisible(bool(body))
        self.setAccessibleName(f"{title}. {body}")
        self.setVisible(True)


class StartingView(QWidget):
    def __init__(self) -> None:
        super().__init__()
        self.setObjectName("Page")
        layout = QVBoxLayout(self)
        layout.addStretch(1)
        brand = TrLabel("app.brand", role="h1")
        brand.setAlignment(Qt.AlignmentFlag.AlignCenter)
        text = TrLabel("starting.text", role="muted")
        text.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(brand)
        layout.addWidget(text)
        layout.addStretch(1)


class LoginView(QWidget):
    def __init__(self, controller: StationController) -> None:
        super().__init__()
        self.c = controller
        self.setObjectName("Page")
        panel, layout = card()
        header = QHBoxLayout()
        brand = TrLabel("app.brand")
        brand.setFont(font(SIZES.font_h1 + 4, bold=True))
        brand.setWordWrap(False)
        header.addWidget(brand, 1)
        self.language = LanguageSwitch()
        self.language.language_selected.connect(controller.set_language)
        header.addWidget(self.language)
        layout.addLayout(header)
        self.station = QLabel()
        self.station.setProperty("role", "muted")
        layout.addWidget(self.station)
        self.notice = MessageBox("info")
        layout.addWidget(self.notice)

        self.form = QWidget()
        form = QVBoxLayout(self.form)
        form.setContentsMargins(0, 0, 0, 0)
        form.setSpacing(SIZES.space_s)
        form.addWidget(TrLabel("login.operator_id", role="h2"))
        self.code = QLineEdit()
        self.code.setMaxLength(32)
        self.code.returnPressed.connect(self._submit)
        form.addWidget(self.code)
        form.addWidget(TrLabel("login.password", role="h2"))
        password_row = QHBoxLayout()
        self.password = QLineEdit()
        self.password.setEchoMode(QLineEdit.EchoMode.Password)
        self.password.returnPressed.connect(self._submit)
        password_row.addWidget(self.password, 1)
        self.show_password = BigButton("action.show_password")
        self.show_password.setCheckable(True)
        self.show_password.toggled.connect(self._toggle_password)
        password_row.addWidget(self.show_password)
        form.addLayout(password_row)
        self.error = MessageBox("fail")
        form.addWidget(self.error)
        self.login_button = BigButton("action.login", variant="primary", hint_key="key.enter")
        self.login_button.clicked.connect(self._submit)
        form.addWidget(self.login_button)
        layout.addWidget(self.form)

        self.ambient = QFrame()
        self.ambient.setProperty("tone", "info")
        ambient_layout = QHBoxLayout(self.ambient)
        ambient_layout.setContentsMargins(
            SIZES.space_l, SIZES.space_l, SIZES.space_l, SIZES.space_l
        )
        ambient_layout.addWidget(Icon("thermo", 48, COLORS.info_fg))
        self.ambient_text = QLabel()
        self.ambient_text.setFont(font(SIZES.font_h1, bold=True))
        self.ambient_text.setWordWrap(True)
        ambient_layout.addWidget(self.ambient_text, 1)
        layout.addWidget(self.ambient)

        self.footer = QLabel()
        self.footer.setProperty("role", "small")
        layout.addWidget(self.footer)

        QWidget.setTabOrder(self.code, self.password)
        QWidget.setTabOrder(self.password, self.show_password)
        QWidget.setTabOrder(self.show_password, self.login_button)
        page = _centered(panel, 640)
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(page)
        controller.login_changed.connect(self.update_view)
        language_notifier().changed.connect(self.update_view)
        self.update_view()

    def _toggle_password(self, shown: bool) -> None:
        self.password.setEchoMode(
            QLineEdit.EchoMode.Normal if shown else QLineEdit.EchoMode.Password
        )
        self.show_password.set_text_key("action.hide_password" if shown else "action.show_password")

    def _submit(self) -> None:
        if self.c.login_phase is LoginPhase.FORM:
            self.c.login(self.code.text(), self.password.text())

    def focus_first(self) -> None:
        (self.password if self.code.text() else self.code).setFocus()

    def update_view(self, *_args: object) -> None:
        c = self.c
        self.language.sync(c.language())
        self.station.setText(t("login.station", station=c.settings.station.station_id))
        self.code.setPlaceholderText(t("login.operator_id_hint"))
        self.code.setAccessibleName(t("login.operator_id"))
        self.password.setPlaceholderText(t("login.password_hint"))
        self.password.setAccessibleName(t("login.password"))
        startup = c.startup
        if c.startup_error is not None:
            self.notice.show_error(c.startup_error)
        elif startup is not None and startup.recovery.abandoned_device_ids:
            self.notice.show_text(
                t("notice.abandoned_title"),
                t("notice.abandoned_body", n=len(startup.recovery.abandoned_device_ids)),
            )
        elif startup is not None and startup.recovery.recovered:
            self.notice.show_text(t("notice.recovered_title"), "")
        else:
            self.notice.setVisible(False)
        phase = c.login_phase
        in_form = phase in (LoginPhase.FORM, LoginPhase.CHECKING)
        self.form.setVisible(in_form)
        self.ambient.setVisible(not in_form)
        checking = phase is LoginPhase.CHECKING
        self.code.setEnabled(not checking)
        self.password.setEnabled(not checking)
        self.login_button.setEnabled(not checking)
        self.login_button.set_text_key("login.checking" if checking else "action.login")
        error = c.login_error
        if error is None:
            self.error.setVisible(False)
        else:
            self.error.show_error(error)
            if error.code is not ErrorCode.AUTH_LOCKED:
                self.password.clear()
        if phase is LoginPhase.AMBIENT:
            self.ambient_text.setText(t("login.measuring_ambient"))
        elif phase is LoginPhase.AMBIENT_DONE and c.ambient_c is not None:
            self.ambient_text.setText(t("login.ambient_result", value=f"{c.ambient_c:.1f}"))
        mock = ""
        if c.ctx.using_mocks:
            mock = t("mock.badge", scenario=getattr(c.ctx.hardware, "scenario", ""))
        self.footer.setText(f"{t('app.version', version=__version__)}   {mock}".strip())


class SessionEndView(QWidget):
    def __init__(self, controller: StationController) -> None:
        super().__init__()
        self.c = controller
        self.setObjectName("Page")
        panel, layout = card()
        layout.addWidget(TrLabel("end.title", role="h1"))
        self.subtitle = QLabel()
        self.subtitle.setProperty("role", "muted")
        layout.addWidget(self.subtitle)
        self.grid = QGridLayout()
        self.grid.setHorizontalSpacing(SIZES.space_xl)
        self.grid.setVerticalSpacing(SIZES.space_s)
        layout.addLayout(self.grid)
        self._values: dict[str, QLabel] = {}
        rows = [
            "end.devices",
            "end.complete",
            "end.rejected",
            *[f"end.rejected_{stage.letter}" for stage in PRODUCTION_STAGES],
            "end.abandoned",
            "end.uploads_ok",
            "end.uploads_fail",
            "end.failures_adjusted",
            "end.yield",
        ]
        for index, key in enumerate(rows):
            column = (index // 6) * 2
            label = QLabel()
            label.setProperty("i18n_key", key)
            value = QLabel("-")
            value.setFont(font(SIZES.font_h2, bold=True))
            self.grid.addWidget(label, index % 6, column)
            self.grid.addWidget(value, index % 6, column + 1)
            self._values[key] = value
            self._values[f"{key}__label"] = label
        send_row = QHBoxLayout()
        self.send_pill = StatusPill()
        self.send_text = QLabel()
        self.send_text.setWordWrap(True)
        self.send_text.setFont(font(SIZES.font_h2))
        send_row.addWidget(self.send_pill)
        send_row.addWidget(self.send_text, 1)
        layout.addLayout(send_row)
        self.report_path = QLabel()
        self.report_path.setProperty("role", "small")
        self.report_path.setWordWrap(True)
        self.report_path.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        layout.addWidget(self.report_path)
        self.logout = BigButton("action.logout", variant="primary", hint_key="key.enter")
        self.logout.clicked.connect(self._logout)
        layout.addWidget(self.logout, 0, Qt.AlignmentFlag.AlignRight)
        page = _centered(panel, 980)
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(page)
        for qt_key in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            shortcut = QShortcut(QKeySequence(qt_key), self)
            shortcut.setContext(Qt.ShortcutContext.WidgetWithChildrenShortcut)
            shortcut.activated.connect(self._logout)
        controller.session_end_changed.connect(self.update_view)
        language_notifier().changed.connect(self.update_view)
        self.update_view()

    def _logout(self) -> None:
        if self.logout.isEnabled():
            self.c.finish_logout()

    def update_view(self, *_args: object) -> None:
        for key, label in self._values.items():
            if key.endswith("__label"):
                base = key.removesuffix("__label")
                if base.startswith("end.rejected_"):
                    letter = base[-1]
                    stage = next(s for s in PRODUCTION_STAGES if s.letter == letter)
                    label.setText(t("end.rejected_stage", letter=letter, stage=t(stage.label_key)))
                else:
                    label.setText(t(base))
        summary = self.c.summary
        if summary is not None:
            fpy = summary.first_pass_yield
            values = {
                "end.devices": summary.total_devices,
                "end.complete": summary.complete,
                "end.rejected": summary.rejected_total,
                "end.abandoned": summary.abandoned,
                "end.uploads_ok": summary.upload_success,
                "end.uploads_fail": summary.upload_failure,
                "end.failures_adjusted": summary.failures_adjusted,
                "end.yield": t("end.yield_value", value=f"{fpy:.1f}")
                if fpy is not None
                else t("end.yield_none"),
            }
            for stage in PRODUCTION_STAGES:
                values[f"end.rejected_{stage.letter}"] = summary.rejected_by_stage.get(stage, 0)
            for key, value in values.items():
                self._values[key].setText(str(value))
            self.subtitle.setText(
                t(
                    "end.subtitle",
                    operator=summary.operator_name,
                    session=summary.session.id,
                    station=summary.session.station_id,
                )
            )
        state = self.c.send_state
        pill, text_key = (
            {
                SendState.CLOSING: ("working", "end.closing"),
                SendState.SENDING: ("working", "end.sending"),
                SendState.SENT: ("pass", "end.sent"),
                SendState.SAVED: ("warn", "end.saved_retry"),
                SendState.DISABLED: ("info", "end.saved_local"),
                SendState.REPORT_ERROR: ("fail", "end.report_error"),
            }.get(state, ("pending", "end.closing"))
            if state
            else ("pending", "end.closing")
        )
        self.send_pill.set_state(pill)
        self.send_text.setText(t(text_key))
        result = self.c.logout_result
        paths = result.queued.report_paths if result and result.queued else []
        self.report_path.setText(
            t("end.report_files", files=", ".join(str(p) for p in paths)) if paths else ""
        )
        self.logout.setEnabled(state not in (None, SendState.CLOSING))


class FatalView(QWidget):
    """Shown instead of the station when it cannot start (invalid settings - naming the exact
    keys - or another instance already running)."""

    def __init__(self, error: ParkomateError, location: str) -> None:
        super().__init__()
        from parkomate.ui.views.admin import settings_issue_text

        self.setObjectName("Page")
        self.setWindowTitle(t("app.brand"))
        panel, layout = card()
        header = QHBoxLayout()
        header.addWidget(Icon("warn", 48, COLORS.fail_fg))
        title = QLabel(error_title(error))
        title.setFont(font(SIZES.font_h1, bold=True))
        title.setWordWrap(True)
        header.addWidget(title, 1)
        layout.addLayout(header)
        cause = QLabel(error_cause(error))
        cause.setWordWrap(True)
        layout.addWidget(cause)
        place = QLabel(t("fatal.location", path=location))
        place.setProperty("role", "muted")
        place.setWordWrap(True)
        place.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        layout.addWidget(place)
        if isinstance(error, SettingsError):
            if error.issues:
                lines = [f"•  {i.key}: {settings_issue_text(i)}" for i in error.issues]
            else:
                lines = [f"•  {key}: {problem}" for key, problem in error.problems]
            listing = QLabel("\n".join(lines))
            listing.setWordWrap(True)
            listing.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
            listing.setFont(font(SIZES.font_h2, bold=True))
            listing.setProperty("status", "fail")
            layout.addWidget(listing)
        steps = QLabel("\n".join(f"{n}.  {s}" for n, s in enumerate(error_steps(error), start=1)))
        steps.setWordWrap(True)
        steps.setFont(font(SIZES.font_h2))
        layout.addWidget(steps)
        self.close_button = BigButton("action.close_app", variant="primary")
        self.close_button.clicked.connect(self.close)
        layout.addWidget(self.close_button, 0, Qt.AlignmentFlag.AlignRight)
        outer = QVBoxLayout(self)
        outer.addWidget(_centered(panel, 900))
