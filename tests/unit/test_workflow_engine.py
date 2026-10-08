"""Workflow engine: stage order, gates, limits (incl. edge values), reject/retry/complete."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from parkomate.config.settings import LimitsSettings, ProgrammingSettings, Settings
from parkomate.core.enums import (
    AmbientReason,
    CheckCode,
    CounterEvent,
    DeviceStatus,
    IdentityStatus,
    IdEntryMethod,
    Stage,
)
from parkomate.core.errors import InputError, RecordStateError
from parkomate.core.events import (
    CheckRecorded,
    DeviceCompleted,
    DeviceRejected,
    DeviceStarted,
    Event,
    EventBus,
    StageChanged,
)
from parkomate.core.interfaces import WorkflowService
from parkomate.core.models import Measurement
from parkomate.data.records import ProductionRecords
from parkomate.workflow import WorkflowEngine, quantize, within

MAC = "24:6F:28:AA:BB:01"


def _measurement(**overrides: float | None) -> Measurement:
    values: dict[str, float | None] = {
        "v_a": 24.0,
        "v_b": 5.0,
        "v_c": 3.3,
        "t_reg_c": 28.5,
        "t_amb_c": 27.1,
    }
    values.update(overrides)
    return Measurement(received_at=datetime.now(UTC), **values)  # type: ignore[arg-type]


@pytest.fixture
def settings_box() -> dict[str, Settings]:
    return {"value": Settings()}


@pytest.fixture
def wf(open_session: ProductionRecords, settings_box: dict[str, Settings]) -> WorkflowEngine:
    open_session.record_ambient(27.0, AmbientReason.SESSION_START)
    return WorkflowEngine(open_session, lambda: settings_box["value"])


def _programming(wf: WorkflowEngine) -> None:
    wf.start_device(MAC)
    wf.submit_check(CheckCode.A_WHITELIST, True)
    wf.submit_check(CheckCode.A_UPLOAD, True, text="2.3.1")
    assert wf.submit_and_next() is Stage.TESTING


def _testing_until_measure(wf: WorkflowEngine) -> None:
    wf.submit_check(CheckCode.B1_COMM, True)
    for i in range(1, 6):
        wf.submit_check(CheckCode.reading(i), 150.0 + i)
    wf.submit_check(CheckCode.B2_SENSOR_OK, True)
    wf.submit_check(CheckCode.B2_INDICATOR_OK, True)


def _to_labeling(wf: WorkflowEngine) -> None:
    _programming(wf)
    _testing_until_measure(wf)
    assert all(o.passed for o in wf.evaluate_measurement(_measurement()))
    assert wf.submit_and_next() is Stage.LABELING


# ------------------------------------------------------------------ pure validation


@pytest.mark.parametrize(
    ("value", "expected"),
    [(3.24, False), (3.25, True), (3.30, True), (3.35, True), (3.36, False)],
)
def test_point_c_edges(value: float, expected: bool) -> None:
    assert within(value, 3.25, 3.35, 2) is expected


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        (3.2449, False),  # rounds to 3.24
        (3.245, True),  # half-up to 3.25
        (3.3549, True),  # rounds to 3.35
        (3.355, False),  # half-up to 3.36
        (23.85, True),
        (24.15, True),
        (24.151, True),  # 24.15 at 2 decimals
        (4.899, True),  # 4.90
    ],
)
def test_rounding_half_up(value: float, expected: bool) -> None:
    low, high = (3.25, 3.35) if value < 4 else ((4.90, 5.10) if value < 10 else (23.85, 24.15))
    assert within(value, low, high, 2) is expected


def test_quantize_decimal_representation() -> None:
    assert str(quantize(2.675, 2)) == "2.68"  # binary float rounding would give 2.67
    assert str(quantize(3.3, 0)) == "3"


# ------------------------------------------------------------------ flow


def test_implements_protocol(wf: WorkflowEngine) -> None:
    assert isinstance(wf, WorkflowService)


def test_happy_path_publishes_events(wf: WorkflowEngine, bus: EventBus) -> None:
    events: list[Event] = []
    bus.subscribe(Event, events.append)
    _to_labeling(wf)
    wf.submit_check(CheckCode.C_QR_READ, "PKM-000519")
    outcome = wf.reconcile_identity("PKM-000519", "PKM-000519")
    assert outcome.status is IdentityStatus.MATCH
    for code in (CheckCode.C1, CheckCode.C2, CheckCode.C3):
        wf.submit_check(code, True)
    assert not wf.can_submit() and wf.missing_checks() == [CheckCode.C4]
    wf.submit_check(CheckCode.C4, True)
    assert wf.submit_and_next() is Stage.PACKAGING
    for code in (CheckCode.D1, CheckCode.D2, CheckCode.D3, CheckCode.D4):
        wf.submit_check(code, True)
    assert wf.submit_and_next() is Stage.COMPLETE
    state = wf.current_device()
    assert state is not None and state.status is DeviceStatus.COMPLETE
    assert state.device_id == "PKM-000519" and state.display_id == "PKM-000519"
    assert wf.current_stage() is Stage.COMPLETE
    kinds = {type(e) for e in events}
    assert {DeviceStarted, StageChanged, CheckRecorded, DeviceCompleted} <= kinds
    device = wf._records.get_device(state.device_row_id)
    assert device.status is DeviceStatus.COMPLETE and device.firmware_version == "2.3.1"
    assert device.id_entry_method is IdEntryMethod.CAMERA
    codes = [c.check_code for c in wf._records.checks_for_device(device.id)]
    assert CheckCode.C4 in codes and CheckCode.D4 in codes and CheckCode.B3_T_AMB in codes
    wf.clear_finished()
    assert wf.current_device() is None and wf.current_stage() is Stage.PROGRAMMING


def test_gate_blocks_until_complete(wf: WorkflowEngine) -> None:
    wf.start_device(MAC)
    assert wf.missing_checks() == [CheckCode.A_WHITELIST, CheckCode.A_UPLOAD]
    with pytest.raises(RecordStateError) as info:
        wf.submit_and_next()
    assert info.value.context["missing"] == ["A_WHITELIST", "A_UPLOAD"]
    assert not wf.is_stage_complete(Stage.PROGRAMMING)
    assert not wf.is_stage_complete(Stage.TESTING)
    with pytest.raises(RecordStateError):  # cannot upload before whitelist
        wf.submit_check(CheckCode.A_UPLOAD, True)
    with pytest.raises(RecordStateError):  # wrong stage
        wf.submit_check(CheckCode.B1_COMM, True)
    wf.submit_check(CheckCode.A_WHITELIST, True)
    wf.submit_check(CheckCode.A_UPLOAD, True)
    assert wf.is_stage_complete(Stage.PROGRAMMING)
    with pytest.raises(RecordStateError):  # already uploaded
        wf.submit_check(CheckCode.A_UPLOAD, True)
    wf.submit_and_next()
    assert wf.is_stage_complete(Stage.PROGRAMMING)  # earlier stage
    with pytest.raises(RecordStateError):
        wf.start_device("24:6F:28:AA:BB:02")


def test_testing_order_enforced(wf: WorkflowEngine) -> None:
    _programming(wf)
    with pytest.raises(RecordStateError):
        wf.submit_check(CheckCode.reading(1), 150.0)  # before B1
    wf.submit_check(CheckCode.B1_COMM, True)
    with pytest.raises(RecordStateError):
        wf.submit_check(CheckCode.reading(2), 150.0)  # out of order
    with pytest.raises(InputError):
        wf.submit_check(CheckCode.reading(1), "x")
    with pytest.raises(RecordStateError):
        wf.submit_check(CheckCode.B2_SENSOR_OK, True)  # readings missing
    with pytest.raises(RecordStateError):
        wf.evaluate_measurement(_measurement())  # B2 not done
    with pytest.raises(RecordStateError):
        wf.submit_check(CheckCode.B3_V_A, 24.0)
    for i in range(1, 6):
        wf.submit_check(CheckCode.reading(i), 150.0)
    with pytest.raises(RecordStateError):
        wf.submit_check(CheckCode.reading(6), 150.0)  # exactly N readings
    state = wf.current_device()
    assert state is not None and len(state.readings) == 5
    with pytest.raises(InputError):
        wf.submit_check(CheckCode.B2_SENSOR_OK, "yes")


def test_configurable_reading_count(
    wf: WorkflowEngine, settings_box: dict[str, Settings]
) -> None:
    settings_box["value"] = Settings(limits=LimitsSettings(sensor_reading_count=2))
    _programming(wf)
    wf.submit_check(CheckCode.B1_COMM, True)
    wf.submit_check(CheckCode.reading(1), 1.0)
    wf.submit_check(CheckCode.reading(2), 2.0)
    wf.submit_check(CheckCode.B2_SENSOR_OK, True)
    assert CheckCode.reading(3) not in wf.required_checks(Stage.TESTING)


def test_whitelist_denied_rejects_at_programming(wf: WorkflowEngine, bus: EventBus) -> None:
    rejected: list[DeviceRejected] = []
    bus.subscribe(DeviceRejected, rejected.append)
    wf.start_device(MAC)
    outcome = wf.submit_check(CheckCode.A_WHITELIST, False)
    assert outcome.passed is False and outcome.reject is not None
    assert outcome.reject.stage is Stage.PROGRAMMING and outcome.reject.box_letter == "A"
    assert outcome.reject.reason_key == "reject.reason.whitelist_denied"
    assert rejected[0].instruction == outcome.reject
    assert wf.current_stage() is Stage.REJECTED
    with pytest.raises(RecordStateError):
        wf.submit_check(CheckCode.A_UPLOAD, True)
    device = wf._records.get_device(outcome.reject.device_row_id)
    assert device.reject_reason == f"MAC {MAC} is not authorised by the server"


def test_upload_retry_then_success_and_adjust(wf: WorkflowEngine) -> None:
    wf.start_device(MAC)
    wf.submit_check(CheckCode.A_WHITELIST, True)
    first = wf.submit_check(CheckCode.A_UPLOAD, False, text="HW_FLASH_FAILED")
    assert first.retry_allowed and first.reject is None
    assert (first.attempt, first.max_attempts) == (1, 3)
    assert wf.can_retry_programming()
    second = wf.submit_check(CheckCode.A_UPLOAD, True)
    assert second.passed and not wf.can_retry_programming()
    state = wf.current_device()
    assert state is not None and (state.upload_attempts, state.upload_failures) == (2, 1)
    records = wf._records
    assert records.can_adjust_failure(state.device_row_id)
    records.adjust_failure(state.device_row_id)
    counters = records.get_counters()
    assert (counters.upload_failure, counters.failures_adjusted, counters.net_upload_failure) == (
        1,
        1,
        0,
    )


def test_upload_max_retries_rejects(
    wf: WorkflowEngine, settings_box: dict[str, Settings]
) -> None:
    settings_box["value"] = Settings(programming=ProgrammingSettings(max_retries=2))
    wf.start_device(MAC)
    wf.submit_check(CheckCode.A_WHITELIST, True)
    assert wf.submit_check(CheckCode.A_UPLOAD, False).retry_allowed
    last = wf.submit_check(CheckCode.A_UPLOAD, False)
    assert not last.retry_allowed and last.reject is not None
    assert last.reject.reason_key == "reject.reason.upload_failed_max"
    assert last.reject.reason_params["attempts"] == 2
    events = wf._records.repos.counters.list_for_device(last.reject.device_row_id)
    assert [e.event for e in events] == [CounterEvent.UPLOAD_FAILURE] * 2


def test_operator_rejects_after_failed_upload(wf: WorkflowEngine) -> None:
    wf.start_device(MAC)
    wf.submit_check(CheckCode.A_WHITELIST, True)
    wf.submit_check(CheckCode.A_UPLOAD, False)
    instruction = wf.reject(CheckCode.A_UPLOAD)
    assert instruction.reason_key == "reject.reason.manual"
    checks = wf._records.checks_for_device(instruction.device_row_id)
    assert [c.check_code for c in checks].count(CheckCode.A_UPLOAD) == 1  # not double-recorded


def test_comm_failure_rejects(wf: WorkflowEngine) -> None:
    _programming(wf)
    outcome = wf.submit_check(CheckCode.B1_COMM, False)
    assert outcome.reject is not None and outcome.reject.box_letter == "B"


def test_operator_marks_sensor_failed(wf: WorkflowEngine) -> None:
    _programming(wf)
    wf.submit_check(CheckCode.B1_COMM, True)
    for i in range(1, 6):
        wf.submit_check(CheckCode.reading(i), 1.0)
    outcome = wf.submit_check(CheckCode.B2_SENSOR_OK, False)
    assert outcome.reject is not None
    assert outcome.reject.reason_params["check_key"] == "check.B2_SENSOR_OK"


def test_point_c_out_of_range_rejects_with_reason(wf: WorkflowEngine) -> None:
    _programming(wf)
    _testing_until_measure(wf)
    outcomes = wf.evaluate_measurement(_measurement(v_c=3.21))
    by_code = {o.check_code: o for o in outcomes}
    assert by_code[CheckCode.B3_V_A].passed and by_code[CheckCode.B3_V_B].passed
    failed = by_code[CheckCode.B3_V_C]
    assert failed.passed is False and failed.reject is not None
    assert (failed.value_num, failed.limit_low, failed.limit_high) == (3.21, 3.25, 3.35)
    device = wf._records.get_device(failed.reject.device_row_id)
    assert device.reject_check_code is CheckCode.B3_V_C
    assert device.reject_reason == "Point C voltage 3.21 V - allowed 3.25-3.35 V"
    # every value is stored, including the passing ones
    stored = {c.check_code for c in wf._records.checks_for_device(device.id)}
    assert {CheckCode.B3_V_A, CheckCode.B3_V_B, CheckCode.B3_V_C, CheckCode.B3_T_REG} <= stored


@pytest.mark.parametrize(
    ("t_reg", "passes"),
    [(30.0, True), (30.004, True), (30.01, False), (31.5, False)],
)
def test_regulator_temperature_margin(wf: WorkflowEngine, t_reg: float, passes: bool) -> None:
    _programming(wf)
    _testing_until_measure(wf)
    outcomes = wf.evaluate_measurement(_measurement(t_reg_c=t_reg))
    temp = next(o for o in outcomes if o.check_code is CheckCode.B3_T_REG)
    assert temp.passed is passes
    assert temp.limit_high == 30.0  # ambient 27.0 + 3.0
    if not passes:
        assert temp.reject is not None
        assert temp.reject.reason_key == "reject.reason.temp_too_high"


def test_ambient_remeasure_used(wf: WorkflowEngine) -> None:
    _programming(wf)
    _testing_until_measure(wf)
    wf._records.record_ambient(28.0, AmbientReason.REMEASURE)
    outcomes = wf.evaluate_measurement(_measurement(t_reg_c=30.5))
    assert all(o.passed for o in outcomes)


def test_missing_value_fails(wf: WorkflowEngine) -> None:
    _programming(wf)
    _testing_until_measure(wf)
    outcomes = wf.evaluate_measurement(_measurement(v_a=None, t_reg_c=None, t_amb_c=None))
    first = outcomes[0]
    assert first.passed is False and first.reject is not None
    assert first.reject.reason_key == "reject.reason.value_missing"


def test_missing_ambient_fails(
    open_session: ProductionRecords, settings_box: dict[str, Settings]
) -> None:
    wf = WorkflowEngine(open_session, lambda: settings_box["value"])
    _programming(wf)
    _testing_until_measure(wf)
    outcomes = wf.evaluate_measurement(_measurement())
    temp = outcomes[-1]
    assert temp.passed is False and temp.reject is not None
    assert temp.reject.reason_key == "reject.reason.ambient_missing"


def test_measurement_outside_testing(wf: WorkflowEngine) -> None:
    wf.start_device(MAC)
    with pytest.raises(RecordStateError):
        wf.evaluate_measurement(_measurement())


def test_identity_write_and_confirm(wf: WorkflowEngine) -> None:
    _to_labeling(wf)
    with pytest.raises(RecordStateError):
        wf.reconcile_identity("PKM-000519", "PKM-000000")  # QR not read yet
    wf.submit_check(CheckCode.C_QR_READ, "PKM-000519")
    first = wf.reconcile_identity("PKM-000519", "PKM-000000")
    assert first.status is IdentityStatus.WRITE_REQUIRED
    assert CheckCode.C_ID_SYNC in wf.missing_checks()
    confirmed = wf.reconcile_identity(
        "PKM-000519", "PKM-000519", after_write=True, method=IdEntryMethod.MANUAL
    )
    assert confirmed.status is IdentityStatus.CONFIRMED
    state = wf.current_device()
    assert state is not None and state.identity is IdentityStatus.CONFIRMED
    device = wf._records.get_device(state.device_row_id)
    assert device.id_entry_method is IdEntryMethod.MANUAL


def test_identity_write_fails_rejects(wf: WorkflowEngine) -> None:
    _to_labeling(wf)
    wf.submit_check(CheckCode.C_QR_READ, "PKM-000519")
    with pytest.raises(RecordStateError):
        wf.reconcile_identity("PKM-000519", "PKM-000519", after_write=True)  # no write requested
    wf.reconcile_identity("PKM-000519", "")
    failed = wf.reconcile_identity("PKM-000519", None, after_write=True)
    assert failed.status is IdentityStatus.FAILED and failed.reject is not None
    assert failed.reject.box_letter == "C"
    assert failed.reject.reason_params == {
        "check_key": "check.C_ID_SYNC",
        "qr": "PKM-000519",
        "device": "-",
    }


def test_bad_qr_format_is_retriable(wf: WorkflowEngine) -> None:
    _to_labeling(wf)
    outcome = wf.submit_check(CheckCode.C_QR_READ, "bad id!")
    assert outcome.passed is False and outcome.retry_allowed and outcome.reject is None
    assert wf.current_stage() is Stage.LABELING
    with pytest.raises(InputError):
        wf.submit_check(CheckCode.C_QR_READ, "")
    with pytest.raises(RecordStateError):
        wf.submit_check(CheckCode.C_ID_SYNC, True)


def test_checklist_untick_and_manual_reject(wf: WorkflowEngine) -> None:
    _to_labeling(wf)
    wf.submit_check(CheckCode.C2, True)
    wf.submit_check(CheckCode.C2, False)
    assert CheckCode.C2 in wf.missing_checks()
    with pytest.raises(RecordStateError):
        wf.reject(CheckCode.D1)  # not this stage
    instruction = wf.reject(CheckCode.C2, "reject.reason.item_missing")
    assert instruction.stage is Stage.LABELING
    device = wf._records.get_device(instruction.device_row_id)
    assert device.reject_reason == "Screws fitted: not done or part missing"
    assert not wf.is_stage_complete(Stage.LABELING)
    assert not wf.can_submit()
    assert wf.missing_checks() == []


def test_abandon_and_clear(wf: WorkflowEngine) -> None:
    wf.abandon_device()  # nothing on the bench: harmless
    wf.start_device(MAC)
    with pytest.raises(RecordStateError):
        wf.clear_finished()
    row = wf.current_device().device_row_id  # type: ignore[union-attr]
    wf.abandon_device()
    assert wf.current_device() is None
    assert wf._records.get_device(row).status is DeviceStatus.ABANDONED
    with pytest.raises(RecordStateError):
        wf.submit_check(CheckCode.A_WHITELIST, True)
    assert wf.required_checks(Stage.COMPLETE) == []
    assert not wf.is_stage_complete(Stage.PROGRAMMING)
