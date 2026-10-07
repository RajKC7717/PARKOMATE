"""Loading, validating, saving and reloading ``settings.toml``."""

from __future__ import annotations

import logging
import os
import threading
import tomllib
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol

import tomli_w
from pydantic import ValidationError

from parkomate.config.settings import Settings
from parkomate.core.enums import Role
from parkomate.core.errors import PermissionDeniedError, SettingsError
from parkomate.core.models import Operator

log = logging.getLogger(__name__)

FILE_HEADER = (
    "# Parkomate Station settings - managed by the admin Settings screen.\n"
    "# Every key is documented in config/settings.example.toml.\n"
    "# Secrets are NOT stored here: *_ref keys name entries in the Windows Credential Manager.\n"
    "\n"
)

SettingsListener = Callable[[Settings, tuple[str, ...]], None]


class AuditSink(Protocol):
    def record(
        self, operator_id: int | None, action: str, details: Mapping[str, Any] | None = ...
    ) -> object: ...


@dataclass(frozen=True, slots=True)
class SettingsIssue:
    """One validation problem: dotted key, pydantic error type, its context, English text."""

    key: str
    type: str
    ctx: dict[str, Any]
    message: str


def validation_issues(exc: ValidationError) -> list[SettingsIssue]:
    issues: list[SettingsIssue] = []
    for error in exc.errors():
        loc = ".".join(str(part) for part in error["loc"]) or "(file)"
        message = error["msg"].removeprefix("Value error, ")
        if error["type"] == "extra_forbidden":
            message = "unknown key (misspelt, or a secret that belongs in the keyring)"
        elif "input" in error and error["type"] not in ("missing",):
            raw = error["input"]
            if not isinstance(raw, dict | list):
                message = f"{message} (got {raw!r})"
        ctx = {k: v for k, v in (error.get("ctx") or {}).items() if not isinstance(v, Exception)}
        if error["type"] == "range_order":
            loc = f"{loc}.{ctx['low_key']}"
        issues.append(SettingsIssue(loc, error["type"], ctx, message))
    return issues


def format_validation_error(exc: ValidationError) -> list[tuple[str, str]]:
    """Turn a pydantic error into ``(dotted.key, problem)`` pairs."""
    return [(issue.key, issue.message) for issue in validation_issues(exc)]


def validate_settings(data: Mapping[str, Any]) -> Settings:
    """Validate a raw mapping, raising :class:`SettingsError` naming every bad key."""
    try:
        return Settings.model_validate(dict(data))
    except ValidationError as exc:
        issues = validation_issues(exc)
        problems = [(issue.key, issue.message) for issue in issues]
        detail = "; ".join(f"{key}: {problem}" for key, problem in problems)
        error = SettingsError(f"invalid settings: {detail}", problems=problems)
        error.issues = issues
        raise error from exc


def load_settings_file(path: Path) -> Settings:
    """Read and validate ``path``. Raises :class:`SettingsError` with the exact problem."""
    try:
        raw = path.read_bytes()
    except FileNotFoundError as exc:
        raise SettingsError(
            f"settings file not found: {path}", problems=[("(file)", f"not found: {path}")]
        ) from exc
    except OSError as exc:
        raise SettingsError(
            f"cannot read settings file {path}: {exc}", problems=[("(file)", str(exc))]
        ) from exc
    try:
        data = tomllib.loads(raw.decode("utf-8-sig"))
    except (tomllib.TOMLDecodeError, UnicodeDecodeError) as exc:
        raise SettingsError(
            f"settings file {path} is not valid TOML: {exc}",
            problems=[("(syntax)", str(exc))],
        ) from exc
    return validate_settings(data)


def settings_to_toml(settings: Settings) -> str:
    return FILE_HEADER + tomli_w.dumps(settings.model_dump(mode="json"))


def flatten(data: Mapping[str, Any], prefix: str = "") -> dict[str, Any]:
    """``{"a": {"b": 1}}`` -> ``{"a.b": 1}``."""
    flat: dict[str, Any] = {}
    for key, value in data.items():
        dotted = f"{prefix}{key}"
        if isinstance(value, Mapping):
            flat.update(flatten(value, f"{dotted}."))
        else:
            flat[dotted] = value
    return flat


def diff_settings(old: Settings, new: Settings) -> dict[str, tuple[Any, Any]]:
    """Changed keys as ``{"dotted.key": (old, new)}``."""
    before = flatten(old.model_dump(mode="json"))
    after = flatten(new.model_dump(mode="json"))
    return {
        key: (before.get(key), after.get(key))
        for key in sorted(set(before) | set(after))
        if before.get(key) != after.get(key)
    }


def _atomic_write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    with tmp.open("w", encoding="utf-8", newline="\n") as handle:
        handle.write(text)
        handle.flush()
        os.fsync(handle.fileno())
    tmp.replace(path)


class SettingsManager:
    """Owns the current :class:`Settings` and the file it came from.

    * :meth:`load` - read the file (creating a default one on first run).
    * :meth:`save` - admin only; validates, writes atomically, audits ``old -> new``.
    * :meth:`reload` - re-read the file and notify listeners.
    """

    def __init__(self, path: Path, *, audit: AuditSink | None = None) -> None:
        self._path = path
        self._audit = audit
        self._lock = threading.RLock()
        self._current: Settings | None = None
        self._listeners: list[SettingsListener] = []

    @property
    def path(self) -> Path:
        return self._path

    @property
    def current(self) -> Settings:
        with self._lock:
            if self._current is None:
                raise SettingsError("settings not loaded yet; call load() first")
            return self._current

    def set_audit(self, audit: AuditSink) -> None:
        self._audit = audit

    def add_listener(self, listener: SettingsListener) -> Callable[[], None]:
        with self._lock:
            self._listeners.append(listener)

        def remove() -> None:
            with self._lock:
                if listener in self._listeners:
                    self._listeners.remove(listener)

        return remove

    def load(self, *, create_if_missing: bool = True) -> Settings:
        """Load the settings file. On first run (no file) write the defaults."""
        with self._lock:
            if not self._path.exists() and create_if_missing:
                log.warning("no settings file at %s - writing defaults", self._path)
                _atomic_write(self._path, settings_to_toml(Settings()))
            self._current = load_settings_file(self._path)
            return self._current

    def reload(self) -> Settings:
        """Re-read the file; listeners receive the new settings and the changed keys."""
        with self._lock:
            old = self._current
            new = load_settings_file(self._path)
            self._current = new
            listeners = list(self._listeners)
        changed = tuple(diff_settings(old, new)) if old is not None else ()
        self._notify(listeners, new, changed)
        return new

    def save(
        self, new: Settings | Mapping[str, Any], actor: Operator
    ) -> dict[str, tuple[Any, Any]]:
        """Validate and persist ``new``. Only admins may save. Returns the changes."""
        if actor.role is not Role.ADMIN or not actor.is_active:
            raise PermissionDeniedError(
                f"operator {actor.operator_code!r} may not change settings",
                context={"operator_id": actor.id},
            )
        validated = new if isinstance(new, Settings) else validate_settings(new)
        # Round-trip through TOML so what we keep in memory is exactly what is on disk.
        text = settings_to_toml(validated)
        validated = validate_settings(tomllib.loads(text))
        with self._lock:
            old = self.current
            changes = diff_settings(old, validated)
            if not changes:
                return {}
            _atomic_write(self._path, text)
            self._current = validated
            listeners = list(self._listeners)
        if self._audit is not None:
            self._audit.record(
                actor.id,
                "settings.update",
                {"changes": {key: [before, after] for key, (before, after) in changes.items()}},
            )
        log.info("settings saved by %s: %s", actor.operator_code, ", ".join(changes))
        self._notify(listeners, validated, tuple(changes))
        return changes

    @staticmethod
    def _notify(
        listeners: list[SettingsListener], settings: Settings, changed: tuple[str, ...]
    ) -> None:
        for listener in listeners:
            try:
                listener(settings, changed)
            except Exception:
                log.exception("settings listener %r failed", listener)
