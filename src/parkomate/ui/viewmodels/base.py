"""Shared view-model types.

A view model owns screen state and commands; its view only renders that state. The shell's
bottom bar renders every stage the same way: status message on the left, secondary actions,
and exactly one primary action at the bottom-right.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

from PySide6.QtCore import QObject, Signal

from parkomate.core.enums import Stage
from parkomate.core.errors import ParkomateError

if TYPE_CHECKING:
    from parkomate.ui.viewmodels.station import StationController


@dataclass(frozen=True, slots=True)
class Action:
    """A button in the bottom bar."""

    key: str
    handler: Callable[[], None] | None = None
    params: dict[str, Any] = field(default_factory=dict)
    enabled: bool = True
    reason_key: str | None = None
    """Why the action is disabled (shown next to the button)."""
    reason_params: dict[str, Any] = field(default_factory=dict)
    hint_key: str | None = None
    """Keyboard shortcut hint (i18n key, e.g. ``key.enter``)."""
    variant: str = "primary"
    name: str = ""
    """Stable id for tests and accessibility."""

    def trigger(self) -> None:
        if self.enabled and self.handler is not None:
            self.handler()


@dataclass(frozen=True, slots=True)
class ErrorState:
    error: ParkomateError
    retry: Callable[[], None] | None = None
    retry_key: str = "action.try_again"


@dataclass(frozen=True, slots=True)
class ConfirmState:
    """Inline confirmation (never an OS dialog) shown in the bottom bar."""

    message_key: str
    on_yes: Callable[[], None]
    yes_key: str = "action.confirm"
    no_key: str = "action.cancel"
    params: dict[str, Any] = field(default_factory=dict)
    danger: bool = True
    on_no: Callable[[], None] | None = None


@dataclass(frozen=True, slots=True)
class StatusLine:
    key: str
    params: dict[str, Any] = field(default_factory=dict)
    tone: str = "info"  # info | pass | fail | warn | pending


class StageViewModel(QObject):
    """Base for the four stage screens."""

    changed = Signal()
    stage: Stage = Stage.PROGRAMMING

    def __init__(self, controller: StationController) -> None:
        super().__init__(controller)
        self.c = controller

    # -- lifecycle ----------------------------------------------------------------------
    def reset(self) -> None:
        """Forget everything about the previous device."""

    def enter(self) -> None:
        """The stage became current."""

    def leave(self) -> None:
        """The stage stops being current."""

    # -- bottom bar ---------------------------------------------------------------------
    def primary(self) -> Action:
        raise NotImplementedError

    def secondary(self) -> list[Action]:
        return []

    def status(self) -> StatusLine | None:
        return None

    # -- keys ---------------------------------------------------------------------------
    def function_key(self, number: int) -> bool:
        """F1-F12 pressed; return True when handled."""
        return False

    # -- helpers ------------------------------------------------------------------------
    def notify(self) -> None:
        self.changed.emit()
        self.c.bottom_bar_changed.emit()

    def guard(self, fn: Callable[[], Any]) -> Any:
        """Run a quick (non-hardware) call; show typed errors in the banner."""
        try:
            return fn()
        except ParkomateError as exc:
            self.c.show_error(exc)
            return None


def missing_reason(missing_count: int, total: int) -> tuple[str, dict[str, Any]]:
    """Reason key for an incomplete checklist: 'tick all N' or 'tick N more'."""
    if missing_count >= total:
        return "gate.tick_all", {"n": total}
    return "gate.tick_more", {"n": missing_count}
