from __future__ import annotations

from datetime import timedelta

import pytest

from parkomate.core.clock import FakeClock
from parkomate.core.enums import (
    AmbientReason,
    CheckCode,
    CounterEvent,
    DeviceStatus,
    IdEntryMethod,
    OutboxStatus,
    Role,
    SessionEndReason,
    Stage,
)
from parkomate.core.errors import DatabaseError, NotFoundError
from parkomate.data import Repositories


def _operator(repos: Repositories, code: str = "OP9") -> int:
    return repos.operators.create(code, "Name", "hash", Role.OPERATOR).id


def test_operator_repo(repos: Repositories, clock: FakeClock) -> None:
    op = repos.operators.create("op7", "Seven", "h1", Role.OPERATOR, language="mr")
    assert op.operator_code == "op7" and op.language == "mr" and op.is_active
    assert repos.operators.get_by_code("OP7") == op  # case-insensitive codes
    assert repos.operators.get_password_hash(op.id) == "h1"
    repos.operators.set_password_hash(op.id, "h2")
    assert repos.operators.get_password_hash(op.id) == "h2"
    until = clock.now() + timedelta(minutes=5)
    repos.operators.set_lock_state(op.id, 3, until)
    locked = repos.operators.require(op.id)
    assert locked.failed_attempts == 3 and locked.locked_until == until
    repos.operators.set_active(op.id, False)
    repos.operators.set_role(op.id, Role.ADMIN)
    repos.operators.set_full_name(op.id, "Renamed")
    repos.operators.set_language(op.id, None)
    updated = repos.operators.require(op.id)
    assert (updated.is_active, updated.role, updated.full_name, updated.language) == (
        False,
        Role.ADMIN,
        "Renamed",
        None,
    )
    assert repos.operators.count_active_admins() == 0
    assert repos.operators.list_all(include_inactive=False) == []
    assert repos.operators.list_all() == [updated]
    with pytest.raises(DatabaseError):
        repos.operators.create("OP7", "Dup", "h", Role.OPERATOR)
    with pytest.raises(NotFoundError):
        repos.operators.require(999)
    with pytest.raises(NotFoundError):
        repos.operators.get_password_hash(999)
    with pytest.raises(NotFoundError):
        repos.operators.set_active(999, True)


def test_session_repo_and_ambient(repos: Repositories, clock: FakeClock) -> None:
    op_id = _operator(repos)
    session = repos.sessions.create(op_id, "ST1", "en")
    assert session.is_open and session.language == "en"
    first = repos.sessions.add_ambient(session.id, 26.8, AmbientReason.SESSION_START)
    clock.advance(minutes=30)
    second = repos.sessions.add_ambient(session.id, 27.4, AmbientReason.REMEASURE)
    assert repos.sessions.require(session.id).ambient_c_initial == 26.8
    assert repos.sessions.ambient_readings(session.id) == [first, second]
    assert repos.sessions.latest_ambient(session.id) == second
    repos.sessions.set_firmware(session.id, "fw.bin", "1.0", "ab" * 32)
    assert repos.sessions.open_sessions()[0].firmware_version == "1.0"
    clock.advance(minutes=5)
    repos.sessions.close(session.id, SessionEndReason.LOGOUT, clock.now())
    closed = repos.sessions.require(session.id)
    assert closed.end_reason is SessionEndReason.LOGOUT and not closed.is_open
    with pytest.raises(NotFoundError):
        repos.sessions.close(session.id, SessionEndReason.LOGOUT, clock.now())
    assert repos.sessions.open_sessions() == []
    assert repos.sessions.list_sessions(operator_id=op_id) == [closed]
    assert repos.sessions.list_sessions(started_from=clock.now()) == []
    assert repos.sessions.list_sessions(started_to=clock.now()) == [closed]
    assert repos.sessions.latest_ambient(999) is None


def test_last_activity(repos: Repositories, clock: FakeClock) -> None:
    op_id = _operator(repos)
    session = repos.sessions.create(op_id, "ST1", "en")
    assert repos.sessions.last_activity(session.id) == session.started_at
    clock.advance(seconds=40)
    device = repos.devices.create(session.id, "AA:BB:CC:DD:EE:FF")
    clock.advance(seconds=20)
    check = repos.checks.add(device.id, Stage.PROGRAMMING, CheckCode.A_WHITELIST, passed=True)
    assert repos.sessions.last_activity(session.id) == check.created_at


def test_device_repo(repos: Repositories, clock: FakeClock) -> None:
    op_id = _operator(repos)
    session = repos.sessions.create(op_id, "ST1", "en")
    device = repos.devices.create(session.id, "AA:BB:CC:DD:EE:01", "2.0")
    assert device.status is DeviceStatus.IN_PROGRESS and device.firmware_version == "2.0"
    assert repos.devices.active_for_session(session.id) == device
    with pytest.raises(DatabaseError):  # one in-progress device per session (unique index)
        repos.devices.create(session.id, "AA:BB:CC:DD:EE:02")
    repos.devices.set_device_id(device.id, "PKM-000001", IdEntryMethod.CAMERA)
    repos.devices.set_firmware_version(device.id, "2.1")
    repos.devices.increment_programming_attempts(device.id)
    repos.devices.increment_programming_attempts(device.id)
    clock.advance(seconds=90)
    repos.devices.reject(
        device.id,
        stage=Stage.TESTING,
        check_code=CheckCode.B3_V_C,
        reason="Point C voltage 3.21 V",
        reason_key="reject.reason.out_of_range",
        reason_params={"value": "3.21"},
        finished_at=clock.now(),
    )
    rejected = repos.devices.require(device.id)
    assert rejected.status is DeviceStatus.REJECTED
    assert rejected.reject_stage is Stage.TESTING
    assert rejected.reject_check_code is CheckCode.B3_V_C
    assert rejected.reject_reason_params == {"value": "3.21"}
    assert rejected.programming_attempts == 2
    assert rejected.device_id == "PKM-000001" and rejected.id_entry_method is IdEntryMethod.CAMERA
    assert rejected.finished_at == clock.now()
    with pytest.raises(NotFoundError):  # finished devices are immutable through finish()/reject()
        repos.devices.finish(device.id, DeviceStatus.COMPLETE, clock.now())
    with pytest.raises(ValueError):
        repos.devices.finish(device.id, DeviceStatus.REJECTED, clock.now())
    other = repos.devices.create(session.id, "AA:BB:CC:DD:EE:02")
    assert repos.devices.abandon_in_session(session.id, clock.now()) == [other.id]
    assert repos.devices.require(other.id).status is DeviceStatus.ABANDONED
    assert [d.id for d in repos.devices.list_for_session(session.id)] == [device.id, other.id]
    assert repos.devices.list_for_sessions([]) == []
    assert repos.devices.search("PKM-0000") == [rejected]
    assert repos.devices.search("ee:02")[0].id == other.id


def test_check_repo(repos: Repositories) -> None:
    op_id = _operator(repos)
    session = repos.sessions.create(op_id, "ST1", "en")
    device = repos.devices.create(session.id, "AA:BB:CC:DD:EE:01")
    first = repos.checks.add(device.id, Stage.PROGRAMMING, CheckCode.A_UPLOAD, passed=False)
    second = repos.checks.add(
        device.id,
        Stage.TESTING,
        CheckCode.B3_V_C,
        value_num=3.3,
        unit="V",
        limit_low=3.25,
        limit_high=3.35,
        passed=True,
    )
    third = repos.checks.add(device.id, Stage.PROGRAMMING, CheckCode.A_UPLOAD, passed=True)
    assert repos.checks.list_for_device(device.id) == [first, second, third]
    latest = repos.checks.latest_by_code(device.id)
    assert latest[CheckCode.A_UPLOAD] == third
    assert latest[CheckCode.B3_V_C].limit_low == 3.25
    assert repos.checks.list_for_devices([device.id]) == [first, second, third]
    assert repos.checks.list_for_devices([]) == []
    reading = repos.checks.add(
        device.id, Stage.TESTING, CheckCode.B2_READING_1, value_num=150.0, passed=None
    )
    assert reading.passed is None


def test_counter_repo(repos: Repositories) -> None:
    op_id = _operator(repos)
    session = repos.sessions.create(op_id, "ST1", "en")
    device = repos.devices.create(session.id, "AA:BB:CC:DD:EE:01")
    repos.counters.add(session.id, CounterEvent.UPLOAD_FAILURE, op_id, device.id)
    repos.counters.add(session.id, CounterEvent.UPLOAD_SUCCESS, op_id, device.id)
    reset = repos.counters.add(session.id, CounterEvent.RESET, op_id)
    repos.counters.add(session.id, CounterEvent.FAILURE_ADJUSTED, op_id, device.id)
    assert repos.counters.last_reset(session.id) == reset
    totals = repos.counters.totals(session.id)
    assert totals[CounterEvent.UPLOAD_FAILURE] == 1 and totals[CounterEvent.RESET] == 1
    after = repos.counters.totals(session.id, after_id=reset.id)
    assert after[CounterEvent.UPLOAD_FAILURE] == 0 and after[CounterEvent.FAILURE_ADJUSTED] == 1
    assert len(repos.counters.list_for_device(device.id)) == 3
    assert len(repos.counters.list_for_session(session.id)) == 4
    with pytest.raises(DatabaseError):  # unique index: at most one adjustment per device
        repos.counters.add(session.id, CounterEvent.FAILURE_ADJUSTED, op_id, device.id)
    with pytest.raises(DatabaseError):  # non-reset events need a device
        repos.counters.add(session.id, CounterEvent.UPLOAD_SUCCESS, op_id, None)


def test_outbox_repo(repos: Repositories, clock: FakeClock) -> None:
    item = repos.outbox.add(None, "Subject", "/tmp/x.eml")
    assert item.status is OutboxStatus.PENDING and item.next_attempt_at == clock.now()
    assert repos.outbox.due(clock.now()) == [item]
    later = clock.now() + timedelta(minutes=1)
    repos.outbox.mark_attempt_failed(item.id, "boom", next_attempt_at=later, give_up=False)
    assert repos.outbox.due(clock.now()) == []
    assert repos.outbox.due(later)[0].attempts == 1
    repos.outbox.mark_attempt_failed(item.id, "boom" * 1000, next_attempt_at=None, give_up=True)
    failed = repos.outbox.require(item.id)
    assert failed.status is OutboxStatus.FAILED and len(failed.last_error or "") == 2000
    repos.outbox.reset_for_resend(item.id)
    assert repos.outbox.require(item.id).attempts == 0
    repos.outbox.mark_sent(item.id)
    sent = repos.outbox.require(item.id)
    assert sent.status is OutboxStatus.SENT and sent.sent_at == clock.now()
    assert repos.outbox.list_items(status=OutboxStatus.SENT) == [sent]
    assert repos.outbox.count_by_status()[OutboxStatus.SENT] == 1
    assert repos.outbox.sent_with_payload_before(clock.now() + timedelta(days=1)) == [sent]
    repos.outbox.set_payload_path(item.id, None)
    assert repos.outbox.sent_with_payload_before(clock.now() + timedelta(days=1)) == []
    assert repos.outbox.list_items() == [repos.outbox.require(item.id)]
    with pytest.raises(NotFoundError):
        repos.outbox.mark_sent(999)


def test_audit_repo(repos: Repositories) -> None:
    entry = repos.audit.record(None, "test.action", {"a": 1, "nested": {"b": [1, 2]}})
    assert entry.details == {"a": 1, "nested": {"b": [1, 2]}}
    repos.audit.record(None, "other")
    assert [e.action for e in repos.audit.list_entries()] == ["other", "test.action"]
    assert repos.audit.list_entries(action="test.action") == [entry]
