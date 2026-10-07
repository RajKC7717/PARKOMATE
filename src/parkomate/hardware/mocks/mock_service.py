"""A realistic, scenario-driven stand-in for the bench hardware.

Implements :class:`parkomate.core.interfaces.HardwareService` with small random delays and
progress ticks so the UI behaves as it will on the real bench. ``delay_scale=0`` makes it
instant (tests).

The simulated "board" is created on the first :meth:`connect` after a :meth:`disconnect`,
which mirrors the operator unplugging one board and plugging in the next.

The firmware image is generated in RAM (``bytearray``) and zeroed by :meth:`shutdown`; it
is never written anywhere.
"""

from __future__ import annotations

import hashlib
import logging
import random
import threading
import time
from dataclasses import dataclass
from datetime import UTC, datetime

from parkomate.core.errors import (
    CameraError,
    ErrorCode,
    HardwareError,
    MeasurementError,
)
from parkomate.core.interfaces import ProgressCallback
from parkomate.core.models import (
    FirmwareInfo,
    FlashResult,
    Measurement,
    PortInfo,
    PreviewFrame,
    SensorReading,
    WhitelistResult,
)
from parkomate.hardware.mocks.scenarios import MockScenario

log = logging.getLogger(__name__)

FIRMWARE_NAME = "parkomate-controller.bin"
FIRMWARE_VERSION = "2.3.1"
FIRMWARE_SIZE = 256 * 1024
FACTORY_DEVICE_ID = "PKM-000000"

_MIXED_FAILURES: tuple[MockScenario, ...] = (
    MockScenario.UPLOAD_FAILS_THEN_SUCCEEDS,
    MockScenario.WHITELIST_DENIED,
    MockScenario.V_C_OUT_OF_RANGE,
    MockScenario.TEMP_TOO_HIGH,
    MockScenario.MEASUREMENT_TIMEOUT,
    MockScenario.QR_UNREADABLE,
    MockScenario.ID_DIFFERS,
)

_PORTS: tuple[PortInfo, ...] = (
    PortInfo(
        name="COM4",
        description="Silicon Labs CP210x USB to UART Bridge",
        vid=0x10C4,
        pid=0xEA60,
        serial_number="0001",
        is_esp_candidate=True,
    ),
    PortInfo(name="COM1", description="Communications Port"),
)


@dataclass(slots=True)
class _Board:
    mac: str
    qr_label: str
    stored_id: str
    scenario: MockScenario
    flash_attempts: int = 0
    firmware_running: bool = False
    measure_attempts: int = 0
    qr_attempts: int = 0


class MockHardwareService:
    """Simulated bench. See :class:`MockScenario` for the behaviours."""

    def __init__(
        self,
        scenario: MockScenario = MockScenario.ALL_PASS,
        *,
        delay_scale: float = 1.0,
        seed: int | None = None,
        first_label: int = 519,
    ) -> None:
        self._scenario = scenario
        self._scale = max(0.0, delay_scale)
        self._rng = random.Random(seed)
        self._lock = threading.RLock()
        self._port: str | None = None
        self._board: _Board | None = None
        self._firmware: bytearray | None = None
        self._firmware_info: FirmwareInfo | None = None
        self._camera_open = False
        self._ambient_c = 27.0
        self._next_label = first_label
        self._closed = False

    # ------------------------------------------------------------------ helpers
    @property
    def scenario(self) -> MockScenario:
        return self._scenario

    def set_scenario(self, scenario: MockScenario) -> None:
        """Change behaviour for boards connected from now on (demo / tests)."""
        with self._lock:
            self._scenario = scenario

    def _sleep(self, seconds: float) -> None:
        if self._scale > 0 and seconds > 0:
            time.sleep(seconds * self._scale)

    def _jitter(self, low: float, high: float) -> None:
        self._sleep(self._rng.uniform(low, high))

    def _require_board(self) -> _Board:
        with self._lock:
            if self._port is None or self._board is None:
                raise HardwareError("board not connected", code=ErrorCode.HW_COM_DISCONNECTED)
            return self._board

    def _new_board(self) -> _Board:
        scenario = self._scenario
        if scenario is MockScenario.MIXED:
            scenario = (
                MockScenario.ALL_PASS
                if self._rng.random() < 0.6
                else self._rng.choice(_MIXED_FAILURES)
            )
        mac = "24:6F:28:" + ":".join(f"{self._rng.randrange(256):02X}" for _ in range(3))
        label = f"PKM-{self._next_label:06d}"
        self._next_label += 1
        differs = scenario in (MockScenario.ID_DIFFERS, MockScenario.ID_WRITE_FAILS)
        stored = FACTORY_DEVICE_ID if differs else label
        log.debug("mock board %s (%s) scenario=%s", mac, label, scenario.value)
        return _Board(mac=mac, qr_label=label, stored_id=stored, scenario=scenario)

    # ------------------------------------------------------------------ serial port
    def list_ports(self) -> list[PortInfo]:
        self._jitter(0.05, 0.15)
        return sorted(_PORTS, key=lambda p: (not p.is_esp_candidate, p.name))

    def connect(self, port: str) -> None:
        self._jitter(0.1, 0.3)
        with self._lock:
            if port not in {p.name for p in _PORTS}:
                raise HardwareError(
                    f"port {port} not found", code=ErrorCode.HW_NO_PORT, params={"port": port}
                )
            self._port = port
            if self._board is None:
                self._board = self._new_board()

    def disconnect(self) -> None:
        with self._lock:
            self._port = None
            self._board = None

    def is_connected(self) -> bool:
        with self._lock:
            return self._port is not None and self._board is not None

    # ------------------------------------------------------------------ identity
    def read_mac(self) -> str:
        board = self._require_board()
        self._jitter(0.1, 0.3)
        return board.mac

    def chip_name(self) -> str:
        self._require_board()
        return "ESP32-D0WD-V3 (revision v3.1)"

    # ------------------------------------------------------------------ server
    def check_whitelist(self, mac: str) -> WhitelistResult:
        board = self._require_board()
        self._jitter(0.2, 0.5)
        allowed = board.scenario is not MockScenario.WHITELIST_DENIED
        return WhitelistResult(
            mac_address=mac,
            allowed=allowed,
            reason=None if allowed else "not registered",
            checked_at=datetime.now(UTC),
        )

    def fetch_firmware(self) -> FirmwareInfo:
        self._jitter(0.4, 0.8)
        with self._lock:
            if self._firmware is None or self._firmware_info is None:
                image = bytearray(self._rng.randbytes(FIRMWARE_SIZE))
                self._firmware = image
                self._firmware_info = FirmwareInfo(
                    name=FIRMWARE_NAME,
                    version=FIRMWARE_VERSION,
                    sha256=hashlib.sha256(image).hexdigest(),
                    size=len(image),
                    hash_verified=True,
                )
            return self._firmware_info

    def firmware_info(self) -> FirmwareInfo | None:
        with self._lock:
            return self._firmware_info

    # ------------------------------------------------------------------ programming
    def flash(self, progress_cb: ProgressCallback) -> FlashResult:
        board = self._require_board()
        with self._lock:
            if self._firmware is None or self._firmware_info is None:
                raise HardwareError("firmware not loaded", code=ErrorCode.FW_NOT_LOADED)
            size = self._firmware_info.size
            board.flash_attempts += 1
            attempt = board.flash_attempts
        started = time.monotonic()
        fail_at: int | None = None
        disconnect_at: int | None = None
        if board.scenario is MockScenario.UPLOAD_FAILS_THEN_SUCCEEDS and attempt == 1:
            fail_at = 60
        elif board.scenario is MockScenario.UPLOAD_ALWAYS_FAILS:
            fail_at = 72
        elif board.scenario is MockScenario.COM_DISCONNECT_MID_FLASH and attempt == 1:
            disconnect_at = 40
        for percent in range(0, 101, 4):
            if disconnect_at is not None and percent >= disconnect_at:
                with self._lock:
                    self._port = None  # cable pulled; the board itself stays the same
                raise HardwareError(
                    "serial port disappeared during flashing",
                    code=ErrorCode.HW_COM_DISCONNECTED,
                    context={"progress": percent},
                )
            if fail_at is not None and percent >= fail_at:
                return FlashResult(
                    success=False,
                    error_code=ErrorCode.HW_FLASH_FAILED,
                    message="verify failed: flash read-back does not match",
                    duration_s=round(time.monotonic() - started, 2),
                    bytes_written=size * percent // 100,
                )
            progress_cb(percent)
            self._sleep(0.06)
        board.firmware_running = True
        return FlashResult(
            success=True,
            duration_s=round(time.monotonic() - started, 2),
            bytes_written=size,
        )

    # ------------------------------------------------------------------ device link
    def ping(self) -> bool:
        board = self._require_board()
        self._jitter(0.1, 0.3)
        return board.firmware_running and board.scenario is not MockScenario.COMM_FAIL

    def read_sensor(self) -> SensorReading:
        self._require_board()
        self._jitter(0.15, 0.4)
        value = round(self._rng.uniform(142.0, 158.0), 1)
        return SensorReading(
            value=value, unit="cm", raw=f"SENSOR {value}", read_at=datetime.now(UTC)
        )

    def get_device_id(self) -> str:
        board = self._require_board()
        self._jitter(0.1, 0.25)
        return board.stored_id

    def set_device_id(self, device_id: str) -> bool:
        board = self._require_board()
        self._jitter(0.2, 0.4)
        if board.scenario is not MockScenario.ID_WRITE_FAILS:
            board.stored_id = device_id
        return True

    # ------------------------------------------------------------------ measurement
    def measure(self, timeout_s: float) -> Measurement:
        board = self._require_board()
        board.measure_attempts += 1
        if board.scenario is MockScenario.MEASUREMENT_TIMEOUT and board.measure_attempts == 1:
            self._sleep(min(timeout_s, 1.5))
            raise MeasurementError(
                f"no measurement within {timeout_s:g} s",
                code=ErrorCode.MEAS_TIMEOUT,
                params={"seconds": round(timeout_s)},
            )
        self._jitter(0.6, 1.2)
        ambient = self._ambient_c
        v_c = (
            3.21
            if board.scenario is MockScenario.V_C_OUT_OF_RANGE
            else self._rng.uniform(3.28, 3.32)
        )
        t_reg = ambient + (
            4.6 if board.scenario is MockScenario.TEMP_TOO_HIGH else self._rng.uniform(0.6, 2.0)
        )
        return Measurement(
            station="MOCK",
            seq=board.measure_attempts,
            v_a=round(self._rng.uniform(23.95, 24.05), 3),
            v_b=round(self._rng.uniform(4.96, 5.04), 3),
            v_c=round(v_c, 3),
            t_reg_c=round(t_reg, 2),
            t_amb_c=round(ambient + self._rng.uniform(-0.2, 0.2), 2),
            received_at=datetime.now(UTC),
        )

    def measure_ambient(self) -> float:
        self._jitter(0.5, 1.0)
        self._ambient_c = round(self._rng.uniform(26.5, 27.5), 1)
        return self._ambient_c

    # ------------------------------------------------------------------ camera
    def open_camera(self) -> None:
        self._jitter(0.1, 0.3)
        if self._scenario is MockScenario.CAMERA_MISSING:
            raise CameraError("no camera at index 0", code=ErrorCode.CAM_NOT_FOUND)
        with self._lock:
            self._camera_open = True

    def read_qr(self, timeout_s: float) -> str | None:
        with self._lock:
            if not self._camera_open:
                raise CameraError("camera is not open", code=ErrorCode.CAM_NOT_FOUND)
        board = self._require_board()
        board.qr_attempts += 1
        if board.scenario is MockScenario.QR_UNREADABLE and board.qr_attempts == 1:
            self._sleep(min(timeout_s, 1.0))
            return None
        self._jitter(0.4, 0.9)
        return board.qr_label

    def get_preview_frame(self) -> PreviewFrame | None:
        return None  # the UI draws an animated placeholder for the mock camera

    def close_camera(self) -> None:
        with self._lock:
            self._camera_open = False

    # ------------------------------------------------------------------ lifecycle
    def shutdown(self) -> None:
        with self._lock:
            if self._firmware is not None:
                self._firmware[:] = bytes(len(self._firmware))  # zero in place
            self._firmware = None
            self._firmware_info = None
            self._camera_open = False
            self._port = None
            self._board = None
            self._closed = True

    # ------------------------------------------------------------------ test hooks
    def _firmware_buffer(self) -> bytearray | None:
        """The in-RAM image (tests only)."""
        return self._firmware
