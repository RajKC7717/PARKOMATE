"""Translation catalogue.

Catalogues are flat JSON files (``en.json``, ``mr.json``) keyed by dotted message ids, for
example ``"stage.programming"`` or ``"error.hw_com_disconnected.action"``. Texts use
``str.format`` placeholders: ``"Reading {n} of {total}"``.

* :func:`t` translates into the current UI language.
* :func:`tr` translates into an explicit language (reports, e-mail).
* Missing keys fall back to English, then to the key itself, and log one warning per key.

Every user-facing string in the application must come from here.
"""

from __future__ import annotations

import json
import logging
import string
import threading
from collections.abc import Callable, Mapping
from importlib import resources
from typing import Any

log = logging.getLogger(__name__)

FALLBACK_LANGUAGE = "en"
LANGUAGES: tuple[str, ...] = ("en", "mr")

LanguageListener = Callable[[str], None]


class _SafeParams(dict[str, Any]):
    """Leaves unknown placeholders visible instead of raising KeyError."""

    def __missing__(self, key: str) -> str:
        return "{" + key + "}"


class Translator:
    def __init__(self, language: str = FALLBACK_LANGUAGE) -> None:
        self._lock = threading.RLock()
        self._catalogues: dict[str, dict[str, str]] = {}
        self._warned: set[tuple[str, str]] = set()
        self._listeners: list[LanguageListener] = []
        for code in LANGUAGES:
            self._catalogues[code] = load_catalogue(code)
        self._language = FALLBACK_LANGUAGE
        self.set_language(language)

    @property
    def language(self) -> str:
        return self._language

    def set_language(self, language: str) -> None:
        if language not in self._catalogues:
            log.warning("unknown language %r - using %s", language, FALLBACK_LANGUAGE)
            language = FALLBACK_LANGUAGE
        with self._lock:
            changed = language != self._language
            self._language = language
            listeners = list(self._listeners)
        if changed:
            for listener in listeners:
                try:
                    listener(language)
                except Exception:
                    log.exception("language listener %r failed", listener)

    def add_listener(self, listener: LanguageListener) -> Callable[[], None]:
        with self._lock:
            self._listeners.append(listener)

        def remove() -> None:
            with self._lock:
                if listener in self._listeners:
                    self._listeners.remove(listener)

        return remove

    def has(self, key: str, language: str | None = None) -> bool:
        return key in self._catalogues.get(language or self._language, {})

    def keys(self, language: str) -> set[str]:
        return set(self._catalogues.get(language, {}))

    def translate(self, language: str | None, key: str, params: dict[str, Any]) -> str:
        lang = language or self._language
        template = self._catalogues.get(lang, {}).get(key)
        if template is None:
            self._warn_missing(lang, key)
            template = self._catalogues[FALLBACK_LANGUAGE].get(key)
            if template is None:
                if lang != FALLBACK_LANGUAGE:
                    self._warn_missing(FALLBACK_LANGUAGE, key)
                return key
        if not params:
            return template
        try:
            return string.Formatter().vformat(template, (), _SafeParams(params))
        except (ValueError, IndexError, AttributeError):
            log.warning("bad placeholders in %s:%s", lang, key)
            return template

    def _warn_missing(self, language: str, key: str) -> None:
        marker = (language, key)
        with self._lock:
            if marker in self._warned:
                return
            self._warned.add(marker)
        log.warning("missing translation %s:%s", language, key)


def load_catalogue(language: str) -> dict[str, str]:
    """Read ``<language>.json`` shipped inside this package."""
    text = resources.files("parkomate.i18n").joinpath(f"{language}.json").read_text("utf-8")
    data = json.loads(text)
    if not isinstance(data, dict):
        raise ValueError(f"{language}.json must contain a JSON object")
    return {str(k): str(v) for k, v in data.items() if not str(k).startswith("_")}


_translator: Translator | None = None
_init_lock = threading.Lock()


def translator() -> Translator:
    global _translator
    if _translator is None:
        with _init_lock:
            if _translator is None:
                _translator = Translator()
    return _translator


def t(key: str, **params: Any) -> str:
    """Translate ``key`` into the current UI language."""
    return translator().translate(None, key, params)


def tr(language: str, key: str, **params: Any) -> str:
    """Translate ``key`` into ``language`` (used for reports and e-mail)."""
    return translator().translate(language, key, params)


def resolve_params(language: str | None, params: Mapping[str, Any]) -> dict[str, Any]:
    """Translate nested message ids passed as ``<name>_key`` params.

    ``{"check_key": "check.B3_V_C", "value": 3.21}`` becomes
    ``{"check": "Point C voltage", "check_key": "check.B3_V_C", "value": 3.21}``, so stored
    reasons can be rendered later in any language.
    """
    resolved: dict[str, Any] = {}
    for name, value in params.items():
        if name.endswith("_key") and isinstance(value, str):
            resolved[name.removesuffix("_key")] = translator().translate(language, value, {})
        resolved[name] = value
    return resolved


def tr_message(language: str | None, key: str, params: Mapping[str, Any]) -> str:
    """Translate ``key`` after resolving ``*_key`` params (see :func:`resolve_params`)."""
    return translator().translate(language, key, resolve_params(language, params))


def set_language(language: str) -> None:
    translator().set_language(language)


def get_language() -> str:
    return translator().language


def add_language_listener(listener: LanguageListener) -> Callable[[], None]:
    return translator().add_listener(listener)


__all__ = [
    "FALLBACK_LANGUAGE",
    "LANGUAGES",
    "Translator",
    "add_language_listener",
    "get_language",
    "load_catalogue",
    "resolve_params",
    "set_language",
    "t",
    "tr",
    "tr_message",
    "translator",
]
