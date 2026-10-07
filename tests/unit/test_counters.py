"""Counters are computed from events; the "reduce failure by 1" rule is enforced."""

from __future__ import annotations

import pytest

from parkomate.core.clock import FakeClock
from parkomate.core.enums import CheckCode, CounterEvent, SessionEndReason, Stage
from parkomate.core.errors import InputError, PermissionDeniedError, RecordStateError
from parkomate.core.models import Operator
from parkomate.data.records import ProductionRecords

MAC = "24:6F:28:AA:BB:01"


def _upload(records: ProductionRecords, row: int, ok: bool) -> None:
    records.counter_event(CounterEvent.UPLOAD_SUCCESS if ok else CounterEvent.UPLOAD_FAILURE, row)


def test_counters_are_computed_from_events(open_session: ProductionRecords) -> None:
    row = open_session.start_device(MAC)
    _upload(open_session, row, False)
    _upload(open_session, row, True)
    counters = open_session.get_counters()
    assert (counters.upload_success, counters.upload_failure, counters.failures_adjusted) == (
        1,
        1,
        0,
    )
    assert open_session.get_device(row).programming_attempts == 2
    assert open_session.repos.db.scalar("SELECT COUNT(*) FROM counter_events") == 2


def test_adjust_only_after_failure_followed_by_success(open_session: ProductionRecords) -> None:
    row = open_session.start_device(MAC)
    assert not open_session.can_adjust_failure(row)  # nothing yet
    _upload(open_session, row, True)
    assert not open_session.can_adjust_failure(row)  # success without failure
    with pytest.raises(RecordStateError):
        open_session.adjust_failure(row)


def test_adjust_not_allowed_while_still_failing(open_session: ProductionRecords) -> None:
    row = open_session.start_device(MAC)
    _upload(open_session, row, False)
    assert not open_session.can_adjust_failure(row)  # failure not (yet) followed by success


def test_adjust_once_per_device(open_session: ProductionRecords) -> None:
    row = open_session.start_device(MAC)
    _upload(open_session, row, False)
    _upload(open_session, row, False)
    _upload(open_session, row, True)
    assert open_session.can_adjust_failure(row)
    open_session.adjust_failure(row)
    assert not open_session.can_adjust_failure(row)
    with pytest.raises(RecordStateError):
        open_session.adjust_failure(row)
    counters = open_session.get_counters()
    assert counters.upload_failure == 2
    assert counters.failures_adjusted == 1
    assert counters.net_upload_failure == 1
    audit = open_session.repos.audit.list_entries(action="counter.failure_adjusted")
    assert audit[0].details["device_row_id"] == row


def test_adjust_unknown_or_foreign_device(
    open_session: ProductionRecords, operator: Operator
) -> None:
    assert not open_session.can_adjust_failure(999)
    row = open_session.start_device(MAC)
    _upload(open_session, row, False)
    _upload(open_session, row, True)
    open_session.end_session(SessionEndReason.LOGOUT)
    open_session.start_session(operator, language="en")
    assert not open_session.can_adjust_failure(row)


def test_upload_events_need_in_progress_device(open_session: ProductionRecords) -> None:
    row = open_session.start_device(MAC)
    open_session.complete_device(row)
    with pytest.raises(RecordStateError):
        _upload(open_session, row, True)
    with pytest.raises(InputError):
        open_session.counter_event(CounterEvent.UPLOAD_SUCCESS)
    with pytest.raises(RecordStateError):
        open_session.counter_event(CounterEvent.RESET)


def test_reset_admin_only_and_live_counters_restart(
    open_session: ProductionRecords, operator: Operator, admin: Operator, clock: FakeClock
) -> None:
    row = open_session.start_device(MAC)
    _upload(open_session, row, False)
    _upload(open_session, row, True)
    open_session.complete_device(row)
    with pytest.raises(PermissionDeniedError):
        open_session.reset_counters(operator)
    clock.advance(seconds=5)
    open_session.reset_counters(admin)
    live = open_session.get_counters()
    assert (live.upload_success, live.upload_failure, live.completed) == (0, 0, 0)
    assert live.since is not None
    clock.advance(seconds=5)
    second = open_session.start_device("24:6F:28:AA:BB:02")
    _upload(open_session, second, True)
    open_session.reject_device(
        second, Stage.TESTING, CheckCode.B1_COMM, "reject.reason.comm_failed"
    )
    live = open_session.get_counters()
    assert (live.upload_success, live.rejected, live.completed) == (1, 1, 0)
    # The session summary still covers the whole session.
    summary = open_session.current_session_summary()
    assert (summary.upload_success, summary.upload_failure, summary.counter_resets) == (2, 1, 1)
    assert summary.complete == 1 and summary.rejected_by_stage[Stage.TESTING] == 1
    assert open_session.repos.audit.list_entries(action="counter.reset")[0].operator_id == admin.id


def test_summary_first_pass_yield(open_session: ProductionRecords) -> None:
    # device 1: complete first time; device 2: failed upload then complete; device 3: rejected
    first = open_session.start_device("24:6F:28:AA:BB:01")
    _upload(open_session, first, True)
    open_session.complete_device(first)
    second = open_session.start_device("24:6F:28:AA:BB:02")
    _upload(open_session, second, False)
    _upload(open_session, second, True)
    open_session.complete_device(second)
    third = open_session.start_device("24:6F:28:AA:BB:03")
    open_session.reject_device(
        third, Stage.PROGRAMMING, CheckCode.A_WHITELIST, "reject.reason.whitelist_denied"
    )
    fourth = open_session.start_device("24:6F:28:AA:BB:04")
    summary = open_session.current_session_summary()
    assert summary.total_devices == 4
    assert summary.in_progress == 1
    assert summary.first_pass_complete == 1
    assert summary.first_pass_yield == pytest.approx(33.3)
    open_session.abandon_device(fourth)
    assert open_session.current_session_summary().abandoned == 1


def test_first_pass_yield_none_without_finished_devices(open_session: ProductionRecords) -> None:
    assert open_session.current_session_summary().first_pass_yield is None
