from __future__ import annotations

import hashlib

import pytest

from parkomate.core.errors import (
    CameraError,
    ErrorCode,
    HardwareError,
    MeasurementError,
    SettingsError,
)
from parkomate.core.interfaces import HardwareService
from parkomate.hardware.mocks import (
    MockHardwareService,
    MockScenario,
    resolve_delay_scale,
    resolve_scenario,
    resolve_seed,
)
from parkomate.hardware.mocks.mock_service import FACTORY_DEVICE_ID


def _hw(scenario: MockScenario = MockScenario.ALL_PASS) -> MockHardwareService:
    hw = MockHardwareService(scenario, delay_scale=0, seed=7)
    port = hw.list_ports()[0]
    assert port.is_esp_candidate and port.vid_pid == "10C4:EA60"
    hw.connect(port.name)
    hw.fetch_firmware()
    return hw


def test_implements_protocol() -> None:
    assert isinstance(MockHardwareService(delay_scale=0), HardwareService)


def test_all_pass_flow() -> None:
    hw = _hw()
    mac = hw.read_mac()
    assert mac.startswith("24:6F:28:") and len(mac) == 17
    assert hw.chip_name().startswith("ESP32")
    assert hw.check_whitelist(mac).allowed
    ticks: list[int] = []
    result = hw.flash(ticks.append)
    assert result.success and ticks[0] == 0 and ticks[-1] == 100
    assert ticks == sorted(ticks)
    assert hw.ping()
    reading = hw.read_sensor()
    assert reading.unit == "cm" and 140 < reading.value < 160
    ambient = hw.measure_ambient()
    m = hw.measure(5)
    assert 23.85 <= (m.v_a or 0) <= 24.15 and 3.25 <= (m.v_c or 0) <= 3.35
    assert (m.t_reg_c or 0) - ambient < 3.0
    hw.open_camera()
    qr = hw.read_qr(1)
    assert qr == "PKM-000519" and hw.get_device_id() == qr
    assert hw.get_preview_frame() is None
    hw.close_camera()


def test_new_board_after_disconnect() -> None:
    hw = _hw()
    first = hw.read_mac()
    hw.disconnect()
    assert not hw.is_connected()
    with pytest.raises(HardwareError) as info:
        hw.read_mac()
    assert info.value.code is ErrorCode.HW_COM_DISCONNECTED
    hw.connect("COM4")
    assert hw.read_mac() != first
    hw.open_camera()
    assert hw.read_qr(1) == "PKM-000520"


def test_unknown_port() -> None:
    with pytest.raises(HardwareError) as info:
        MockHardwareService(delay_scale=0).connect("COM99")
    assert info.value.code is ErrorCode.HW_NO_PORT


def test_flash_without_firmware() -> None:
    hw = MockHardwareService(delay_scale=0)
    hw.connect("COM4")
    with pytest.raises(HardwareError) as info:
        hw.flash(lambda _p: None)
    assert info.value.code is ErrorCode.FW_NOT_LOADED
    assert not hw.ping()  # firmware not running yet


def test_upload_fails_then_succeeds() -> None:
    hw = _hw(MockScenario.UPLOAD_FAILS_THEN_SUCCEEDS)
    first = hw.flash(lambda _p: None)
    assert not first.success and first.error_code is ErrorCode.HW_FLASH_FAILED
    assert hw.flash(lambda _p: None).success


def test_upload_always_fails() -> None:
    hw = _hw(MockScenario.UPLOAD_ALWAYS_FAILS)
    assert not any(hw.flash(lambda _p: None).success for _ in range(3))


def test_com_disconnect_mid_flash_keeps_board() -> None:
    hw = _hw(MockScenario.COM_DISCONNECT_MID_FLASH)
    mac = hw.read_mac()
    ticks: list[int] = []
    with pytest.raises(HardwareError) as info:
        hw.flash(ticks.append)
    assert info.value.code is ErrorCode.HW_COM_DISCONNECTED and max(ticks) < 40
    assert not hw.is_connected()
    hw.connect("COM4")  # operator re-plugs: same board
    assert hw.read_mac() == mac
    assert hw.flash(lambda _p: None).success


@pytest.mark.parametrize(
    ("scenario", "check"),
    [
        (MockScenario.WHITELIST_DENIED, lambda hw: not hw.check_whitelist(hw.read_mac()).allowed),
        (MockScenario.V_C_OUT_OF_RANGE, lambda hw: hw.measure(1).v_c == 3.21),
        (
            MockScenario.TEMP_TOO_HIGH,
            lambda hw: (hw.measure(1).t_reg_c or 0) - hw._ambient_c > 3.0,
        ),
        (MockScenario.COMM_FAIL, lambda hw: hw.flash(lambda _p: None).success and not hw.ping()),
    ],
)
def test_failure_scenarios(scenario: MockScenario, check) -> None:  # type: ignore[no-untyped-def]
    assert check(_hw(scenario))


def test_measurement_timeout_first_attempt_only() -> None:
    hw = _hw(MockScenario.MEASUREMENT_TIMEOUT)
    with pytest.raises(MeasurementError) as info:
        hw.measure(30)
    assert info.value.code is ErrorCode.MEAS_TIMEOUT and info.value.params == {"seconds": 30}
    assert hw.measure(30).v_a is not None


def test_qr_unreadable_first_scan_only() -> None:
    hw = _hw(MockScenario.QR_UNREADABLE)
    hw.open_camera()
    assert hw.read_qr(1) is None
    assert hw.read_qr(1) == "PKM-000519"


def test_camera_errors() -> None:
    hw = _hw(MockScenario.CAMERA_MISSING)
    with pytest.raises(CameraError):
        hw.open_camera()
    with pytest.raises(CameraError):
        hw.read_qr(1)


def test_id_differs_and_write() -> None:
    hw = _hw(MockScenario.ID_DIFFERS)
    assert hw.get_device_id() == FACTORY_DEVICE_ID
    assert hw.set_device_id("PKM-000519")
    assert hw.get_device_id() == "PKM-000519"


def test_id_write_fails_read_back_differs() -> None:
    hw = _hw(MockScenario.ID_WRITE_FAILS)
    assert hw.set_device_id("PKM-000519")
    assert hw.get_device_id() == FACTORY_DEVICE_ID


def test_mixed_scenario_is_per_board() -> None:
    hw = MockHardwareService(MockScenario.MIXED, delay_scale=0, seed=3)
    scenarios = set()
    for _ in range(40):
        hw.connect("COM4")
        assert hw._board is not None
        scenarios.add(hw._board.scenario)
        hw.disconnect()
    assert MockScenario.ALL_PASS in scenarios and len(scenarios) > 2


def test_firmware_in_ram_and_zeroed_on_shutdown() -> None:
    hw = _hw()
    info = hw.firmware_info()
    buffer = hw._firmware_buffer()
    assert info is not None and buffer is not None and isinstance(buffer, bytearray)
    assert hashlib.sha256(buffer).hexdigest() == info.sha256 and info.hash_verified
    assert hw.fetch_firmware() == info  # cached, not re-downloaded
    hw.shutdown()
    assert not any(buffer)  # same bytearray object, now all zeros
    assert hw.firmware_info() is None


def test_set_scenario() -> None:
    hw = MockHardwareService(delay_scale=0)
    hw.set_scenario(MockScenario.COMM_FAIL)
    assert hw.scenario is MockScenario.COMM_FAIL


def test_scenario_resolution(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("PARKOMATE_MOCK_SCENARIO", raising=False)
    assert resolve_scenario("all_pass") is MockScenario.ALL_PASS
    monkeypatch.setenv("PARKOMATE_MOCK_SCENARIO", "Upload-Fails-Then-Succeeds")
    assert resolve_scenario("all_pass") is MockScenario.UPLOAD_FAILS_THEN_SUCCEEDS
    monkeypatch.setenv("PARKOMATE_MOCK_SCENARIO", "nonsense")
    with pytest.raises(SettingsError) as info:
        resolve_scenario("all_pass")
    assert "PARKOMATE_MOCK_SCENARIO" in info.value.problems[0][0]


def test_delay_and_seed_resolution(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("PARKOMATE_MOCK_DELAY", raising=False)
    assert resolve_delay_scale(0.5) == 0.5
    monkeypatch.setenv("PARKOMATE_MOCK_DELAY", "2")
    assert resolve_delay_scale(0.5) == 2.0
    monkeypatch.setenv("PARKOMATE_MOCK_DELAY", "fast")
    with pytest.raises(SettingsError):
        resolve_delay_scale(1.0)
    monkeypatch.setenv("PARKOMATE_MOCK_SEED", "42")
    assert resolve_seed() == 42
    monkeypatch.setenv("PARKOMATE_MOCK_SEED", "x")
    assert resolve_seed() is None


def test_delays_are_real_when_scaled(monkeypatch: pytest.MonkeyPatch) -> None:
    slept: list[float] = []
    monkeypatch.setattr("parkomate.hardware.mocks.mock_service.time.sleep", slept.append)
    hw = MockHardwareService(delay_scale=2.0, seed=1)
    hw.list_ports()
    assert slept and all(s > 0 for s in slept)
