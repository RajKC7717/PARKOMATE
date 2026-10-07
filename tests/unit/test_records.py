from __future__ import annotations

import pytest

from parkomate.core.clock import FakeClock
from parkomate.core.enums import (
    AmbientReason,
    CheckCode,
    DeviceStatus,
    IdEntryMethod,
    SessionEndReason,
    Stage,
)
from parkomate.core.errors import InputError, RecordStateError
from parkomate.core.events import (
    AmbientMeasured,
    CountersChanged,
    DeviceAbandoned,
    Event,
    EventBus,
    SessionEnded,
    SessionStarted,
)
from parkomate.core.models import FirmwareInfo, Operator
from parkomate.data.records import ProductionRecords, normalise_mac

MAC = "24:6F:28:AA:BB:01"


def test_normalise_mac() -> None:
    assert normalise_mac("24-6f-28-aa-bb-cc") == "24:6F:28:AA:BB:CC"
    assert normalise_mac("246F28AABBCC") == "24:6F:28:AA:BB:CC"
    for bad in ("", "24:6F:28:AA:BB", "ZZ:6F:28:AA:BB:CC", "24:6F:28:AA:BB:CC:DD"):
        with pytest.raises(InputError):
            normalise_mac(bad)


def test_no_device_without_session(records: ProductionRecords) -> None:
    with pytest.raises(RecordStateError):
        records.start_device(MAC)
    with pytest.raises(RecordStateError):
        records.require_operator()
    assert records.active_device() is None
    assert records.session is None


def test_session_lifecycle_publishes_and_audits(
    records: ProductionRecords, operator: Operator, bus: EventBus
) -> None:
    events: list[Event] = []
    bus.subscribe(Event, events.append)
    session = records.start_session(operator, language="mr")
    assert session.language == "mr" and session.station_id == "ST-TEST"
    with pytest.raises(RecordStateError):
        records.start_session(operator, language="en")
    row = records.start_device(MAC)
    closed = records.end_session(SessionEndReason.LOGOUT)
    assert closed.end_reason is SessionEndReason.LOGOUT and closed.ended_at is not None
    assert records.get_device(row).status is DeviceStatus.ABANDONED
    assert records.session is None
    kinds = [type(e) for e in events]
    assert kinds == [SessionStarted, DeviceAbandoned, SessionEnded]
    actions = [e.action for e in records.repos.audit.list_entries()]
    assert "session.start" in actions and "session.end" in actions


def test_inactive_operator_cannot_start(records: ProductionRecords, operator: Operator) -> None:
    with pytest.raises(RecordStateError):
        records.start_session(operator.model_copy(update={"is_active": False}), language="en")


def test_one_device_at_a_time(open_session: ProductionRecords) -> None:
    row = open_session.start_device(MAC)
    with pytest.raises(RecordStateError):
        open_session.start_device("24:6F:28:AA:BB:02")
    open_session.complete_device(row)
    second = open_session.start_device("24:6F:28:AA:BB:02")
    assert open_session.active_device() is not None
    assert open_session.active_device().id == second  # type: ignore[union-attr]


def test_record_check_validates_stage_and_limits(open_session: ProductionRecords) -> None:
    row = open_session.start_device(MAC)
    with pytest.raises(RecordStateError):
        open_session.record_check(row, Stage.PROGRAMMING, CheckCode.B3_V_C, value=3.3)
    with pytest.raises(InputError):
        open_session.record_check(
            row, Stage.TESTING, CheckCode.B3_V_C, value=3.3, limits=(3.35, 3.25)
        )
    with pytest.raises(InputError):
        open_session.record_check(row, Stage.TESTING, CheckCode.B1_COMM, value=True)  # type: ignore[arg-type]
    result = open_session.record_check(
        row, Stage.TESTING, CheckCode.B3_V_C, value=3.3, limits=(3.25, 3.35), passed=True
    )
    assert (result.value_num, result.unit, result.limit_low, result.limit_high) == (
        3.3,
        "V",
        3.25,
        3.35,
    )
    text = open_session.record_check(
        row, Stage.LABELING, CheckCode.C_QR_READ, value="PKM-1", value_text="camera"
    )
    assert text.value_text == "PKM-1 | camera"
    assert len(open_session.checks_for_device(row)) == 2


def test_cannot_complete_rejected_device(open_session: ProductionRecords) -> None:
    row = open_session.start_device(MAC)
    device = open_session.reject_device(
        row,
        Stage.TESTING,
        CheckCode.B3_V_C,
        "reject.reason.out_of_range",
        {"check_key": "check.B3_V_C", "value": "3.21", "unit": "V", "low": "3.25", "high": "3.35"},
    )
    assert device.status is DeviceStatus.REJECTED
    assert device.reject_reason == "Point C voltage 3.21 V - allowed 3.25-3.35 V"
    assert device.reject_reason_key == "reject.reason.out_of_range"
    with pytest.raises(RecordStateError):
        open_session.complete_device(row)
    with pytest.raises(RecordStateError):
        open_session.reject_device(row, Stage.TESTING, CheckCode.B3_V_C, "reject.reason.manual")
    with pytest.raises(RecordStateError):
        open_session.record_check(row, Stage.TESTING, CheckCode.B1_COMM, passed=True)
    with pytest.raises(RecordStateError):
        open_session.set_device_id(row, "PKM-1", IdEntryMethod.CAMERA)


def test_reject_only_at_production_stage(open_session: ProductionRecords) -> None:
    row = open_session.start_device(MAC)
    with pytest.raises(RecordStateError):
        open_session.reject_device(row, Stage.COMPLETE, CheckCode.D1, "reject.reason.manual")


def test_device_identity_and_firmware(open_session: ProductionRecords) -> None:
    row = open_session.start_device(MAC)
    with pytest.raises(InputError):
        open_session.set_device_id(row, "   ", IdEntryMethod.CAMERA)
    open_session.set_device_id(row, " PKM-000519 ", IdEntryMethod.MANUAL)
    open_session.set_device_firmware(row, "2.3.1")
    device = open_session.get_device(row)
    assert device.device_id == "PKM-000519"
    assert device.id_entry_method is IdEntryMethod.MANUAL
    assert device.firmware_version == "2.3.1"


def test_device_from_other_session_rejected(
    open_session: ProductionRecords, operator: Operator
) -> None:
    row = open_session.start_device(MAC)
    open_session.end_session(SessionEndReason.CLOSE)
    open_session.start_session(operator, language="en")
    with pytest.raises(RecordStateError, match="another session"):
        open_session.complete_device(row)


def test_abandon_device(open_session: ProductionRecords, bus: EventBus) -> None:
    seen: list[DeviceAbandoned] = []
    bus.subscribe(DeviceAbandoned, seen.append)
    row = open_session.start_device(MAC)
    assert open_session.abandon_device(row).status is DeviceStatus.ABANDONED
    assert seen == [DeviceAbandoned(row)]


def test_ambient(open_session: ProductionRecords, clock: FakeClock, bus: EventBus) -> None:
    seen: list[AmbientMeasured] = []
    bus.subscribe(AmbientMeasured, seen.append)
    open_session.record_ambient(26.9, AmbientReason.SESSION_START)
    clock.advance(minutes=10)
    open_session.record_ambient(27.5, AmbientReason.REMEASURE)
    latest = open_session.latest_ambient()
    assert latest is not None and latest.value_c == 27.5
    assert open_session.require_session().ambient_c_initial == 26.9
    assert [e.value_c for e in seen] == [26.9, 27.5]
    with pytest.raises(InputError):
        open_session.record_ambient(300.0, AmbientReason.REMEASURE)


def test_session_firmware_and_language(open_session: ProductionRecords) -> None:
    open_session.set_session_firmware(
        FirmwareInfo(name="fw.bin", version="2.3.1", sha256="ab" * 32, size=10)
    )
    session = open_session.require_session()
    assert (session.firmware_name, session.firmware_version) == ("fw.bin", "2.3.1")
    open_session.set_session_language("mr")
    assert open_session.require_operator().language == "mr"


def test_counters_published(open_session: ProductionRecords, bus: EventBus) -> None:
    seen: list[CountersChanged] = []
    bus.subscribe(CountersChanged, seen.append)
    row = open_session.start_device(MAC)
    open_session.complete_device(row)
    assert len(seen) == 1


def test_list_session_devices(open_session: ProductionRecords) -> None:
    row = open_session.start_device(MAC)
    assert [d.id for d in open_session.list_session_devices()] == [row]
