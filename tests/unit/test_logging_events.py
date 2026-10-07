from __future__ import annotations

import json
import logging
from collections.abc import Iterator
from pathlib import Path

import pytest

from parkomate.config.settings import LoggingSettings
from parkomate.core.errors import ErrorCode, HardwareError
from parkomate.core.events import CountersChanged, Event, EventBus, SessionEnded
from parkomate.logging_setup import (
    ERROR_LOG,
    read_error_log,
    redact_text,
    redact_value,
    setup_logging,
)


@pytest.fixture
def logs(tmp_path: Path) -> Iterator[Path]:
    setup_logging(tmp_path, LoggingSettings(level="DEBUG"), console=False)
    yield tmp_path
    root = logging.getLogger()
    for handler in list(root.handlers):
        if getattr(handler, "_parkomate_handler", False):
            root.removeHandler(handler)
            handler.close()


def _flush() -> None:
    for handler in logging.getLogger().handlers:
        handler.flush()


def test_error_log_is_json_lines_with_code(logs: Path) -> None:
    log = logging.getLogger("parkomate.test")
    log.info("just info")
    try:
        raise HardwareError(
            "port vanished", code=ErrorCode.HW_COM_DISCONNECTED, context={"port": "COM4"}
        )
    except HardwareError:
        log.exception("flash failed")
    log.error("mail down", extra={"error_code": "MAIL_FAILED", "context": {"attempt": 2}})
    _flush()
    lines = (logs / ERROR_LOG).read_text(encoding="utf-8").splitlines()
    assert len(lines) == 2
    first = json.loads(lines[0])
    assert set(first) == {
        "time",
        "level",
        "module",
        "error_code",
        "message",
        "context",
        "traceback",
    }
    assert first["error_code"] == "HW_COM_DISCONNECTED"
    assert first["context"] == {"port": "COM4"}
    assert "port vanished" in first["traceback"]
    assert json.loads(lines[1])["context"] == {"attempt": 2}
    assert "just info" in (logs / "app.log").read_text(encoding="utf-8")


def test_secrets_and_bytes_never_logged(logs: Path) -> None:
    log = logging.getLogger("parkomate.test")
    firmware = bytes(range(256)) * 4
    log.error(
        "login password=hunter2 token: abc123 payload %s",
        firmware,
        extra={"context": {"smtp_password": "hunter2", "api_key": "k", "data": b"\x00\x01"}},
    )
    _flush()
    text = (logs / ERROR_LOG).read_text(encoding="utf-8")
    app = (logs / "app.log").read_text(encoding="utf-8")
    for content in (text, app):
        assert "hunter2" not in content and "abc123" not in content
        assert "<1024 bytes>" in content
    entry = json.loads(text.splitlines()[0])
    assert entry["context"] == {"smtp_password": "***", "api_key": "***", "data": "<2 bytes>"}


def test_read_error_log_newest_first_and_filter(logs: Path) -> None:
    log = logging.getLogger("parkomate.test")
    for i in range(5):
        log.error("e%d", i, extra={"error_code": "MAIL_FAILED" if i % 2 else "DB_ERROR"})
    _flush()
    with (logs / ERROR_LOG).open("a", encoding="utf-8") as handle:
        handle.write("not json\n\n[1, 2]\n")
    entries = read_error_log(logs, limit=3)
    assert [e["message"] for e in entries] == ["e4", "e3", "e2"]
    mail = read_error_log(logs, error_code="MAIL_FAILED")
    assert [e["message"] for e in mail] == ["e3", "e1"]
    assert read_error_log(logs / "missing") == []


def test_setup_logging_is_idempotent(logs: Path) -> None:
    setup_logging(logs, LoggingSettings(), console=True)
    ours = [h for h in logging.getLogger().handlers if getattr(h, "_parkomate_handler", False)]
    assert len(ours) == 3


def test_redaction_helpers() -> None:
    assert redact_text("Password: abc") == "Password: ***"
    assert redact_value({"nested": {"token": "x"}, "list": [b"ab"]}) == {
        "nested": {"token": "***"},
        "list": ["<2 bytes>"],
    }
    assert redact_value(5) == 5


# ------------------------------------------------------------------ event bus


def test_bus_routes_by_type_and_unsubscribes() -> None:
    bus = EventBus()
    everything: list[Event] = []
    counters: list[CountersChanged] = []
    bus.subscribe(Event, everything.append)
    remove = bus.subscribe(CountersChanged, counters.append)
    bus.publish(CountersChanged(1))
    bus.publish(SessionEnded(1))
    remove()
    remove()  # twice is harmless
    bus.publish(CountersChanged(2))
    assert counters == [CountersChanged(1)]
    assert len(everything) == 3
    bus.clear()
    bus.publish(CountersChanged(3))
    assert len(everything) == 3


def test_failing_handler_does_not_break_others(caplog: pytest.LogCaptureFixture) -> None:
    bus = EventBus()
    received: list[Event] = []

    def broken(_event: Event) -> None:
        raise RuntimeError("bug")

    bus.subscribe(Event, broken)
    bus.subscribe(Event, received.append)
    with caplog.at_level(logging.ERROR):
        bus.publish(SessionEnded(1))
    assert received == [SessionEnded(1)]
    assert "event handler" in caplog.text
