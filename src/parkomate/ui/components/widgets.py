"""Reusable widgets: BigButton, StatusPill, CheckRow, StageStepper, CounterBadge,
LanguageSwitch, InlineConfirm, TrLabel.

Every widget stores i18n *keys* and re-renders itself when the language changes.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from PySide6.QtCore import QRectF, QSize, Qt, Signal
from PySide6.QtGui import QColor, QKeyEvent, QPainter, QPaintEvent, QPen
from PySide6.QtWidgets import (
    QAbstractButton,
    QButtonGroup,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from parkomate.core.enums import PRODUCTION_STAGES, Stage
from parkomate.i18n import t
from parkomate.ui.components.icons import Icon, paint_icon
from parkomate.ui.qt_i18n import language_notifier
from parkomate.ui.theme.fonts import font
from parkomate.ui.theme.tokens import COLORS, SIZES


def restyle(widget: QWidget) -> None:
    """Re-apply the stylesheet after changing a dynamic property."""
    style = widget.style()
    style.unpolish(widget)
    style.polish(widget)
    widget.update()


def set_prop(widget: QWidget, name: str, value: Any) -> None:
    if widget.property(name) != value:
        widget.setProperty(name, value)
        restyle(widget)


class TrLabel(QLabel):
    """A label showing ``t(key, **params)``; re-renders on language change."""

    def __init__(
        self, key: str = "", role: str | None = None, parent: QWidget | None = None, **params: Any
    ) -> None:
        super().__init__(parent)
        self._key = key
        self._params = params
        self.setWordWrap(True)
        if role:
            self.setProperty("role", role)
        language_notifier().changed.connect(self.retranslate)
        self.retranslate()

    def set_key(self, key: str, **params: Any) -> None:
        self._key = key
        self._params = params
        self.retranslate()

    def key(self) -> str:
        return self._key

    def retranslate(self, *_args: object) -> None:
        self.setText(t(self._key, **self._params) if self._key else "")


class BigButton(QPushButton):
    """Large button labelled with a verb; shows its keyboard shortcut; min 56 px tall."""

    def __init__(
        self,
        key: str = "",
        *,
        variant: str = "secondary",
        hint_key: str | None = None,
        parent: QWidget | None = None,
        **params: Any,
    ) -> None:
        super().__init__(parent)
        self._key = key
        self._params = params
        self._hint_key = hint_key
        self.setProperty("variant", variant)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setMinimumHeight(SIZES.button_height)
        self.setAutoDefault(False)
        language_notifier().changed.connect(self.retranslate)
        self.retranslate()

    def set_text_key(self, key: str, **params: Any) -> None:
        self._key = key
        self._params = params
        self.retranslate()

    def set_hint_key(self, hint_key: str | None) -> None:
        self._hint_key = hint_key
        self.retranslate()

    def set_variant(self, variant: str) -> None:
        set_prop(self, "variant", variant)

    def label(self) -> str:
        return t(self._key, **self._params) if self._key else ""

    def retranslate(self, *_args: object) -> None:
        label = self.label()
        text = f"{label}   [{t(self._hint_key)}]" if self._hint_key and label else label
        self.setText(text)
        self.setAccessibleName(label)


_STATE_STYLE = {
    "pass": ("check", COLORS.pass_fg, "status.word.pass"),
    "fail": ("cross", COLORS.fail_fg, "status.word.fail"),
    "warn": ("warn", COLORS.warn_fg, "status.word.warn"),
    "working": ("clock", COLORS.info_fg, "status.word.working"),
    "pending": ("clock", COLORS.text_muted, "status.word.pending"),
    "info": ("info", COLORS.info_fg, "status.word.info"),
}


class StatusPill(QFrame):
    """Icon + word + colour. Never colour alone."""

    def __init__(
        self, state: str = "pending", parent: QWidget | None = None, size: str = "normal"
    ) -> None:
        super().__init__(parent)
        self._state = state
        self._key: str | None = None
        self._params: dict[str, Any] = {}
        layout = QHBoxLayout(self)
        layout.setContentsMargins(10, 4, 14, 4)
        layout.setSpacing(8)
        icon_size = 36 if size == "large" else 24
        self._icon = Icon("clock", icon_size)
        self._label = QLabel()
        self._label.setFont(font(SIZES.font_h1 if size == "large" else SIZES.font_base, bold=True))
        layout.addWidget(self._icon)
        layout.addWidget(self._label)
        self.setSizePolicy(QSizePolicy.Policy.Maximum, QSizePolicy.Policy.Fixed)
        language_notifier().changed.connect(self.retranslate)
        self.set_state(state)

    def state(self) -> str:
        return self._state

    def set_state(self, state: str, key: str | None = None, **params: Any) -> None:
        self._state = state if state in _STATE_STYLE else "pending"
        self._key = key
        self._params = params
        status = {"working": "info"}.get(self._state, self._state)
        set_prop(self, "tone", status)
        set_prop(self._label, "status", status)
        icon, color, _ = _STATE_STYLE[self._state]
        self._icon.set_icon(icon, color)
        self.retranslate()

    def text(self) -> str:
        return self._label.text()

    def retranslate(self, *_args: object) -> None:
        word = t(self._key, **self._params) if self._key else t(_STATE_STYLE[self._state][2])
        self._label.setText(word)
        self.setAccessibleName(word)


class CheckRow(QAbstractButton):
    """A whole-row checkbox (min 68 px): big box, illustrative icon, label, F-key hint.

    Click anywhere on the row, press Space when focused, or press its F-key (handled by the
    view model) to toggle.
    """

    def __init__(
        self, key: str, icon: str, hint_key: str | None = None, parent: QWidget | None = None
    ) -> None:
        super().__init__(parent)
        self._key = key
        self._icon = icon
        self._hint_key = hint_key
        self.setCheckable(True)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setMinimumHeight(SIZES.check_row_height)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.setFont(font(SIZES.font_h2, bold=False))
        language_notifier().changed.connect(self.retranslate)
        self.retranslate()

    def sizeHint(self) -> QSize:
        return QSize(420, SIZES.check_row_height)

    def label(self) -> str:
        return t(self._key)

    def retranslate(self, *_args: object) -> None:
        self.setText(self.label())
        self.setAccessibleName(self.label())
        self.update()

    def keyPressEvent(self, event: QKeyEvent) -> None:
        if event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            event.ignore()  # Enter is the primary action, never a toggle
            return
        super().keyPressEvent(event)

    def paintEvent(self, _event: QPaintEvent) -> None:
        c = COLORS
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        rect = QRectF(self.rect()).adjusted(2, 2, -2, -2)
        checked = self.isChecked()
        enabled = self.isEnabled()
        background = QColor(c.pass_bg if checked else c.surface)
        border = QColor(c.pass_fg if checked else c.border_strong)
        width = 2.0
        if self.hasFocus():
            border = QColor(c.focus)
            width = float(SIZES.focus_width)
        if not enabled:
            background = QColor(c.disabled_bg)
            border = QColor(c.disabled_bg)
        painter.setPen(QPen(border, width))
        painter.setBrush(background)
        painter.drawRoundedRect(rect, SIZES.radius, SIZES.radius)

        box = QRectF(rect.x() + 16, rect.center().y() - 20, 40, 40)
        painter.setPen(QPen(QColor(c.pass_fg if checked else c.border_strong), 3))
        painter.setBrush(QColor(c.pass_solid if checked else c.surface))
        painter.drawRoundedRect(box, 6, 6)
        if checked:
            paint_icon(painter, "check", box.adjusted(4, 4, -4, -4), QColor(c.on_status_solid))

        icon_rect = QRectF(box.right() + 16, rect.center().y() - 18, 36, 36)
        paint_icon(painter, self._icon, icon_rect, QColor(c.text_muted))

        painter.setPen(QColor(c.text if enabled else c.disabled_fg))
        text_rect = QRectF(icon_rect.right() + 16, rect.y(), rect.width() - 260, rect.height())
        f = font(SIZES.font_h2, bold=checked)
        painter.setFont(f)
        painter.drawText(
            text_rect,
            int(Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft)
            | int(Qt.TextFlag.TextWordWrap),
            self.text(),
        )

        right = rect.right() - 16
        if checked:
            painter.setPen(QColor(c.pass_fg))
            painter.setFont(font(SIZES.font_base, bold=True))
            done = t("status.word.done")
            painter.drawText(
                QRectF(right - 150, rect.y(), 110, rect.height()),
                int(Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignRight),
                done,
            )
        if self._hint_key:
            painter.setPen(QColor(c.text_muted))
            painter.setFont(font(SIZES.font_small, bold=True))
            painter.drawText(
                QRectF(right - 36, rect.y(), 36, rect.height()),
                int(Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignRight),
                t(self._hint_key),
            )
        painter.end()


class StageStepper(QWidget):
    """Programming › Testing › Labeling › Packaging - current highlighted, done ticked."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)
        self._labels: dict[Stage, QLabel] = {}
        for index, stage in enumerate(PRODUCTION_STAGES):
            if index:
                arrow = QLabel("›")
                arrow.setProperty("role", "muted")
                arrow.setFont(font(SIZES.font_h2))
                layout.addWidget(arrow)
            label = QLabel()
            label.setFont(font(SIZES.font_base, bold=True))
            label.setContentsMargins(10, 6, 10, 6)
            label.setSizePolicy(QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Preferred)
            self._labels[stage] = label
            layout.addWidget(label)
        self._current: Stage = Stage.PROGRAMMING
        self._rejected = False
        self._active = True
        language_notifier().changed.connect(self.retranslate)
        self.retranslate()

    def set_state(self, current: Stage, *, rejected: bool = False, active: bool = True) -> None:
        self._current = current
        self._rejected = rejected
        self._active = active
        self.retranslate()

    def label_for(self, stage: Stage) -> QLabel:
        return self._labels[stage]

    def retranslate(self, *_args: object) -> None:
        order = list(PRODUCTION_STAGES)
        current = self._current
        complete = current is Stage.COMPLETE
        current_index = order.index(current) if current in order else len(order)
        names = []
        for index, stage in enumerate(order):
            label = self._labels[stage]
            name = t(stage.label_key)
            if not self._active:
                state, text = "todo", f"{index + 1}  {name}"
            elif complete or index < current_index:
                state, text = "done", f"✓  {name}"
            elif index == current_index and self._rejected:
                state, text = "rejected", f"✕  {name}"
            elif index == current_index:
                state, text = "current", f"{index + 1}  {name}"
            else:
                state, text = "todo", f"{index + 1}  {name}"
            label.setText(text)
            set_prop(label, "step", state)
            names.append(f"{name}: {t('stepper.' + state)}")
        self.setAccessibleName(", ".join(names))


class CounterBadge(QFrame):
    """Caption + big number, e.g. 'Completed  12'."""

    def __init__(
        self, caption_key: str, icon: str | None = None, parent: QWidget | None = None
    ) -> None:
        super().__init__(parent)
        self._caption_key = caption_key
        layout = QHBoxLayout(self)
        layout.setContentsMargins(8, 2, 8, 2)
        layout.setSpacing(6)
        if icon:
            layout.addWidget(Icon(icon, 22, COLORS.text_muted))
        self._caption = QLabel()
        self._caption.setProperty("role", "small")
        self._value = QLabel("0")
        self._value.setFont(font(SIZES.font_h2, bold=True))
        layout.addWidget(self._caption)
        layout.addWidget(self._value)
        language_notifier().changed.connect(self.retranslate)
        self.retranslate()

    def set_value(self, value: str) -> None:
        self._value.setText(value)
        self.retranslate()

    def value(self) -> str:
        return self._value.text()

    def retranslate(self, *_args: object) -> None:
        caption = t(self._caption_key)
        self._caption.setText(caption)
        self.setAccessibleName(f"{caption} {self._value.text()}")


class LanguageSwitch(QWidget):
    """English | मराठी (language names always shown in their own script)."""

    language_selected = Signal(str)

    def __init__(
        self, languages: Sequence[str] = ("en", "mr"), parent: QWidget | None = None
    ) -> None:
        super().__init__(parent)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        self._group = QButtonGroup(self)
        self._group.setExclusive(True)
        self._buttons: dict[str, QPushButton] = {}
        for code in languages:
            button = QPushButton()
            button.setCheckable(True)
            button.setProperty("variant", "toggle")
            button.setCursor(Qt.CursorShape.PointingHandCursor)
            button.setText(t(f"language.{code}"))
            button.clicked.connect(lambda _checked=False, c=code: self.language_selected.emit(c))
            self._group.addButton(button)
            self._buttons[code] = button
            layout.addWidget(button)
        language_notifier().changed.connect(self.sync)
        self.retranslate()

    def sync(self, language: str) -> None:
        button = self._buttons.get(language)
        if button is not None:
            button.setChecked(True)
        self.retranslate()

    def button(self, language: str) -> QPushButton:
        return self._buttons[language]

    def retranslate(self, *_args: object) -> None:
        for code, button in self._buttons.items():
            button.setText(t(f"language.{code}"))
            button.setAccessibleName(t("a11y.language_switch", language=t(f"language.{code}")))


class InlineConfirm(QFrame):
    """Inline 'Are you sure?' bar - used instead of OS dialogs."""

    answered = Signal(bool)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setProperty("tone", "warn")
        layout = QHBoxLayout(self)
        layout.setContentsMargins(SIZES.space_m, SIZES.space_s, SIZES.space_m, SIZES.space_s)
        layout.setSpacing(SIZES.space_m)
        layout.addWidget(Icon("warn", 32, COLORS.warn_fg))
        self.message = QLabel()
        self.message.setWordWrap(True)
        self.message.setFont(font(SIZES.font_h2, bold=True))
        layout.addWidget(self.message, 1)
        self.no_button = BigButton("action.cancel", variant="secondary", hint_key="key.esc")
        self.yes_button = BigButton("action.confirm", variant="danger", hint_key="key.enter")
        self.no_button.clicked.connect(lambda: self.answered.emit(False))
        self.yes_button.clicked.connect(lambda: self.answered.emit(True))
        layout.addWidget(self.no_button)
        layout.addWidget(self.yes_button)

    def show_confirm(self, message: str, yes_key: str, no_key: str, danger: bool) -> None:
        self.message.setText(message)
        self.yes_button.set_text_key(yes_key)
        self.no_button.set_text_key(no_key)
        self.yes_button.set_variant("danger" if danger else "primary")
        self.setVisible(True)


class ValueRow:
    """One row of a check table: name | measured value | allowed range | PASS/FAIL pill.

    Not a widget itself: it places its four widgets in a shared ``QGridLayout`` row so the
    columns of every row line up.
    """

    def __init__(self, grid: QGridLayout, row: int, name_key: str) -> None:
        self.name = TrLabel(name_key)
        self.name.setFont(font(SIZES.font_base))
        self.measured = QLabel("-")
        self.measured.setFont(font(SIZES.font_h2, bold=True))
        self.allowed = QLabel()
        self.allowed.setWordWrap(True)
        self.allowed.setFont(font(SIZES.font_small))
        self.pill = StatusPill()
        for column, widget in enumerate((self.name, self.measured, self.allowed, self.pill)):
            grid.addWidget(widget, row, column)

    def set_value(self, measured: str | None, allowed: str, state: str) -> None:
        self.measured.setText(measured or "-")
        self.allowed.setText(allowed)
        self.pill.set_state(state)
        self.measured.setAccessibleName(f"{self.name.text()}: {self.measured.text()}")


def card(
    parent: QWidget | None = None, *, margins: int = SIZES.space_l
) -> tuple[QFrame, QVBoxLayout]:
    """A white rounded panel and its layout."""
    frame = QFrame(parent)
    frame.setProperty("card", True)
    layout = QVBoxLayout(frame)
    layout.setContentsMargins(margins, margins, margins, margins)
    layout.setSpacing(SIZES.space_m)
    return frame, layout


def scroll_card(parent: QWidget | None = None) -> tuple[QFrame, QVBoxLayout]:
    """A card whose content scrolls instead of overlapping when the screen is too small
    (1366x768 with long Marathi texts)."""
    frame = QFrame(parent)
    frame.setProperty("card", True)
    outer = QVBoxLayout(frame)
    outer.setContentsMargins(2, 2, 2, 2)
    scroll = QScrollArea()
    scroll.setObjectName("CardScroll")
    scroll.setWidgetResizable(True)
    scroll.setFrameShape(QFrame.Shape.NoFrame)
    scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
    inner = QWidget()
    inner.setObjectName("CardInner")
    layout = QVBoxLayout(inner)
    layout.setContentsMargins(SIZES.space_m, SIZES.space_m, SIZES.space_m, SIZES.space_m)
    layout.setSpacing(SIZES.space_s)
    scroll.setWidget(inner)
    outer.addWidget(scroll)
    return frame, layout
