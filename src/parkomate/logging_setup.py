"""Application logging.

* ``logs/app.log`` - human-readable, everything at the configured level.
* ``logs/errors.jsonl`` - one JSON object per line for ERROR and above:
  ``time, level, module, error_code, message, context, traceback``.

Both files rotate by size. A filter scrubs secrets (password / token / key values) and
replaces any ``bytes`` argument with its length, so passwords and firmware bytes never
reach a log file.

Attach an error code to a log call with ``extra={"error_code": ..., "context": {...}}`` or
log a :class:`~parkomate.core.errors.ParkomateError` with ``log.exception``.
"""

from __future__ import annotations

import json
import logging
import re
import sys
from collections import deque
from datetime import datetime
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Any

from parkomate.config.settings import LoggingSettings
from parkomate.core.errors import ParkomateError

APP_LOG = "app.log"
ERROR_LOG = "errors.jsonl"
_HANDLER_MARK = "_parkomate_handler"

_SECRET_KEY = re.compile(r"pass(word)?|secret|token|api[_-]?key|authorization|credential", re.I)
_SECRET_IN_TEXT = re.compile(
    r"(?i)\b(password|passwd|pwd|secret|token|api[_-]?key|authorization)\b(\s*[=:]\s*)(\S+)"
)
REDACTED = "***"


def redact_text(text: str) -> str:
    return _SECRET_IN_TEXT.sub(lambda m: f"{m.group(1)}{m.group(2)}{REDACTED}", text)


def redact_value(value: Any, key: str = "") -> Any:
    if key and _SECRET_KEY.search(key):
        return REDACTED
    if isinstance(value, bytes | bytearray | memoryview):
        return f"<{len(value)} bytes>"
    if isinstance(value, dict):
        return {str(k): redact_value(v, str(k)) for k, v in value.items()}
    if isinstance(value, list | tuple):
        return [redact_value(v) for v in value]
    if isinstance(value, str):
        return redact_text(value)
    return value


class RedactingFilter(logging.Filter):
    """Scrubs secrets and binary payloads before any handler formats the record."""

    def filter(self, record: logging.LogRecord) -> bool:
        if isinstance(record.msg, str):
            record.msg = redact_text(record.msg)
        if record.args:
            if isinstance(record.args, dict):
                record.args = {k: redact_value(v, str(k)) for k, v in record.args.items()}
            else:
                record.args = tuple(redact_value(arg) for arg in record.args)
        context = getattr(record, "context", None)
        if isinstance(context, dict):
            record.context = redact_value(context)
        return True


class JsonLinesFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        error_code = getattr(record, "error_code", None)
        context = getattr(record, "context", None)
        exc = record.exc_info[1] if record.exc_info else None
        if isinstance(exc, ParkomateError):
            error_code = error_code or exc.code.value
            merged = dict(exc.context)
            if isinstance(context, dict):
                merged.update(context)
            context = redact_value(merged)
        payload = {
            "time": datetime.fromtimestamp(record.created)
            .astimezone()
            .isoformat(timespec="milliseconds"),
            "level": record.levelname,
            "module": record.name,
            "error_code": error_code,
            "message": redact_text(record.getMessage()),
            "context": context if isinstance(context, dict) else {},
            "traceback": redact_text(self.formatException(record.exc_info))
            if record.exc_info
            else None,
        }
        return json.dumps(payload, ensure_ascii=False, default=str)


def setup_logging(
    logs_dir: Path, settings: LoggingSettings | None = None, *, console: bool = True
) -> None:
    """(Re)configure the root logger. Safe to call more than once."""
    settings = settings or LoggingSettings()
    logs_dir.mkdir(parents=True, exist_ok=True)
    root = logging.getLogger()
    for handler in list(root.handlers):
        if getattr(handler, _HANDLER_MARK, False):
            root.removeHandler(handler)
            handler.close()
    root.setLevel(settings.level)
    redactor = RedactingFilter()

    app_handler = RotatingFileHandler(
        logs_dir / APP_LOG,
        maxBytes=settings.max_bytes,
        backupCount=settings.backup_count,
        encoding="utf-8",
    )
    app_handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)-8s %(name)s: %(message)s"))
    error_handler = RotatingFileHandler(
        logs_dir / ERROR_LOG,
        maxBytes=settings.max_bytes,
        backupCount=settings.backup_count,
        encoding="utf-8",
    )
    error_handler.setLevel(logging.ERROR)
    error_handler.setFormatter(JsonLinesFormatter())
    handlers: list[logging.Handler] = [app_handler, error_handler]
    if console:
        stream = logging.StreamHandler(sys.stderr)
        stream.setLevel(logging.WARNING)
        stream.setFormatter(logging.Formatter("%(levelname)s %(name)s: %(message)s"))
        handlers.append(stream)
    for handler in handlers:
        handler.addFilter(redactor)
        setattr(handler, _HANDLER_MARK, True)
        root.addHandler(handler)
    logging.captureWarnings(True)


def read_error_log(
    logs_dir: Path, *, limit: int = 200, error_code: str | None = None
) -> list[dict[str, Any]]:
    """The newest ``limit`` entries of ``errors.jsonl`` (newest first), optionally filtered by
    error code. Unreadable lines are skipped."""
    path = logs_dir / ERROR_LOG
    if not path.exists():
        return []
    entries: deque[dict[str, Any]] = deque(maxlen=limit)
    with path.open(encoding="utf-8", errors="replace") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            try:
                entry = json.loads(line)
            except json.JSONDecodeError:
                continue
            if not isinstance(entry, dict):
                continue
            if error_code and entry.get("error_code") != error_code:
                continue
            entries.append(entry)
    return list(reversed(entries))
