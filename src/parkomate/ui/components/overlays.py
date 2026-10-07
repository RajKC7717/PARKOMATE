"""ErrorBanner, RejectTakeover and SuccessToast."""

from __future__ import annotations

from PySide6.QtCore import QEvent, QObject, Qt, QTimer, Signal
from PySide6.QtGui import QKeyEvent
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QVBoxLayout, QWidget

from parkomate.core.enums import Severity
from parkomate.core.errors import ParkomateError
from parkomate.core.models import RejectInstruction
from parkomate.i18n import t, tr_message
from parkomate.ui.components.icons import Icon
from parkomate.ui.components.widgets import BigButton, set_prop
from parkomate.ui.qt_i18n import error_cause, error_steps, error_title, language_notifier
from parkomate.ui.theme.fonts import font
from parkomate.ui.theme.tokens import COLORS, SIZES


class ErrorBanner(QFrame):
    """Tells the operator what to do: title, one-line cause, numbered steps, one 'Try again'.

    Technical details are hidden behind a small 'Details for support' link.
    """

    retry_requested = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("ErrorBanner")
        self.setProperty("tone", "fail")
        self._error: ParkomateError | None = None
        self._retry_key = "action.try_again"
        self._has_retry = False
        outer = QHBoxLayout(self)
        outer.setContentsMargins(SIZES.space_l, SIZES.space_s, SIZES.space_l, SIZES.space_s)
        outer.setSpacing(SIZES.space_m)
        self._icon = Icon("warn", 40, COLORS.fail_fg)
        outer.addWidget(self._icon, 0, Qt.AlignmentFlag.AlignTop)
        text = QVBoxLayout()
        text.setSpacing(SIZES.space_xs)
        self.title = QLabel()
        self.title.setFont(font(SIZES.font_h2 + 2, bold=True))
        self.title.setWordWrap(True)
        self.cause = QLabel()
        self.cause.setWordWrap(True)
        self.steps = QLabel()
        self.steps.setWordWrap(True)
        self.steps.setTextFormat(Qt.TextFormat.PlainText)
        self.steps.setFont(font(SIZES.font_base, bold=True))
        self.details = QLabel()
        self.details.setProperty("role", "small")
        self.details.setWordWrap(True)
        self.details.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        self.details.setVisible(False)
        text.addWidget(self.title)
        text.addWidget(self.cause)
        text.addWidget(self.steps)
        text.addWidget(self.details)
        outer.addLayout(text, 1)
        buttons = QVBoxLayout()
        buttons.setSpacing(SIZES.space_s)
        self.retry_button = BigButton("action.try_again", variant="secondary")
        self.retry_button.clicked.connect(self.retry_requested.emit)
        self.details_link = BigButton("action.details_for_support", variant="link")
        self.details_link.clicked.connect(self._toggle_details)
        buttons.addWidget(self.retry_button)
        buttons.addWidget(self.details_link, 0, Qt.AlignmentFlag.AlignRight)
        buttons.addStretch(1)
        outer.addLayout(buttons)
        self.setVisible(False)
        language_notifier().changed.connect(self.retranslate)

    def show_error(self, error: ParkomateError, *, has_retry: bool, retry_key: str) -> None:
        self._error = error
        self._has_retry = has_retry
        self._retry_key = retry_key
        severe = error.severity in (Severity.ERROR, Severity.CRITICAL)
        set_prop(self, "tone", "fail" if severe else "warn")
        self._icon.set_icon("warn", COLORS.fail_fg if severe else COLORS.warn_fg)
        self.details.setVisible(False)
        self.retranslate()
        self.setVisible(True)

    def clear(self) -> None:
        self._error = None
        self.setVisible(False)

    def error(self) -> ParkomateError | None:
        return self._error

    def _toggle_details(self) -> None:
        self.details.setVisible(not self.details.isVisible())

    def retranslate(self, *_args: object) -> None:
        error = self._error
        if error is None:
            return
        self.title.setText(error_title(error))
        self.cause.setText(error_cause(error))
        steps = error_steps(error)
        self.steps.setText("\n".join(f"{i}.  {step}" for i, step in enumerate(steps, start=1)))
        self.retry_button.set_text_key(self._retry_key)
        self.retry_button.setVisible(self._has_retry)
        self.details.setText(t("error.details", code=error.code.value, message=error.message))
        self.setAccessibleName(f"{error_title(error)}. {error_cause(error)}")


class _OverlayMixin(QFrame):
    """Keeps the overlay sized to its parent."""

    def __init__(self, parent: QWidget) -> None:
        super().__init__(parent)
        parent.installEventFilter(self)

    def eventFilter(self, watched: QObject, event: QEvent) -> bool:
        if watched is self.parent() and event.type() == QEvent.Type.Resize:
            self.reposition()
        return False

    def reposition(self) -> None:
        parent = self.parentWidget()
        if parent is not None:
            self.setGeometry(parent.rect())


class RejectTakeover(_OverlayMixin):
    """Full-screen red: REJECT, which box, why, and one button."""

    confirmed = Signal()

    def __init__(self, parent: QWidget) -> None:
        super().__init__(parent)
        self.setObjectName("RejectTakeover")
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self._instruction: RejectInstruction | None = None
        layout = QVBoxLayout(self)
        layout.setContentsMargins(64, 48, 64, 48)
        layout.setSpacing(SIZES.space_l)
        layout.addStretch(1)
        top = QHBoxLayout()
        top.addStretch(1)
        top.addWidget(Icon("cross", 96, COLORS.on_status_solid))
        self.headline = QLabel()
        self.headline.setFont(font(SIZES.font_takeover, bold=True))
        top.addWidget(self.headline)
        top.addStretch(1)
        layout.addLayout(top)
        self.place = QLabel()
        self.place.setFont(font(40, bold=True))
        self.place.setWordWrap(True)
        self.place.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.place)
        box_row = QHBoxLayout()
        box_row.addStretch(1)
        self.box_caption = QLabel()
        self.box_caption.setFont(font(SIZES.font_h1, bold=True))
        self.box = QLabel()
        self.box.setFont(font(SIZES.font_box_letter, bold=True))
        self.box.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.box.setStyleSheet(
            f"border: 6px solid {COLORS.on_status_solid}; border-radius: 24px;"
            f" padding: 0 40px; color: {COLORS.on_status_solid};"
        )
        box_row.addWidget(self.box_caption, 0, Qt.AlignmentFlag.AlignVCenter)
        box_row.addSpacing(SIZES.space_l)
        box_row.addWidget(self.box)
        box_row.addStretch(1)
        layout.addLayout(box_row)
        self.reason = QLabel()
        self.reason.setFont(font(SIZES.font_h1))
        self.reason.setWordWrap(True)
        self.reason.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.reason)
        layout.addStretch(1)
        button_row = QHBoxLayout()
        button_row.addStretch(1)
        self.button = BigButton("action.device_placed", variant="takeover", hint_key="key.enter")
        self.button.clicked.connect(self.confirmed.emit)
        button_row.addWidget(self.button)
        button_row.addStretch(1)
        layout.addLayout(button_row)
        self.setVisible(False)
        language_notifier().changed.connect(self.retranslate)

    def show_instruction(self, instruction: RejectInstruction) -> None:
        self._instruction = instruction
        self.retranslate()
        self.reposition()
        self.setVisible(True)
        self.raise_()
        self.button.setFocus()

    def instruction(self) -> RejectInstruction | None:
        return self._instruction

    def hide_takeover(self) -> None:
        self._instruction = None
        self.setVisible(False)

    def keyPressEvent(self, event: QKeyEvent) -> None:
        if event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            self.confirmed.emit()
            return
        if event.key() == Qt.Key.Key_Escape:
            return  # Esc never dismisses a reject
        super().keyPressEvent(event)

    def retranslate(self, *_args: object) -> None:
        instruction = self._instruction
        if instruction is None:
            return
        stage_name = t(instruction.stage.label_key)
        self.headline.setText(t("reject.headline"))
        self.place.setText(
            t(instruction.message_key, stage=stage_name.upper(), box=instruction.box_letter)
        )
        self.box_caption.setText(t("reject.box_caption"))
        self.box.setText(instruction.box_letter)
        self.reason.setText(tr_message(None, instruction.reason_key, instruction.reason_params))
        self.setAccessibleName(f"{self.headline.text()}. {self.place.text()}. {self.reason.text()}")


class SuccessToast(QFrame):
    """Green full-width confirmation that hides itself."""

    def __init__(self, parent: QWidget) -> None:
        super().__init__(parent)
        self.setObjectName("SuccessToast")
        layout = QHBoxLayout(self)
        layout.setContentsMargins(SIZES.space_l, SIZES.space_m, SIZES.space_l, SIZES.space_m)
        layout.setSpacing(SIZES.space_m)
        layout.addStretch(1)
        layout.addWidget(Icon("check", 44, COLORS.on_status_solid))
        self.label = QLabel()
        layout.addWidget(self.label)
        layout.addStretch(1)
        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.timeout.connect(self.hide)
        self._device = ""
        self.setVisible(False)
        language_notifier().changed.connect(self.retranslate)

    def show_message(self, device: str, seconds: float) -> None:
        self._device = device
        self.retranslate()
        parent = self.parentWidget()
        if parent is not None:
            width = parent.width() - 2 * SIZES.space_l
            self.setGeometry(SIZES.space_l, SIZES.space_m, max(400, width), 84)
        self.setVisible(True)
        self.raise_()
        self._timer.start(int(seconds * 1000))

    def retranslate(self, *_args: object) -> None:
        self.label.setText(t("toast.device_complete", device=self._device))
        self.setAccessibleName(self.label.text())
