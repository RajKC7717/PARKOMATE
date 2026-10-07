"""Qt glue for live language switching.

``language_notifier().changed`` fires on the GUI thread whenever the UI language changes.
Widgets keep i18n *keys* (not texts) and re-render in ``retranslate()``.
"""

from __future__ import annotations

from typing import Any

from PySide6.QtCore import QObject, Signal

from parkomate.core.errors import ParkomateError
from parkomate.i18n import add_language_listener, t


class LanguageNotifier(QObject):
    changed = Signal(str)

    def __init__(self) -> None:
        super().__init__()
        self._remove = add_language_listener(self.changed.emit)


_notifier: LanguageNotifier | None = None


def language_notifier() -> LanguageNotifier:
    global _notifier
    if _notifier is None:
        _notifier = LanguageNotifier()
    return _notifier


class TextKey:
    """An i18n key plus parameters, rendered on demand."""

    __slots__ = ("key", "params")

    def __init__(self, key: str, **params: Any) -> None:
        self.key = key
        self.params = params

    def render(self) -> str:
        resolved = {
            k: (v.render() if isinstance(v, TextKey) else v) for k, v in self.params.items()
        }
        return t(self.key, **resolved)

    def __eq__(self, other: object) -> bool:
        return isinstance(other, TextKey) and (self.key, self.params) == (other.key, other.params)

    def __hash__(self) -> int:
        return hash(self.key)

    def __repr__(self) -> str:
        return f"TextKey({self.key!r}, {self.params!r})"


def error_title(error: ParkomateError) -> str:
    return t(error.title_key, **error.params)


def error_cause(error: ParkomateError) -> str:
    return t(error.cause_key, **error.params)


def error_steps(error: ParkomateError) -> list[str]:
    text = t(error.action_key, **error.params)
    return [line.strip() for line in text.splitlines() if line.strip()]
