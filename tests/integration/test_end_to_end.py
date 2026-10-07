"""Backend end to end on the mock bench: build the real context, run devices, close the session."""

from __future__ import annotations

import hashlib
import io
from collections.abc import Iterator
from email.message import EmailMessage
from pathlib import Path

import pytest

from parkomate.app import AppContext, build_context, create_hardware
from parkomate.app_paths import AppPaths
from parkomate.cli import main as cli_main
from parkomate.config.manager import settings_to_toml, validate_settings
from parkomate.config.secrets import MemorySecretStore
from parkomate.config.settings import Settings
from parkomate.core.enums import (
    AmbientReason,
    CheckCode,
    DeviceStatus,
    IdentityStatus,
    OutboxStatus,
    SessionEndReason,
    Stage,
)
from parkomate.core.errors import SettingsError
from parkomate.data.records import ProductionRecords
from parkomate.hardware.mocks import MockHardwareService, MockScenario

PASSWORD = "secret-pass-1"


@pytest.fixture
def data_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.setenv("PARKOMATE_DATA_DIR", str(tmp_path / "data"))
    monkeypatch.delenv("PARKOMATE_SETTINGS", raising=False)
    return tmp_path / "data"


@pytest.fixture
def ctx(data_dir: Path) -> Iterator[AppContext]:
    context = build_context(
        AppPaths(data_dir),
        mock=True,
        secrets=MemorySecretStore(),
        hardware=MockHardwareService(MockScenario.ALL_PASS, delay_scale=0, seed=1),
        configure_logging=False,
    )
    context.auth.create_first_admin("ADM1", "Admin", PASSWORD)
    yield context
    context.close()


def run_device(ctx: AppContext) -> Stage:
    """Drive one board through the line exactly as the UI does (hardware -> workflow)."""
    hw, wf = ctx.hardware, ctx.workflow
    hw.connect(hw.list_ports()[0].name)
    mac = hw.read_mac()
    wf.start_device(mac)
    outcome = wf.submit_check(CheckCode.A_WHITELIST, hw.check_whitelist(mac).allowed)
    while outcome.reject is None and not wf.is_stage_complete(Stage.PROGRAMMING):
        result = hw.flash(lambda _p: None)
        outcome = wf.submit_check(CheckCode.A_UPLOAD, result.success, text="2.3.1")
        if outcome.passed and ctx.records.can_adjust_failure(outcome_row(ctx)):
            ctx.records.adjust_failure(outcome_row(ctx))
    if outcome.reject is not None:
        return finish(ctx)
    wf.submit_and_next()
    if wf.submit_check(CheckCode.B1_COMM, hw.ping()).reject is not None:
        return finish(ctx)
    for i in range(1, ctx.settings.limits.sensor_reading_count + 1):
        wf.submit_check(CheckCode.reading(i), hw.read_sensor().value)
    wf.submit_check(CheckCode.B2_SENSOR_OK, True)
    wf.submit_check(CheckCode.B2_INDICATOR_OK, True)
    outcomes = wf.evaluate_measurement(hw.measure(ctx.settings.timeouts.measurement_s))
    if any(o.reject for o in outcomes):
        return finish(ctx)
    wf.submit_and_next()
    hw.open_camera()
    qr = hw.read_qr(1) or hw.read_qr(1)
    assert qr is not None
    wf.submit_check(CheckCode.C_QR_READ, qr)
    identity = wf.reconcile_identity(qr, hw.get_device_id())
    if identity.status is IdentityStatus.WRITE_REQUIRED:
        hw.set_device_id(qr)
        identity = wf.reconcile_identity(qr, hw.get_device_id(), after_write=True)
    hw.close_camera()
    if identity.reject is not None:
        return finish(ctx)
    for code in (CheckCode.C1, CheckCode.C2, CheckCode.C3, CheckCode.C4):
        wf.submit_check(code, True)
    wf.submit_and_next()
    for code in (CheckCode.D1, CheckCode.D2, CheckCode.D3, CheckCode.D4):
        wf.submit_check(code, True)
    assert wf.submit_and_next() is Stage.COMPLETE
    return finish(ctx)


def outcome_row(ctx: AppContext) -> int:
    state = ctx.workflow.current_device()
    assert state is not None
    return state.device_row_id


def finish(ctx: AppContext) -> Stage:
    stage = ctx.workflow.current_stage()
    ctx.workflow.clear_finished()
    ctx.hardware.disconnect()
    return stage


def _login(ctx: AppContext) -> None:
    ctx.station.login("ADM1", PASSWORD)
    ctx.hardware.fetch_firmware()
    info = ctx.hardware.firmware_info()
    assert info is not None
    ctx.records.set_session_firmware(info)
    ctx.records.record_ambient(ctx.hardware.measure_ambient(), AmbientReason.SESSION_START)


@pytest.mark.parametrize(
    ("scenario", "expected"),
    [
        (MockScenario.ALL_PASS, Stage.COMPLETE),
        (MockScenario.UPLOAD_FAILS_THEN_SUCCEEDS, Stage.COMPLETE),
        (MockScenario.ID_DIFFERS, Stage.COMPLETE),
        (MockScenario.WHITELIST_DENIED, Stage.REJECTED),
        (MockScenario.UPLOAD_ALWAYS_FAILS, Stage.REJECTED),
        (MockScenario.V_C_OUT_OF_RANGE, Stage.REJECTED),
        (MockScenario.TEMP_TOO_HIGH, Stage.REJECTED),
        (MockScenario.COMM_FAIL, Stage.REJECTED),
        (MockScenario.ID_WRITE_FAILS, Stage.REJECTED),
        (MockScenario.QR_UNREADABLE, Stage.COMPLETE),
    ],
)
def test_scenarios_end_to_end(ctx: AppContext, scenario: MockScenario, expected: Stage) -> None:
    assert isinstance(ctx.hardware, MockHardwareService)
    ctx.hardware.set_scenario(scenario)
    _login(ctx)
    assert run_device(ctx) is expected


def test_session_close_reports_and_firmware_never_on_disk(ctx: AppContext, data_dir: Path) -> None:
    _login(ctx)
    for _ in range(3):
        assert run_device(ctx) is Stage.COMPLETE
    assert isinstance(ctx.hardware, MockHardwareService)
    ctx.hardware.set_scenario(MockScenario.V_C_OUT_OF_RANGE)
    assert run_device(ctx) is Stage.REJECTED
    ctx.hardware.set_scenario(MockScenario.UPLOAD_FAILS_THEN_SUCCEEDS)
    assert run_device(ctx) is Stage.COMPLETE
    counters = ctx.records.get_counters()
    assert (counters.completed, counters.rejected) == (4, 1)
    assert (counters.upload_failure, counters.failures_adjusted) == (1, 1)

    firmware = ctx.hardware._firmware_buffer()
    assert firmware is not None
    signature = bytes(firmware[1024:1088])
    assert hashlib.sha256(firmware).hexdigest() == ctx.records.require_session().firmware_sha256

    result = ctx.station.logout()
    assert result.report_error is None and result.queued is not None
    assert result.summary.complete == 4 and result.summary.rejected_by_stage[Stage.TESTING] == 1
    assert result.queued.outbox_item is None  # e-mail disabled by default
    assert result.queued.report_paths[0].exists()

    # Firmware must never reach the disk (DB, reports, logs, outbox).
    for path in data_dir.rglob("*"):
        if path.is_file():
            assert signature not in path.read_bytes(), path
    ctx.hardware.shutdown()
    assert not any(firmware)


def test_logout_with_device_on_bench_abandons(ctx: AppContext) -> None:
    _login(ctx)
    hw = ctx.hardware
    hw.connect("COM4")
    ctx.workflow.start_device(hw.read_mac())
    row = outcome_row(ctx)
    result = ctx.station.logout(SessionEndReason.CLOSE)
    assert result.summary.abandoned == 1
    assert ctx.repos.devices.require(row).status is DeviceStatus.ABANDONED


def test_email_outbox_survives_offline_and_recovery(data_dir: Path) -> None:
    paths = AppPaths(data_dir).ensure()
    settings = validate_settings(
        {
            "email": {
                "enabled": True,
                "recipients": ["qa@parkomate.example"],
                "sender": "st@parkomate.example",
                "host": "smtp.invalid",
            }
        }
    )
    paths.settings_file.write_text(settings_to_toml(settings), encoding="utf-8")
    ctx = build_context(
        paths,
        mock=True,
        secrets=MemorySecretStore({"smtp_password": "pw"}),
        configure_logging=False,
    )
    ctx.auth.create_first_admin("ADM1", "Admin", PASSWORD)
    _login(ctx)
    sent: list[EmailMessage] = []

    class Offline:
        def send(self, message: EmailMessage) -> None:
            raise OSError("network is unreachable")

    ctx.outbox._mailer = Offline()
    result = ctx.station.logout()
    assert result.queued is not None and result.queued.outbox_item is not None
    report = ctx.station.send_pending()
    assert (report.sent, report.failed) == (0, 1)
    item = ctx.repos.outbox.require(result.queued.outbox_item.id)
    assert item.status is OutboxStatus.PENDING and item.attempts == 1

    # Crash with an open session, restart, recover.
    _login(ctx)
    ctx.hardware.connect("COM4")
    ctx.workflow.start_device(ctx.hardware.read_mac())
    ctx.close()

    restarted = build_context(
        paths,
        mock=True,
        secrets=MemorySecretStore({"smtp_password": "pw"}),
        configure_logging=False,
    )
    startup = restarted.station.startup()
    assert startup.recovery.recovered and len(startup.recovery.abandoned_device_ids) == 1
    assert len(startup.queued_reports) == 1

    class Online:
        def send(self, message: EmailMessage) -> None:
            sent.append(message)

    restarted.outbox._mailer = Online()
    restarted.repos.outbox.reset_for_resend(item.id)  # skip the back-off wait
    assert restarted.station.send_pending().sent == 2
    assert len(sent) == 2
    restarted.close()


def test_real_hardware_not_available_yet() -> None:
    with pytest.raises(SettingsError):
        create_hardware(Settings(), mock=False)
    hardware, mocked = create_hardware(Settings(), mock=None)
    assert mocked and isinstance(hardware, MockHardwareService)


def test_invalid_settings_refuse_start(data_dir: Path) -> None:
    paths = AppPaths(data_dir).ensure()
    paths.settings_file.write_text("[limits]\nv_c_low = 'abc'\n", encoding="utf-8")
    with pytest.raises(SettingsError) as info:
        build_context(paths, mock=True, configure_logging=False)
    assert info.value.problems[0][0] == "limits.v_c_low"


# ------------------------------------------------------------------ CLI


def test_cli_admin_lifecycle(
    data_dir: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr("sys.stdin", io.StringIO(PASSWORD + "\n"))
    assert (
        cli_main(["admin", "create", "--code", "BOSS", "--name", "Boss", "--password-stdin"]) == 0
    )
    assert "Administrator BOSS created." in capsys.readouterr().out
    assert cli_main(["admin", "create", "--code", "B2", "--name", "B", "--password-stdin"]) == 1
    assert cli_main(["admin", "unlock", "BOSS"]) == 0
    assert cli_main(["admin", "unlock", "NOBODY"]) == 1
    monkeypatch.setattr("sys.stdin", io.StringIO("another-pass\n"))
    assert cli_main(["admin", "reset-password", "BOSS", "--password-stdin"]) == 0
    monkeypatch.setattr("sys.stdin", io.StringIO("123\n"))
    assert cli_main(["admin", "reset-password", "BOSS", "--password-stdin"]) == 1
    assert "Password too short" in capsys.readouterr().err


def test_cli_settings_outbox_report(
    data_dir: Path, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    AppPaths(data_dir).ensure()
    assert cli_main(["settings", "check"]) == 1  # no file yet
    capsys.readouterr()
    ctx = build_context(AppPaths(data_dir), mock=True, configure_logging=False)
    ctx.auth.create_first_admin("ADM1", "Admin", PASSWORD)
    _login(ctx)
    session = ctx.station.logout().session
    ctx.close()
    assert cli_main(["settings", "check"]) == 0
    assert cli_main(["outbox", "send"]) == 0
    assert "switched off" in capsys.readouterr().out
    out_dir = data_dir / "export"
    assert cli_main(["report", str(session.id), "--format", "csv", "--out", str(out_dir)]) == 0
    assert len(list(out_dir.glob("*.csv"))) == 4
    assert cli_main(["report", "999"]) == 1

    stored: dict[str, str] = {}
    monkeypatch.setattr("parkomate.cli.getpass.getpass", lambda _prompt: "pw")
    monkeypatch.setattr(
        "parkomate.config.secrets.KeyringSecretStore.set",
        lambda self, name, value: stored.__setitem__(name, value),
    )
    monkeypatch.setattr(
        "parkomate.config.secrets.KeyringSecretStore.delete",
        lambda self, name: stored.pop(name, None),
    )
    assert cli_main(["secrets", "set", "smtp_password"]) == 0
    assert stored == {"smtp_password": "pw"}
    assert cli_main(["secrets", "delete", "smtp_password"]) == 0
    assert stored == {}


def test_cli_invalid_settings_named(data_dir: Path, capsys: pytest.CaptureFixture[str]) -> None:
    paths = AppPaths(data_dir).ensure()
    paths.settings_file.write_text("[email]\npassword = 'x'\n", encoding="utf-8")
    assert cli_main(["settings", "check"]) == 1
    assert "email.password" in capsys.readouterr().err


def test_records_station_follows_settings(ctx: AppContext) -> None:
    raw = ctx.settings.model_dump(mode="json")
    raw["station"]["station_id"] = "BENCH-9"
    admin = ctx.repos.operators.get_by_code("ADM1")
    assert admin is not None
    ctx.settings_manager.save(raw, admin)
    assert ctx.records.station_id == "BENCH-9"
    assert isinstance(ctx.records, ProductionRecords)
